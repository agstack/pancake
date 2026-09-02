# `network/` — the existing TerraPipe stores, when they are local

Default bind mount for `TERRAPIPE_NETWORK` in the `openscience` profile, and
empty here for the same reason as `share/`: a missing bind-mount source becomes
a root-owned directory, which reads as a permissions fault rather than as an
absent mirror.

This one holds the stores TerraPipe already maintains rather than any this
repository builds — Sentinel-2 NDVI under `SENTINEL/`, and the GFS forecast
store. Both are written by a pipeline outside these repositories, which is why
`terrapipe-os` mounts them read-only and pins their schema in
`terrapipe-os/tests/test_ndvi_schema.py` instead of assuming it.

    TERRAPIPE_NETWORK=/network docker compose --profile openscience up
