# Pancake Services

Production services for the AgStack DPI: **field ownership + permission grants**, the **TAP
vendor-data runtime**, and the **BITE store**. Built July 2026 under the FATFD quality harness
(see [`.audit/README.md`](../.audit/README.md)).

## What each piece does

| Component | Role |
|---|---|
| `pancake_services/grants` | FieldLists ("my fields" as Merkle ListIDs), SD-JWT VC grant issuance/retrieval/revocation, StatusList2021 revocation, signed MEAL audit ledger, audit API |
| `pancake_services/tap` | Vendor-data runtime: adapter interface, per-vendor scheduler, retry policy, `${VAR}` config interpolation |
| `pancake_services/store` | BITE persistence with content-hash dedupe and GeoID/type/time querying |
| `services/specs` | Normative specs: [CREDENTIAL_PROFILE.md](specs/CREDENTIAL_PROFILE.md), [MERKLE_LISTID.md](specs/MERKLE_LISTID.md) |

Architecture invariants (enforced, see [`../.audit/GUARDRAILS.md`](../.audit/GUARDRAILS.md)): AR nodes
and the AR hub never store ownership; Pancake never stores geometry; permissions travel as
credentials, not database rows.

## API surface

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /healthz`, `GET /healthz/me` | none / hub token | liveness; auth smoke check |
| `POST /fieldlists`, `GET /fieldlists[/{list_id}]` | hub token | create/list owner's fieldlists (idempotent by Merkle construction) |
| `GET /fieldlists/{list_id}/proof/{geoid}` | hub token | Merkle inclusion proof |
| `POST /grants/issue` | hub token (owner) | issue SD-JWT VC grant to a hub account |
| `GET /grants/received` | hub token (grantee) | DPI-account credential delivery (no OTP) |
| `GET /grants/issued` | hub token (owner) | grants I issued |
| `POST /grants/revoke` | hub token (issuer) | revoke: bit + audit packet recorded before success; hub report when `HUB_URL` set |
| `GET /grants/status-list` | none | public revocation bitstring |
| `POST /grants/verify` | none | relying-party verification (signature, expiry, revocation, disclosures) |
| `GET /audit/{geoid}[,/report]` | hub token | per-GeoID provenance; compliance report with chain-integrity results |
| `GET /audit/meals/{meal_id}/verify` | hub token | hash-chain + signature verification |
| `GET /bites` | hub token | query ingested vendor data by GeoID/type/vendor/time |

Machine-readable spec: `python export_openapi.py` writes `openapi.json`.

## Authentication model

The AR hub is the trust anchor. Clients present the hub's **RS256 access tokens**; this service
verifies them against the hub JWKS (`HUB_JWKS_URL`, cached 5 min), rejects non-access tokens, and
mirrors accounts locally on first sight. There are no local passwords and no OTP.

## Configuration (environment variables)

| Variable | Required | Meaning |
|---|---|---|
| `PANCAKE_ISSUER_KEY` | **yes** | Ed25519 signing key (PEM or base64url 32-byte seed). Service refuses to start without it. Generate: `python -m pancake_services.grants.testkit.mint_test_credentials --keygen`. Interim custody: env var now, vault/KMS before production (finding PC-2026-0005) |
| `DATABASE_URL` | no | default `sqlite:///pancake_dev.db`; use Postgres in staging/prod |
| `HUB_JWKS_URL` | no | hub JWKS endpoint (default `http://localhost:8000/.well-known/jwks.json`) |
| `HUB_URL` | no | when set, revocations are reported to `{HUB_URL}/revocations` |
| `STATUS_LIST_URI` | no | public URI embedded in credentials' `status` claim |
| `PANCAKE_ISSUER_ID` / `PANCAKE_ISSUER_KID` | no | `did:web:pancake.agstack.org` / `pancake-issuer-1` |
| `STATUS_LIST_INDEX_START` / `STATUS_LIST_SIZE` | no | hub-allocated revocation index range (default 0 / 65536) |
| `TERRAPIPE_SECRET`, `TERRAPIPE_CLIENT`, ... | per vendor | TAP vendor credentials, referenced from the vendor YAML as `${VAR}` |

## Running locally

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r services/requirements.txt
export PANCAKE_ISSUER_KEY=$( .venv/bin/python -m pancake_services.grants.testkit.mint_test_credentials --keygen )  # run from services/
cd services
../.venv/bin/uvicorn "pancake_services.grants.app:create_app" --factory --port 8100
```

## Running with Docker Compose (Postgres)

```bash
cd services
cp .env.example .env          # fill in PANCAKE_ISSUER_KEY (and vendor creds if using TAP)
docker compose up --build
# service on :8100, postgres on :5433
```

## Tests

```bash
# Full suite (99 tests) + lint
.venv/bin/python -m pytest services/tests tests -q
.venv/bin/ruff check services/pancake_services services/tests
# End-to-end demo (issue -> retrieve -> verify -> revoke -> audit), in-process:
cd services && ../.venv/bin/python demo/end_to_end_demo.py
```

Tests are written before code for every endpoint (guardrail 8) and the count never decreases
(validator check D). The five relying-party test credentials (valid / expired / revoked /
tampered / wrong-geoid) are minted by
`python -m pancake_services.grants.testkit.mint_test_credentials`.

## TAP: adding a vendor adapter

1. Subclass `pancake_services.tap.adapter_base.TAPAdapter` (three methods:
   `get_vendor_data`, `transform_to_sirup`, `sirup_to_bite`).
2. Add the vendor to your YAML config with `adapter_class`, `sirup_types`, credentials as
   `${ENV_VARS}`, and a `schedule` block (`interval_seconds` + `tasks`).
3. The runtime owns retries (exponential backoff); return `None` on failure — never retry inside
   the adapter.
4. Test with recorded fixtures so CI runs without vendor credentials.

The ingest contract is frozen: `sink(bite: dict) -> None`; the production sink is
`BiteStore.save`, which dedupes by content hash.

## Deployment guide (clean machine to running demo)

1. Install Docker (or Python 3.10+ for the uvicorn path).
2. `git clone https://github.com/agstack/pancake && cd pancake/services`.
3. `cp .env.example .env`; generate `PANCAKE_ISSUER_KEY` (command above); set `HUB_JWKS_URL` to
   your AR hub.
4. `docker compose up --build`.
5. Smoke: `curl localhost:8100/healthz` returns `{"status":"ok"...}`;
   `curl localhost:8100/grants/status-list` returns the revocation bitstring.
6. Point your AR node's grant verifier at `POST /grants/verify` (or embed
   `pancake_services.grants.sdjwt` + the public status list for offline verification).
