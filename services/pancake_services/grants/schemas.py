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
