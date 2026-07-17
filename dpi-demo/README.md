# PnD DPI OpenScience Demo

A one-command local stack that shows the AgStack DPI end to end for pest & disease:

```
register a field -> GeoID -> owner grant -> TerraPipe weather ingested as BITEs
   -> agstack-pnd runs a disease forecast off those BITEs -> publishes risk BITEs
   -> aggregate across distinct fields -> call it all from an MCP tool
```

This directory is the **orchestration glue**. The moving parts live in their own repos:

| Service | Repo | Port | Role |
|---|---|---|---|
| AR2 Hub | `agstack/ar2-hub` | 8000 | Identity anchor (RS256 JWT + JWKS), gateway |
| AR2 Node | `agstack/ar2` | 8001 | Holds geometry, verifies grants, register-field |
| Pancake Grants | `agstack/pancake` (this repo) | 8100 | FieldLists, grants, BITE store, `/bites` |
| Pancake TAP worker | `agstack/pancake` (this repo) | - | Ingests TerraPipe weather -> BITE store |
| agstack-pnd | `agstack/opensource-pestmodels` | 8080 | Disease forecast off BITEs; publishes risk BITEs; MCP |

## Design decisions (locked)

- **BITE-native weather**: PnD never calls a weather API directly. Pancake's TAP runtime
  ingests TerraPipe into the BITE store; PnD reads weather BITEs by GeoID. This is the
  DPI data-plane in miniature.
- **Local reproducible**: docker-compose + an executable notebook. No public hosting.
- **Always runnable**: if `TERRAPIPE_*` credentials are absent, the TAP worker uses the
  built-in `seed` adapter to write canned-but-realistic weather BITEs, so the demo runs
  offline. See [tap_vendors.yaml](tap_vendors.yaml).

## Quick start

```bash
# from this directory
make demo
```

`make demo` will:
1. Clone/checkout `ar2` and `ar2-hub` at tag `v0.9-review` as siblings of this repo (if missing).
2. Generate a Pancake issuer keypair and write `.env` from `.env.example` (if missing).
3. `docker compose up --build`.

Then run the walkthrough:

```bash
make notebook     # executes pnd_dpi_demo.ipynb headless
# or open pnd_dpi_demo.ipynb interactively
```

## Profiles

The registry services (hub, node) are external repos. If you only want the parts that
live in the Pancake + PnD repos (grants, TAP -> BITE, PnD forecast off seeded weather),
bring up just the `core` profile:

```bash
docker compose --profile core up --build
```

Bring up everything (requires the `ar2` / `ar2-hub` clones):

```bash
docker compose --profile core --profile registry up --build
```

## Version pinning (important)

The demo was validated against AR hub/node tag **`v0.9-review`** (RS256 hub tokens +
`/.well-known/jwks.json`). Older local checkouts of `ar2-hub` used HS256 and lacked JWKS;
grant verification will fail against those. `make clone-deps` checks out the right tag.

## What is real vs. synthesized

- Field registration, GeoID, owner grant, BITE store, `/bites`, TAP runtime: **real code**.
- TerraPipe hourly weather: the deployed TP-1 hourly API does not exist yet. The demo uses
  either legacy `getGFSStats` (daily GFS -> hourly synthesized, like the NOAA provider) or
  the offline `seed` adapter. The synthesis is marked in every BITE's `metadata.resolution`.

See [WHATS_MISSING.md](WHATS_MISSING.md) for the honest gap list and roadmap.
