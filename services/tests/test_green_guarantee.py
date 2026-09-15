"""Green Guarantee lifecycle: pre-approve -> verify -> issue (supersede) -> verify -> revoke -> verify fails.

The guarantee is a credential over a GeoID or ListID. These tests pin what a
lender can rely on: the signature and type check, the risk class and rule-set
version travel inside the credential, exactly one active guarantee stands for a
request at a time, revocation is public and immediate, and every step is in the
MEAL for the subject.
"""
import pytest

from pancake_services.grants import sdjwt
from pancake_services.grants.routers.guarantees import VCT

GEOID = "3f1a9f0f36e44c0cb1ad4c2f8e3a7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f"
LENDER = "hub-acct-buyer"  # the buyer fixture doubles as the lender


def _body(**over):
    body = {
        "subject": GEOID,
        "subject_kind": "geoid",
        "beneficiary_account": LENDER,
        "request_ref": "CR-2026-0001",
        "amount": 1500.0,
        "currency": "HNL",
        "coverage_ratio": 0.8,
        "risk_class": "low",
        "rule_set_version": "eudr-perennial-crop/2026.09.15",
        "evidence": ["bite-screen-01"],
        "state": "PRE_APPROVED",
        "validity_days": 365,
    }
    body.update(over)
    return body


