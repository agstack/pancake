# SPDX-License-Identifier: EUPL-1.2
# Copyright (c) 2026 AgStack project contributors.
# Licensed under the EUPL, Version 1.2; see the LICENSE file for the full text.

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
from pancake_services.grants.schemas import FieldListCreate, FieldListOut, InclusionProofOut, HoldersRequest, HoldersResponse

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
    import os
    headers = {"x-pancake-internal": os.getenv("AR2_INTERNAL_SHARED_SECRET", "true")}
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


@router.post("/holders", response_model=HoldersResponse)
def resolve_holders(
    body: HoldersRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Tier 3 identity disclosure. Requires BOTH the AR2 internal secret AND a
    valid, in-scope authority credential. Every disclosure is written to MEAL
    in the same transaction as the lookup."""
    import os
    import hmac
    
    # (a) transport: only AR2 may call this at all
    secret = os.getenv("AR2_INTERNAL_SHARED_SECRET")
    presented = request.headers.get("X-Pancake-Internal")
    if not secret or not presented or not hmac.compare_digest(presented.encode(), secret.encode()):
        raise HTTPException(status_code=403, detail="not authorized")

    # (b) authorization: verify the credential ourselves - never on AR2's word
    from pancake_services.grants.auth import verify_authority_credential, VerificationError
    from pancake_services.grants.issuer import authority_pubkey
    
    authority_token = request.headers.get("X-Authority-Token")
    if not authority_token:
        raise HTTPException(status_code=403, detail="authority credential required")
    try:
        claims = verify_authority_credential(
            authority_token,
            authority_pubkey(),                 # Pancake's own trust anchor
            requested_scope=body.scope,
            local_status_list_path=os.getenv("TEST_STATUS_LIST_DIR"),
        )
    except VerificationError as e:
        raise HTTPException(status_code=403, detail=f"authority credential invalid: {e}") from None

    # (c) the lookup
    holders = {}
    if body.list_ids:
        rows = db.execute(
            select(FieldList.list_id, User.hub_account_id)
            .join(User, FieldList.owner_id == User.id)
            .where(FieldList.list_id.in_(body.list_ids))
        ).all()
        holders = {list_id: acct for list_id, acct in rows}

    # (d) the disclosure is on the record, in the same transaction as the read
    from pancake_services.grants.mealstore import MealStore
    MealStore(request.app.state.issuer).append_event(
        db,
        meal_key=body.seed_geoid,
        event_type="traceforward.disclosure",
        author_account=claims.get("sub"),
        payload={
            "credential_id": claims.get("jti"),
            "scope": body.scope,
            "disclosed_count": len(holders),
            "requested_count": len(body.list_ids),
        },
        geoid=body.seed_geoid,
        meal_type="recall_audit",
    )
    db.commit()
    return HoldersResponse(holders=holders)


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
