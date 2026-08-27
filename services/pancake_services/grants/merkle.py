# SPDX-License-Identifier: EUPL-1.2
# Copyright (c) 2026 AgStack project contributors.
# Licensed under the EUPL, Version 1.2; see the LICENSE file for the full text.

"""Merkle ListID construction per services/specs/MERKLE_LISTID.md.

A List's identifier (ListID) is the hex Merkle root over its members
(GeoIDs, nested RegionIDs prefixed with R:, or nested ListIDs prefixed with L:).
Leaves are SHA-256 of the UTF-8 strings in lexicographic order.
Parents are SHA-256(left || right), and an odd node is promoted unchanged.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def canonical_members(members: List[str]) -> List[str]:
    """Deduplicate and sort members into canonical (lexicographic) order."""
    if not members:
        raise ValueError("a List must contain at least one member")
    return sorted(set(members))


def _levels(members: List[str]) -> List[List[bytes]]:
    """Build all tree levels, leaves first."""
    level = [_sha256(g.encode("utf-8")) for g in members]
    levels = [level]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(_sha256(level[i] + level[i + 1]))
        if len(level) % 2 == 1:
            nxt.append(level[-1])  # odd node promoted unchanged
        levels.append(nxt)
        level = nxt
    return levels


def merkle_root(members: List[str]) -> str:
    """Compute the ListID (lowercase hex Merkle root) for a set of members."""
    canonical = canonical_members(members)
    return _levels(canonical)[-1][0].hex()


def inclusion_proof(members: List[str], member: str) -> List[Dict[str, str]]:
    """Build an inclusion proof (list of {sibling, position} steps) for one member."""
    canonical = canonical_members(members)
    if member not in canonical:
        raise ValueError(f"Member not in list: {member}")
    levels = _levels(canonical)
    index = canonical.index(member)
    proof: List[Dict[str, str]] = []
    for level in levels[:-1]:
        pair_start = index - (index % 2)
        if pair_start + 1 < len(level):
            if index % 2 == 0:
                proof.append({"sibling": level[index + 1].hex(), "position": "right"})
            else:
                proof.append({"sibling": level[index - 1].hex(), "position": "left"})
            index = pair_start // 2
        else:
            # Unpaired node promoted: no step at this level.
            index = index // 2
    return proof


def verify_inclusion(member: str, proof: List[Dict[str, str]], list_id: str) -> bool:
    """Verify an inclusion proof against a ListID."""
    node = _sha256(member.encode("utf-8"))
    for step in proof:
        sibling = bytes.fromhex(step["sibling"])
        if step["position"] == "right":
            node = _sha256(node + sibling)
        elif step["position"] == "left":
            node = _sha256(sibling + node)
        else:
            return False
    return node.hex() == list_id
