"""Green Guarantee lifecycle: issue, advance, retrieve, revoke, verify.

A guarantee is a promise a guarantor makes to a lender about a plot or a batch
of plots: if this farmer defaults, we cover this share of this amount. The
Confianza design carried it as a row in a database. Here it is a credential,
for the same reasons a field-access grant is one: the lender can verify it
without asking the issuer; it can be revoked and the revocation is public in the
status list; it names the risk class it was issued on and the rule set that
class was reached under; and every step of its life is in the MEAL.

The subject is a GeoID or a ListID -- never a geometry. What the lender receives
is the guarantee and the L0 view of the plot; the polygon stays with the farmer
and whoever holds an L1 grant for the screen.

State: PRE_APPROVED -> ISSUED is a new credential that names the one it
supersedes; the superseded one is revoked in the same transaction, so at any
moment exactly one active guarantee stands for a request. REVOKED is the
status-list bit, as for a grant, with a reason recorded.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ulid import ULID

from pancake_services.grants import sdjwt, statuslist_service
from pancake_services.grants.auth import get_current_user, get_db
from pancake_services.grants.mealstore import MealStore
from pancake_services.grants.models import Guarantee, User
from pancake_services.grants.schemas import (
    GuaranteeIssueRequest,
    GuaranteeOut,
    GuaranteeRevokeRequest,
    GuaranteeWithCredential,
)

router = APIRouter(prefix="/guarantees", tags=["guarantees"])

VCT = "agstack.org/credentials/green-guarantee/v1"
"""The credential type. A verifier built for field-access grants must refuse
this, and one built for guarantees must refuse a grant: ``sdjwt.verify`` checks
the ``vct`` for exactly that reason."""

MEAL_TYPE = "guarantee_lifecycle"


def _out(g: Guarantee) -> GuaranteeOut:
    return GuaranteeOut(
        jti=g.jti,
        subject=g.subject,
        subject_kind=g.subject_kind,
        beneficiary_account=g.beneficiary_account,
        request_ref=g.request_ref,
        amount=g.amount,
        currency=g.currency,
        coverage_ratio=g.coverage_ratio,
        risk_class=g.risk_class,
        rule_set_version=g.rule_set_version,
        state=g.state,
        supersedes_jti=g.supersedes_jti,
        status=g.status,
        status_list_index=g.status_list_index,
        expires_at=g.expires_at,
        created_at=g.created_at,
        revoked_at=g.revoked_at,
        revoked_reason=g.revoked_reason,
    )


def _build_odrl(jti: str, body: GuaranteeIssueRequest, exp: int) -> dict:
    """What the lender may do with the guarantee: rely on it, for this request, until it expires."""
    exp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp))
    return {
        "@context": "http://www.w3.org/ns/odrl.jsonld",
        "@type": "Agreement",
        "uid": f"urn:agstack:guarantee:{jti}",
        "permission": [{
            "target": f"urn:agstack:{body.subject_kind}:{body.subject}",
            "action": "use",
            "assignee": body.beneficiary_account,
            "constraint": [
                {"leftOperand": "dateTime", "operator": "lteq", "rightOperand": exp_iso},
                {"leftOperand": "purpose", "operator": "eq", "rightOperand": "credit-guarantee"},
                {"leftOperand": "event", "operator": "eq", "rightOperand": body.request_ref},
            ],
        }],
        "prohibition": [{
            "target": f"urn:agstack:{body.subject_kind}:{body.subject}",
            "action": "distribute",
        }],
    }


def _revoke(db: Session, settings, issuer, g: Guarantee, *, author: str, reason: str) -> None:
    """Set the bit, mark the row, write the packet -- all before anyone is told it succeeded."""
    statuslist_service.revoke_index(
        db, g.status_list_index, settings.status_list_size, settings.status_list_index_start
    )
    g.status = "revoked"
    g.revoked_at = datetime.now(timezone.utc)
    g.revoked_reason = reason
    MealStore(issuer).append_event(
        db,
        meal_key=g.subject,
        event_type="guarantee.revoked",
        author_account=author,
        payload={
            "jti": g.jti,
            "request_ref": g.request_ref,
            "state_at_revocation": g.state,
            "status_list_index": g.status_list_index,
            "reason": reason,
        },
        geoid=g.subject,
        meal_type=MEAL_TYPE,
    )


@router.post("/issue", response_model=GuaranteeWithCredential, status_code=201)
def issue_guarantee(
    body: GuaranteeIssueRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Issue a guarantee, or advance one from PRE_APPROVED to ISSUED.

    Advancing names the prior credential in ``supersedes_jti``; it must be this
    issuer's, active, for the same request, and it is revoked here so that one
    active guarantee stands for a request at any time.
    """
    settings = request.app.state.settings
    issuer = request.app.state.issuer

    prior: Guarantee | None = None
    if body.supersedes_jti:
        prior = db.execute(
            select(Guarantee).where(Guarantee.jti == body.supersedes_jti)
        ).scalar_one_or_none()
        if prior is None or prior.issuer_user_id != user.id:
            raise HTTPException(status_code=404, detail="superseded guarantee not found")
        if prior.status != "active":
            raise HTTPException(status_code=409, detail="superseded guarantee is not active")
        if prior.request_ref != body.request_ref or prior.subject != body.subject:
            raise HTTPException(
                status_code=409, detail="a guarantee may only supersede one for the same request and subject"
            )
        if prior.state == "ISSUED" and body.state == "PRE_APPROVED":
            raise HTTPException(status_code=409, detail="an issued guarantee cannot go back to pre-approved")
    elif body.state == "ISSUED":
        # Direct issue without pre-approval is allowed; it is simply a
        # single-step life. The state machine forbids only going backwards.
        pass

    index = statuslist_service.allocate_index(
        db, settings.status_list_size, settings.status_list_index_start
    )
    jti = str(ULID())
    now = int(time.time())
    exp = now + body.validity_days * 86400
    claims = {
        "iss": issuer.issuer_id,
        "sub": body.subject,
        "iat": now,
        "exp": exp,
        "jti": jti,
        "vct": VCT,
        "subject_kind": body.subject_kind,
        "beneficiary": body.beneficiary_account,
        "guarantee": {
            "request_ref": body.request_ref,
            "amount": body.amount,
            "currency": body.currency,
            "coverage_ratio": body.coverage_ratio,
            "state": body.state,
            "supersedes": body.supersedes_jti,
        },
        "risk": {
            "risk_class": body.risk_class,
            "rule_set_version": body.rule_set_version,
            "evidence": list(body.evidence),
        },
        "odrl": _build_odrl(jti, body, exp),
        "status": {"status_list": {"uri": settings.status_list_uri, "idx": index}},
    }
    # Nothing is selectively disclosable: a guarantee is shown whole or not at all.
    credential = sdjwt.issue(claims, [], issuer.private_key_pem, issuer.kid)

    g = Guarantee(
        jti=jti,
        subject=body.subject,
        subject_kind=body.subject_kind,
        issuer_user_id=user.id,
        beneficiary_account=body.beneficiary_account,
        request_ref=body.request_ref,
        amount=body.amount,
        currency=body.currency,
        coverage_ratio=body.coverage_ratio,
        risk_class=body.risk_class,
        rule_set_version=body.rule_set_version,
        state=body.state,
        supersedes_jti=body.supersedes_jti,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        status="active",
        status_list_index=index,
        credential=credential,
    )
    db.add(g)
    db.flush()

    if prior is not None:
        _revoke(db, settings, issuer, prior, author=user.hub_account_id, reason=f"superseded by {jti}")

    MealStore(issuer).append_event(
        db,
        meal_key=body.subject,
        event_type=f"guarantee.{body.state.lower()}",
        author_account=user.hub_account_id,
        payload={
            "jti": jti,
            "request_ref": body.request_ref,
            "beneficiary": body.beneficiary_account,
            "amount": body.amount,
            "currency": body.currency,
            "coverage_ratio": body.coverage_ratio,
            "risk_class": body.risk_class,
            "rule_set_version": body.rule_set_version,
            "evidence": list(body.evidence),
            "supersedes": body.supersedes_jti,
            "expires_at": g.expires_at.isoformat(),
        },
        geoid=body.subject,
        meal_type=MEAL_TYPE,
    )
    db.commit()
    return GuaranteeWithCredential(credential=credential, **_out(g).model_dump())


