"""Known-answer and property tests for the Merkle ListID (MERKLE_LISTID.md)."""
import hashlib

import pytest

from pancake_services.grants.merkle import (
    canonical_members,
    inclusion_proof,
    merkle_root,
    verify_inclusion,
)

# Normative test vectors from services/specs/MERKLE_LISTID.md
VECTOR_1 = (["geo-a"], "80796c5dba2ba9b8c3d9d71e2e38735e37ad25e267fae70d262fdebcc405ec97")
VECTOR_2 = (["geo-b", "geo-a"], "6f41030b5e4221af251efb44e86ee1947ee0d6ccbc5c08b798ef60a2d861df54")
VECTOR_3 = (["geo-c", "geo-a", "geo-b"], "44aa157374cca1544e5de5717f79630835ae0e672785e096bc2e3ee5609a3427")
VECTOR_4 = ([f"geo-{i:02d}" for i in range(12)],
            "ea96927d77bb5c9b44e11a11c6565f75bd935ccd49b4ef6d2a02677390260c0a")


@pytest.mark.parametrize("members,expected", [VECTOR_1, VECTOR_2, VECTOR_3, VECTOR_4])
def test_known_answer_vectors(members, expected):
    assert merkle_root(members) == expected


def test_single_leaf_is_sha256_of_geoid():
    assert merkle_root(["geo-a"]) == hashlib.sha256(b"geo-a").hexdigest()


def test_order_invariance():
    members = [f"geo-{i:02d}" for i in range(12)]
    shuffled = members[::-1]
    assert merkle_root(members) == merkle_root(shuffled)


def test_duplicates_removed():
    assert merkle_root(["geo-a", "geo-a", "geo-b"]) == merkle_root(["geo-a", "geo-b"])


def test_membership_change_changes_listid():
    base = merkle_root(["geo-a", "geo-b", "geo-c"])
    assert merkle_root(["geo-a", "geo-b"]) != base
    assert merkle_root(["geo-a", "geo-b", "geo-d"]) != base


def test_empty_list_rejected():
    with pytest.raises(ValueError):
        merkle_root([])


def test_canonical_members_sorted_and_deduped():
    assert canonical_members(["b", "a", "b"]) == ["a", "b"]


@pytest.mark.parametrize("members", [VECTOR_1[0], VECTOR_2[0], VECTOR_3[0], VECTOR_4[0]])
def test_inclusion_proofs_verify_for_every_member(members):
    root = merkle_root(members)
    for geoid in canonical_members(members):
        proof = inclusion_proof(members, geoid)
        assert verify_inclusion(geoid, proof, root)


def test_inclusion_proof_fails_for_wrong_geoid():
    members = VECTOR_4[0]
    root = merkle_root(members)
    proof = inclusion_proof(members, "geo-05")
    assert not verify_inclusion("geo-06", proof, root)
    assert not verify_inclusion("not-in-list", proof, root)


def test_inclusion_proof_fails_against_wrong_root():
    members = VECTOR_3[0]
    proof = inclusion_proof(members, "geo-a")
    other_root = merkle_root(["geo-x", "geo-y"])
    assert not verify_inclusion("geo-a", proof, other_root)


def test_proof_for_nonmember_raises():
    with pytest.raises(ValueError):
        inclusion_proof(["geo-a"], "geo-z")


def test_odd_promotion_structure():
    """Three leaves: proof for the promoted leaf (geo-c) has exactly one step."""
    members = ["geo-a", "geo-b", "geo-c"]
    proof = inclusion_proof(members, "geo-c")
    assert len(proof) == 1
    assert proof[0]["position"] == "left"
