"""The demo fields are readable from this repository alone, and have not drifted.

``terrapipe-os`` is private; ``pancake`` is not. The open-science notebook is
the artefact an outside reviewer is asked to read, so anything it needs before
it can reach a service has to live here. Until 2026-09-02 the four demo fields
were resolved out of ``terrapipe-os/examples``, which meant a reviewer without
access to that repository could not get past the notebook's opening section --
the one part that needs no services at all.

So the file is vendored, and preferred even when terrapipe-os is present, so
that the demo behaves the same for someone who has both repositories and
someone who has one. The cost of a vendored copy is that it can go stale, which
is what the drift test below is for.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PANCAKE = Path(__file__).resolve().parents[2]
DEMO = PANCAKE / "dpi-demo"
VENDORED = DEMO / "honduras_demo_fields.geojson"
UPSTREAM = PANCAKE.parent / "terrapipe-os" / "examples" / "honduras_demo_fields.geojson"


@pytest.fixture(scope="module")
def vendored() -> dict:
    return json.loads(VENDORED.read_text(encoding="utf-8"))


def test_the_fields_are_in_this_repository() -> None:
    assert VENDORED.is_file(), (
        "the demo fields are not vendored, so the notebook cannot list them without "
        "access to the private terrapipe-os repository"
    )


def test_there_are_four_fields_and_each_says_it_is_synthetic(vendored) -> None:
    """The boundaries are S2 cells. A reader must not take them for surveyed farms."""
    features = vendored["features"]

    assert len(features) == 4
    for feature in features:
        properties = feature["properties"]
        assert properties["name"]
        assert properties["s2_token"], "the cover shortcut depends on each field being an S2 cell"
        assert "synthetic" in properties["boundary"].lower()


def test_the_placement_records_what_it_was_computed_from(vendored) -> None:
    """Where the fields are is not synthetic, and the file has to show why."""
    provenance = vendored["properties"]

    assert provenance["placed_from"], "no record of which stores these were chosen against"
    assert provenance["candidates_examined"] > 0
    assert provenance["cutoff_year"] == 2020


def test_the_expected_values_came_from_the_stores_rather_than_being_asserted(vendored) -> None:
    """These are what the notebook compares a live screen against.

    If they were hand-written, the comparison would be checking the demo against
    its own author rather than against the public data.
    """
    assert "computed from the stores" in vendored["properties"]["note"]
    for feature in vendored["features"]:
        assert "expected" in feature["properties"]


def test_the_notebook_prefers_the_vendored_copy() -> None:
    """Otherwise the demo behaves differently for someone who has both repos."""
    source = (DEMO / "openscience_demo.py").read_text(encoding="utf-8")
    vendored_at = source.index("_VENDORED_FIELDS if")
    upstream_at = source.index("else _UPSTREAM_FIELDS")

    assert vendored_at < upstream_at


@pytest.mark.skipif(not UPSTREAM.is_file(), reason="terrapipe-os is not cloned beside pancake")
def test_the_vendored_copy_has_not_drifted_from_the_one_it_was_copied_from() -> None:
    """The standing cost of vendoring, paid here rather than discovered later.

    A stale copy is worse than no copy: the notebook would screen fields chosen
    against a different set of rasters and compare them to expectations from
    that other run, and every number would look plausible.
    """
    mine = json.loads(VENDORED.read_text(encoding="utf-8"))
    theirs = json.loads(UPSTREAM.read_text(encoding="utf-8"))

    assert mine == theirs, (
        "dpi-demo/honduras_demo_fields.geojson differs from terrapipe-os/examples. "
        "Re-copy it after running bin/place-demo-fields."
    )
