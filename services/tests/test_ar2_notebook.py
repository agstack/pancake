"""Checks on the AR2 field-identity notebook.

The notebook makes four claims that a reader cannot verify by reading it: that
the name is computed from the geometry rather than handed down, that redrawing
a boundary keeps one name, that a different field gets its own, and that a name
alone discloses nothing. Each is easy to appear to demonstrate while
demonstrating nothing, which is what these are for.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

DEMO = pathlib.Path(__file__).resolve().parents[2] / "dpi-demo"
BUILDER = DEMO / "build_ar2_notebook.py"


def _module():
    """The support module, loaded fresh.

    Imported by path rather than by name so the test does not depend on the
    notebook's sys.path juggling having already happened.
    """
    if str(DEMO) not in sys.path:
        sys.path.insert(0, str(DEMO))
    name = "ar2_demo_under_test"
    spec = importlib.util.spec_from_file_location(name, DEMO / "ar2_demo.py")
    module = importlib.util.module_from_spec(spec)
    # Registered before exec, because @dataclass resolves a class's annotations
    # through sys.modules[cls.__module__]. Without this every dataclass in the
    # module raises AttributeError on None during import.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _body_of(name: str) -> str:
    source = (DEMO / "ar2_demo.py").read_text()
    start = source.index(f"def {name}(")
    rest = source[start:]
    following = re.search(r"\n(?:def |class |@dataclass\n)", rest)
    body = rest[: following.start()] if following else rest
    assert body.strip(), f"no body found for {name}"
    return body


# A stand-in for a real parcel: irregular, and noticeably smaller than its own
# bounding box. A square is a bad fixture here and quietly weakened two checks
# -- its bounding box *is* the field, so the L-shaped control overlapped it 75%
# rather than the 48% measured on real geometry, and with five vertices every
# perturbation is a large fraction of the whole shape.
PARCEL = [
    [5.000, 52.000], [5.004, 52.0005], [5.008, 52.001], [5.010, 52.004],
    [5.0095, 52.007], [5.006, 52.0085], [5.002, 52.009], [5.0005, 52.006],
    [5.000, 52.003], [5.000, 52.000],
]


# --------------------------------------------------------------------------
# The parcels
# --------------------------------------------------------------------------


def test_the_parcel_source_is_named_with_its_licence() -> None:
    """A demo that leans on somebody's data says whose and under what terms."""
    ar = _module()

    assert "pdok.nl" in ar.BRP_WFS
    assert "CC0" in ar.BRP_LICENCE
    assert "RVO" in ar.BRP_CREDIT or "PDOK" in ar.BRP_CREDIT


def test_the_bounding_box_is_latitude_first() -> None:
    """WFS 2.0 with a URN CRS uses the axis order EPSG:4326 declares.

    Longitude first returns HTTP 200 with zero features, which is
    indistinguishable from an empty area. That happened on the first attempt.
    """
    body = _body_of("parcels")
    assert "{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}" in body
    assert "urn:ogc:def:crs:EPSG::4326" in body

    south, west, north, east = _module().BRP_BBOX

    # Against the Netherlands specifically, not against the legal range of a
    # coordinate. Both orderings of this box are legal lat/lon pairs -- 5.55 is
    # a valid latitude and 52.45 a valid longitude -- so a range check passes
    # either way round and proved nothing. The Netherlands sits near 52 N, 5 E,
    # and those two do not overlap.
    assert 50 < south < north < 54, (  # noqa: PLR2004
        f"({south}, {north}) is not a Dutch latitude range; the axes look swapped"
    )
    assert 3 < west < east < 8, (  # noqa: PLR2004
        f"({west}, {east}) is not a Dutch longitude range; the axes look swapped"
    )


def test_an_empty_answer_is_not_reported_as_an_empty_area() -> None:
    """The failure that looks exactly like a true negative."""
    body = _body_of("parcels")
    assert "axes" in body, (
        "an empty result is passed through without mentioning the axis-order trap"
    )


def test_only_actual_fields_are_offered() -> None:
    """The register returns ditches and margins beside the fields."""
    ar = _module()
    assert ar.WORKED == "Bouwland"
    assert "category" in _body_of("parcels")


# --------------------------------------------------------------------------
# The name
# --------------------------------------------------------------------------


def test_the_local_derivation_never_falls_back_to_the_node() -> None:
    """The claim is that the name needs no node. A fallback would void it."""
    body = _body_of("computed_here")

    assert "geoid_v2" in body
    assert "requests" not in body and "NODE_URL" not in body, (
        "the local derivation can reach the node, so agreement proves nothing"
    )
    assert "return None" in body, "an unavailable derivation is not reported as unavailable"


