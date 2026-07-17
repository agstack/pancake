"""BITE query API: GeoID-indexed access to ingested vendor data.

Weather reads can be consent-gated: when ``require_grant_for_weather`` is set,
querying ``weather_*`` BITEs requires a valid ``X-Field-Grant`` credential that
covers the requested GeoID. This makes the data plane genuinely grant-gated
(hub JWT proves *who you are*; the field grant proves *what you may read*),
while staying off by default so the demo works without a grant.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request

from pancake_services.grants import sdjwt, statuslist_service
from pancake_services.grants.auth import get_current_user
from pancake_services.grants.models import User
from pancake_services.store.bites import BiteStore

router = APIRouter(prefix="/bites", tags=["bites"])

WEATHER_PREFIX = "weather"


def _store(request: Request) -> BiteStore:
    return BiteStore(request.app.state.session_factory)


def _is_weather_query(bite_type: Optional[str]) -> bool:
    """A query touches weather if it asks for a weather_* type or for all types."""
    return bite_type is None or bite_type.startswith(WEATHER_PREFIX)


def _enforce_weather_grant(
    request: Request, geoid: Optional[str], field_grant: Optional[str]
) -> None:
    """Raise unless a valid, unrevoked grant covers the requested GeoID."""
    if not geoid:
        raise HTTPException(
            status_code=400,
            detail="weather BITE reads require a geoid when grant-gating is enabled",
        )
    if not field_grant:
        raise HTTPException(status_code=401, detail="missing X-Field-Grant for weather read")

    issuer = request.app.state.issuer
    settings = request.app.state.settings
    try:
        result = sdjwt.verify(field_grant, issuer.public_key_pem)
    except sdjwt.VerificationError as e:
        raise HTTPException(status_code=403, detail=f"invalid field grant: {e}") from e

    status = result.claims.get("status", {}).get("status_list", {})
    idx = status.get("idx")
    if idx is not None:
        session = request.app.state.session_factory()
        try:
            if statuslist_service.is_revoked(
                session, idx, settings.status_list_size, settings.status_list_index_start
            ):
                raise HTTPException(status_code=403, detail="field grant revoked")
        finally:
            session.close()

    if geoid not in result.disclosed_geoids:
        raise HTTPException(
            status_code=403, detail="field grant does not cover the requested geoid"
        )


@router.get("")
def query_bites(
    request: Request,
    geoid: Optional[str] = None,
    bite_type: Optional[str] = Query(default=None, alias="type"),
    vendor: Optional[str] = None,
    since: Optional[datetime] = Query(default=None, alias="from"),
    until: Optional[datetime] = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    x_field_grant: Optional[str] = Header(default=None, alias="X-Field-Grant"),
    user: User = Depends(get_current_user),
):
    settings = request.app.state.settings
    if getattr(settings, "require_grant_for_weather", False) and _is_weather_query(bite_type):
        _enforce_weather_grant(request, geoid, x_field_grant)

    rows = _store(request).query(
        geoid=geoid, bite_type=bite_type, vendor=vendor,
        since=since, until=until, limit=limit, offset=offset,
    )
    return {
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "bites": [row.envelope for row in rows],
    }


@router.post("", status_code=201)
def ingest_bite(
    request: Request,
    bite: dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
):
    """Ingest a BITE envelope (e.g. an agstack-pnd PEST_DISEASE risk result).

    Requires a hub JWT (the publisher's DPI identity). The envelope is validated
    and deduped by content hash in the store. This is the write side that closes
    the OpenScience loop: services publish results as GeoID-addressed, queryable,
    auditable BITEs rather than opaque API responses.
    """
    try:
        stored = _store(request).save(bite)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    header = bite.get("Header", {})
    return {
        "stored": stored,
        "duplicate": not stored,
        "bite_id": header.get("id"),
        "geoid": header.get("geoid"),
        "type": header.get("type"),
    }
