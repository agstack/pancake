"""Support module for the AR2 field-identity notebook.

The honesty machinery -- the ledger, the step badges, the settings loader, the
map styling -- is shared with the open-science notebook and imported from it
rather than copied. What lives here is specific to the identity argument: real
parcels from a public register, the perturbations that test what a field's name
survives, and the comparison between what AR2 does with them and what the AR 1.x
lineage does.

One deliberate difference from ``openscience_demo``. That module blocks
``terrapipe_os`` from being imported, because a demo of a remote node that
quietly computed the answer locally would be a lie. Here the opposite holds:
computing a GeoID locally, off the node, and getting the same string the node
returns *is* the claim. So ``app.geoid_v2`` is imported on purpose, and the
notebook shows the two agreeing rather than trusting either.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

# The shared machinery. Imported rather than reimplemented so that a fix to the
# ledger or the map styling reaches both notebooks.
from openscience_demo import (  # noqa: F401
    ACCENT,
    ACCENT_TINT,
    HUB_URL,
    LIVE,
    LOCAL,
    LEDGER,
    NODE_URL,
    OUTLINE,
    PANCAKE_URL,
    SKIPPED,
    _basemap,
    _bounds,
    _legend,
    _pin,
    _hand_over_to_the_boundaries,
    have_folium,
    hub_token,
    mode,
    skip,
    step,
)

HTTP_OK = 200

# --------------------------------------------------------------------------
# Parcels somebody else drew
# --------------------------------------------------------------------------

BRP_WFS = "https://service.pdok.nl/rvo/brpgewaspercelen/wfs/v1_0"
"""The Dutch crop parcel register, served openly by PDOK.

Real parcels rather than shapes we drew, because the identity argument is about
what a name survives when the boundary is redrawn -- and a boundary we invented
can be quietly invented to make the point. These were digitised by the Rijksdienst
voor Ondernemend Nederland for subsidy administration by people who have never
heard of a GeoID.

The service's own GetCapabilities gives ``Fees: none`` and an AccessConstraints
of https://creativecommons.org/publicdomain/zero/1.0/deed.nl -- CC0, a public
domain dedication, so no attribution is owed. It is credited anyway.

Dutch rather than Honduran, which is a seam in a project otherwise about
Honduras. No parcel register of comparable openness appears to exist there. The
notebook says so, and makes the point that the identity argument is about
geometry and is indifferent to which country drew it -- which is itself part of
what is being claimed.
"""

BRP_LICENCE = "CC0 1.0 (public domain dedication)"
BRP_CREDIT = "Basisregistratie Gewaspercelen, RVO / PDOK"

# Flevoland: reclaimed seabed, laid out for mechanised farming, so the parcels
# are large and unambiguous. A cramped river-valley parcel would make the
# perturbation figures harder to read without changing what they show.
BRP_BBOX = (52.45, 5.55, 52.60, 5.75)

WORKED = "Bouwland"
"""Arable land.

