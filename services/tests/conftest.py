"""Shared fixtures: fake hub (RSA JWKS + token minting), in-memory app, clients."""
import base64
import sys
import time
from pathlib import Path
from unittest.mock import patch
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make pancake_services importable

from pancake_services.grants.merkle import merkle_root
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

@pytest.fixture(autouse=True)
def mock_ar2():
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json_data = json_data
            self.status_code = status_code

        def json(self):
            return self._json_data
            
        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPError("mock error")

    original_post = httpx.post
    original_get = httpx.get

    registry: dict[str, list[str]] = {}

    def mock_post(url, *args, **kwargs):
        if url.endswith("/list-artifact"):
            json_payload = kwargs.get("json", {})
            members = json_payload.get("members", [])
            list_id = merkle_root(members)
            registry[list_id] = sorted(set(members))
            return MockResponse({"list_id": list_id, "message": "Success"})
        elif "/traceforward" in url:
            json_payload = kwargs.get("json", {})
            geoid = json_payload.get("seed_geoid", "")
                
            found = set()
            frontier = set()
            
            for list_id, members in registry.items():
                if geoid in members:
                    frontier.add(list_id)
            
            found.update(frontier)
            while frontier:
                parents = set()
                for list_id, members in registry.items():
                    for member in members:
                        if member.startswith("L:") and member[2:] in frontier:
                            parents.add(list_id)
                frontier = parents - found
                found.update(parents)
                
            return MockResponse({"seed_geoid": geoid, "list_ids": list(found)})
        return original_post(url, *args, **kwargs)

    def mock_get(url, *args, **kwargs):
        if "/list-artifact/reverse/" in url:
            geoid = url.rstrip("/").rsplit("/", 1)[-1]
            return MockResponse({"list_ids": [lid for lid, m in registry.items() if geoid in m]})
        elif "/list-artifact/" in url:
            list_id = url.rstrip("/").rsplit("/", 1)[-1]
            if list_id not in registry:
                return MockResponse({"detail": "not found"}, status_code=404)
            return MockResponse({"members": registry[list_id]})
        return original_get(url, *args, **kwargs)

    with patch("pancake_services.grants.routers.fieldlists.httpx.post", side_effect=mock_post), \
         patch("pancake_services.grants.routers.fieldlists.httpx.get", side_effect=mock_get), \
         patch("pancake_services.grants.routers.grants.httpx.get", side_effect=mock_get), \
         patch("pancake_services.grants.routers.audit.httpx.post", side_effect=mock_post):
        yield
