"""Pydantic request/response schemas for the grants service."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FieldListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    geoids: List[str] = Field(min_length=1)


class FieldListOut(BaseModel):
    list_id: str
    name: str
    geoids: List[str]
    created_at: datetime


class InclusionProofOut(BaseModel):
    geoid: str
    list_id: str
    proof: List[dict]


class GrantIssueRequest(BaseModel):
    list_id: str = Field(min_length=64, max_length=64)
    grantee_account: str = Field(min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=256)
    validity_days: int = Field(default=30, ge=1, le=365)
    masking_level: str = Field(default="L1", pattern="^L[12]$")


class GrantOut(BaseModel):
    jti: str
    list_id: str
    grantee_account: str
    purpose: str
    masking_level: str
    status: str
    status_list_index: int
    expires_at: datetime
    created_at: datetime
    revoked_at: Optional[datetime] = None


class GrantWithCredential(GrantOut):
    credential: str


class RevokeRequest(BaseModel):
    jti: str


class StatusListOut(BaseModel):
    uri: str
    encoded: str
    size: int


class GuaranteeIssueRequest(BaseModel):
    """Issue (or advance) a Green Guarantee over a plot or a cooperative batch."""

    subject: str = Field(min_length=64, max_length=64, description="GeoID or ListID")
    subject_kind: str = Field(pattern="^(geoid|fieldlist)$")
    beneficiary_account: str = Field(min_length=1, max_length=128, description="hub account of the lender")
    request_ref: str = Field(min_length=1, max_length=128, description="the credit request this backs")
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    coverage_ratio: float = Field(gt=0, le=1, description="share of the loan the guarantee covers")
    risk_class: str = Field(pattern="^(low|high|more_info_needed)$")
    rule_set_version: str = Field(min_length=1, max_length=64, description="the screen's rule_set.version")
    evidence: List[str] = Field(default_factory=list, description="BITE ids the decision rests on")
    state: str = Field(pattern="^(PRE_APPROVED|ISSUED)$")
    supersedes_jti: Optional[str] = Field(default=None, description="prior guarantee this replaces")
    validity_days: int = Field(default=365, ge=1, le=1830)


class GuaranteeOut(BaseModel):
    jti: str
    subject: str
    subject_kind: str
    beneficiary_account: str
    request_ref: str
    amount: float
    currency: str
    coverage_ratio: float
    risk_class: str
    rule_set_version: str
    state: str
    supersedes_jti: Optional[str] = None
    status: str
    status_list_index: int
    expires_at: datetime
    created_at: datetime
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None


class GuaranteeWithCredential(GuaranteeOut):
    credential: str


class GuaranteeRevokeRequest(BaseModel):
    jti: str
    reason: str = Field(min_length=1, max_length=256)

class HoldersRequest(BaseModel):
    list_ids: List[str]
    scope: str
    seed_geoid: str

class HoldersResponse(BaseModel):
    holders: dict[str, str]
