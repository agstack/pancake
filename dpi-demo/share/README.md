# `share/` — the mirrored raster stores, when they are local

This directory is the default bind mount for `TERRAPIPE_SHARE` in the
`openscience` compose profile. It exists so that profile comes up on a machine
with no mirror attached: Docker creates a missing bind-mount source as a
root-owned directory, which then fails to read and looks like a permissions
problem rather than an absent mirror.

Empty is a valid state. The node starts, and every layer whose store is missing
reports `not_mirrored` rather than zero — so a screen over an empty share is
inconclusive, never "no deforestation found". That distinction is the whole
point of bringing it up empty, and it is worth seeing once before the data
lands.

To point at a real mirror instead, set the variable rather than copying data
here:

    TERRAPIPE_SHARE=/mnt/md0 docker compose --profile openscience up

The stores this expects, and the layer that declares each path, are in
`terrapipe-os/layers/layers.json`. A store built anywhere else is invisible to
the node however correct it is.
