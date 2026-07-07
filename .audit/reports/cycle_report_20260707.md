# FATFD Cycle Report — 2026-07-07 (C0 through C7)

**Branch:** `feat/dpi-production-hardening` · **Version:** 0.1.0 → 1.0.0

## Summary

Pancake went from POC (loose scripts, no service, no auth, unverifiable MEAL chains) to a
tested DPI service in seven FATFD cycles executed back-to-back:

| Cycle | Delivered | Tests after |
|---|---|---|
| C0 | Harness: validator (A–E), guardrails, knowledge base, pre-commit hook | 0 |
| C1 | CREDENTIAL_PROFILE.md + MERKLE_LISTID.md (normative), merkle/sdjwt/statuslist/issuer modules, 5-credential test-issuer kit | 43 |
| C2 | FastAPI grants service, hub-delegated RS256/JWKS auth, ORM models | 51 |
| C3 | FieldLists (Merkle ListIDs), grant issue/receive/revoke/verify, public status list | 71 |
| C4 | Signed MEAL ledger (Ed25519 + hash chain), OpenScience audit API, legacy meal.py fixes | 83 |
| C5 | TAP runtime: scheduler, executor, retry policy, env-interpolated config, frozen ingest interface | 91 |
| C6 | BITE store: dedupe, validation, GeoID/type/time queries, /bites API, end-to-end runtime→store test | 99 |
| C7 | Docker/compose packaging, .env.example, CI rewrite, sprint-4 doc rewrite, OpenAPI export, e2e demo script | 99 |

## Verification evidence

- `pytest services/tests` — 95 passed; `pytest tests` — 4 passed, 1 skipped (legacy POC intake suite skips by design).
- `ruff check services` — clean.
- `python .audit/validate_fatfd.py` — checks A–E pass.
- `services/demo/end_to_end_demo.py` — issue → retrieve (DPI account) → verify → revoke → audit, all assertions green.
- `services/export_openapi.py` — 15 API paths exported.

## Findings ledger

- PC-2026-0001 (high) MEAL signatures/linkage — **fixed** (mealstore + legacy fixes).
- PC-2026-0002 (critical) no service/auth layer — **fixed** (grants service).
- PC-2026-0003 (medium) Sprint-4 Indy/Aries doc drift — **fixed** (rewritten).
- PC-2026-0004 (high) legacy MEAL hash-order bug, verify_chain never passable — **fixed** + regression tests.
- PC-2026-0005 (medium) issuer key custody env-var interim — **learned**; vault/KMS is a production gate.

## Deferred by design

- pgvector/RAG columns on the BITE store (no RAG this sprint).
- TerraPipe vendor adapters (separate workstream; frozen ingest interface published).
- Wallet holder-binding (`cnf`) for TraceFoodChain presentation flows (credential profile already reserves the claim).
- OTP-to-VC bridge: intentionally not built (DPI-account delivery decision); flagged for grant-owner confirmation.
