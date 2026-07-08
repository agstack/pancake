# Sprint 4: Data Wallets & Chain of Custody — SUPERSEDED AND SHIPPED

**An AgStack Project | Powered by The Linux Foundation**

**Status:** Superseded (July 2026). The original plan on this page proposed Hyperledger Indy/Aries.
That design was **not built**. The shipped implementation uses a lighter, EU-dataspace-aligned stack.
This page now documents what actually exists and where.

---

## What shipped instead of Indy/Aries

| Original proposal | Shipped design | Why the change |
|---|---|---|
| Hyperledger Indy ledger + DIDs | `did:web` issuer identifiers, hub-accredited issuer registry | No blockchain to operate; trust anchors in the AR hub, which already exists |
| Aries agents + AnonCreds | **SD-JWT VC** (IETF `draft-ietf-oauth-sd-jwt-vc`), Ed25519 signatures | Selective disclosure without ZK infrastructure; plain JWT tooling verifies it |
| Smart-contract unlock | **StatusList2021** revocation bitstring + expiry claims | Revocation is a bit flip published over HTTPS, verifiable offline |
| Wallet-required access | **DPI-account delivery**: grantee authenticates with their hub account and retrieves credentials via API (`GET /grants/received`); wallet holder-binding (`cnf`) is an optional layer for TraceFoodChain | Wallet-less users are first-class; no OTP flows |
| Chain of custody "on chain" | **MEAL ledger**: SHA-256 hash-chained, Ed25519-signed audit packets, per-ListID, with an audit API | Same tamper-evidence, no consensus overhead |

## Where the implementation lives

- Credential format (normative): [`services/specs/CREDENTIAL_PROFILE.md`](../services/specs/CREDENTIAL_PROFILE.md)
- FieldList ListID construction (normative): [`services/specs/MERKLE_LISTID.md`](../services/specs/MERKLE_LISTID.md)
- Service code: [`services/pancake_services/`](../services/) — grants, TAP runtime, BITE store
- Service documentation and deployment guide: [`services/README.md`](../services/README.md)
- Quality harness and findings: [`.audit/`](../.audit/README.md)

## What this enables (unchanged goals)

- **EUDR compliance**: a grant credential + selectively disclosed GeoIDs + ODRL policy is the
  due-diligence artifact an EU buyer presents; the audit API produces the provenance report.
- **Food safety / certification**: same credential rail, different `purpose` and credential types.
- **Chain of custody**: every fieldlist/grant lifecycle event is a signed MEAL packet.
