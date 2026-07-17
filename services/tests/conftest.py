"""Shared fixtures: fake hub (RSA JWKS + token minting), in-memory app, clients."""
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make pancake_services importable

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from pancake_services.common.config import Settings
from pancake_services.grants.app import create_app
from pancake_services.grants.issuer import IssuerIdentity, generate_keypair_pem


def _b64url_uint(n: int) -> str:
    data = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeHub:
    """Mints RS256 access tokens and serves a static JWKS, like the AR hub."""

    def __init__(self):
        self.kid = "hub-key-1"
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_numbers = self.private_key.public_key().public_numbers()
        self.jwks = {
            "keys": [{
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": self.kid,
                "n": _b64url_uint(public_numbers.n),
                "e": _b64url_uint(public_numbers.e),
            }]
        }

    def token(self, account_id: str, token_type: str = "access", email: str | None = None,
              exp_offset: int = 3600) -> str:
        claims = {
            "sub": account_id,
            "type": token_type,
            "iat": int(time.time()),
            "exp": int(time.time()) + exp_offset,
        }
        if email:
            claims["email"] = email
        return pyjwt.encode(claims, self.private_key, algorithm="RS256",
                            headers={"kid": self.kid})


class StaticJWKSCache:
    """Drop-in replacement for JWKSCache backed by a FakeHub (no network)."""

    def __init__(self, hub: FakeHub):
        self.hub = hub

    def get_jwks(self):
        return self.hub.jwks

    def key_for(self, kid):
        for key in self.hub.jwks["keys"]:
            if kid is None or key.get("kid") == kid:
                return pyjwt.PyJWK(key).key
        raise KeyError(f"no JWKS key matching kid={kid}")


@pytest.fixture(scope="session")
def fake_hub():
    return FakeHub()


@pytest.fixture(scope="session")
def dev_issuer():
    priv, pub = generate_keypair_pem()
    return IssuerIdentity(
        issuer_id="did:web:pancake.test",
        kid="pancake-test-1",
        private_key_pem=priv,
        public_key_pem=pub,
    )


@pytest.fixture()
def make_app(fake_hub, dev_issuer):
    """Factory for apps with custom settings (e.g. HUB_URL set)."""

    def _make(**overrides):
        settings = Settings(
            database_url="sqlite:///:memory:",
            hub_jwks_url="http://fake-hub/jwks",
            hub_url=overrides.get("hub_url", ""),
            status_list_uri="http://pancake.test/grants/status-list",
            require_grant_for_weather=overrides.get("require_grant_for_weather", False),
        )
        return create_app(
            settings=settings, issuer=dev_issuer, jwks_cache=StaticJWKSCache(fake_hub)
        )

    return _make


@pytest.fixture()
def app(make_app):
    return make_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def owner_headers(fake_hub):
    return {"Authorization": f"Bearer {fake_hub.token('hub-acct-owner', email='owner@x.org')}"}


@pytest.fixture()
def buyer_headers(fake_hub):
    return {"Authorization": f"Bearer {fake_hub.token('hub-acct-buyer', email='buyer@x.org')}"}


GEOIDS = [
    "3f1a9f0f36e44c0cb1ad4c2f8e3a7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f",
    "7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f3f1a9f0f36e44c0cb1ad4c2f8e3a",
    "b1ad4c2f8e3a7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f3f1a9f0f36e44c0c",
]


@pytest.fixture()
def geoids():
    return list(GEOIDS)


@pytest.fixture()
def fieldlist(client, owner_headers, geoids):
    response = client.post(
        "/fieldlists", json={"name": "Finca Demo", "geoids": geoids}, headers=owner_headers
    )
    assert response.status_code == 201, response.text
    return response.json()