def test_the_name_is_read_from_the_key_ar2_actually_uses() -> None:
    """AR2 answers with "Geo Id". Reading geo_id gets None on every path.

    Two Nones compare equal, so on 2026-09-07 a newly registered field appeared
    to have resolved to the original's name.
    """
    body = _body_of("name_of")
    assert '"Geo Id"' in body
    assert 'body.get("geo_id")' not in body


def test_a_verdict_is_read_from_the_identifier_not_the_wording() -> None:
    """The node says "already registered" for two opposite outcomes.

    A redrawing recognised as the original, and a genuinely different field it
    happens to have seen before, produce the same message and different names.
    """
    ar = _module()
    original = ar.Naming("aaa111", "Field Boundary registered successfully.", 200)

    same = ar.Naming("aaa111", "Exact geometry already registered.", 200)
    other = ar.Naming("bbb222", "Exact geometry already registered.", 200)

    assert "same field" in ar._verdict_on(original, same)
    assert "own name" in ar._verdict_on(original, other), (
        "a distinct field is being described as one the node already knows"
    )


def test_a_redrawing_that_split_is_called_out() -> None:
    """The prose says near-identical redrawings keep one name. Check it."""
    ar = _module()
    original = ar.Naming("aaa111", "registered successfully", 200)
    redrawing = ar.Redrawing("one vertex out", [], "a GPS wobble", 0.976, same_ground=True)

    notes = ar._where_naming_disagrees_with_overlap(
        original, [(redrawing, ar.Naming("ccc333", "registered successfully", 200))]
    )
    assert any("split identity" in n for n in notes)


def test_a_collision_is_called_out_more_loudly_than_a_split() -> None:
    """Two different fields under one name is the worse failure."""
    ar = _module()
    original = ar.Naming("aaa111", "registered successfully", 200)
    different = ar.Redrawing("a different field", [], "not this field", 0.36, same_ground=False)

    notes = ar._where_naming_disagrees_with_overlap(
        original, [(different, ar.Naming("aaa111", "Resolved to existing field", 200))]
    )
    assert any("collision" in n for n in notes)


def test_a_correct_run_is_not_nagged() -> None:
    """A check that fires on correct runs gets ignored, then deleted."""
    ar = _module()
    original = ar.Naming("aaa111", "registered successfully", 200)

    notes = ar._where_naming_disagrees_with_overlap(original, [
        (ar.Redrawing("one vertex out", [], "", 0.994, same_ground=True), ar.Naming("aaa111", "Resolved to existing field", 200)),
        (ar.Redrawing("a different field", [], "", 0.485, same_ground=False), ar.Naming("ddd444", "registered successfully", 200)),
    ])
    assert notes == []


# --------------------------------------------------------------------------
# The redrawings
# --------------------------------------------------------------------------


def test_the_control_case_is_genuinely_a_different_field() -> None:
    """The L-shape must actually share the bounding box and not the ground.

    Without both properties it tests nothing: sharing the box is what the
    previous generation cannot see past, and not sharing the ground is what
    makes a distinct name the right answer.
    """
    ar = _module()

    control = next(r for r in ar.redrawings(PARCEL) if "L-shaped" in r.label)

    def box(ring):
        return (min(p[0] for p in ring), min(p[1] for p in ring),
                max(p[0] for p in ring), max(p[1] for p in ring))

    assert box(control.ring) == pytest.approx(box(PARCEL)), "the control does not share the bounding box"

    # Below the registration threshold with room to spare, rather than below
    # some particular number. The first version of this asserted < 0.60, which
    # was the figure measured on one real parcel and had no meaning on any
    # other shape -- it failed at 0.64 on a fixture that is a perfectly good
    # different field. What has to hold is that no reasonable threshold would
    # call this the same field.
    threshold = 0.95
    assert control.iou < threshold - 0.15, (  # noqa: PLR2004
        f"the control overlaps the original {control.iou:.0%}, too close to the "
        f"{threshold:.0%} threshold to be a convincing different field"
    )

    near = [r for r in ar.redrawings(PARCEL) if "L-shaped" not in r.label]
    assert control.iou < min(r.iou for r in near) - 0.2, (  # noqa: PLR2004
        "the control is no more different from the original than the redrawings are"
    )


