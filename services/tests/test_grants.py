"""Grant lifecycle: issue -> retrieve -> verify -> revoke -> verify fails."""
import pytest

from pancake_services.grants import sdjwt
from pancake_services.grants.statuslist import StatusList


@pytest.fixture()
def issued(client, owner_headers, fieldlist):
    response = client.post(
        "/grants/issue",
        json={
            "list_id": fieldlist["list_id"],
            "grantee_account": "hub-acct-buyer",
            "purpose": "eudr-due-diligence",
            "validity_days": 30,
        },
        headers=owner_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_issue_returns_signed_credential(issued, fieldlist, dev_issuer):
    result = sdjwt.verify(issued["credential"], dev_issuer.public_key_pem)
    assert result.claims["sub"] == fieldlist["list_id"]
    assert result.claims["grantee"] == "hub-acct-buyer"
    assert result.claims["masking_level"] == "L1"
    assert sorted(result.disclosed_geoids) == fieldlist["geoids"]
    assert result.claims["odrl"]["permission"][0]["action"] == "read"


def test_issue_requires_list_ownership(client, buyer_headers, fieldlist):
    response = client.post(
        "/grants/issue",
        json={
            "list_id": fieldlist["list_id"],
            "grantee_account": "hub-acct-eve",
            "purpose": "x",
        },
        headers=buyer_headers,
    )
    assert response.status_code == 404


def test_issue_requires_auth(client, fieldlist):
    response = client.post(
        "/grants/issue",
        json={"list_id": fieldlist["list_id"], "grantee_account": "x", "purpose": "y"},
    )
    assert response.status_code == 401


def test_grantee_retrieves_via_account(client, buyer_headers, issued):
    response = client.get("/grants/received", headers=buyer_headers)
    assert response.status_code == 200
    grants = response.json()
    assert len(grants) == 1
    assert grants[0]["jti"] == issued["jti"]
    assert grants[0]["credential"] == issued["credential"]


def test_other_accounts_see_nothing(client, fake_hub, issued):
    headers = {"Authorization": f"Bearer {fake_hub.token('hub-acct-stranger')}"}
    assert client.get("/grants/received", headers=headers).json() == []
    assert client.get("/grants/issued", headers=headers).json() == []


def test_verify_endpoint_accepts_active(client, issued):
    response = client.post("/grants/verify", json={"credential": issued["credential"]})
    body = response.json()
    assert body["valid"] is True
    assert body["claims"]["jti"] == issued["jti"]
    assert len(body["disclosed_geoids"]) == 3


def test_revoke_then_verify_fails(client, owner_headers, issued):
    revoke = client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=owner_headers)
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    verify = client.post("/grants/verify", json={"credential": issued["credential"]})
    assert verify.json() == {"valid": False, "reason": "credential revoked"}


def test_revoke_flips_public_status_bit(client, owner_headers, issued):
    idx = issued["status_list_index"]
    before = StatusList.decode(client.get("/grants/status-list").json()["encoded"])
    assert not before.is_revoked(idx)

    client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=owner_headers)

    after = StatusList.decode(client.get("/grants/status-list").json()["encoded"])
    assert after.is_revoked(idx)


def test_only_issuer_can_revoke(client, buyer_headers, issued):
    response = client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=buyer_headers)
    assert response.status_code == 404
    # Credential still valid.
    assert client.post("/grants/verify", json={"credential": issued["credential"]}).json()["valid"]


def test_revoke_idempotent(client, owner_headers, issued):
    first = client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=owner_headers)
    second = client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=owner_headers)
    assert first.status_code == second.status_code == 200
    assert second.json()["status"] == "revoked"


def test_status_indexes_unique_across_grants(client, owner_headers, fieldlist):
    indexes = set()
    for i in range(3):
        response = client.post(
            "/grants/issue",
            json={
                "list_id": fieldlist["list_id"],
                "grantee_account": f"hub-acct-{i}",
                "purpose": "p",
            },
            headers=owner_headers,
        )
        indexes.add(response.json()["status_list_index"])
    assert len(indexes) == 3


def test_tampered_credential_rejected_by_verify(client, issued):
    credential = issued["credential"]
    token, rest = credential.split("~", 1)
    header, payload, sig = token.split(".")
    tampered = ".".join([header, payload[:-4] + "AAAA", sig]) + "~" + rest
    response = client.post("/grants/verify", json={"credential": tampered})
    assert response.json()["valid"] is False


def test_hub_report_called_on_revoke(fake_hub, make_app, geoids, monkeypatch):
    """When HUB_URL is configured, revocation is reported to the hub."""
    from fastapi.testclient import TestClient

    client = TestClient(make_app(hub_url="http://hub.test"))
    headers = {"Authorization": f"Bearer {fake_hub.token('hub-acct-owner')}"}

    fieldlist = client.post(
        "/fieldlists", json={"name": "x", "geoids": geoids}, headers=headers
    ).json()
    issued = client.post(
        "/grants/issue",
        json={"list_id": fieldlist["list_id"], "grantee_account": "b", "purpose": "p"},
        headers=headers,
    ).json()

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json))
        return FakeResponse()

    import pancake_services.grants.routers.grants as grants_router

    monkeypatch.setattr(grants_router.httpx, "post", fake_post)
    response = client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=headers)
    assert response.status_code == 200
    assert calls and calls[0][0] == "http://hub.test/revocations"
    assert calls[0][1]["jti"] == issued["jti"]
