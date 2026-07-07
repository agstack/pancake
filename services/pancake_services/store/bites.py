"""BITE store: persistence and GeoID-indexed querying of BITE envelopes.

``BiteStore.save`` is the production TAP ingest sink (the frozen interface
from pancake_services.tap.runtime). Deduplication is by content hash: the
same BITE ingested twice is stored once.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pancake_services.grants.models import Bite


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class BiteStore:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def save(self, bite: Dict[str, Any]) -> bool:
        """Persist a BITE envelope. Returns True if stored, False if duplicate.

        Validates envelope shape at the boundary: Header (id, geoid,
        timestamp, type) and Footer (hash) are required.
        """
        header = bite.get("Header") or {}
        footer = bite.get("Footer") or {}
        for key in ("id", "geoid", "timestamp", "type"):
            if not header.get(key):
                raise ValueError(f"BITE Header missing required field: {key}")
        content_hash = footer.get("hash")
        if not content_hash:
            raise ValueError("BITE Footer missing required field: hash")

        session: Session = self._session_factory()
        try:
            existing = session.execute(
                select(Bite.id).where(Bite.content_hash == content_hash)
            ).scalar_one_or_none()
            if existing is not None:
                return False
            session.add(Bite(
                bite_id=header["id"],
                geoid=header["geoid"],
                bite_type=header["type"],
                vendor=(header.get("source") or {}).get("vendor"),
                timestamp=_parse_timestamp(header["timestamp"]),
                content_hash=content_hash,
                envelope=bite,
            ))
            session.commit()
            return True
        finally:
            session.close()

    def query(
        self,
        geoid: Optional[str] = None,
        bite_type: Optional[str] = None,
        vendor: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Bite]:
        session: Session = self._session_factory()
        try:
            query = select(Bite)
            if geoid is not None:
                query = query.where(Bite.geoid == geoid)
            if bite_type is not None:
                query = query.where(Bite.bite_type == bite_type)
            if vendor is not None:
                query = query.where(Bite.vendor == vendor)
            if since is not None:
                query = query.where(Bite.timestamp >= since)
            if until is not None:
                query = query.where(Bite.timestamp <= until)
            query = query.order_by(Bite.timestamp.desc()).limit(limit).offset(offset)
            return list(session.execute(query).scalars())
        finally:
            session.close()

    def get_by_hash(self, content_hash: str) -> Optional[Bite]:
        session: Session = self._session_factory()
        try:
            return session.execute(
                select(Bite).where(Bite.content_hash == content_hash)
            ).scalar_one_or_none()
        finally:
            session.close()
