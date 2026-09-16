# AgStack Field-Access Grant — Credential Profile

**Status:** v1.0 (normative) · **Format:** SD-JWT VC (IETF `draft-ietf-oauth-sd-jwt-vc`) · **Signature:** Ed25519 (`EdDSA`)
**Reference implementation:** `services/pancake_services/grants/sdjwt.py` · **Revocation:** StatusList2021 bitstring (`services/pancake_services/grants/statuslist.py`)

## 1. What this credential says

"The holder identified below has been granted **read access at masking level L1** (the plot as registered) to the plots in FieldList `<ListID>`, for purpose `<purpose>`, until `<exp>` — signed by an issuer the AgStack hub accredits."

A relying party (an AR node, TerraPipe, an EUDR auditor) verifies:

1. the signature against the issuer's public key (resolved via the hub's `/trust/issuers` registry, keyed by `iss` + `kid`),
2. that `exp` has not passed,
3. that the credential's status bit in the referenced status list is **0** (not revoked),
4. selectively disclosed GeoID membership, when the presentation includes disclosures + a Merkle inclusion proof (see [MERKLE_LISTID.md](MERKLE_LISTID.md)).

## 2. JWT header

```json
{
  "alg": "EdDSA",
  "typ": "vc+sd-jwt",
  "kid": "pancake-issuer-1"
}
```

## 3. Claims

| Claim | Required | Meaning |
|---|---|---|
| `iss` | yes | Issuer identifier, `did:web` form (e.g. `did:web:pancake.agstack.org`). Must appear in the hub's accredited-issuer registry |
| `sub` | yes | The **ListID** (Merkle root hex) the grant covers |
| `iat` | yes | Issued-at (epoch seconds) |
| `exp` | yes | Expiry (epoch seconds). **Every grant expires**; no unbounded grants |
| `jti` | yes | Unique grant id (ULID). Used as the revocation handle |
| `vct` | yes | Verifiable credential type: `agstack.org/credentials/field-access-grant/v1` |
| `grantee` | yes | Hub account id of the grantee (the DPI-account delivery path: grantee authenticates to the hub and retrieves credentials issued to them) |
| `cnf` | no | Holder key binding (`{"jwk": ...}`) — set when the grantee holds a wallet keypair (e.g. TraceFoodChain wallet); omitted for account-delivery-only grants in phase 1 |
| `masking_level` | yes | Access level granted: `"L1"` (the plot as registered: a boundary, or a coordinate and its declared area). Future: `"L2"` (centroid+area) |
| `purpose` | yes | Free-text purpose string echoed into ODRL (e.g. `"eudr-due-diligence"`) |
| `odrl` | yes | Embedded ODRL 2.2 policy object (below) |
| `status` | yes | StatusList2021 reference: `{"status_list": {"uri": "<https URL>", "idx": <int>}}` |
| `_sd` / `_sd_alg` | when disclosures present | SD-JWT selective-disclosure digests, `_sd_alg: "sha-256"` |

### 3.1 Selectively disclosable claims

The **GeoID members** of the granted list are carried as selectively disclosable claims (`fields` array), so a presentation can reveal only the specific field(s) relevant to a transaction:

- Issuance embeds `SHA-256(disclosure)` digests in `_sd`; the raw disclosures (`[salt, "fields.N", geoid]` arrays, base64url-encoded) travel alongside the JWT in the SD-JWT compact serialization: `<jwt>~<disclosure1>~<disclosure2>~...~`.
- The verifier recomputes each disclosure digest and requires it to be present in `_sd`.
- For stronger-than-disclosure proof, the presentation may also carry a Merkle inclusion proof binding the disclosed GeoID to `sub` (the ListID).

### 3.2 ODRL policy object

```json
{
  "@context": "http://www.w3.org/ns/odrl.jsonld",
  "@type": "Agreement",
  "uid": "urn:agstack:grant:<jti>",
  "permission": [{
    "target": "urn:agstack:fieldlist:<ListID>",
    "action": "read",
    "constraint": [{
      "leftOperand": "dateTime",
      "operator": "lteq",
      "rightOperand": "<exp as ISO 8601>"
    }, {
      "leftOperand": "purpose",
      "operator": "eq",
      "rightOperand": "<purpose>"
    }],
    "duty": [{"action": "delete", "constraint": [{
      "leftOperand": "elapsedTime", "operator": "eq", "rightOperand": "P30D"
    }]}]
  }]
}
```

The ODRL object is what makes the grant legible to EU dataspace tooling (IDSA / DSP policy negotiation); the JWT claims are what make it cheaply verifiable at AR nodes. They are generated together from the same inputs and are semantically equivalent.

## 4. Revocation — StatusList2021

- Each accredited issuer is allocated an **index range** by the hub at accreditation time; the issuer assigns `idx` values within its range (Pancake dev default: range start 0, size 65536).
- The status list is a zlib-compressed, base64url-encoded bitstring published at `status.status_list.uri` (Pancake serves `GET /grants/status-list`).
- Bit = 1 means **revoked**. Verifiers must fail closed if the list cannot be fetched *and* the credential is older than a configurable freshness window.
- On revocation, Pancake: (1) flips the bit, (2) reports the revocation to the hub revocation registry (`POST {HUB_URL}/revocations`), (3) writes a MEAL audit packet — all **before** returning success to the caller.

## 5. Example (unsigned claim set)

