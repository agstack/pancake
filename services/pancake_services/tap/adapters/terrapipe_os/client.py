"""HTTP client for a terrapipe-os open-science node.

One place that knows how to talk to the node, shared by the three adapters, so
that the token handling and the error vocabulary are written once.

Two things distinguish this from the legacy TerraPipe client. It authenticates
with a hub access token obtained by client credentials, not a vendor secret
key -- terrapipe-os verifies that token against the hub's JWKS, so the node
never holds a Pancake secret. And it can carry a field-access grant, which is
the whole point of the pairing: Pancake is the party that issues grants, so a
Pancake adapter is the natural holder of one. Without a grant the node answers
about the neighbourhood; with one it answers about the field. Both answers are
usable and they are labelled differently, so an adapter never has to guess
which it received.

Adapters stay dumb: this client does no retrying (the TAP runtime owns retry
policy) and raises a typed error rather than returning a plausible empty
result, because an empty deforestation screen and a clean one look identical
once they are in a BITE.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import jwt as pyjwt
import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60


class TerrapipeOSError(RuntimeError):
    """The node could not answer.

    ``reason`` is the node's own machine-readable label for the refusal --
    ``grant_required``, ``no_data``, ``store_unavailable`` and so on -- which is
    what callers branch on. The status code alone is not enough: 404 covers an
    unknown GeoID, an unknown layer and a field the store does not reach, and
    those are three different things to do next.
    """

    def __init__(self, message: str, status_code: Optional[int] = None, reason: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


class GrantRequired(TerrapipeOSError):
    """A field-tier answer was refused: no grant presented, or the one presented was refused."""


class NoDataHere(TerrapipeOSError):
    """The node has no data for this field in this layer.

    Its own distinct type because the one thing an adapter must never do with
    it is write a BITE. An absent reading and a zero reading are the same
    number once they are in an envelope.
    """


class HubTokenSource:
    """Client-credentials access token from the AR hub, refreshed before expiry.

    The hub issues 24-hour RS256 tokens from ``POST /users/token``. The expiry
    is read out of the token without verifying it: we are the party that just
    received it from the issuer over a channel we chose, so a signature check
    here would prove nothing, and all we want is when to ask again.
    """

    def __init__(
        self,
        hub_url: str,
        client_id: str,
        client_secret: str,
        *,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
        margin_seconds: int = 300,
        clock=time.time,
    ):
        self._hub_url = hub_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session or requests.Session()
        self._timeout = timeout
        self._margin = margin_seconds
        self._clock = clock
        self._token: Optional[str] = None
        self._expires_at = 0.0

    def token(self) -> str:
        if self._token is None or self._clock() >= self._expires_at - self._margin:
            self._refresh()
        assert self._token is not None
        return self._token

    def _refresh(self) -> None:
        response = self._session.post(
            f"{self._hub_url}/users/token",
            json={"client_id": self._client_id, "client_secret": self._client_secret},
            timeout=self._timeout,
        )
        if response.status_code != 200:
            raise TerrapipeOSError(
                f"hub refused client credentials: {response.status_code} {response.text[:200]}",
                response.status_code,
            )
        body = response.json()
        self._token = body["access_token"]
        self._expires_at = self._clock() + _lifetime_of(self._token)

    def invalidate(self) -> None:
        self._token = None


def _lifetime_of(token: str, default_seconds: int = 23 * 3600) -> int:
    try:
        claims = pyjwt.decode(token, options={"verify_signature": False, "verify_exp": False})
    except Exception:  # noqa: BLE001 - an opaque token is still usable, just not schedulable
        return default_seconds
    expiry, issued = claims.get("exp"), claims.get("iat")
    if not isinstance(expiry, (int, float)):
        return default_seconds
    reference = issued if isinstance(issued, (int, float)) else time.time()
    return max(60, int(expiry - reference))


class TerrapipeOSClient:
    """Read layers, screens and forecasts for one GeoID from a terrapipe-os node."""

    def __init__(
        self,
        base_url: str,
        token_source: Optional[HubTokenSource] = None,
        *,
        static_token: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not base_url:
            raise ValueError("terrapipe-os base_url is required")
        self.base_url = base_url.rstrip("/")
        self._tokens = token_source
        self._static_token = static_token
        self._session = session or requests.Session()
        self._timeout = timeout

    # -- discovery (open, no token) -----------------------------------------

    def health(self) -> Dict[str, Any]:
        return self._get("/health", authenticated=False)

    def layers(self) -> list:
        return self._get("/layers", authenticated=False)

    # -- per-field (hub token; grant optional) ------------------------------

    def menu(self, geoid: str) -> Dict[str, Any]:
        """What the node can say about this field. Coarse only, so it discloses nothing."""
        return self._get(f"/menu/{geoid}")

    def read_layer(
        self, geoid: str, layer_id: str, *, grant: Optional[str] = None, time_value: Optional[str] = None
    ) -> Dict[str, Any]:
        params = {"time": time_value} if time_value else None
        return self._get(f"/data/{geoid}/{layer_id}", grant=grant, params=params)

    def screen(self, geoid: str, *, grant: Optional[str] = None) -> Dict[str, Any]:
        """Deforestation screen. Field-scoped with a grant, neighbourhood-scoped without."""
        return self._get(f"/screen/{geoid}", grant=grant)

    def forecast(
        self, geoid: str, *, start: Optional[str] = None, end: Optional[str] = None
    ) -> Dict[str, Any]:
        params = {k: v for k, v in (("start", start), ("end", end)) if v}
        return self._get(f"/forecast/{geoid}", params=params or None)

    # -- transport ----------------------------------------------------------

    def _headers(self, authenticated: bool, grant: Optional[str]) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if authenticated:
            token = self._static_token or (self._tokens.token() if self._tokens else None)
            if not token:
                raise TerrapipeOSError("no hub access token configured for terrapipe-os")
            headers["Authorization"] = f"Bearer {token}"
        if grant:
            headers["X-Field-Grant"] = grant
        return headers

    def _get(
        self,
        path: str,
        *,
        authenticated: bool = True,
        grant: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(
                url, headers=self._headers(authenticated, grant), params=params, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise TerrapipeOSError(f"terrapipe-os unreachable at {url}: {exc}") from exc

        if response.status_code == 401 and self._tokens is not None and not self._static_token:
            # The token may have been revoked before its stated expiry. Once.
            self._tokens.invalidate()
            response = self._session.get(
                url, headers=self._headers(authenticated, grant), params=params, timeout=self._timeout
            )

        if response.status_code == 200:
            return response.json()

        reason, detail = _refusal_of(response)
        message = f"{url} returned {response.status_code} ({reason or 'unlabelled'}): {detail}"
        if reason in ("grant_required", "grant_refused"):
            raise GrantRequired(message, response.status_code, reason)
        if reason == "no_data":
            raise NoDataHere(message, response.status_code, reason)
        raise TerrapipeOSError(message, response.status_code, reason)


def _refusal_of(response: requests.Response) -> tuple:
    """The node's ``reason`` label and its prose ``detail``, both worth keeping."""
    try:
        body = response.json()
    except ValueError:
        return "", response.text[:300]
    if not isinstance(body, dict):
        return "", str(body)[:300]
    reason = body.get("reason") if isinstance(body.get("reason"), str) else ""
    detail = body.get("detail") or body.get("message") or ""
    return reason, str(detail)[:300]