The register also returns ``Landschapselement`` -- ditches, field margins,
rough ground -- which are administrative features rather than fields, and
``Grasland``. Filtering to arable keeps the demo about the thing being named.
"""


def parcels(limit: int = 6, bbox: tuple[float, float, float, float] = BRP_BBOX) -> tuple[list[dict], str]:
    """A handful of real crop parcels, as GeoJSON features in WGS84.

    Fetched live rather than vendored, so the licence claim can be checked
    against the source at the moment of reading, and so nobody has to trust a
    file in this repository to be what it says it is.

    The bounding box is given in latitude, longitude order. WFS 2.0 with a URN
    CRS uses the axis order the CRS declares, and EPSG:4326 declares lat first.
    Passing lon first returns HTTP 200 with zero features, which is
    indistinguishable from an empty area -- that is what happened on the first
    attempt on 2026-09-07.
    """
    query = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "BrpGewas",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        # Ask for more than we need: most features in any box are ditches.
        "count": str(max(limit * 8, 40)),
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},urn:ogc:def:crs:EPSG::4326",
    }
    try:
        response = requests.get(BRP_WFS, params=query, timeout=90)
    except requests.RequestException as exc:
        return [], f"the parcel register could not be reached: {exc.__class__.__name__}"
    if response.status_code != HTTP_OK:
        return [], f"the parcel register answered HTTP {response.status_code}"

    features = (response.json() or {}).get("features") or []
    if not features:
        return [], (
            "the register answered with no parcels. An empty answer here usually means the "
            "bounding box axes were given the wrong way round rather than that the area is empty."
        )

    arable = [f for f in features if f["properties"].get("category") == WORKED]
    arable = [f for f in arable if f["geometry"]["type"] == "Polygon"]
    arable.sort(key=lambda f: -_rough_area_m2(_ring(f)))
    chosen = arable[:limit]
    return chosen, (
        f"{len(chosen)} arable parcels of {len(features)} features returned, "
        f"{BRP_CREDIT}, {BRP_LICENCE}"
    )


def _ring(feature: dict) -> list[list[float]]:
    """The exterior ring, as [lon, lat] pairs."""
    return [list(p) for p in feature["geometry"]["coordinates"][0]]


def _rough_area_m2(ring: list[list[float]]) -> float:
    """Shoelace area, degrees converted at this latitude. For ordering only."""
    lat = sum(p[1] for p in ring) / len(ring)
    scale_x = 111_320 * math.cos(math.radians(lat))
    twice = sum(
        (ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1])
        for i in range(len(ring) - 1)
    )
    return abs(twice) / 2 * scale_x * 111_320


def describe(feature: dict) -> str:
    """What the register says this parcel is."""
    p = feature["properties"]
    hectares = _rough_area_m2(_ring(feature)) / 10_000
    return f"{p.get('gewas', 'unknown')} ({hectares:.1f} ha, {len(_ring(feature))} vertices, {p.get('jaar')})"


def wkt(ring: list[list[float]]) -> str:
    """A closed ring as WKT, which is what AR2 registers."""
    closed = ring if ring[0] == ring[-1] else [*ring, ring[0]]
    return "POLYGON((" + ", ".join(f"{x} {y}" for x, y in closed) + "))"


# --------------------------------------------------------------------------
# Redrawing the same field
# --------------------------------------------------------------------------


@dataclass
class Redrawing:
    """One way of redrawing a boundary, and how true it stayed to the original."""

    label: str
    ring: list[list[float]]
    what_changed: str
    iou: float
    same_ground: bool
    """Whether this is meant to be the same field, declared rather than inferred.

    The control is a different field by construction, and saying so here beats
    deriving it from the overlap. The map used to ask ``iou < 0.5``, which is a
    number picked off one real parcel: on a rounder field the control scores
    0.64, sailed past the threshold, and got drawn in the same colour as the
    genuine redrawings -- so the one shape whose whole job is to look different
    looked identical.
    """


def _metre_in_degrees(ring: list[list[float]]) -> tuple[float, float]:
    lat = sum(p[1] for p in ring) / len(ring)
    return 1 / (111_320 * math.cos(math.radians(lat))), 1 / 110_540


def _towards(
    point: list[float], target: tuple[float, float], metres: float, east: float, north: float
) -> list[float]:
    """``point`` moved ``metres`` towards ``target``, never past it.

    Degrees of longitude and latitude are different lengths, so the direction
    is computed in metres and converted back rather than interpolated in
    degrees, which would skew the move towards the equator.
    """
    dx = (target[0] - point[0]) / east
    dy = (target[1] - point[1]) / north
    span = math.hypot(dx, dy)
    if span <= metres:
        return [target[0], target[1]]
    return [point[0] + dx / span * metres * east, point[1] + dy / span * metres * north]


def redrawings(ring: list[list[float]]) -> list[Redrawing]:
    """The perturbations from the deck's Appendix E, on a real parcel.

    Each is a plausible redrawing of the same ground: a GPS fix a few metres
    out, a surveyor cutting a corner, a neighbour's field that happens to sit
    in the same bounding box. What a naming scheme does with these is the whole
    of the identity question.

    The last one is not the same field at all. It is here because the AR 1.x
    lineage covers the bounding box rather than the polygon, so a genuinely
    different field sharing a bounding box is indistinguishable to it -- and it
    rejects the registration as a duplicate.
    """
    east, north = _metre_in_degrees(ring)
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    west, far_east = min(lons), max(lons)
    south, far_north = min(lats), max(lats)
    centre = (sum(lons[:-1]) / (len(lons) - 1), sum(lats[:-1]) / (len(lats) - 1))

    pushed = [list(p) for p in ring]
    pushed[1] = [pushed[1][0] + 20 * east, pushed[1][1]]

    # A vertex moved inward, chosen away from the extremes so the bounding box
    # does not change. That is the case the lineage cannot see at all.
    #
    # Moved a fixed 15 m towards the centre rather than a fixed *fraction* of
    # the way there. A fraction is not a distance: half the way to the centroid
    # is a couple of metres on a 24-vertex parcel and a quarter of the whole
    # field on a five-vertex one, so the same line of code meant "a resurvey
    # nudge" on real data and "a different field" on a square. Every other
    # redrawing here is specified in metres; this one now is too.
    interior = min(range(1, len(ring) - 1), key=lambda k: abs(ring[k][0] - centre[0]))
    pulled = [list(p) for p in ring]
    pulled[interior] = _towards(ring[interior], centre, 15.0, east, north)

    drifted = [[p[0] + 3 * east, p[1] + 3 * north] for p in ring]

    mid_x, mid_y = (west + far_east) / 2, (south + far_north) / 2
    l_shaped = [
        [west, south], [far_east, south], [far_east, mid_y],
        [mid_x, mid_y], [mid_x, far_north], [west, far_north], [west, south],
    ]

    candidates = [
        (pushed, "one vertex pushed out about 20 m", "a GPS fix a few metres out", True),
        (pulled, "one vertex pulled in, bounding box unchanged", "a corner cut on resurvey", True),
        (drifted, "every vertex drifted 3 m", "a different receiver, same walk", True),
        (l_shaped, "a different L-shaped field, same bounding box", "not this field at all", False),
    ]
    return [
        Redrawing(label, redrawn, why, true_overlap(ring, redrawn), same_ground)
        for redrawn, label, why, same_ground in candidates
    ]


def true_overlap(a: list[list[float]], b: list[list[float]]) -> float:
    """Intersection over union of the two polygons, as area, not as tokens.

    The honest measure of "how much the same field is this", against which a
    naming scheme's answer can be judged. Computed with shapely rather than
    with either scheme's own cover arithmetic, so it is not marking its own
    homework.
    """
    from shapely.geometry import Polygon  # noqa: PLC0415

    first, second = Polygon(a), Polygon(b)
    if not first.is_valid:
        first = first.buffer(0)
    if not second.is_valid:
        second = second.buffer(0)
    union = first.union(second).area
    return first.intersection(second).area / union if union else 0.0


# --------------------------------------------------------------------------
# Asking AR2 what it makes of them
# --------------------------------------------------------------------------


@dataclass
class Naming:
    """What the node called a boundary, and whether that was a new name."""

    geo_id: str | None
    message: str
    status: int

    @property
    def is_new(self) -> bool:
        return "registered successfully" in self.message.lower()

    @property
    def resolved(self) -> bool:
        """Recognised as a field already known, under either wording."""
        low = self.message.lower()
        return "resolved to existing" in low or "already registered" in low


def name_of(ring: list[list[float]], token: str, *, at: str | None = None) -> Naming:
    """Register a boundary and report the name it was given.

    Registration is how you ask: the node answers with the canonical name for
    this ground, whether or not that means a new one. Sending the same field
    twice is not an error and does not create a second field, which is the
    property being demonstrated.
    """
    try:
        response = requests.post(
            f"{at or NODE_URL}/register-field-boundary",
            headers={"Authorization": f"Bearer {token}"},
            json={"wkt": wkt(ring), "threshold": 95},
            timeout=120,
        )
    except requests.RequestException as exc:
        return Naming(None, f"the node could not be reached: {exc.__class__.__name__}", 0)
    if response.status_code != HTTP_OK:
        return Naming(None, f"refused: {response.text[:120]}", response.status_code)

    body = response.json() or {}
    # "Geo Id", with a space and capitals. Reading body["geo_id"] returns None
    # on every path, and comparing two Nones made a newly registered field look
    # like a resolution to an existing one on 2026-09-07.
    return Naming(body.get("Geo Id"), body.get("message", ""), response.status_code)


def computed_here(ring: list[list[float]]) -> tuple[str | None, str]:
    """The GeoID derived from the boundary on this machine, with no node.

    The point of the whole scheme: the name is a function of the geometry, so
    anyone holding the boundary can compute it and check the node's answer
    rather than trusting it. If this import fails the notebook says so instead
    of quietly falling back to what the node said, which would demonstrate
    nothing.
    """
    try:
        from app.geoid_v2 import geo_id  # noqa: PLC0415
    except ImportError as exc:
        return None, (
            f"AR2's geoid_v2 is not importable here ({exc.__class__.__name__}). "
            "Set PYTHONPATH to an ar2 checkout to recompute the name independently."
        )
    return geo_id(wkt(ring)), "derived from the boundary alone, no node involved"


def cover_of(ring: list[list[float]]) -> tuple[list[str], str]:
    """The S2 cells the name is hashed over."""
    try:
        from app.geoid_v2 import cover_tokens  # noqa: PLC0415
    except ImportError:
        return [], "AR2's geoid_v2 is not importable here"
    tokens = sorted(cover_tokens(wkt(ring)))
    return tokens, f"{len(tokens)} cells, sorted, then one SHA-256 over the list"


def show_redrawings(original: Naming, rows: list[tuple[Redrawing, Naming]]) -> None:
    """Each redrawing, what it truly overlapped, and what it got called."""
    print(f"{'redrawn as':46} {'true overlap':>12}  {'AR2 calls it':30}")
    print(f"{'as the register drew it':46} {'':>12}  the original")
    for redrawing, naming in rows:
        print(f"{redrawing.label:46} {redrawing.iou:>11.1%}  {_verdict_on(original, naming):30}")

    for note in _where_naming_disagrees_with_overlap(original, rows):
        print(f"\n  NOTE: {note}")


def _verdict_on(original: Naming, naming: Naming) -> str:
    """Whether this redrawing got the original's name, in words.

    Read from the identifier rather than from the wording of the reply. The
    node says "Exact geometry already registered" both when a redrawing is
    recognised as the original *and* when a genuinely different field is one it
    has seen before -- and on 2026-09-07 that made the control case, a
    different field with its own distinct name, print as "a field it already
    knows". The identifier is the answer; the message is commentary on how it
    was reached.
    """
    if not naming.geo_id:
        return naming.message[:30]
    if naming.geo_id == original.geo_id:
        return "the same field, one name"
    return f"its own name, {naming.geo_id[:8]}..."


def _where_naming_disagrees_with_overlap(
    original: Naming, rows: list[tuple[Redrawing, Naming]]
) -> list[str]:
    """The claims the surrounding prose makes, checked against the results.

    The paragraphs around this table say that near-identical redrawings resolve
    to one name and that a different field gets its own. Markdown says that
    whatever the table shows. So the table checks it.
    """
    notes = []
    for redrawing, naming in rows:
        if not naming.geo_id:
            continue
        got_the_same_name = naming.geo_id == original.geo_id

        # Read from what each redrawing was built to be, not from its overlap.
        # Gating the collision case on ``iou < 0.5`` meant a different field
        # scoring 0.64 -- the likeliest case in the field, and the most
        # dangerous -- was folded into another's name with nothing said.
        if redrawing.same_ground and not got_the_same_name:
            notes.append(
                f"{redrawing.label!r} overlaps the original {redrawing.iou:.1%} and still got "
                "its own name. That is the split identity this section says AR2 avoids."
            )
        if not redrawing.same_ground and got_the_same_name:
            notes.append(
                f"{redrawing.label!r} is a different field and was folded into the original's "
                f"name, on {redrawing.iou:.1%} overlap. That is a collision, and it is worse "
                "than a split: one name now stands for two pieces of ground."
            )
    return notes


# --------------------------------------------------------------------------
# What a name discloses
# --------------------------------------------------------------------------


def what_the_name_reveals(geo_id: str, token: str, grant: str | None = None) -> tuple[int, dict[str, Any]]:
    """Look a name up, with or without a permission slip."""
    headers = {"Authorization": f"Bearer {token}"}
    if grant:
        headers["X-Field-Grant"] = grant
    try:
        response = requests.get(f"{NODE_URL}/fetch-field/{geo_id}", headers=headers, timeout=60)
    except requests.RequestException as exc:
        return 0, {"reason": f"the node could not be reached: {exc.__class__.__name__}"}
    try:
        return response.status_code, response.json() or {}
    except ValueError:
        return response.status_code, {"reason": response.text[:160]}


def show_what_is_revealed(rows: list[tuple[str, int, dict[str, Any]]]) -> None:
    """The same name, looked up with and without permission.

    Reports what actually came back rather than whether a key was present. The
    first version looked for "WKT" and "geometry", neither of which AR2 uses,
    so both tiers printed "-" and the section demonstrated nothing while
    appearing to run.
    """
    print(f"{'presented':22} {'HTTP':5} {'tier':5} {'what came back':56}")
    for label, status, body in rows:
        level = body.get("MaskingLevel") or "-"
        print(f"{label:22} {status:<5} {str(level):5} {_disclosure_summary(body):56}")


def _disclosure_summary(body: dict[str, Any]) -> str:
    """One line describing what a fetch actually disclosed."""
    if coarse := body.get("Geo Data"):
        return (
            f"{coarse.get('country', '?')}, about {coarse.get('area_ha', '?')} ha, "
            f"in cell {coarse.get('cell_token', '?')}"
        )
    shape = body.get("Geo JSON") or {}
    geometry = shape.get("geometry") if shape.get("type") == "Feature" else shape
    ring = (geometry or {}).get("coordinates", [[]])
    vertices = len(ring[0]) if ring and ring[0] else 0
    if vertices:
        return f"the exact boundary: a {vertices}-vertex polygon"
    return str(body.get("reason") or body.get("message") or "-")[:56]


def vertices_disclosed(body: dict[str, Any]) -> int:
    """How many boundary points a response actually handed over.

    The number that distinguishes the tiers: the coarse answer is a four-corner
    grid cell, the precise one is the surveyed boundary.
    """
    shape = body.get("Geo JSON") or {}
    geometry = shape.get("geometry") if shape.get("type") == "Feature" else shape
    ring = (geometry or {}).get("coordinates", [[]])
    return len(ring[0]) if ring and ring[0] else 0


def disclosure_map(coarse: dict[str, Any], precise: dict[str, Any]):
    """The coarse cell and the exact boundary it stands in for, on one map."""
    if not have_folium():
        return None
    import folium  # noqa: PLC0415

    def ring_of(body):
        shape = body.get("Geo JSON") or {}
        geometry = shape.get("geometry") if shape.get("type") == "Feature" else shape
        coords = (geometry or {}).get("coordinates") or []
        return [[p[1], p[0]] for p in coords[0]] if coords else []

    masked, exact = ring_of(coarse), ring_of(precise)
    if not masked and not exact:
        return None

    canvas = _basemap([r for r in (masked, exact) if r])

    if masked:
        group = folium.FeatureGroup(name="L0 — what anyone may learn")
        folium.Polygon(masked, color=OUTLINE, weight=2, dash_array="6,6", fill=True,
                       fill_color=OUTLINE, fill_opacity=0.08,
                       tooltip="L0: the grid cell, the country, a rounded area").add_to(group)
        group.add_to(canvas)
    if exact:
        group = folium.FeatureGroup(name="L1 — what the slip unlocks")
        folium.Polygon(exact, color=ACCENT, weight=3, fill=True, fill_color=ACCENT,
                       fill_opacity=0.25, tooltip="L1: the surveyed boundary").add_to(group)
        group.add_to(canvas)

    folium.LayerControl(collapsed=False).add_to(canvas)
    _legend(canvas, [
        ("L0 — no permission needed", OUTLINE, "dashed"),
        ("L1 — with a field-access slip", ACCENT, "solid"),
    ], title="The same name, two answers")
    return canvas


# --------------------------------------------------------------------------
# Maps
# --------------------------------------------------------------------------


def parcel_map(features: list[dict]):
    """The parcels as the register drew them."""
    if not have_folium():
        return None
    import folium  # noqa: PLC0415

    rings = [[[p[1], p[0]] for p in _ring(f)] for f in features]
    canvas = _basemap(rings)
    group = folium.FeatureGroup(name="Parcels, as the register drew them")
    for feature, ring in zip(features, rings, strict=True):
        folium.Polygon(
            ring, color=ACCENT, weight=2, fill=True, fill_color=ACCENT, fill_opacity=0.18,
            tooltip=describe(feature),
        ).add_to(group)
    group.add_to(canvas)
    folium.LayerControl(collapsed=False).add_to(canvas)
    _legend(canvas, [("Arable parcel (BRP)", ACCENT, "solid")],
            title=f"{BRP_CREDIT} — {BRP_LICENCE}")
    return canvas


def redrawing_map(original: list[list[float]], rows: list[Redrawing]):
    """Every redrawing over the original, so the reader can see how small they are."""
    if not have_folium():
        return None
    import folium  # noqa: PLC0415

    as_latlon = lambda r: [[p[1], p[0]] for p in r]  # noqa: E731
    canvas = _basemap([as_latlon(original), *(as_latlon(r.ring) for r in rows)])

    base = folium.FeatureGroup(name="As the register drew it")
    folium.Polygon(as_latlon(original), color=ACCENT, weight=3, fill=True,
                   fill_color=ACCENT, fill_opacity=0.15,
                   tooltip="as the register drew it").add_to(base)
    base.add_to(canvas)

    for redrawing in rows:
        # The different field is not a redrawing of this one, so it is not
        # coloured as though it were. Read from the declaration, not from the
        # overlap: see Redrawing.same_ground.
        group = folium.FeatureGroup(name=redrawing.label, show=not redrawing.same_ground)
        folium.Polygon(
            as_latlon(redrawing.ring),
            color=ACCENT_TINT if redrawing.same_ground else OUTLINE,
            weight=2, dash_array="6,4", fill=False,
            tooltip=f"{redrawing.label} — {redrawing.iou:.1%} true overlap",
        ).add_to(group)
        group.add_to(canvas)

    folium.LayerControl(collapsed=False).add_to(canvas)
    _legend(canvas, [
        ("As the register drew it", ACCENT, "solid"),
        ("A redrawing of the same field", ACCENT_TINT, "dashed"),
        ("A different field, same bounding box", OUTLINE, "dashed"),
    ], title="One field, redrawn")
    return canvas


def cover_map(ring: list[list[float]], tokens: list[str], limit: int = 400):
    """The S2 cells the name is hashed over, drawn on the field."""
    if not have_folium() or not tokens:
        return None
    import folium  # noqa: PLC0415
    import s2sphere  # noqa: PLC0415

    as_latlon = [[p[1], p[0]] for p in ring]
    canvas = _basemap([as_latlon])

    cells = folium.FeatureGroup(name=f"S2 cover ({len(tokens)} cells)")
    for token in tokens[:limit]:
        cell = s2sphere.Cell(s2sphere.CellId.from_token(token))
        corners = []
        for i in range(4):
            point = s2sphere.LatLng.from_point(cell.get_vertex(i))
            corners.append([point.lat().degrees, point.lng().degrees])
        folium.Polygon(corners, color=ACCENT_TINT, weight=1, fill=True,
                       fill_color=ACCENT_TINT, fill_opacity=0.25,
                       tooltip=token).add_to(cells)
    cells.add_to(canvas)

    boundary = folium.FeatureGroup(name="The boundary")
    folium.Polygon(as_latlon, color=ACCENT, weight=3, fill=False,
                   tooltip="the parcel").add_to(boundary)
    boundary.add_to(canvas)

    folium.LayerControl(collapsed=False).add_to(canvas)
    shown = min(len(tokens), limit)
    _legend(canvas, [
        ("The boundary", ACCENT, "solid"),
        (f"S2 cell ({shown} of {len(tokens)} drawn)", ACCENT_TINT, "solid"),
    ], title="What the name is hashed over")
    return canvas


def demo_fields() -> list[dict]:
    """The Honduran fields the other two notebooks use, for the routing section."""
    here = Path(__file__).resolve().parent
    return json.loads((here / "honduras_demo_fields.geojson").read_text())["features"]
