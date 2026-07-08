# Pancake Guardrails

Human-owned invariants. The system may NEVER modify this file without explicit human approval.

## Architecture invariants

1. **The AR node never stores ownership.** Nodes verify presented grant credentials; they do not keep grantee lists.
2. **The AR hub never stores field ownership or "my fields" lists.** The hub is the trust anchor (accounts, issuer accreditation, revocation registry) — not the ownership ledger.
3. **Pancake never stores field geometry** beyond GeoID list membership. Geometry lives in AR nodes.
4. **Permissions travel as credentials, not database rows.** Any relying party (TerraPipe included) verifies a presented credential; no service holds another service's ACLs.
5. **GeoIDs are the only spatial join key** across services.

## Credential-security checklist (applied at every Phase 2.5 review)

1. The issuer private key is never logged, serialized into responses, or committed.
2. Every issuance path requires an authenticated owner.
3. Every credential has an expiry (`exp`) set.
4. Revocation is recorded before the revoke API returns success.
5. No endpoint returns another user's fieldlists or grants.
6. SQL is always parameterized (ORM or bound parameters only).
7. Vendor credentials (TAP) come from environment variables only.

## Process invariants

8. Tests are written before code for every new endpoint.
9. Test count never decreases (zero-regression rule, enforced by validator check D).
10. No direct commits to main; every cycle lands via a feature branch.
