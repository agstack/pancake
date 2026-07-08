"""BITE query API: GeoID-indexed access to ingested vendor data."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from pancake_services.grants.auth import get_current_user
from pancake_services.grants.models import User
from pancake_services.store.bites import BiteStore

router = APIRouter(prefix="/bites", tags=["bites"])


def _store(request: Request) -> BiteStore:
    return BiteStore(request.app.state.session_factory)


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
    user: User = Depends(get_current_user),
):
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
