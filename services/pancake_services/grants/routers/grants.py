"""Grant lifecycle endpoints: issue, retrieve, revoke, status list, verify.

Delivery model (no OTP): the grantee authenticates to the hub with their
DPI account and retrieves credentials issued to them via GET /grants/received.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ulid import ULID

from pancake_services.grants import sdjwt, statuslist_service
from pancake_services.grants.auth import get_current_user, get_db
from pancake_services.grants.mealstore import MealStore
from pancake_services.grants.models import FieldList, Grant, User
from pancake_services.grants.schemas import (
    GrantIssueRequest,
    GrantOut,
    GrantWithCredential,
    RevokeRequest,
    StatusListOut,
)

router = APIRouter(prefix="/grants", tags=["grants"])


def _grant_out(g: Grant) -> GrantOut:
    return GrantOut(
        jti=g.jti,
        list_id=g.list_id,
        grantee_account=g.grantee_account,
        purpose=g.purpose,
        masking_level=g.masking_level,
        status=g.status,
        status_list_index=g.status_list_index,
        expires_at=g.expires_at,
        created_at=g.created_at,
        revoked_at=g.revoked_at,
    )


def _build_odrl(jti: str, list_id: str, purpose: str, exp: int) -> dict:
    exp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp))
    return {
        "@context": "http://www.w3.org/ns/odrl.jsonld",
        "@type": "Agreement",
        "uid": f"urn:agstack:grant:{jti}",
        "permission": [{
            "target": f"urn:agstack:fieldlist:{list_id}",
            "action": "read",
            "constraint": [
                {"leftOperand": "dateTime", "operator": "lteq", "rightOperand": exp_iso},
                {"leftOperand": "purpose", "operator": "eq", "rightOperand": purpose},
            ],
            "duty": [{"action": "delete", "constraint": [
                {"leftOperand": "elapsedTime", "operator": "eq", "rightOperand": "P30D"},
            ]}],
        }],
    }


@router.post("/issue", response_model=GrantWithCredential, status_code=201)
def issue_grant(
    body: GrantIssueRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = request.app.state.settings
    issuer = request.app.state.issuer

    fieldlist = db.execute(
        select(FieldList).where(
            FieldList.list_id == body.list_id, FieldList.owner_id == user.id
        )
    ).scalar_one_or_none()
    if fieldlist is None:
        raise HTTPException(status_code=404, detail="fieldlist not found")

    index = statuslist_service.allocate_index(
        db, settings.status_list_size, settings.status_list_index_start
    )
    jti = str(ULID())
    now = int(time.time())
    exp = now + body.validity_days * 86400
    claims = {
        "iss": issuer.issuer_id,
        "sub": body.list_id,
        "iat": now,
        "exp": exp,
        "jti": jti,
        "vct": sdjwt.VCT,
        "grantee": body.grantee_account,
        "masking_level": body.masking_level,
        "purpose": body.purpose,
        "odrl": _build_odrl(jti, body.list_id, body.purpose, exp),
        "status": {"status_list": {"uri": settings.status_list_uri, "idx": index}},
    }
    credential = sdjwt.issue(claims, fieldlist.geoids, issuer.private_key_pem, issuer.kid)

    grant = Grant(
        jti=jti,
        list_id=body.list_id,
        issuer_user_id=user.id,
        grantee_account=body.grantee_account,
        purpose=body.purpose,
        masking_level=body.masking_level,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        status="active",
        status_list_index=index,
        credential=credential,
    )
    db.add(grant)
    db.flush()

    MealStore(issuer).append_event(
        db,
        meal_key=body.list_id,
        event_type="grant.issued",
        author_account=user.hub_account_id,
        payload={
            "jti": jti,
            "grantee": body.grantee_account,
            "purpose": body.purpose,
            "masking_level": body.masking_level,
            "expires_at": grant.expires_at.isoformat(),
        },
        geoid=body.list_id,
    )
    db.commit()

    return GrantWithCredential(credential=credential, **_grant_out(grant).model_dump())


@router.get("/issued", response_model=list[GrantOut])
def grants_issued(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Grant).where(Grant.issuer_user_id == user.id)).scalars()
    return [_grant_out(g) for g in rows]


@router.get("/received", response_model=list[GrantWithCredential])
def grants_received(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DPI-account credential delivery: the authenticated grantee retrieves
    active credentials issued to their hub account."""
    rows = list(
        db.execute(
            select(Grant).where(
                Grant.grantee_account == user.hub_account_id, Grant.status == "active"
            )
        ).scalars()
    )
    issuer = request.app.state.issuer
    store = MealStore(issuer)
    for g in rows:
        store.append_event(
            db,
            meal_key=g.list_id,
            event_type="grant.retrieved",
            author_account=user.hub_account_id,
            payload={"jti": g.jti},
            geoid=g.list_id,
        )
    db.commit()
    return [GrantWithCredential(credential=g.credential, **_grant_out(g).model_dump()) for g in rows]