def test_the_near_redrawings_really_are_near() -> None:
    """A 'redrawing' that moved the field would prove nothing about naming."""
    ar = _module()

    near = [r for r in ar.redrawings(PARCEL) if "L-shaped" not in r.label]
    assert len(near) == 3  # noqa: PLR2004
    for redrawing in near:
        assert redrawing.iou > 0.9, f"{redrawing.label!r} overlaps only {redrawing.iou:.0%}"  # noqa: PLR2004


def test_the_pulled_in_vertex_leaves_the_bounding_box_alone() -> None:
    """That is the case AR 1.x cannot see at all, so it must hold here."""
    ar = _module()

    pulled = next(r for r in ar.redrawings(PARCEL) if "pulled in" in r.label)

    def box(ring):
        return (min(p[0] for p in ring), min(p[1] for p in ring),
                max(p[0] for p in ring), max(p[1] for p in ring))

    assert box(pulled.ring) == pytest.approx(box(PARCEL)), "the pulled-in vertex changed the bounding box"


def test_overlap_is_measured_by_area_not_by_tokens() -> None:
    """Neither scheme may mark its own homework."""
    body = _body_of("true_overlap")
    # The docstring is where those words belong; it is the code that must not
    # reach for either scheme's own arithmetic.
    code = body[body.index('"""', body.index('"""') + 3) + 3:]
    assert "shapely" in code
    assert "cover" not in code and "token" not in code


# --------------------------------------------------------------------------
# Disclosure
# --------------------------------------------------------------------------


def test_the_disclosure_summary_reads_ar2s_actual_keys() -> None:
    """The first version looked for WKT and geometry, which AR2 does not use.

    Both tiers printed "-" and the section demonstrated nothing while appearing
    to run.
    """
    ar = _module()

    coarse = ar._disclosure_summary({
        "MaskingLevel": "L0",
        "Geo Data": {"cell_token": "47c881", "country": "Netherlands", "area_ha": 15.3},
    })
    assert "Netherlands" in coarse and "15.3" in coarse and "47c881" in coarse

    precise = ar._disclosure_summary({
        "MaskingLevel": "L1",
        "Geo Data": None,
        "Geo JSON": {"type": "Feature", "geometry": {"type": "Polygon",
                     "coordinates": [[[5.0, 52.0]] * 24]}},
    })
    assert "24" in precise and "boundary" in precise


def test_the_coarse_answer_carries_fewer_points_than_the_precise_one() -> None:
    """The whole of the tier difference, in one number."""
    ar = _module()

    cell = {"Geo JSON": {"type": "Polygon", "coordinates": [[[5.0, 52.0]] * 5]}}
    field = {"Geo JSON": {"type": "Feature", "geometry": {"type": "Polygon",
             "coordinates": [[[5.0, 52.0]] * 24]}}}

    assert ar.vertices_disclosed(cell) == 5  # noqa: PLR2004
    assert ar.vertices_disclosed(field) == 24  # noqa: PLR2004
    assert ar.vertices_disclosed({}) == 0


# --------------------------------------------------------------------------
# What the notebook claims
# --------------------------------------------------------------------------


def test_the_notebook_does_not_claim_sovereignty_from_one_node() -> None:
    """Routing is exercised here; in-country residency is not shown.

    One node stands behind this hub, so both countries land on it. Saying data
    stays in-country on that evidence would be the kind of claim this project
    exists to make checkable.
    """
    built = BUILDER.read_text()
    section = built[built.index("## 6. One hub, many countries"):]

    assert "one node" in section.lower(), "the single-node caveat is gone"
    assert "sovereignty is not" in section or "not shown by this run" in section

    # And the caveat must not sit beside a bare claim that contradicts it. The
    # first version only looked for the caveat, so replacing the code's
    # disclaimer with "Data stays in-country." left this passing.
    for overclaim in ("Data stays in-country.", "data stays in-country.\")", "residency is shown"):
        assert overclaim not in section, f"the section asserts {overclaim!r} on one node"


def test_the_notebook_says_where_the_parcels_are_from_and_why() -> None:
    """Dutch geometry in a Honduras project is a seam. Leave it visible."""
    built = BUILDER.read_text()

    assert "Dutch" in built
    assert "Honduran parcel register" in built or "no Honduran" in built.lower()
    assert "CC0" in built


def test_the_notebook_reports_a_missing_derivation_rather_than_hiding_it() -> None:
    """Without ar2 on the path the independence claim cannot be made."""
    built = BUILDER.read_text()

    assert "NOT CHECKED" in built, "a missing local derivation passes silently"
    assert "AR2_SOURCE" in built


