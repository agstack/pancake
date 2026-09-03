"""The shared secret that lets Pancake read a list artifact in order to grant it.

Written after the first live deployment, 2026-09-03. The whole grant path was
dead on a stack where every service was up, healthy and correctly addressed,
and the message that surfaced was a 404 from AR2 for an artifact that existed
under exactly the id Pancake had asked for.

The cause was an unset environment variable and a default that hid it. These
tests fix the two halves of that: the variable must be refused when absent, and
the refusal must name it.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

from pancake_services.grants.ar2_client import SECRET_ENV, internal_headers


class _Request:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


def test_an_unset_secret_is_refused_before_the_request_is_made(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refused here, where the cause is visible, not three services away as a 404."""
    monkeypatch.delenv(SECRET_ENV, raising=False)

    with pytest.raises(HTTPException) as raised:
        internal_headers(_Request())

    assert raised.value.status_code == 500
    assert SECRET_ENV in raised.value.detail


def test_the_refusal_says_both_sides_must_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """AR2 with no secret set trusts nobody, so setting it on one side is not enough.

    Named in the message because the obvious reading of "Pancake needs a secret"
    is to set it on Pancake, restart, and get the identical 404.
    """
    monkeypatch.delenv(SECRET_ENV, raising=False)

    with pytest.raises(HTTPException) as raised:
        internal_headers(_Request())

    detail = raised.value.detail
    assert "AR2 node" in detail
    assert "same value" in detail
    assert "restart" in detail


def test_no_placeholder_is_ever_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default was the string "true", which AR2 cannot distinguish from a guess."""
    monkeypatch.delenv(SECRET_ENV, raising=False)

    with pytest.raises(HTTPException):
        internal_headers(_Request())


def test_the_secret_is_sent_when_it_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, "s3cret")

    headers = internal_headers(_Request())

    assert headers["x-pancake-internal"] == "s3cret"


def test_the_callers_authorization_is_carried_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """AR2 still wants a hub user; the internal secret says which node is asking."""
    monkeypatch.setenv(SECRET_ENV, "s3cret")

    headers = internal_headers(_Request({"authorization": "Bearer abc"}))

    assert headers["authorization"] == "Bearer abc"
    assert headers["x-pancake-internal"] == "s3cret"


def test_no_router_builds_the_outbound_header_itself() -> None:
    """One refusal, not three, because three will not stay in agreement.

    Only the outbound direction. Two routers legitimately read the same variable
    to verify that AR2 is calling *them*, which is the mirror of this and not
    the thing that had a placeholder default.
    """
    from pathlib import Path

    routers = Path(__file__).resolve().parents[1] / "pancake_services" / "grants" / "routers"
    offenders = [
        path.name
        for path in routers.glob("*.py")
        if '"x-pancake-internal"' in path.read_text(encoding="utf-8")
    ]

    assert offenders == [], f"{offenders} build the AR2 header instead of using internal_headers"


def test_the_demo_compose_sets_the_secret_on_both_services() -> None:
    """The gap was deployment, not code: nothing told an operator to set this."""
    from pathlib import Path

    import yaml

    compose = Path(__file__).resolve().parents[2] / "dpi-demo" / "docker-compose.yml"
    if not compose.exists():  # pragma: no cover - the demo is optional
        pytest.skip("dpi-demo/docker-compose.yml is not present")

    services = yaml.safe_load(compose.read_text(encoding="utf-8"))["services"]
    # The node decides who is trusted; pancake-grants is the caller that reads a
    # list artifact in order to grant it. pancake-tap is deliberately not here:
    # it consumes grants rather than issuing them, and giving it the secret
    # would widen who can read artifact members for no reason.
    wants = ["node", "pancake-grants"]
    missing = [name for name in wants if name not in services]
    assert not missing, f"{missing} not found in the demo compose; the check needs updating"

    for name in wants:
        env = services[name].get("environment") or {}
        keys = env.keys() if isinstance(env, dict) else [e.split("=")[0] for e in env]
        assert SECRET_ENV in keys, f"{name} does not set {SECRET_ENV}"
