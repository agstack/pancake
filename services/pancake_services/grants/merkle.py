"""Merkle ListID construction per services/specs/MERKLE_LISTID.md.

A FieldList's identifier (ListID) is the hex Merkle root over its member
GeoIDs: leaves are SHA-256 of the UTF-8 GeoID strings in lexicographic
order, parents are SHA-256(left || right), and an odd node is promoted
unchanged to the next level.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def canonical_members(geoids: List[str]) -> List[str]:
    """Deduplicate and sort GeoIDs into canonical (lexicographic) order."""
    if not geoids:
        raise ValueError("a FieldList must contain at least one GeoID")
    return sorted(set(geoids))


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


def merkle_root(geoids: List[str]) -> str:
    """Compute the ListID (lowercase hex Merkle root) for a set of GeoIDs."""
    members = canonical_members(geoids)
    return _levels(members)[-1][0].hex()


def inclusion_proof(geoids: List[str], geoid: str) -> List[Dict[str, str]]:
    """Build an inclusion proof (list of {sibling, position} steps) for one GeoID."""
    members = canonical_members(geoids)
    if geoid not in members:
        raise ValueError(f"GeoID not in list: {geoid}")
    levels = _levels(members)
    index = members.index(geoid)
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


def verify_inclusion(geoid: str, proof: List[Dict[str, str]], list_id: str) -> bool:
    """Verify an inclusion proof against a ListID."""
    node = _sha256(geoid.encode("utf-8"))
    for step in proof:
        sibling = bytes.fromhex(step["sibling"])
        if step["position"] == "right":
            node = _sha256(node + sibling)
        elif step["position"] == "left":
            node = _sha256(sibling + node)
        else:
            return False
    return node.hex() == list_id
