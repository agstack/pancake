"""OpenScience Auditing API: per-GeoID provenance from the signed MEAL ledger."""
from __future__ import annotations

import hmac
import httpx
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from pancake_services.grants.auth import get_current_user, get_db
from pancake_services.grants.mealstore import MealStore
from pancake_services.grants.models import Meal, MealPacket, User


router = APIRouter(prefix="/audit", tags=["audit"])



def _packets_for_geoid(
    request: Request,
    db: Session,
    geoid: str,
    since: Optional[datetime],
    until: Optional[datetime],
) -> list[MealPacket]:
    """Events indexed directly on the geoid, plus events on any fieldlist
    (ListID) that contains it."""
    ar2_url = request.app.state.settings.ar2_node_url
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    if "x-authority-token" in request.headers:
        headers["x-authority-token"] = request.headers["x-authority-token"]
    if "x-pancake-signature" in request.headers:
        headers["x-pancake-signature"] = request.headers["x-pancake-signature"]
        
    list_ids = set()
    try:
        resp = httpx.post(f"{ar2_url}/traceforward", json={"seed_geoid": geoid}, headers=headers, timeout=10)
        if resp.status_code == 200:
            for match in resp.json().get("matches", []):
                list_ids.add(match["list_id"])
    except httpx.HTTPError:
        pass # If AR2 fails or 404s, just use the geoid

    keys = list(list_ids | {geoid})
    query = select(MealPacket).where(MealPacket.geoid.in_(keys))
    if since is not None:
        query = query.where(MealPacket.time_index >= since)
    if until is not None:
        query = query.where(MealPacket.time_index <= until)
    return list(db.execute(query.order_by(MealPacket.time_index)).scalars())


def _packet_json(p: MealPacket) -> dict:
    return {
        "packet_id": p.packet_id,
        "meal_id": p.meal_id,
        "sequence_number": p.sequence_number,
        "time_index": p.time_index.isoformat(),
        "author": p.author,
        "event": p.payload,
        "packet_hash": p.packet_hash,
        "signature": p.signature,
    }


@router.get("/{geoid}")
def audit_events(
    geoid: str,
    request: Request,
    since: Optional[datetime] = Query(default=None, alias="from"),
    until: Optional[datetime] = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    packets = _packets_for_geoid(request, db, geoid, since, until)
    return {"geoid": geoid, "event_count": len(packets), "events": [_packet_json(p) for p in packets]}


@router.get("/{geoid}/report")
def audit_report(
    geoid: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compliance report: full provenance plus chain-integrity verification
    for every MEAL touching this GeoID."""
    packets = _packets_for_geoid(request, db, geoid, None, None)
    store = MealStore(request.app.state.issuer)
    meal_ids = sorted({p.meal_id for p in packets})
    chains = {meal_id: store.verify_chain(db, meal_id) for meal_id in meal_ids}
    events_by_type: dict[str, int] = {}
    for p in packets:
        event_type = p.payload.get("event_type", "unknown")
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
    return {
        "geoid": geoid,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(packets),
        "events_by_type": events_by_type,
        "chain_integrity": chains,
        "all_chains_valid": all(c.get("valid") for c in chains.values()) if chains else True,
        "events": [_packet_json(p) for p in packets],
    }


@router.get("/meals/{meal_id}/verify")
def verify_meal_chain(
    meal_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meal = db.execute(select(Meal).where(Meal.meal_id == meal_id)).scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=404, detail="meal not found")
    return MealStore(request.app.state.issuer).verify_chain(db, meal_id)


class AuditEventRequest(BaseModel):
    event: str
    who: str
    credential_id: str
    seed_geoid: str
    scope: Optional[str] = None
    match_count: Optional[int] = None
    artifact: Optional[str] = None

@router.post("/events")
def append_audit_event(
    body: AuditEventRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Internal endpoint for AR2 to append traceforward/traceback MEAL events."""
    internal_token = request.headers.get("X-Pancake-Internal")
    expected = os.getenv("AR2_INTERNAL_SHARED_SECRET")
    if not expected or not internal_token or not hmac.compare_digest(internal_token, expected):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    store = MealStore(request.app.state.issuer)
    # the meal_key should be the seed_geoid or the artifact id
    meal_key = body.seed_geoid if body.seed_geoid else body.artifact
    if not meal_key:
        raise HTTPException(status_code=400, detail="meal_key required")
        
    payload = {
        "credential_id": body.credential_id,
        "scope": body.scope,
        "match_count": body.match_count,
        "artifact": body.artifact
    }
    
    store.append_event(
        db,
        meal_key=meal_key,
        event_type=body.event,
        author_account=body.who,
        payload=payload,
        geoid=meal_key,
        meal_type="recall_audit"
    )
    db.commit()
    return {"status": "ok"}