```json
{
  "iss": "did:web:pancake.agstack.org",
  "sub": "44aa157374cca1544e5de5717f79630835ae0e672785e096bc2e3ee5609a3427",
  "iat": 1783468800,
  "exp": 1786060800,
  "jti": "01K1V3XWCS4N2QW9RCPXV0J8YD",
  "vct": "agstack.org/credentials/field-access-grant/v1",
  "grantee": "hub-acct-7f3a",
  "masking_level": "L1",
  "purpose": "eudr-due-diligence",
  "odrl": { "...": "see 3.2" },
  "status": {"status_list": {"uri": "https://pancake.agstack.org/grants/status-list", "idx": 42}},
  "_sd_alg": "sha-256",
  "_sd": ["<digest-of-geoid-1-disclosure>", "<digest-of-geoid-2-disclosure>"]
}
```

## 6. Verifier rules (normative summary)

A relying party MUST reject a presentation when any of the following holds:

1. Signature invalid, or `iss`/`kid` not resolvable to an accredited issuer key.
2. `exp` in the past (no grace period) or `iat` in the future beyond clock skew (300 s).
3. `vct` is not `agstack.org/credentials/field-access-grant/v1`.
4. Status bit at `status.status_list.idx` is 1 (revoked).
5. Any presented disclosure whose digest is not in `_sd`.
6. When a Merkle inclusion proof is presented: proof does not verify against `sub`.

## 7. Test kit

`services/pancake_services/grants/testkit/mint_test_credentials.py` generates a dev Ed25519 keypair (never committed) and mints five credentials for verifier development:

| # | Credential | Expected verifier outcome |
|---|---|---|
| 1 | `valid.sdjwt` | accept |
| 2 | `expired.sdjwt` | reject (rule 2) |
| 3 | `revoked.sdjwt` | reject (rule 4) |
| 4 | `tampered.sdjwt` | reject (rule 1) |
| 5 | `wrong_geoid.sdjwt` | reject (rule 5/6: disclosed GeoID not in `_sd` / proof fails) |

---

# AgStack Green Guarantee — Credential Profile

*Added 2026-09-15. Implemented in `pancake_services/grants/routers/guarantees.py`; tested in `tests/test_green_guarantee.py`.*

## 8. What this credential says

A guarantor (Confianza, or any accredited issuer) promises a lender that, should the borrower default, it covers a stated share of a stated amount on a stated credit request, and that the promise was made on a named risk class reached under a named rule set from named evidence. The subject is a plot (GeoID) or a cooperative batch (ListID) — **never a geometry**. The lender verifies the guarantee without asking the issuer; the issuer revokes it publicly; every step of its life is in the MEAL for the subject.

It is the same SD-JWT VC machinery as the field-access grant, with a different `vct`, so a verifier built for one refuses the other (`sdjwt.verify(..., expected_vct=...)`).

## 9. Claims

| Claim | Required | Meaning |
|---|---|---|
| `iss` | yes | Issuer identifier, as for grants |
| `sub` | yes | The **GeoID** or **ListID** (64 hex) the guarantee stands behind |
| `subject_kind` | yes | `"geoid"` or `"fieldlist"` |
| `iat`, `exp`, `jti` | yes | As for grants. **Every guarantee expires.** `jti` is the revocation handle and the supersession handle |
| `vct` | yes | `agstack.org/credentials/green-guarantee/v1` |
| `beneficiary` | yes | Hub account id of the lender |
| `guarantee.request_ref` | yes | The credit request this backs (issuer's reference) |
| `guarantee.amount`, `guarantee.currency` | yes | Loan principal guaranteed against; ISO 4217 code |
| `guarantee.coverage_ratio` | yes | Share of the amount covered, in (0, 1] |
| `guarantee.state` | yes | `"PRE_APPROVED"` or `"ISSUED"` |
| `guarantee.supersedes` | no | `jti` of the credential this one replaces (PRE_APPROVED → ISSUED). The superseded credential is revoked in the same transaction |
| `risk.risk_class` | yes | `"low"`, `"high"` or `"more_info_needed"` — the screen's three-valued class |
| `risk.rule_set_version` | yes | The `rule_set.version` string of the screen the class was read from (e.g. `eudr-perennial-crop/2026.09.15`) |
| `risk.evidence` | yes (may be empty) | BITE ids of the screen record(s) the decision rests on |
| `odrl` | yes | ODRL 2.2 `Agreement`: permission `use` by the beneficiary for purpose `credit-guarantee` on event `request_ref` until `exp`; prohibition `distribute` |
| `status` | yes | StatusList2021 reference, shared bitstring with grants |

No claim is selectively disclosable: a guarantee is shown whole or not at all.

## 10. State machine

```
            issue(state=PRE_APPROVED)              issue(state=ISSUED, supersedes=jti₁)
  (none) ───────────────────────────► PRE_APPROVED ─────────────────────────────────► ISSUED
                                          │                                              │
                                          │ revoke(reason)                               │ revoke(reason)
                                          ▼                                              ▼
                                       REVOKED                                        REVOKED
```

- `issue(state=ISSUED)` without `supersedes` is permitted (a single-step life).
- `supersedes` must name this issuer's active credential for the **same** `request_ref` and `sub`; otherwise `409`.
- ISSUED → PRE_APPROVED is refused (`409`).
- At any moment exactly one active guarantee stands for a request.

## 11. MEAL events

Written to the MEAL keyed by `sub`, `meal_type = guarantee_lifecycle`: `guarantee.pre_approved`, `guarantee.issued`, `guarantee.retrieved` (each lender retrieval), `guarantee.revoked` (with `reason`; a supersession writes one with reason `superseded by <jti>`).

## 12. Verifier rules

Rules 1–4 of §6 apply unchanged (signature, expiry, issuer, status bit). Rule 5 becomes: `vct` **must** equal `agstack.org/credentials/green-guarantee/v1`. There are no disclosures to check.
