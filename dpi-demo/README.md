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

### `openscience`: the terrapipe-os node

Adds a [terrapipe-os](https://github.com/sumerjohal/terrapipe-os) node on port
8200, which answers a deforestation screen, an NDVI series and a GFS forecast
for a GeoID from mirrored public data. This is the EUDR path, and it needs no
Earth Engine account and no FAO credentials.

```bash
docker compose --profile core --profile registry --profile openscience up --build
```

Two things to know before running it.

**It needs the mirror mounted, and says so when it is not.** Point
`TERRAPIPE_SHARE` and `TERRAPIPE_NETWORK` at the ingested stores. Bring it up
without them and the node still starts and still answers: every layer reports
`not_mirrored` rather than a zero, which is a useful way to see the shape of a
screen before the rasters land. It is not a clean bill of health, and no BITE
it produces can be mistaken for one.

**The screen is field-scoped only with a grant.** Pancake issues those. Without
one the node answers about the neighbourhood cell rather than the field, and
every BITE records which it was, so the demo is meaningful before any grant
exists and sharper once one does. Set `PANCAKE_GRANT_<geoid>` on the TAP worker
to hand it a grant for a specific field.

**terrapipe-os is private.** `make clone-deps` tries to clone it and carries on
when it cannot, saying so. `make demo`, `make core` and `make up` are
unaffected; only `make openscience` and the deforestation, NDVI and GFS half of
the notebook need it, and those cells report `SKIPPED` with that reason rather
than failing. Everything the notebook needs *before* it reaches a service —
including the four demo fields — is vendored here.

**Two surfaces, two services.** `terrapipe-os` on 8200 is the HTTP node;
`terrapipe-os-mcp` on 8201 is the same handlers over MCP, for agents. They are
separate services because they authenticate differently and should be able to
fail independently: the MCP one advertises itself as an OAuth resource and
refuses to start over HTTP without `TERRAPIPE_OS_MCP_URL`, rather than serving
unauthenticated.

**The mounts default to directories in this repo.** `share/` and `network/`
exist and are empty, because Docker creates a missing bind-mount source as a
root-owned directory — which then fails to read and looks like a permissions
problem rather than an absent mirror. Each has a README saying what belongs
there. Set the variables rather than copying data in:

```bash
TERRAPIPE_SHARE=/mnt/md0 TERRAPIPE_NETWORK=/network make openscience
```

### The notebook

[`openscience_dpi_demo.ipynb`](openscience_dpi_demo.ipynb) walks the EUDR path
end to end for four Honduran fields: boundary to GeoID, consent, screen, BITE,
and a DDS-ready GeoJSON out the other side. It is meant to be *read* as much as
run, so its committed output is from a real execution.

Two files rather than one, deliberately:

- `build_openscience_notebook.py` is the source. Prose and code sit together in
  one reviewable Python file, instead of a JSON diff full of escaped newlines.
- `openscience_dpi_demo.ipynb` is generated from it, with
  `python build_openscience_notebook.py --run`.

Edit the builder, not the notebook. **Never hand-edit the committed output** —
its whole value is that it records what actually happened.

Every step prints `LIVE` (ran against the stack), `LOCAL` (stack down, but the
mirrored rasters were read in process), `SKIPPED` or `FAILED`, and the last cell
prints a ledger of all of them. Nothing invents a reading to keep the narrative
moving, so the skipped lines are an honest list of what a given run did not
demonstrate. `make openscience` closes most of them.

To execute it headless: `make notebook-openscience`, which regenerates it from
the builder first so a committed notebook that has drifted cannot be what gets
run. It passes `--allow-errors` on purpose — a cell that cannot reach a service
marks itself `SKIPPED` and the run continues, because aborting on the first
unreachable service would leave the ledger unwritten, and the ledger is the only
honest summary of what a run demonstrated.

Measured on 2026-09-02, with nothing running: 0 cells raise, 3 steps run against
local data, 9 skip. With `TERRAPIPE_SHARE` pointed at two ingested layers:
9 local, 3 skipped, still 0 raising, and all four field verdicts match what the
field placer recorded independently from the same stores.

A note on how the calls are checked. Three of the notebook's calls were wrong
until 2026-09-02 — a GeoJSON geometry posted where AR2 takes WKT, a GeoID read
from `geo_id` where AR2 returns `Geo Id`, and a `POST /grants` that Pancake does
not serve. None of them raised visibly: the step recorder caught each failure
and printed `SKIPPED`, which reads as "the stack was not up". So
`services/tests/test_notebook_routes.py` now extracts every URL the notebook
builds and checks it against the routes those services actually declare.

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