@router.post("/revoke", response_model=GrantOut)
def revoke_grant(
    body: RevokeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = request.app.state.settings
    grant = db.execute(select(Grant).where(Grant.jti == body.jti)).scalar_one_or_none()
    if grant is None or grant.issuer_user_id != user.id:
        raise HTTPException(status_code=404, detail="grant not found")
    if grant.status == "revoked":
        return _grant_out(grant)

    # Guardrail: revocation is recorded (bit + row + audit packet) BEFORE this
    # endpoint returns success.
    statuslist_service.revoke_index(
        db, grant.status_list_index, settings.status_list_size, settings.status_list_index_start
    )
    grant.status = "revoked"
    grant.revoked_at = datetime.now(timezone.utc)

    MealStore(request.app.state.issuer).append_event(
        db,
        meal_key=grant.list_id,
        event_type="grant.revoked",
        author_account=user.hub_account_id,
        payload={"jti": grant.jti, "status_list_index": grant.status_list_index},
        geoid=grant.list_id,
    )
    db.commit()

    # Report to the hub revocation registry when configured.
    if settings.hub_url:
        try:
            httpx.post(
                f"{settings.hub_url.rstrip('/')}/revocations",
                json={
                    "jti": grant.jti,
                    "status_list_uri": settings.status_list_uri,
                    "status_list_index": grant.status_list_index,
                },
                timeout=10,
            ).raise_for_status()
        except httpx.HTTPError as e:
            # Local revocation already durable; surface the reporting failure.
            raise HTTPException(
                status_code=502,
                detail=f"grant revoked locally but hub report failed: {e}",
            ) from e

    return _grant_out(grant)


@router.get("/status-list", response_model=StatusListOut)
def status_list(request: Request, db: Session = Depends(get_db)):
    """Public revocation bitstring (StatusList2021-style). No auth: it leaks
    nothing but revocation bits."""
    settings = request.app.state.settings
    encoded = statuslist_service.encoded_list(
        db, settings.status_list_size, settings.status_list_index_start
    )
    return StatusListOut(uri=settings.status_list_uri, encoded=encoded, size=settings.status_list_size)


@router.post("/verify")
def verify_credential(
    request: Request,
    credential: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Relying-party convenience endpoint: verify a credential issued by THIS
    instance (signature, expiry, revocation bit). AR nodes embed the same
    logic locally via pancake_services.grants.sdjwt."""
    settings = request.app.state.settings
    issuer = request.app.state.issuer
    try:
        result = sdjwt.verify(credential, issuer.public_key_pem)
    except sdjwt.VerificationError as e:
        return {"valid": False, "reason": str(e)}

    status = result.claims.get("status", {}).get("status_list", {})
    idx = status.get("idx")
    if idx is not None and statuslist_service.is_revoked(
        db, idx, settings.status_list_size, settings.status_list_index_start
    ):
        return {"valid": False, "reason": "credential revoked"}

    return {
        "valid": True,
        "claims": {
            "sub": result.claims["sub"],
            "grantee": result.claims["grantee"],
            "purpose": result.claims["purpose"],
            "masking_level": result.claims["masking_level"],
            "exp": result.claims["exp"],
            "jti": result.claims["jti"],
        },
        "disclosed_geoids": result.disclosed_geoids,
    }
