"""Hub-delegated authentication.

The AR hub is the trust anchor: users authenticate to the hub and present
its RS256 access tokens here. This service verifies them against the hub's
JWKS (cached), rejects non-access tokens, and mirrors the account into a
local users row on first sight. No passwords, no OTP -- the hub account IS
the identity check (DPI-account delivery decision).
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx
import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from pancake_services.grants.models import User

bearer_scheme = HTTPBearer(auto_error=False)


class JWKSCache:
    """Fetches and caches the hub's JWKS with a TTL."""

    def __init__(self, jwks_url: str, ttl_seconds: int = 300):
        self.jwks_url = jwks_url
        self.ttl = ttl_seconds
        self._keys: Optional[Dict[str, Any]] = None
        self._fetched_at: float = 0.0

    def get_jwks(self) -> Dict[str, Any]:
        now = time.monotonic()
        if self._keys is None or now - self._fetched_at > self.ttl:
            response = httpx.get(self.jwks_url, timeout=10)
            response.raise_for_status()
            self._keys = response.json()
            self._fetched_at = now
        return self._keys

    def key_for(self, kid: Optional[str]):
        jwks = self.get_jwks()
        keys = jwks.get("keys", [])
        for key in keys:
            if kid is None or key.get("kid") == kid:
                return pyjwt.PyJWK(key).key
        raise KeyError(f"no JWKS key matching kid={kid}")


def verify_hub_token(token: str, jwks_cache: JWKSCache) -> Dict[str, Any]:
    """Verify an RS256 hub access token. Returns its claims."""
    try:
        header = pyjwt.get_unverified_header(token)
        key = jwks_cache.key_for(header.get("kid"))
        claims = pyjwt.decode(token, key, algorithms=["RS256"])
    except (pyjwt.PyJWTError, KeyError, httpx.HTTPError) as e:
        raise HTTPException(status_code=401, detail=f"invalid hub token: {e}") from e

    token_type = claims.get("type", claims.get("token_type", "access"))
    if token_type != "access":
        raise HTTPException(status_code=401, detail="not an access token")
    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="token has no subject")
    return claims


def get_db(request: Request) -> Session:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing bearer token")
    claims = verify_hub_token(credentials.credentials, request.app.state.jwks_cache)

    account_id = str(claims["sub"])
    user = db.execute(select(User).where(User.hub_account_id == account_id)).scalar_one_or_none()
    if user is None:
        user = User(hub_account_id=account_id, email=claims.get("email"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
