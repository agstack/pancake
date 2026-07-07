"""Mint the five test credentials verifier developers need.

Usage:
    python -m pancake_services.grants.testkit.mint_test_credentials [--keygen] [--out DIR]

Generates (into --out, default services/pancake_services/grants/testkit/dev_keys/):
    dev_issuer_private.pem   Ed25519 dev signing key (gitignored, generated fresh)
    dev_issuer_public.pem    matching public key for verifier tests
    status_list.txt          encoded status list with the 'revoked' credential's bit set
    valid.sdjwt              verifier must ACCEPT
    expired.sdjwt            verifier must REJECT (exp in the past)
    revoked.sdjwt            verifier must REJECT (status bit set)
    tampered.sdjwt           verifier must REJECT (payload modified after signing)
    wrong_geoid.sdjwt        verifier must REJECT (disclosure not in _sd)
    manifest.json            index of the above with expected outcomes
"""
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

from ulid import ULID

from pancake_services.grants import merkle, sdjwt
from pancake_services.grants.issuer import DEFAULT_ISSUER_ID, DEFAULT_KID, generate_keypair_pem
from pancake_services.grants.statuslist import StatusList

DEV_GEOIDS = [
    "3f1a9f0f36e44c0cb1ad4c2f8e3a7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f",
    "7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f3f1a9f0f36e44c0cb1ad4c2f8e3a",
    "b1ad4c2f8e3a7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f3f1a9f0f36e44c0c",
]
STATUS_URI = "https://pancake.dev.local/grants/status-list"
REVOKED_INDEX = 7


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def base_claims(issuer_id: str, list_id: str, exp: int, idx: int) -> dict:
    jti = str(ULID())
    return {
        "iss": issuer_id,
        "sub": list_id,
        "iat": int(time.time()),
        "exp": exp,
        "jti": jti,
        "vct": sdjwt.VCT,
        "grantee": "hub-acct-dev-buyer",
        "masking_level": "L1",
        "purpose": "eudr-due-diligence",
        "odrl": build_odrl(jti, list_id, exp),
        "status": {"status_list": {"uri": STATUS_URI, "idx": idx}},
    }


def build_odrl(jti: str, list_id: str, exp: int) -> dict:
    exp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp))
    return {
        "@context": "http://www.w3.org/ns/odrl.jsonld",
        "@type": "Agreement",
        "uid": f"urn:agstack:grant:{jti}",
        "permission": [{
            "target": f"urn:agstack:fieldlist:{list_id}",
            "action": "read",
            "constraint": [
                {"leftOperand": "dateTime", "operator": "lteq", "rightOperand": exp_iso},
                {"leftOperand": "purpose", "operator": "eq", "rightOperand": "eudr-due-diligence"},
            ],
            "duty": [{"action": "delete", "constraint": [
                {"leftOperand": "elapsedTime", "operator": "eq", "rightOperand": "P30D"},
            ]}],
        }],
    }


def mint_all(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    private_pem, public_pem = generate_keypair_pem()
    (out_dir / "dev_issuer_private.pem").write_bytes(private_pem)
    (out_dir / "dev_issuer_public.pem").write_bytes(public_pem)

    list_id = merkle.merkle_root(DEV_GEOIDS)
    now = int(time.time())
    future = now + 30 * 24 * 3600
    past = now - 3600

    creds = {}

    creds["valid"] = sdjwt.issue(
        base_claims(DEFAULT_ISSUER_ID, list_id, future, idx=1),
        DEV_GEOIDS, private_pem, DEFAULT_KID,
    )

    creds["expired"] = sdjwt.issue(
        base_claims(DEFAULT_ISSUER_ID, list_id, past, idx=2),
        DEV_GEOIDS, private_pem, DEFAULT_KID,
    )

    creds["revoked"] = sdjwt.issue(
        base_claims(DEFAULT_ISSUER_ID, list_id, future, idx=REVOKED_INDEX),
        DEV_GEOIDS, private_pem, DEFAULT_KID,
    )

    # Tampered: flip the grantee inside the signed payload without re-signing.
    good = sdjwt.issue(
        base_claims(DEFAULT_ISSUER_ID, list_id, future, idx=3),
        DEV_GEOIDS, private_pem, DEFAULT_KID,
    )
    token, *disclosures = [p for p in good.split("~") if p]
    header, payload, signature = token.split(".")
    padding = "=" * (-len(payload) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload + padding))
    decoded["grantee"] = "hub-acct-attacker"
    tampered_payload = _b64url(json.dumps(decoded).encode())
    creds["tampered"] = "~".join([".".join([header, tampered_payload, signature]), *disclosures]) + "~"

    # Wrong GeoID: attach a disclosure for a GeoID that was never issued.
    valid_for_swap = sdjwt.issue(
        base_claims(DEFAULT_ISSUER_ID, list_id, future, idx=4),
        DEV_GEOIDS[:2], private_pem, DEFAULT_KID,
    )
    foreign_disclosure, _ = sdjwt._disclosure("fields.2", "not-a-granted-geoid")
    creds["wrong_geoid"] = valid_for_swap + foreign_disclosure + "~"

    for name, cred in creds.items():
        (out_dir / f"{name}.sdjwt").write_text(cred)

    status = StatusList()
    status.set(REVOKED_INDEX, True)
    (out_dir / "status_list.txt").write_text(status.encode())

    manifest = {
        "issuer": DEFAULT_ISSUER_ID,
        "kid": DEFAULT_KID,
        "list_id": list_id,
        "geoids": DEV_GEOIDS,
        "status_list_uri": STATUS_URI,
        "revoked_index": REVOKED_INDEX,
        "credentials": {
            "valid.sdjwt": "accept",
            "expired.sdjwt": "reject: expired",
            "revoked.sdjwt": f"reject: status bit {REVOKED_INDEX} set",
            "tampered.sdjwt": "reject: signature invalid",
            "wrong_geoid.sdjwt": "reject: disclosure digest not in _sd",
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(Path(__file__).parent / "dev_keys"))
    parser.add_argument("--keygen", action="store_true",
                        help="only print a fresh base64url Ed25519 seed for PANCAKE_ISSUER_KEY")
    args = parser.parse_args()

    if args.keygen:
        import secrets
        print(_b64url(secrets.token_bytes(32)))
        return

    manifest = mint_all(Path(args.out))
    print(f"Minted {len(manifest['credentials'])} test credentials into {args.out}")
    print(f"ListID: {manifest['list_id']}")


if __name__ == "__main__":
    main()