def test_disagreement_between_the_two_derivations_is_called_a_defect() -> None:
    """Two implementations of a pure function disagreeing is not a caveat."""
    built = BUILDER.read_text()

    assert "THEY DIFFER" in built
    assert "defect" in built[built.index("THEY DIFFER") - 400:built.index("THEY DIFFER") + 300]


# --------------------------------------------------------------------------
# The maps
# --------------------------------------------------------------------------


def _rendered(canvas) -> str:
    import html as html_module

    return html_module.unescape(canvas._repr_html_())


def _ar_maps(ar):
    """Every map this notebook draws, built from fixtures rather than the network."""
    feature = {
        "geometry": {"type": "Polygon", "coordinates": [PARCEL]},
        "properties": {"gewas": "Aardappelen", "jaar": 2025, "category": "Bouwland"},
    }
    redrawn = ar.redrawings(PARCEL)
    coarse = {"MaskingLevel": "L0", "Geo Data": {"cell_token": "47c881",
              "country": "Netherlands", "area_ha": 15.3},
              "Geo JSON": {"type": "Polygon", "coordinates": [[
                  [4.9, 51.9], [5.1, 51.9], [5.1, 52.1], [4.9, 52.1], [4.9, 51.9]]]}}
    precise = {"MaskingLevel": "L1", "Geo JSON": {"type": "Feature",
               "geometry": {"type": "Polygon", "coordinates": [PARCEL]}}}
    return {
        "parcel_map": ar.parcel_map([feature]),
        "redrawing_map": ar.redrawing_map(PARCEL, redrawn),
        "disclosure_map": ar.disclosure_map(coarse, precise),
    }


def test_every_map_fits_itself_to_what_it_draws() -> None:
    """A fixed zoom framed one map and cut the others off."""
    ar = _module()
    if not ar.have_folium():
        pytest.skip("folium is not installed")

    for name, canvas in _ar_maps(ar).items():
        assert canvas is not None, f"{name} drew nothing"
        assert "fitBounds" in _rendered(canvas), f"{name} does not fit itself to its shapes"


def test_every_basemap_is_black_and_white() -> None:
    """Overlays are the only coloured thing, so a thin outline reads."""
    ar = _module()
    if not ar.have_folium():
        pytest.skip("folium is not installed")

    for name, canvas in _ar_maps(ar).items():
        assert "grayscale(100%)" in _rendered(canvas), f"{name} has a colour basemap"


def test_every_overlay_can_be_switched_off() -> None:
    """Four redrawings over one field is unreadable without layer control."""
    ar = _module()
    if not ar.have_folium():
        pytest.skip("folium is not installed")

    for name, canvas in _ar_maps(ar).items():
        assert "L.control.layers" in _rendered(canvas), f"{name} has no layer control"


def test_the_fitted_box_holds_every_redrawing() -> None:
    """The control shares a bounding box but the drifted one does not."""
    ar = _module()
    rings = [PARCEL, *(r.ring for r in ar.redrawings(PARCEL))]
    as_latlon = [[[p[1], p[0]] for p in ring] for ring in rings]

    (south, west), (north, east) = ar._bounds(as_latlon)

    for ring in as_latlon:
        for lat, lon in ring:
            assert south < lat < north, "a redrawing's latitude falls outside the fitted box"
            assert west < lon < east, "a redrawing's longitude falls outside the fitted box"


def test_the_different_field_is_not_coloured_as_a_redrawing() -> None:
    """It is the control. Colouring it like the others hides the point."""
    ar = _module()
    if not ar.have_folium():
        pytest.skip("folium is not installed")

    html = _rendered(ar.redrawing_map(PARCEL, ar.redrawings(PARCEL)))

    # The colours of the drawn polygons, not of the whole document. The legend
    # names the control's colour whatever the polygon uses, so searching the
    # page left this passing against a map that drew the control exactly like
    # the redrawings.
    drawn = [
        re.search(r'"color":\s*"(#[0-9a-fA-F]{6})"', html[m.start():m.start() + 1400]).group(1)
        for m in re.finditer(r"L\.polygon\(", html)
    ]
    near = [r for r in ar.redrawings(PARCEL) if r.same_ground]

    assert drawn.count(ar.OUTLINE) == 1, (
        f"expected exactly one polygon in the control colour, found "
        f"{drawn.count(ar.OUTLINE)} -- the control is drawn like a redrawing"
    )
    assert drawn.count(ar.ACCENT_TINT) == len(near)


