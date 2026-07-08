"""Persistent, signed MEAL audit ledger.

Every consequential event in the grants service (fieldlist created, grant
issued/retrieved/revoked) is appended as a packet to a per-ListID MEAL:
hash-chained (SHA-256) and signed with the instance Ed25519 key. This
closes finding PC-2026-0001 (unsigned packets, broken previous_packet_id).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session
from ulid import ULID

from pancake_services.grants.issuer import IssuerIdentity
from pancake_services.grants.models import Meal, MealPacket


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _content_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _packet_hash(
    packet_id: str,
    meal_id: str,
    sequence_number: int,
    time_index: str,
    author: Dict[str, Any],
    content_hash: str,
    previous_hash: Optional[str],
) -> str:
    canonical = _canonical(
        {
            "packet_id": packet_id,
            "meal_id": meal_id,
            "sequence_number": sequence_number,
            "time_index": time_index,
            "author": author,
            "content_hash": content_hash,
            "previous_hash": previous_hash or "",
        }
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class MealStore:
    def __init__(self, issuer: IssuerIdentity):
        self._issuer = issuer
        self._signing_key = serialization.load_pem_private_key(
            issuer.private_key_pem, password=None
        )
        assert isinstance(self._signing_key, Ed25519PrivateKey)

    # -- write path ---------------------------------------------------------

    def append_event(
        self,
        db: Session,
        meal_key: str,
        event_type: str,
        author_account: str,
        payload: Dict[str, Any],
        geoid: Optional[str] = None,
        meal_type: str = "grant_lifecycle",
    ) -> MealPacket:
        """Append a signed event packet to the MEAL identified by meal_key.

        meal_key is a stable business key (we use the ListID); the MEAL row
        is created on first use.
        """
        meal = db.execute(select(Meal).where(Meal.primary_geoid == meal_key)).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if meal is None:
            meal = Meal(
                meal_id=str(ULID()),
                meal_type=meal_type,
                primary_geoid=meal_key,
                participant_agents=[],
                packet_count=0,
            )
            db.add(meal)
            db.flush()

        participants = list(meal.participant_agents or [])
        if author_account not in [p.get("agent_id") for p in participants]:
            participants.append(
                {"agent_id": author_account, "agent_type": "human", "joined_at": now.isoformat()}
            )
            meal.participant_agents = participants

        sequence_number = meal.packet_count + 1
        packet_id = str(ULID())
        time_index = now.isoformat()
        author = {"agent_id": author_account, "agent_type": "human"}
        body = {"event_type": event_type, **payload}
        content_hash = _content_hash(body)
        previous_hash = meal.last_packet_hash
        packet_hash = _packet_hash(
            packet_id, meal.meal_id, sequence_number, time_index, author, content_hash, previous_hash
        )
        signature = self._signing_key.sign(bytes.fromhex(packet_hash)).hex()

        packet = MealPacket(
            packet_id=packet_id,
            meal_id=meal.meal_id,
            packet_type="sip",
            sequence_number=sequence_number,
            previous_packet_id=self._last_packet_id(db, meal) if meal.packet_count else None,
            previous_packet_hash=previous_hash,
            time_index=now,
            geoid=geoid,
            author=author,
            payload=body,
            content_hash=content_hash,
            packet_hash=packet_hash,
            signature=signature,
        )
        db.add(packet)

        meal.packet_count = sequence_number
        meal.last_packet_hash = packet_hash
        meal.last_updated_time = now
        if sequence_number == 1:
            meal.root_hash = packet_hash
        db.flush()
        return packet

    @staticmethod
    def _last_packet_id(db: Session, meal: Meal) -> Optional[str]:
        row = db.execute(
            select(MealPacket.packet_id)
            .where(MealPacket.meal_id == meal.meal_id)
            .order_by(MealPacket.sequence_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        return row

    # -- verify path --------------------------------------------------------

    def verify_chain(self, db: Session, meal_id: str) -> Dict[str, Any]:
        """Recompute the hash chain and check every packet signature."""
        packets: List[MealPacket] = list(
            db.execute(
                select(MealPacket)
                .where(MealPacket.meal_id == meal_id)
                .order_by(MealPacket.sequence_number)
            ).scalars()
        )
        public_key = serialization.load_pem_public_key(self._issuer.public_key_pem)
        assert isinstance(public_key, Ed25519PublicKey)

        previous_hash: Optional[str] = None
        for i, packet in enumerate(packets):
            if packet.sequence_number != i + 1:
                return {"valid": False, "error": f"sequence gap at packet {i + 1}"}
            expected_content = _content_hash(packet.payload)
            if packet.content_hash != expected_content:
                return {"valid": False, "error": f"content hash mismatch at packet {i + 1}"}
            time_index = packet.time_index
            if time_index.tzinfo is None:
                time_index = time_index.replace(tzinfo=timezone.utc)
            expected_hash = _packet_hash(
                packet.packet_id,
                packet.meal_id,
                packet.sequence_number,
                time_index.isoformat(),
                packet.author,
                packet.content_hash,
                previous_hash,
            )
            if packet.packet_hash != expected_hash:
                return {"valid": False, "error": f"packet hash mismatch at packet {i + 1}"}
            if not packet.signature:
                return {"valid": False, "error": f"missing signature at packet {i + 1}"}
            try:
                public_key.verify(bytes.fromhex(packet.signature), bytes.fromhex(packet.packet_hash))
            except InvalidSignature:
                return {"valid": False, "error": f"invalid signature at packet {i + 1}"}
            previous_hash = packet.packet_hash

        return {"valid": True, "packet_count": len(packets)}