@router.get("/issued", response_model=list[GuaranteeOut])
def guarantees_issued(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Guarantee).where(Guarantee.issuer_user_id == user.id)).scalars()
    return [_out(g) for g in rows]


@router.get("/received", response_model=list[GuaranteeWithCredential])
def guarantees_received(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The lender retrieves the active guarantees issued to its account; each retrieval is logged."""
    rows = list(
        db.execute(
            select(Guarantee).where(
                Guarantee.beneficiary_account == user.hub_account_id, Guarantee.status == "active"
            )
        ).scalars()
    )
    store = MealStore(request.app.state.issuer)
    for g in rows:
        store.append_event(
            db,
            meal_key=g.subject,
            event_type="guarantee.retrieved",
            author_account=user.hub_account_id,
            payload={"jti": g.jti, "request_ref": g.request_ref},
            geoid=g.subject,
            meal_type=MEAL_TYPE,
        )
    db.commit()
    return [GuaranteeWithCredential(credential=g.credential, **_out(g).model_dump()) for g in rows]


@router.post("/revoke", response_model=GuaranteeOut)
def revoke_guarantee(
    body: GuaranteeRevokeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    g = db.execute(select(Guarantee).where(Guarantee.jti == body.jti)).scalar_one_or_none()
    if g is None or g.issuer_user_id != user.id:
        raise HTTPException(status_code=404, detail="guarantee not found")
    if g.status == "revoked":
        return _out(g)
    _revoke(db, request.app.state.settings, request.app.state.issuer, g, author=user.hub_account_id, reason=body.reason)
    db.commit()
    return _out(g)


@router.post("/verify")
def verify_guarantee(
    request: Request,
    credential: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Relying-party check: signature, expiry, type, revocation bit. What a lender runs before it lends."""
    settings = request.app.state.settings
    issuer = request.app.state.issuer
    try:
        result = sdjwt.verify(credential, issuer.public_key_pem, expected_vct=VCT)
    except sdjwt.VerificationError as e:
        return {"valid": False, "reason": str(e)}

    status = result.claims.get("status", {}).get("status_list", {})
    idx = status.get("idx")
    if idx is not None and statuslist_service.is_revoked(
        db, idx, settings.status_list_size, settings.status_list_index_start
    ):
        return {"valid": False, "reason": "guarantee revoked"}

    c = result.claims
    return {
        "valid": True,
        "claims": {
            "sub": c["sub"],
            "subject_kind": c["subject_kind"],
            "beneficiary": c["beneficiary"],
            "guarantee": c["guarantee"],
            "risk": c["risk"],
            "exp": c["exp"],
            "jti": c["jti"],
        },
    }