@pytest.fixture()
def pre_approved(client, owner_headers):
    response = client.post("/guarantees/issue", json=_body(), headers=owner_headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_pre_approval_is_a_signed_credential_of_its_own_type(pre_approved, dev_issuer):
    result = sdjwt.verify(pre_approved["credential"], dev_issuer.public_key_pem, expected_vct=VCT)
    assert result.claims["sub"] == GEOID
    assert result.claims["beneficiary"] == LENDER
    assert result.claims["guarantee"]["state"] == "PRE_APPROVED"
    assert result.claims["guarantee"]["coverage_ratio"] == 0.8
    assert result.claims["risk"] == {
        "risk_class": "low",
        "rule_set_version": "eudr-perennial-crop/2026.09.15",
        "evidence": ["bite-screen-01"],
    }
    assert result.claims["odrl"]["permission"][0]["action"] == "use"
    assert result.claims["odrl"]["prohibition"][0]["action"] == "distribute"
    assert result.disclosed_geoids == []  # nothing selectively disclosable: shown whole or not at all


def test_a_grant_verifier_refuses_a_guarantee_and_vice_versa(pre_approved, dev_issuer, client, owner_headers, fieldlist):
    with pytest.raises(sdjwt.VerificationError, match="unexpected vct"):
        sdjwt.verify(pre_approved["credential"], dev_issuer.public_key_pem)  # default vct = field grant
    grant = client.post(
        "/grants/issue",
        json={"list_id": fieldlist["list_id"], "grantee_account": LENDER, "purpose": "eudr-due-diligence"},
        headers=owner_headers,
    ).json()
    assert client.post("/guarantees/verify", json={"credential": grant["credential"]}).json()["valid"] is False


def test_the_lender_retrieves_it_and_the_retrieval_is_logged(client, buyer_headers, owner_headers, pre_approved):
    received = client.get("/guarantees/received", headers=buyer_headers).json()
    assert [g["jti"] for g in received] == [pre_approved["jti"]]
    assert received[0]["credential"] == pre_approved["credential"]
    report = client.get(f"/audit/{GEOID}/report", headers=owner_headers).json()
    assert report["events_by_type"]["guarantee.retrieved"] == 1


def test_issuing_supersedes_the_pre_approval_so_one_guarantee_stands(client, owner_headers, pre_approved):
    issued = client.post(
        "/guarantees/issue",
        json=_body(state="ISSUED", supersedes_jti=pre_approved["jti"]),
        headers=owner_headers,
    )
    assert issued.status_code == 201, issued.text
    issued = issued.json()
    assert issued["state"] == "ISSUED"
    assert issued["supersedes_jti"] == pre_approved["jti"]

    assert client.post("/guarantees/verify", json={"credential": issued["credential"]}).json()["valid"] is True
    old = client.post("/guarantees/verify", json={"credential": pre_approved["credential"]}).json()
    assert old == {"valid": False, "reason": "guarantee revoked"}

    active = [g for g in client.get("/guarantees/issued", headers=owner_headers).json() if g["status"] == "active"]
    assert [g["jti"] for g in active] == [issued["jti"]]
    superseded = next(g for g in client.get("/guarantees/issued", headers=owner_headers).json() if g["jti"] == pre_approved["jti"])
    assert superseded["revoked_reason"] == f"superseded by {issued['jti']}"


def test_an_issued_guarantee_cannot_go_back_to_pre_approved(client, owner_headers):
    issued = client.post("/guarantees/issue", json=_body(state="ISSUED"), headers=owner_headers).json()
    back = client.post(
        "/guarantees/issue", json=_body(state="PRE_APPROVED", supersedes_jti=issued["jti"]), headers=owner_headers
    )
    assert back.status_code == 409


def test_superseding_another_request_is_refused(client, owner_headers, pre_approved):
    other = client.post(
        "/guarantees/issue",
        json=_body(state="ISSUED", request_ref="CR-2026-0002", supersedes_jti=pre_approved["jti"]),
        headers=owner_headers,
    )
    assert other.status_code == 409
    assert client.post("/guarantees/verify", json={"credential": pre_approved["credential"]}).json()["valid"] is True


def test_revocation_is_immediate_public_and_reasoned(client, owner_headers, buyer_headers, pre_approved):
    revoke = client.post(
        "/guarantees/revoke", json={"jti": pre_approved["jti"], "reason": "loan repaid"}, headers=owner_headers
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"
    assert revoke.json()["revoked_reason"] == "loan repaid"
    assert client.post("/guarantees/verify", json={"credential": pre_approved["credential"]}).json() == {
        "valid": False,
        "reason": "guarantee revoked",
    }
    assert client.get("/guarantees/received", headers=buyer_headers).json() == []
    # the bit is in the public list
    status = client.get("/grants/status-list").json()
    assert status["encoded"]


def test_only_the_issuer_may_revoke(client, buyer_headers, pre_approved):
    response = client.post(
        "/guarantees/revoke", json={"jti": pre_approved["jti"], "reason": "x"}, headers=buyer_headers
    )
    assert response.status_code == 404


def test_every_step_is_in_the_meal_for_the_subject_and_the_chain_verifies(client, owner_headers, buyer_headers, pre_approved):
    client.get("/guarantees/received", headers=buyer_headers)
    issued = client.post(
        "/guarantees/issue", json=_body(state="ISSUED", supersedes_jti=pre_approved["jti"]), headers=owner_headers
    ).json()
    client.post("/guarantees/revoke", json={"jti": issued["jti"], "reason": "loan repaid"}, headers=owner_headers)

    report = client.get(f"/audit/{GEOID}/report", headers=owner_headers).json()
    assert report["all_chains_valid"] is True
    assert report["events_by_type"] == {
        "guarantee.pre_approved": 1,
        "guarantee.retrieved": 1,
        "guarantee.issued": 1,
        "guarantee.revoked": 2,  # the superseded pre-approval, then the issued one
    }


def test_the_request_is_validated(client, owner_headers):
    assert client.post("/guarantees/issue", json=_body(risk_class="medium"), headers=owner_headers).status_code == 422
    assert client.post("/guarantees/issue", json=_body(coverage_ratio=1.5), headers=owner_headers).status_code == 422
    assert client.post("/guarantees/issue", json=_body(subject="short"), headers=owner_headers).status_code == 422
    assert client.post("/guarantees/issue", json=_body(currency="hnl"), headers=owner_headers).status_code == 422


def test_issue_requires_auth(client):
    assert client.post("/guarantees/issue", json=_body()).status_code == 401
