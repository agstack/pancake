"""Persistence and index allocation for the issuer's revocation status list."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pancake_services.grants.models import StatusListState
from pancake_services.grants.statuslist import StatusList


def _get_or_create(db: Session, size: int, index_start: int) -> StatusListState:
    state = db.execute(select(StatusListState)).scalar_one_or_none()
    if state is None:
        state = StatusListState(encoded=StatusList(size).encode(), next_index=index_start)
        db.add(state)
        db.flush()
    return state


def allocate_index(db: Session, size: int, index_start: int) -> int:
    """Allocate the next status-list index within this issuer's hub-assigned range."""
    state = _get_or_create(db, size, index_start)
    index = state.next_index
    if index >= index_start + size:
        raise RuntimeError("status list index range exhausted; request a new range from the hub")
    state.next_index = index + 1
    db.flush()
    return index


def revoke_index(db: Session, index: int, size: int, index_start: int) -> None:
    state = _get_or_create(db, size, index_start)
    status = StatusList.decode(state.encoded)
    status.set(index, True)
    state.encoded = status.encode()
    db.flush()


def encoded_list(db: Session, size: int, index_start: int) -> str:
    return _get_or_create(db, size, index_start).encoded


def is_revoked(db: Session, index: int, size: int, index_start: int) -> bool:
    return StatusList.decode(_get_or_create(db, size, index_start).encoded).is_revoked(index)
