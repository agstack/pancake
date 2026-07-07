# ListID Specification — Merkle Root over GeoIDs

**Status:** v1.0 (normative) · **Reference implementation:** `services/pancake_services/grants/merkle.py`

## Purpose

A **FieldList** is a named set of GeoIDs owned by one account. Its identifier, the **ListID**, is content-derived: the hex-encoded Merkle root over its member GeoIDs. Properties this buys us:

- **Deterministic:** the same set of GeoIDs always produces the same ListID, on any machine, in any order of entry.
- **Tamper-evident:** changing, adding, or removing any member changes the ListID.
- **Provable membership:** an inclusion proof shows a specific GeoID is in a list without revealing the other members — this pairs with selective disclosure in the grant credential.

## Construction (normative)

1. **Canonical ordering.** Sort the member GeoID strings lexicographically (byte-wise, on their UTF-8 encoding). Duplicate GeoIDs are removed before sorting.
2. **Leaves.** For each GeoID `g` in sorted order: `leaf = SHA-256(UTF8(g))` (32 raw bytes).
3. **Tree.** While more than one node remains, process the current level left to right:
   - Pair adjacent nodes: `parent = SHA-256(left || right)` where `||` is raw byte concatenation.
   - If the level has an odd count, the final unpaired node is **promoted unchanged** to the next level (no self-hashing).
4. **Root.** The single remaining node is the Merkle root. The **ListID is its lowercase hex encoding** (64 characters).
5. **Empty list** is invalid: a FieldList must contain at least one GeoID.
6. **Single member:** the ListID is simply `hex(SHA-256(UTF8(g)))`.

## Inclusion proofs

A proof for leaf `g` is an ordered array of steps from leaf to root:

```json
{
  "geoid": "<g>",
  "list_id": "<root hex>",
  "proof": [
    {"sibling": "<hex 32-byte node>", "position": "right"},
    {"sibling": "<hex>", "position": "left"}
  ]
}
```

- `position` is the side the **sibling** occupies in the concatenation.
- A promoted (unpaired) node contributes **no step** at that level.

**Verification:** start with `node = SHA-256(UTF8(g))`; for each step compute `node = SHA-256(node || sibling)` if `position == "right"` else `SHA-256(sibling || node)`; accept iff the final `node` hex equals `list_id`.

## Test vectors (SHA-256)

GeoIDs here are short strings for readability; production GeoIDs are 64-char hex but the algorithm is identical.

### Vector 1 — single leaf
- Members: `["geo-a"]`
- ListID = SHA-256("geo-a") = `80796c5dba2ba9b8c3d9d71e2e38735e37ad25e267fae70d262fdebcc405ec97`

### Vector 2 — two leaves
- Members: `["geo-b", "geo-a"]` (note: input order is irrelevant; sorted order is `geo-a`, `geo-b`)
- `leaf_a = SHA-256("geo-a")`, `leaf_b = SHA-256("geo-b")`
- ListID = SHA-256(leaf_a || leaf_b) = `6f41030b5e4221af251efb44e86ee1947ee0d6ccbc5c08b798ef60a2d861df54`

### Vector 3 — three leaves (odd promotion)
- Members: `["geo-c", "geo-a", "geo-b"]` → sorted `geo-a, geo-b, geo-c`
- Level 0: `leaf_a, leaf_b, leaf_c`
- Level 1: `SHA-256(leaf_a || leaf_b)`, `leaf_c` (promoted)
- ListID = SHA-256(H_ab || leaf_c) = `44aa157374cca1544e5de5717f79630835ae0e672785e096bc2e3ee5609a3427`

### Vector 4 — twelve leaves
- Members: `["geo-00" .. "geo-11"]` (already in lexicographic order)
- ListID = `ea96927d77bb5c9b44e11a11c6565f75bd935ccd49b4ef6d2a02677390260c0a`

The reference implementation's test suite (`services/tests/test_merkle.py`) asserts all four vectors and round-trips inclusion proofs for every member of every vector.

## Notes

- SHA-256 everywhere for consistency with GeoID generation and MEAL packet hashing.
- ListIDs are **not secret**; they are identifiers. Confidentiality of list membership is handled by selective disclosure in the grant credential (see [CREDENTIAL_PROFILE.md](CREDENTIAL_PROFILE.md)).
- Renaming a list does not change its ListID (the name is metadata, not content). Changing membership creates a *new* list identity by construction; grants issued against the old ListID remain bound to the old membership — this is intentional: a grant is a grant over an exact set of fields.
