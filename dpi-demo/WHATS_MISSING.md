# What's missing for a world-class DPI discussion

This demo is deliberately honest. It stitches together real components (AR2
GeoID, Pancake grants + BITE store + TAP runtime, agstack-pnd models, MCP) into
one runnable story. But "runnable demo" is not "production DPI." Below is the gap
list, roughly in priority order, so a serious discussion starts from reality
rather than a happy path.

## 1. Weather is synthesized, not truly hourly

- **Now:** TerraPipe's deployed endpoint returns daily/coarse GFS stats; we
  synthesize hourly (sinusoidal diurnal cycle) exactly like the NOAA provider,
  and mark every BITE `resolution: hourly-synthesized-from-daily`. Offline, the
  `seed` adapter generates deterministic weather.
- **Needed:** a real TerraPipe **TP-1 hourly** API (and/or ERA5-Land, station
  networks) so disease models that depend on genuine leaf-wetness and overnight
  RH dynamics get real inputs, not a smooth curve. The adapter is structured so
  only `_to_daily_records`/one method changes when that ships.

## 2. Registry trust is pinned, not native

- **Now:** grant verification needs an RS256 hub with `/.well-known/jwks.json`.
  The demo pins `ar2`/`ar2-hub` at `v0.9-review`; older local checkouts used
  HS256 and had no JWKS. The hub/node run from best-effort generic Dockerfiles.
- **Needed:** first-class, versioned container images for the hub and node with a
  documented, stable trust bootstrap; automated key rotation; and a conformance
  test that a node correctly rejects revoked/expired grants end to end.

## 3. Field nesting / child roll-up is a stub

- **Now:** `/aggregate` de-duplicates an explicit GeoID set correctly. A
  `parent_geo_id` is expanded via a `/geoid/{id}/children` call that most nodes
  don't implement yet, so today the parent alone is used.
- **Needed:** the AR2 `child_of` relationship exposed over the node API, plus a
  defined roll-up contract (does a parent's stat include children? how are
  partial overlaps handled?). This is where AR2's identity model must be pinned
  down precisely, because population statistics depend on it.

## 4. Cross-vendor / cross-namespace identity

- **Now:** everything assumes one GeoID regime (AgStack S2-cover). A field known
  to FAO (UUIDv7) or a vendor's own key is not reconciled.
- **Needed:** a hub-level cross-reference service that maps foreign namespaces to
  the canonical GeoID (recompute-or-alias at registration), so a consumer can
  merge two vendors' data for "the same field" without manual joins. This is the
  single biggest interoperability question for a real DPI.

## 5. Consent model is minimal

- **Now:** owner-issued SD-JWT grants; optional flag gate on weather BITE reads;
  revocation via a status list. Grantee identity in the demo is simplified.
- **Needed:** purpose-binding actually enforced per query, masking levels (L0/L1)
  honored consistently across *every* read path, delegation/expiry UX, and an
  audit trail a regulator would accept.

## 6. Provenance and reproducibility of results

- **Now:** risk is published as a `pest_disease` BITE with a content hash and the
  model uuid/version and weather source in metadata.
- **Needed:** a full provenance chain (which exact weather BITEs -> which model
  build -> which result), signed results, and the ability to *re-run* a historical
  forecast bit-for-bit. OpenScience credibility lives or dies here.

## 7. Model governance

- **Now:** any pip wheel with the right entry point is discovered and served.
- **Needed:** model signing/attestation, a review/curation lane for published
  models, versioned model catalogs, and clear semantics for competing models on
  the same crop-threat (how does a consumer choose, and how is that recorded?).

## 8. Operational hardening

- **Now:** single-node docker-compose, SQLite/Postgres, no scheduler in the
  grants app, in-process TAP worker, no metrics/alerting, secrets via `.env`.
- **Needed:** horizontal scaling, a real job scheduler for TAP, backpressure and
  dead-letter handling on ingestion, observability, and a secrets story beyond a
  local file.

## 9. Data licensing and economics

- **Not addressed at all.** Who may read whose weather/risk, under what license,
  and how vendors are compensated when their data or model is used. A DPI needs
  an answer even if the answer is "out of scope, handled by policy layer X."

---

**Bottom line for the discussion:** the *shape* is right and demonstrable today —
identity, consent, a governed data plane, published open models, and de-duplicated
aggregation. The credibility gaps are (in order) **real hourly weather**,
**native registry trust + nesting**, **cross-namespace identity**, and
**signed, reproducible provenance**. Those four are what separate a compelling
demo from infrastructure a ministry of agriculture could adopt.
