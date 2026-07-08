"""Minimal SD-JWT VC implementation per services/specs/CREDENTIAL_PROFILE.md.

Implements the subset of draft-ietf-oauth-sd-jwt-vc that the field-access
grant profile needs: EdDSA-signed JWT with SHA-256 selective-disclosure
digests (flat `fields` claims) in compact serialization
``<jwt>~<disclosure1>~...~``.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import jwt as pyjwt

VCT = "agstack.org/credentials/field-access-grant/v1"
CLOCK_SKEW_SECONDS = 300


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _disclosure(claim_name: str, value: Any) -> Tuple[str, str]:
    """Build one disclosure; returns (encoded_disclosure, digest)."""
    salt = _b64url(secrets.token_bytes(16))
    encoded = _b64url(json.dumps([salt, claim_name, value]).encode("utf-8"))
    digest = _b64url(hashlib.sha256(encoded.encode("ascii")).digest())
    return encoded, digest


class VerificationError(Exception):
    """Raised when an SD-JWT presentation fails verification."""


@dataclass
class VerifiedGrant:
    claims: Dict[str, Any]
    disclosed: Dict[str, Any] = field(default_factory=dict)

    @property
    def disclosed_geoids(self) -> List[str]:
        return [v for k, v in sorted(self.disclosed.items()) if k.startswith("fields.")]


def issue(
    claims: Dict[str, Any],
    disclosable_geoids: List[str],
    private_key_pem: bytes,
    kid: str,
) -> str:
    """Issue an SD-JWT VC. GeoIDs go in as selectively disclosable claims.

    Returns the compact serialization: <jwt>~<disclosure1>~...~
    """
    payload = dict(claims)
    payload.setdefault("vct", VCT)
    payload.setdefault("iat", int(time.time()))

    disclosures: List[str] = []
    digests: List[str] = []
    for i, geoid in enumerate(disclosable_geoids):
        encoded, digest = _disclosure(f"fields.{i}", geoid)
        disclosures.append(encoded)
        digests.append(digest)

    if digests:
        payload["_sd"] = sorted(digests)  # sorted to avoid ordering leaks
        payload["_sd_alg"] = "sha-256"

    token = pyjwt.encode(
        payload,
        private_key_pem,
        algorithm="EdDSA",
        headers={"typ": "vc+sd-jwt", "kid": kid},
    )
    return "~".join([token, *disclosures]) + "~"


def _split(sd_jwt: str) -> Tuple[str, List[str]]:
    if "~" not in sd_jwt:
        return sd_jwt, []
    parts = sd_jwt.split("~")
    return parts[0], [p for p in parts[1:] if p]


def peek_claims(sd_jwt: str) -> Dict[str, Any]:
    """Decode claims WITHOUT verification (for routing/status lookups only)."""
    token, _ = _split(sd_jwt)
    return pyjwt.decode(token, options={"verify_signature": False})


def verify(
    sd_jwt: str,
    public_key_pem: bytes,
    expected_vct: str = VCT,
    now: Optional[int] = None,
) -> VerifiedGrant:
    """Verify signature, temporal validity, vct, and all presented disclosures.

    Status-list (revocation) checking is a separate step -- see statuslist.py --
    because the verifier may need to fetch the list out-of-band.
    """
    token, disclosures = _split(sd_jwt)
    now = now if now is not None else int(time.time())

    try:
        claims = pyjwt.decode(
            token,
            public_key_pem,
            algorithms=["EdDSA"],
            leeway=CLOCK_SKEW_SECONDS,
            # exp/iat are checked manually below against the caller-supplied `now`.
            options={"verify_exp": False, "verify_iat": False},
        )
    except pyjwt.PyJWTError as e:
        raise VerificationError(f"signature verification failed: {e}") from e

    exp = claims.get("exp")
    if exp is None:
        raise VerificationError("credential has no exp")
    if now > int(exp):
        raise VerificationError("credential expired")
    iat = claims.get("iat")
    if iat is not None and int(iat) > now + CLOCK_SKEW_SECONDS:
        raise VerificationError("credential issued in the future")

    if claims.get("vct") != expected_vct:
        raise VerificationError(f"unexpected vct: {claims.get('vct')}")

    disclosed: Dict[str, Any] = {}
    if disclosures:
        sd_digests = set(claims.get("_sd", []))
        if claims.get("_sd_alg", "sha-256") != "sha-256":
            raise VerificationError("unsupported _sd_alg")
        for encoded in disclosures:
            digest = _b64url(hashlib.sha256(encoded.encode("ascii")).digest())
            if digest not in sd_digests:
                raise VerificationError("disclosure digest not present in _sd")
            salt, claim_name, value = json.loads(_b64url_decode(encoded))
            disclosed[claim_name] = value

    return VerifiedGrant(claims=claims, disclosed=disclosed)
