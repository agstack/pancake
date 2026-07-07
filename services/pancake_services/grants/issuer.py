"""Issuer key management.

The instance signing key is an Ed25519 private key supplied via the
PANCAKE_ISSUER_KEY environment variable (PEM, or base64url of the 32-byte
raw seed). Interim custody decision: env var now, vault before production.
The key is never logged and never serialized into any response.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ENV_KEY = "PANCAKE_ISSUER_KEY"
ENV_ISSUER_ID = "PANCAKE_ISSUER_ID"
ENV_KID = "PANCAKE_ISSUER_KID"

DEFAULT_ISSUER_ID = "did:web:pancake.agstack.org"
DEFAULT_KID = "pancake-issuer-1"


@dataclass(frozen=True)
class IssuerIdentity:
    issuer_id: str
    kid: str
    private_key_pem: bytes
    public_key_pem: bytes


def _load_private_key(value: str) -> Ed25519PrivateKey:
    value = value.strip()
    if value.startswith("-----BEGIN"):
        key = serialization.load_pem_private_key(value.encode(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("PANCAKE_ISSUER_KEY is not an Ed25519 key")
        return key
    padding = "=" * (-len(value) % 4)
    seed = base64.urlsafe_b64decode(value + padding)
    if len(seed) != 32:
        raise ValueError("PANCAKE_ISSUER_KEY base64 seed must decode to 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(seed)


def generate_keypair_pem() -> tuple[bytes, bytes]:
    """Generate a fresh Ed25519 keypair (private PEM, public PEM)."""
    key = Ed25519PrivateKey.generate()
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub


def load_issuer_identity() -> IssuerIdentity:
    """Load the issuer identity from the environment.

    Raises RuntimeError when PANCAKE_ISSUER_KEY is unset -- the grants
    service refuses to start without a signing key rather than falling
    back to an insecure default.
    """
    raw = os.environ.get(ENV_KEY)
    if not raw:
        raise RuntimeError(
            f"{ENV_KEY} is not set. Generate one with: "
            "python -m pancake_services.grants.testkit.mint_test_credentials --keygen"
        )
    key = _load_private_key(raw)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return IssuerIdentity(
        issuer_id=os.environ.get(ENV_ISSUER_ID, DEFAULT_ISSUER_ID),
        kid=os.environ.get(ENV_KID, DEFAULT_KID),
        private_key_pem=private_pem,
        public_key_pem=public_pem,
    )
