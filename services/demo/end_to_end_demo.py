"""End-to-end demo: the full DPI grant lifecycle, in-process.

Simulates the AR hub (RS256 JWKS), then runs:
  1. Owner creates a FieldList (Merkle ListID)
  2. Owner issues an SD-JWT VC grant to a buyer's hub account
  3. Buyer retrieves the credential via their DPI account (no OTP)
  4. A relying party verifies it (signature, expiry, revocation, disclosures)
  5. Owner revokes; verification now fails; public status bit is set
  6. The audit API returns the full signed provenance chain

Run:  cd services && ../.venv/bin/python demo/end_to_end_demo.py
Exits 0 only if every step behaves exactly as specified.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from conftest import GEOIDS, FakeHub, StaticJWKSCache  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pancake_services.common.config import Settings  # noqa: E402
from pancake_services.grants.app import create_app  # noqa: E402
from pancake_services.grants.issuer import IssuerIdentity, generate_keypair_pem  # noqa: E402
from pancake_services.grants.statuslist import StatusList  # noqa: E402


def step(n: int, message: str) -> None:
    print(f"  [{n}] {message}")


def main() -> int:
    print("Pancake DPI end-to-end demo")

    hub = FakeHub()
    priv, pub = generate_keypair_pem()
    issuer = IssuerIdentity(
        issuer_id="did:web:pancake.demo", kid="demo-1",
        private_key_pem=priv, public_key_pem=pub,
    )
    app = create_app(
        settings=Settings(
            database_url="sqlite:///:memory:",
            hub_jwks_url="http://demo-hub/jwks",
            status_list_uri="http://demo/grants/status-list",
        ),
        issuer=issuer,
        jwks_cache=StaticJWKSCache(hub),
    )
    client = TestClient(app)
    owner = {"Authorization": f"Bearer {hub.token('hub-acct-farmer-maria')}"}
    buyer = {"Authorization": f"Bearer {hub.token('hub-acct-eu-buyer')}"}

    # 1. FieldList
    fieldlist = client.post(
        "/fieldlists", json={"name": "Finca Santa Rosa", "geoids": GEOIDS}, headers=owner
    ).json()
    step(1, f"FieldList created, ListID={fieldlist['list_id'][:16]}… ({len(fieldlist['geoids'])} fields)")

    # 2. Issue
    issued = client.post(
        "/grants/issue",
        json={
            "list_id": fieldlist["list_id"],
            "grantee_account": "hub-acct-eu-buyer",
            "purpose": "eudr-due-diligence",
            "validity_days": 30,
        },
        headers=owner,
    ).json()
    step(2, f"Grant issued, jti={issued['jti']}, status index={issued['status_list_index']}")

    # 3. Retrieve via DPI account
    received = client.get("/grants/received", headers=buyer).json()
    assert len(received) == 1 and received[0]["jti"] == issued["jti"]
    credential = received[0]["credential"]
    step(3, "Buyer retrieved the credential with their DPI account (no OTP)")

    # 4. Verify
    verdict = client.post("/grants/verify", json={"credential": credential}).json()
    assert verdict["valid"] is True, verdict
    assert len(verdict["disclosed_geoids"]) == 3
    step(4, f"Relying party verified: purpose={verdict['claims']['purpose']}, "
            f"masking={verdict['claims']['masking_level']}, geoids disclosed={len(verdict['disclosed_geoids'])}")

    # 5. Revoke
    revoked = client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=owner).json()
    assert revoked["status"] == "revoked"
    verdict_after = client.post("/grants/verify", json={"credential": credential}).json()
    assert verdict_after == {"valid": False, "reason": "credential revoked"}
    status = StatusList.decode(client.get("/grants/status-list").json()["encoded"])
    assert status.is_revoked(issued["status_list_index"])
    step(5, "Revoked: verification fails and the public status bit is set")

    # 6. Audit
    report = client.get(f"/audit/{GEOIDS[0]}/report", headers=owner).json()
    assert report["all_chains_valid"] is True
    expected = {"fieldlist.created": 1, "grant.issued": 1, "grant.retrieved": 1, "grant.revoked": 1}
    assert report["events_by_type"] == expected, report["events_by_type"]
    step(6, f"Audit chain valid, events: {report['events_by_type']}")

    print("DEMO PASSED: issue -> retrieve -> verify -> revoke -> audit all green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
