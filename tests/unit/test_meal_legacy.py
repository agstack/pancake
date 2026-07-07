"""Regression tests for the legacy POC MEAL implementation (implementation/meal.py).

Covers findings PC-2026-0001/PC-2026-0004: previous_packet_id linkage and
hash-computation ordering, which previously made verify_chain impossible.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "implementation"))

from meal import MEAL  # noqa: E402

AUTHOR = {"agent_id": "user-a", "agent_type": "human", "name": "A"}


def _build_chain(n=3):
    meal = MEAL.create("discussion", {"geoid": "g1", "label": "X"}, ["user-a"])
    packets = []
    for i in range(n):
        meal, packet = MEAL.append_packet(meal, "sip", AUTHOR, content={"text": f"msg-{i}"})
        packets.append(packet)
    return meal, packets


def test_previous_packet_id_linkage():
    _, packets = _build_chain()
    assert packets[0]["sequence"]["previous_packet_id"] is None
    assert packets[1]["sequence"]["previous_packet_id"] == packets[0]["packet_id"]
    assert packets[2]["sequence"]["previous_packet_id"] == packets[1]["packet_id"]


def test_verify_chain_passes_for_valid_chain():
    _, packets = _build_chain()
    assert MEAL.verify_chain(packets) is True


def test_verify_chain_detects_tampering():
    _, packets = _build_chain()
    packets[1]["sip_data"] = {"text": "tampered"}
    packets[1]["cryptographic"]["content_hash"] = MEAL._compute_content_hash(packets[1])
    assert MEAL.verify_chain(packets) is False


def test_create_with_initial_packet_sets_root_hash():
    meal = MEAL.create(
        "field_visit",
        {"geoid": "g1", "label": "F"},
        ["user-a"],
        initial_packet={"type": "sip", "author": AUTHOR, "content": {"text": "hi"}},
    )
    assert meal["cryptographic_chain"]["root_hash"] is not None
    assert meal["packet_sequence"]["packet_count"] == 1
