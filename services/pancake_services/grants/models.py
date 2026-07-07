"""ORM models for the grants service.

Guardrail reminder: Pancake stores GeoID list membership and grant
metadata -- never field geometry, and never another service's ACLs.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pancake_services.common.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Local mirror of a hub account, created on first authenticated request."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hub_account_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    fieldlists: Mapped[list["FieldList"]] = relationship(back_populates="owner")


class FieldList(Base):
    """A named set of GeoIDs owned by one account; id is the Merkle root (ListID)."""

    __tablename__ = "fieldlists"
    __table_args__ = (UniqueConstraint("list_id", "owner_id", name="uq_fieldlist_owner"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="fieldlists")
    members: Mapped[list["FieldListMember"]] = relationship(
        back_populates="fieldlist", cascade="all, delete-orphan"
    )

    @property
    def geoids(self) -> list[str]:
        return sorted(m.geoid for m in self.members)


class FieldListMember(Base):
    __tablename__ = "fieldlist_members"
    __table_args__ = (UniqueConstraint("fieldlist_id", "geoid", name="uq_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fieldlist_id: Mapped[int] = mapped_column(ForeignKey("fieldlists.id"), index=True)
    geoid: Mapped[str] = mapped_column(String(128), index=True)

    fieldlist: Mapped[FieldList] = relationship(back_populates="members")


class Grant(Base):
    """An issued field-access grant credential (metadata; the credential itself is signed)."""

    __tablename__ = "grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    list_id: Mapped[str] = mapped_column(String(64), index=True)
    issuer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    grantee_account: Mapped[str] = mapped_column(String(128), index=True)
    purpose: Mapped[str] = mapped_column(String(256))
    masking_level: Mapped[str] = mapped_column(String(8), default="L1")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | revoked
    status_list_index: Mapped[int] = mapped_column(Integer, unique=True)
    credential: Mapped[str] = mapped_column(Text)  # SD-JWT compact serialization
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StatusListState(Base):
    """Single-row persistence of the issuer's revocation bitstring."""

    __tablename__ = "status_list_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encoded: Mapped[str] = mapped_column(Text)
    next_index: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Meal(Base):
    """MEAL root metadata (audit ledger cover page)."""

    __tablename__ = "meals"

    meal_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    meal_type: Mapped[str] = mapped_column(String(50))
    created_at_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_updated_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    primary_geoid: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    participant_agents: Mapped[list] = mapped_column(JSON, default=list)
    packet_count: Mapped[int] = mapped_column(Integer, default=0)
    root_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    last_packet_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class MealPacket(Base):
    """A packet in a MEAL hash chain, signed by the instance key."""

    __tablename__ = "meal_packets"
    __table_args__ = (UniqueConstraint("meal_id", "sequence_number", name="uq_meal_seq"),)

    packet_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    meal_id: Mapped[str] = mapped_column(ForeignKey("meals.meal_id"), index=True)
    packet_type: Mapped[str] = mapped_column(String(10))  # 'sip' or 'bite'
    sequence_number: Mapped[int] = mapped_column(Integer)
    previous_packet_id: Mapped[str | None] = mapped_column(String(26), nullable=True)
    previous_packet_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    time_index: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    geoid: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    author: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[dict] = mapped_column(JSON)  # sip content or bite envelope
    content_hash: Mapped[str] = mapped_column(String(66))
    packet_hash: Mapped[str] = mapped_column(String(66))
    signature: Mapped[str | None] = mapped_column(String(256), nullable=True)


class Bite(Base):
    """Stored BITE envelope, queryable by GeoID/type/time (Cycle 6)."""

    __tablename__ = "bites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bite_id: Mapped[str] = mapped_column(String(64), index=True)
    geoid: Mapped[str] = mapped_column(String(128), index=True)
    bite_type: Mapped[str] = mapped_column(String(64), index=True)
    vendor: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(66), unique=True)
    envelope: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
