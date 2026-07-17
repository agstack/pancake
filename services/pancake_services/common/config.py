"""Service configuration, sourced from environment variables only.

No secrets are ever hardcoded or defaulted; missing security-critical
values fail loudly at startup (see grants/issuer.py).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///pancake_dev.db")
    )
    hub_jwks_url: str = field(
        default_factory=lambda: os.environ.get(
            "HUB_JWKS_URL", "http://localhost:8000/.well-known/jwks.json"
        )
    )
    hub_url: str = field(default_factory=lambda: os.environ.get("HUB_URL", ""))
    status_list_uri: str = field(
        default_factory=lambda: os.environ.get(
            "STATUS_LIST_URI", "http://localhost:8100/grants/status-list"
        )
    )
    jwks_cache_ttl_seconds: int = 300
    status_list_index_start: int = field(
        default_factory=lambda: int(os.environ.get("STATUS_LIST_INDEX_START", "0"))
    )
    status_list_size: int = field(
        default_factory=lambda: int(os.environ.get("STATUS_LIST_SIZE", "65536"))
    )
    # When true, GET /bites for weather_* types requires a valid X-Field-Grant
    # covering the requested GeoID (consent-gated data plane). Off by default so
    # the demo degrades gracefully.
    require_grant_for_weather: bool = field(
        default_factory=lambda: os.environ.get(
            "PANCAKE_REQUIRE_GRANT_FOR_WEATHER", "false"
        ).strip().lower()
        in ("1", "true", "yes", "on")
    )


def load_settings() -> Settings:
    return Settings()
