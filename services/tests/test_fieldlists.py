# SPDX-License-Identifier: EUPL-1.2
# Copyright (c) 2026 AgStack project contributors.
# Licensed under the EUPL, Version 1.2; see the LICENSE file for the full text.

"""FieldList endpoints: idempotent creation, owner scoping, proofs."""
from pancake_services.grants.merkle import merkle_root, verify_inclusion
import pytest


def test_create_returns_merkle_listid(client, owner_headers, geoids):
    response = client.post(
        "/fieldlists", json={"name": "Finca A", "geoids": geoids}, headers=owner_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["list_id"] == merkle_root(geoids)
    assert body["geoids"] == sorted(set(geoids))


def test_create_is_idempotent(client, owner_headers, geoids):
    first = client.post(
        "/fieldlists", json={"name": "Finca A", "geoids": geoids}, headers=owner_headers
    )
    again = client.post(
        "/fieldlists",
        json={"name": "Renamed", "geoids": list(reversed(geoids))},
        headers=owner_headers,
    )
    assert first.json()["list_id"] == again.json()["list_id"]
    listing = client.get("/fieldlists", headers=owner_headers).json()
    assert len(listing) == 1


def test_requires_auth(client, geoids):
    assert client.post("/fieldlists", json={"name": "x", "geoids": geoids}).status_code == 401
    assert client.get("/fieldlists").status_code == 401


def test_empty_geoids_rejected(client, owner_headers):
    response = client.post(
        "/fieldlists", json={"name": "empty", "geoids": []}, headers=owner_headers
    )
    assert response.status_code == 422


def test_owner_scoping(client, owner_headers, buyer_headers, fieldlist):
    list_id = fieldlist["list_id"]
    assert client.get(f"/fieldlists/{list_id}", headers=owner_headers).status_code == 200
    # Another account cannot see it -- and gets 404, not 403.
    assert client.get(f"/fieldlists/{list_id}", headers=buyer_headers).status_code == 404
    assert client.get("/fieldlists", headers=buyer_headers).json() == []


def test_inclusion_proof_endpoint(client, owner_headers, fieldlist, geoids):
    list_id = fieldlist["list_id"]
    response = client.get(f"/fieldlists/{list_id}/proof/{geoids[0]}", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert verify_inclusion(body["geoid"], body["proof"], body["list_id"])


def test_proof_for_nonmember_404(client, owner_headers, fieldlist):
    list_id = fieldlist["list_id"]
    response = client.get(f"/fieldlists/{list_id}/proof/unknown-geoid", headers=owner_headers)
    assert response.status_code == 404




@pytest.mark.parametrize("row_name, headers_func, expected_status", [
    ("1 farmer, no secret, no cred",        lambda o, t: o,                                              403),
    ("2 farmer, no secret, valid cred",     lambda o, t: {**o, "X-Authority-Token": t["valid"]},          403),
    ("3 anonymous",                          lambda o, t: {},                                             403),
    ("4 AR2, secret, no cred",              lambda o, t: {"X-Pancake-Internal": "test-secret"},                  403),
    ("5 AR2, wrong secret, valid cred",     lambda o, t: {"X-Pancake-Internal": "wrong", "X-Authority-Token": t["valid"]},            403),
    ("6 AR2, secret, expired cred",         lambda o, t: {"X-Pancake-Internal": "test-secret", "X-Authority-Token": t["expired"]},                               403),
    ("7 AR2, secret, revoked cred",         lambda o, t: {"X-Pancake-Internal": "test-secret", "X-Authority-Token": t["revoked"]},                               403),
    ("8 AR2, secret, out-of-scope cred",    lambda o, t: {"X-Pancake-Internal": "test-secret", "X-Authority-Token": t["out_of_scope"]},                          403),
    ("9 AR2, secret, valid & in scope",     lambda o, t: {"X-Pancake-Internal": "test-secret", "X-Authority-Token": t["valid"]}, 200),
])
def test_resolve_holders_matrix(row_name, headers_func, expected_status, client, owner_headers, fieldlist, dev_issuer, monkeypatch, tmp_path):
    import time
    from pancake_services.grants import sdjwt

    monkeypatch.setenv("AR2_INTERNAL_SHARED_SECRET", "test-secret")
    pubkey_path = tmp_path / "test_authority_pubkey.pem"
    pubkey_path.write_bytes(dev_issuer.public_key_pem)
    monkeypatch.setenv("PANCAKE_TRUSTED_AUTHORITY_PUBKEY", str(pubkey_path))
    monkeypatch.setenv("TEST_STATUS_LIST_DIR", str(tmp_path))
    
    import json
    import base64
    import zlib
    def create_status_list(revoked_indices):
        lst = bytearray(16)
        for idx in revoked_indices:
            lst[idx // 8] |= (1 << (idx % 8))
        compressed = zlib.compress(bytes(lst))
        return {"status_list": {"bits": 1, "lst": base64.urlsafe_b64encode(compressed).decode('utf-8').rstrip('=')}}

    with open(tmp_path / "local", "w") as f:
        json.dump(create_status_list([1]), f)

    list_id = fieldlist["list_id"]
    seed_geoid = "fake-seed"
    
    def issue_token(scope="demo-recall", exp_offset=3600, status_idx=0):
        claims = {
            "iss": dev_issuer.issuer_id,
            "sub": "auth-subject",
            "iat": int(time.time()),
            "exp": int(time.time()) + exp_offset,
            "vct": "agstack.org/credentials/traceforward-authority/v1",
            "scope": scope,
            "status": {"status_list": {"uri": "local", "idx": status_idx}},
        }
        return sdjwt.issue(claims, [], dev_issuer.private_key_pem, dev_issuer.kid)

    tokens = {
        "valid": issue_token(status_idx=0),
        "expired": issue_token(exp_offset=-3600),
        "out_of_scope": issue_token(scope="wrong-scope"),
        "revoked": issue_token(status_idx=1)
    }

    req_body = {"list_ids": [list_id], "scope": "demo-recall", "seed_geoid": seed_geoid}
    
    headers = headers_func(owner_headers, tokens)
    res = client.post("/fieldlists/holders", json=req_body, headers=headers)
    
    assert res.status_code == expected_status
    if expected_status == 200:
        assert res.json()["holders"] == {list_id: "hub-acct-owner"}
        audit_res = client.get(f"/audit/{seed_geoid}/report", headers=owner_headers)
        assert audit_res.status_code == 200
        events = audit_res.json()["events"]
        assert len(events) == 1
        assert events[0]["event"]["event_type"] == "traceforward.disclosure"


def test_holders_rejects_credential_without_status_list(client, owner_headers, fieldlist, dev_issuer, monkeypatch, tmp_path):
    import time
    from pancake_services.grants import sdjwt
    monkeypatch.setenv("AR2_INTERNAL_SHARED_SECRET", "test-secret")
    pubkey_path = tmp_path / "test_authority_pubkey.pem"
    pubkey_path.write_bytes(dev_issuer.public_key_pem)
    monkeypatch.setenv("PANCAKE_TRUSTED_AUTHORITY_PUBKEY", str(pubkey_path))
    
    list_id = fieldlist["list_id"]
    claims = {
        "iss": dev_issuer.issuer_id,
        "sub": "auth-subject",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "vct": "agstack.org/credentials/traceforward-authority/v1",
        "scope": "demo-recall",
    }
    token = sdjwt.issue(claims, [], dev_issuer.private_key_pem, dev_issuer.kid)
    
    req_body = {"list_ids": [list_id], "scope": "demo-recall", "seed_geoid": "fake-seed"}
    res = client.post("/fieldlists/holders", json=req_body, headers={"X-Pancake-Internal": "test-secret", "X-Authority-Token": token})
    assert res.status_code == 403

def _setup_ar2_and_pancake(monkeypatch, tmp_path, dev_issuer):
    import time
    import json
    import base64
    import zlib
    from pancake_services.grants import sdjwt
    
    # Pancake env
    monkeypatch.setenv("AR2_INTERNAL_SHARED_SECRET", "test-secret")
    pubkey_path = tmp_path / "test_authority_pubkey.pem"
    pubkey_path.write_bytes(dev_issuer.public_key_pem)
    monkeypatch.setenv("PANCAKE_TRUSTED_AUTHORITY_PUBKEY", str(pubkey_path))
    monkeypatch.setenv("TEST_STATUS_LIST_DIR", str(tmp_path))
    
    # AR2 env
    monkeypatch.setenv("AR_TRUSTED_AUTHORITY_PUBKEY", str(pubkey_path))

    def create_status_list(revoked_indices):
        lst = bytearray(16)
        for idx in revoked_indices:
            lst[idx // 8] |= (1 << (idx % 8))
        compressed = zlib.compress(bytes(lst))
        return {"status_list": {"bits": 1, "lst": base64.urlsafe_b64encode(compressed).decode('utf-8').rstrip('=')}}

    with open(tmp_path / "local", "w") as f:
        json.dump(create_status_list([1]), f)

    def issue_token(status_idx=0):
        claims = {
            "iss": dev_issuer.issuer_id,
            "sub": "auth-subject",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "vct": "agstack.org/credentials/traceforward-authority/v1",
            "scope": "demo-recall",
            "status": {"status_list": {"uri": "local", "idx": status_idx}},
        }
        return sdjwt.issue(claims, [], dev_issuer.private_key_pem, dev_issuer.kid)

    return issue_token(status_idx=0), issue_token(status_idx=1)

def test_revoked_credential_rejected_by_both_layers(client, fieldlist, dev_issuer, monkeypatch, tmp_path):
    import sys
    import os
    import pytest
    
    ar2_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../ar2')),
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../ar2'))
    ]
    ar2_path = next((p for p in ar2_paths if os.path.exists(p)), None)
    
    if not ar2_path:
        pytest.skip("AR2 repository not available for cross-layer test")
    if ar2_path not in sys.path:
        sys.path.append(ar2_path)
    from unittest.mock import MagicMock
    sys.modules['pyproj'] = MagicMock()
    sys.modules['h3'] = MagicMock()
    sys.modules['psycopg2'] = MagicMock()
    import os
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    from app.main import app as ar2_app
    from fastapi.testclient import TestClient
    ar2_client = TestClient(ar2_app)

    valid_token, revoked_token = _setup_ar2_and_pancake(monkeypatch, tmp_path, dev_issuer)
    monkeypatch.setattr('app.auth.verify_token', lambda token: {"sub": "test", "masking_level": 1})
    
    # Rejected by both
    assert ar2_client.post("/traceforward", headers={"X-Authority-Token": revoked_token, "Authorization": "Bearer test"}, json={"seed_geoid": "fake-seed"}).status_code == 403
    assert client.post("/fieldlists/holders",
                               headers={"X-Pancake-Internal": "test-secret", "X-Authority-Token": revoked_token},
                               json={"list_ids": [fieldlist["list_id"]], "scope": "demo-recall", "seed_geoid": "fake-seed"}).status_code == 403

def test_valid_credential_accepted_by_both_layers(client, fieldlist, dev_issuer, monkeypatch, tmp_path):
    import sys
    import os
    import pytest
    
    ar2_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../ar2')),
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../ar2'))
    ]
    ar2_path = next((p for p in ar2_paths if os.path.exists(p)), None)
    
    if not ar2_path:
        pytest.skip("AR2 repository not available for cross-layer test")
    if ar2_path not in sys.path:
        sys.path.append(ar2_path)
    from unittest.mock import MagicMock
    sys.modules['pyproj'] = MagicMock()
    sys.modules['h3'] = MagicMock()
    sys.modules['psycopg2'] = MagicMock()
    import os
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    from app.main import app as ar2_app
    from fastapi.testclient import TestClient
    ar2_client = TestClient(ar2_app)

    valid_token, revoked_token = _setup_ar2_and_pancake(monkeypatch, tmp_path, dev_issuer)

    monkeypatch.setattr('app.auth.verify_token', lambda token: {"sub": "test", "masking_level": 1})

    res_ar2 = ar2_client.post("/traceforward", headers={"X-Authority-Token": valid_token, "Authorization": "Bearer test"}, json={"seed_geoid": "fake-seed"})
    assert res_ar2.status_code != 401, res_ar2.text
    
    res_pancake = client.post("/fieldlists/holders",
                               headers={"X-Pancake-Internal": "test-secret", "X-Authority-Token": valid_token},
                               json={"list_ids": [fieldlist["list_id"]], "scope": "demo-recall", "seed_geoid": "fake-seed"})
    assert res_pancake.status_code == 200
