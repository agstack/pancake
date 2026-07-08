# AgStack Field-Access Grant — Credential Profile

**Status:** v1.0 (normative) · **Format:** SD-JWT VC (IETF `draft-ietf-oauth-sd-jwt-vc`) · **Signature:** Ed25519 (`EdDSA`)
**Reference implementation:** `services/pancake_services/grants/sdjwt.py` · **Revocation:** StatusList2021 bitstring (`services/pancake_services/grants/statuslist.py`)

## 1. What this credential says

"The holder identified below has been granted **read access at masking level L1** (full geometry) to the fields in FieldList `<ListID>`, for purpose `<purpose>`, until `<exp>` — signed by an issuer the AgStack hub accredits."

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
| `masking_level` | yes | Access level granted: `"L1"` (full geometry). Future: `"L2"` (centroid+area) |
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
