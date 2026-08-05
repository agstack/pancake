"""FieldList endpoints: owner-scoped GeoID lists identified by Merkle ListIDs."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from pancake_services.grants import merkle
from pancake_services.grants.auth import get_current_user, get_db
from pancake_services.grants.mealstore import MealStore
from pancake_services.grants.models import FieldList, User
from pancake_services.grants.schemas import FieldListCreate, FieldListOut, InclusionProofOut

router = APIRouter(prefix="/fieldlists", tags=["fieldlists"])


def _meal_store(request: Request) -> MealStore:
    return MealStore(request.app.state.issuer)


def _owned(db: Session, user: User, list_id: str) -> FieldList:
    fieldlist = db.execute(
        select(FieldList).where(FieldList.list_id == list_id, FieldList.owner_id == user.id)
    ).scalar_one_or_none()
    if fieldlist is None:
        # 404 (not 403) so existence of another owner's list is not disclosed.
        raise HTTPException(status_code=404, detail="fieldlist not found")
    return fieldlist


def _fetch_geoids(request: Request, list_id: str) -> list[str]:
    ar2_url = request.app.state.settings.ar2_node_url
    headers = {"x-pancake-internal": "true"}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    try:
        resp = httpx.get(f"{ar2_url}/list-artifact/{list_id}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("members", [])
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch list artifact from AR2: {e}")


@router.post("", response_model=FieldListOut, status_code=201)
def create_fieldlist(
    body: FieldListCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    members = merkle.canonical_members(body.geoids)
    list_id = merkle.merkle_root(members)

    existing = db.execute(
        select(FieldList).where(FieldList.list_id == list_id, FieldList.owner_id == user.id)
    ).scalar_one_or_none()
    if existing:
        # Idempotent by construction: same set of GeoIDs -> same ListID.
        return FieldListOut(
            list_id=existing.list_id,
            name=existing.name,
            geoids=members, # Returning from request body
            created_at=existing.created_at,
        )

    # Call AR2 to register the list artifact
    ar2_url = request.app.state.settings.ar2_node_url
    headers = {}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    try:
        resp = httpx.post(f"{ar2_url}/list-artifact", json={"members": members}, headers=headers, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to register list artifact on AR2: {e}")

    fieldlist = FieldList(list_id=list_id, name=body.name, owner_id=user.id)
    # fieldlist.members no longer used
    db.add(fieldlist)
    db.flush()

    _meal_store(request).append_event(
        db,
        meal_key=list_id,
        event_type="fieldlist.created",
        author_account=user.hub_account_id,
        payload={"list_id": list_id, "name": body.name, "geoid_count": len(members)},
        geoid=list_id,
    )
    db.commit()

    return FieldListOut(
        list_id=list_id, name=body.name, geoids=members, created_at=fieldlist.created_at
    )


@router.get("", response_model=list[FieldListOut])
def list_fieldlists(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(FieldList).where(FieldList.owner_id == user.id)).scalars()
    result = []
    for f in rows:
        geoids = _fetch_geoids(request, f.list_id)
        result.append(FieldListOut(list_id=f.list_id, name=f.name, geoids=geoids, created_at=f.created_at))
    return result


@router.get("/{list_id}", response_model=FieldListOut)
def get_fieldlist(
    list_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    f = _owned(db, user, list_id)
    geoids = _fetch_geoids(request, list_id)
    return FieldListOut(list_id=f.list_id, name=f.name, geoids=geoids, created_at=f.created_at)


@router.get("/{list_id}/proof/{geoid}", response_model=InclusionProofOut)
def inclusion_proof(
    list_id: str,
    geoid: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned(db, user, list_id)
    geoids = _fetch_geoids(request, list_id)
    try:
        proof = merkle.inclusion_proof(geoids, geoid)
    except ValueError:
        raise HTTPException(status_code=404, detail="geoid not in fieldlist") from None
    return InclusionProofOut(geoid=geoid, list_id=list_id, proof=proof)
