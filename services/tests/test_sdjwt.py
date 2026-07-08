"""Tests for the minimal SD-JWT VC implementation (CREDENTIAL_PROFILE.md)."""
import time

import pytest

from pancake_services.grants import sdjwt
from pancake_services.grants.issuer import generate_keypair_pem

GEOIDS = ["geoid-aaa", "geoid-bbb", "geoid-ccc"]


@pytest.fixture(scope="module")
def keypair():
    return generate_keypair_pem()


def make_claims(exp_offset=3600):
    now = int(time.time())
    return {
        "iss": "did:web:pancake.agstack.org",
        "sub": "a" * 64,
        "iat": now,
        "exp": now + exp_offset,
        "jti": "01TESTJTI0000000000000000",
        "grantee": "hub-acct-1",
        "masking_level": "L1",
        "purpose": "eudr-due-diligence",
        "status": {"status_list": {"uri": "https://x/status", "idx": 5}},
    }


def test_issue_and_verify_roundtrip(keypair):
    priv, pub = keypair
    cred = sdjwt.issue(make_claims(), GEOIDS, priv, "kid-1")
    result = sdjwt.verify(cred, pub)
    assert result.claims["grantee"] == "hub-acct-1"
    assert result.claims["vct"] == sdjwt.VCT
    assert sorted(result.disclosed_geoids) == sorted(GEOIDS)


def test_compact_serialization_shape(keypair):
    priv, _ = keypair
    cred = sdjwt.issue(make_claims(), GEOIDS, priv, "kid-1")
    assert cred.endswith("~")
    parts = [p for p in cred.split("~") if p]
    assert len(parts) == 1 + len(GEOIDS)  # jwt + one disclosure per geoid


def test_expired_rejected(keypair):
    priv, pub = keypair
    cred = sdjwt.issue(make_claims(exp_offset=-10), GEOIDS, priv, "kid-1")
    with pytest.raises(sdjwt.VerificationError, match="expired"):
        sdjwt.verify(cred, pub)


def test_missing_exp_rejected(keypair):
    priv, pub = keypair
    claims = make_claims()
    del claims["exp"]
    cred = sdjwt.issue(claims, [], priv, "kid-1")
    with pytest.raises(sdjwt.VerificationError, match="no exp"):
        sdjwt.verify(cred, pub)


def test_future_iat_rejected(keypair):
    priv, pub = keypair
    claims = make_claims()
    claims["iat"] = int(time.time()) + 3600
    cred = sdjwt.issue(claims, [], priv, "kid-1")
    with pytest.raises(sdjwt.VerificationError, match="future"):
        sdjwt.verify(cred, pub)


def test_wrong_key_rejected(keypair):
    priv, _ = keypair
    _, other_pub = generate_keypair_pem()
    cred = sdjwt.issue(make_claims(), GEOIDS, priv, "kid-1")
    with pytest.raises(sdjwt.VerificationError, match="signature"):
        sdjwt.verify(cred, other_pub)


def test_tampered_payload_rejected(keypair):
    import base64
    import json

    priv, pub = keypair
    cred = sdjwt.issue(make_claims(), GEOIDS, priv, "kid-1")
    token, *disclosures = [p for p in cred.split("~") if p]
    header, payload, sig = token.split(".")
    decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    decoded["grantee"] = "attacker"
    forged = base64.urlsafe_b64encode(json.dumps(decoded).encode()).rstrip(b"=").decode()
    tampered = "~".join([".".join([header, forged, sig]), *disclosures]) + "~"
    with pytest.raises(sdjwt.VerificationError, match="signature"):
        sdjwt.verify(tampered, pub)


def test_foreign_disclosure_rejected(keypair):
    priv, pub = keypair
    cred = sdjwt.issue(make_claims(), GEOIDS[:2], priv, "kid-1")
    foreign, _ = sdjwt._disclosure("fields.2", "geoid-not-granted")
    with pytest.raises(sdjwt.VerificationError, match="not present in _sd"):
        sdjwt.verify(cred + foreign + "~", pub)


def test_wrong_vct_rejected(keypair):
    priv, pub = keypair
    claims = make_claims()
    claims["vct"] = "something/else"
    cred = sdjwt.issue(claims, [], priv, "kid-1")
    with pytest.raises(sdjwt.VerificationError, match="vct"):
        sdjwt.verify(cred, pub)


def test_selective_disclosure_subset(keypair):
    """Holder presents only one of three disclosures; verifier sees only that one."""
    priv, pub = keypair
    cred = sdjwt.issue(make_claims(), GEOIDS, priv, "kid-1")
    token, *disclosures = [p for p in cred.split("~") if p]
    partial = token + "~" + disclosures[0] + "~"
    result = sdjwt.verify(partial, pub)
    assert len(result.disclosed_geoids) == 1
    assert result.disclosed_geoids[0] in GEOIDS


def test_peek_claims_without_verification(keypair):
    priv, _ = keypair
    cred = sdjwt.issue(make_claims(), GEOIDS, priv, "kid-1")
    claims = sdjwt.peek_claims(cred)
    assert claims["status"]["status_list"]["idx"] == 5
