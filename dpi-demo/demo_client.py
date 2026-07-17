"""Tiny HTTP client helpers for the PnD DPI demo notebook/scripts.

Deliberately dependency-light (requests only) and forgiving: every call returns
a structured dict and never raises on a down service, so the walkthrough narrates
cleanly whether or not the whole stack is live.
"""
from __future__ import annotations

import os
from typing import Any

import requests

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8000")
NODE_URL = os.environ.get("PND_AGSTACK_REGISTRY_URL", "http://localhost:8001")
PANCAKE_URL = os.environ.get("PND_PANCAKE_URL", "http://localhost:8100")
PND_URL = os.environ.get("PND_URL", "http://localhost:8080")

TIMEOUT = 15


def _call(method: str, url: str, **kwargs) -> dict[str, Any]:
    try:
        resp = requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        return {"ok": False, "down": True, "error": str(exc), "url": url}
    out: dict[str, Any] = {"ok": resp.ok, "status": resp.status_code, "url": url}
    try:
        out["json"] = resp.json()
    except ValueError:
        out["text"] = resp.text
    return out


def get(url: str, **kwargs) -> dict[str, Any]:
    return _call("GET", url, **kwargs)


def post(url: str, **kwargs) -> dict[str, Any]:
    return _call("POST", url, **kwargs)


def bearer(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def health() -> dict[str, Any]:
    """Probe every service so the notebook can show a status table up front."""
    return {
        "hub": get(f"{HUB_URL}/health"),
        "node": get(f"{NODE_URL}/health"),
        "pancake": get(f"{PANCAKE_URL}/health"),
        "pnd": get(f"{PND_URL}/health"),
    }