def test_the_masked_cell_encloses_the_boundary_it_stands_for() -> None:
    """L0 is a cell the field sits inside; drawn otherwise it misleads."""
    ar = _module()
    if not ar.have_folium():
        pytest.skip("folium is not installed")

    cell = [[4.9, 51.9], [5.1, 51.9], [5.1, 52.1], [4.9, 52.1], [4.9, 51.9]]
    for lon, lat in PARCEL:
        assert min(p[0] for p in cell) <= lon <= max(p[0] for p in cell)
        assert min(p[1] for p in cell) <= lat <= max(p[1] for p in cell)


def test_the_control_is_declared_a_different_field_not_guessed_from_overlap() -> None:
    """An overlap threshold is a guess, and it guessed wrong.

    The map asked ``iou < 0.5``, a number taken from one real parcel. On a
    rounder field the control scores 0.64, so the one shape whose whole job is
    to look different was drawn exactly like the three that should look the
    same.
    """
    ar = _module()

    drawn = ar.redrawings(PARCEL)
    control = next(r for r in drawn if "L-shaped" in r.label)

    assert control.same_ground is False
    assert all(r.same_ground for r in drawn if "L-shaped" not in r.label)
    assert "iou < 0.5" not in _body_of("redrawing_map"), (
        "the map is inferring the control from its overlap again"
    )


def test_a_collision_is_reported_however_much_the_shapes_overlap() -> None:
    """A different field folded into another's name is a collision at any IoU.

    Gated on ``iou < 0.5`` this went unreported for a control scoring 0.64 --
    the case most likely to happen in the field, and the most dangerous.
    """
    ar = _module()
    original = ar.Naming("aaa111", "registered successfully", 200)
    control = ar.Redrawing("a different field", [], "", 0.64, same_ground=False)

    notes = ar._where_naming_disagrees_with_overlap(
        original, [(control, ar.Naming("aaa111", "Resolved to existing field", 200))]
    )
    assert any("collision" in n for n in notes)


# --------------------------------------------------------------------------
# Withdrawing a slip. The deck's third goal says grants are "instantly
# revocable", and a notebook that only ever issues one does not show it.
# --------------------------------------------------------------------------


def test_the_slip_is_revoked_and_the_same_one_presented_again() -> None:
    """A revocation call returning 200 says nothing about whether the door shut.

    The only thing that demonstrates revocation is re-presenting the identical
    credential, so the test is that the notebook does exactly that rather than
    minting a fresh one or asking without a slip at all.
    """
    built = BUILDER.read_text()
    section = built[built.index("revoke the slip and present the very same one again"):]
    section = section[:section.index('""")')]

    assert "CONSENT.credential" in section, "the revoked slip is not the one re-presented"
    assert "ar.revoke" in section
    assert "consent_for" not in section, "a fresh slip is minted instead of reusing the old"


def test_the_three_answers_are_shown_in_one_table() -> None:
    """Before, after, and after-revocation only mean something side by side."""
    built = BUILDER.read_text()
    section = built[built.index("revoke the slip and present the very same one again"):]
    section = section[:section.index('""")')]

    assert "DISCLOSED" in section
    assert "the same slip, revoked" in section


def test_a_revoked_slip_that_still_works_is_called_a_defect() -> None:
    """The outcome the step exists to catch, not the one it expects."""
    built = BUILDER.read_text()
    section = built[built.index("revoke the slip and present the very same one again"):]
    section = section[:section.index('""")')]

    # The sentence, not the word. "defect" alone survived deleting the line
    # that names the failure, because it recurs on the line after.
    assert "still returned the exact boundary" in section
    assert "vertices_disclosed" in section, "the two answers are not actually compared"


def test_the_degrade_is_explained_rather_than_shown_as_an_error() -> None:
    """A revoked slip returns 200 and L0. Read as success that is misleading."""
    built = " ".join(BUILDER.read_text().split())

    # Split across two print calls in the source, so the phrase is matched in
    # halves rather than whole.
    assert "a revoked slip does" in built
    assert "not error, it degrades" in built


def test_revocation_reaches_the_notebook_from_the_support_module() -> None:
    """It lives in the open-science module; ar2_demo has to re-export it."""
    ar = _module()

    assert hasattr(ar, "revoke")


def test_the_notebook_covers_the_decks_first_three_goals() -> None:
    """Slide 2 lists six. This notebook is the walkthrough for the first three;
    lists, tracing and compliance export belong to the other two notebooks."""
    built = BUILDER.read_text()

    assert "derived from" in built or "computed" in built     # one name per field
    assert "countries" in built                               # federated by country
    assert "revoke" in built                                  # revocable permissions
