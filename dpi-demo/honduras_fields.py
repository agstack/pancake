"""Real smallholder coffee boundaries, loaded without their owners' identities.

Sixteen KML files from a Honduran cooperative's plot survey. They are the best
fixture in this repository and the most sensitive: each file is named for a
farmer and their national identity number, and the boundary inside it is the
kind of personal data AR2's whole masking design exists to keep from being
published by accident.

So this module reads geometry and nothing else. It never returns a filename, a
person's name, or a national id, and it refuses a plot code that looks like
one -- the survey's own labelling is inconsistent and one polygon is named for
the identity number of the person who walked it.

The directory is **not in this repository and must not be committed.** Point at
it with ``HONDURAS_FIELDS_DIR``; every caller degrades to its own fixture when
it is absent, so a public clone still runs.

What makes these worth the handling:

- **Two files are one boundary.** Two farmers, two identity numbers, one
  identical vertex list. The duplicate-registration case, occurring in real
  data rather than constructed for a demonstration.
- **Two traces self-intersect.** Walked badly with a phone, which is what field
  data looks like before anybody cleans it.
- **They are tiny.** 0.10 to 7.19 hectares, median about 0.3. A tenth of a
  hectare is roughly a thirty-metre square -- one Hansen pixel.
- **All fifteen read as tree cover to ESA WorldCover**, including plots
  Honduras's own map calls entirely coffee.
"""

from __future__ import annotations

import math
import os
import pathlib
import re
from dataclasses import dataclass

DEFAULT_DIR = pathlib.Path.home() / "agstack" / "fieldboundaries"

# A survey label is usable if it names the plot. Two do not: one is the
# identity number of the person who walked it, and several are the export
# tool's placeholder. Both are replaced with a neutral label rather than
# carried into a notebook that gets committed.
_LOOKS_LIKE_AN_IDENTITY = re.compile(r"\d{4}[-_]?\d{4}[-_]?\d{3,}")
_PLACEHOLDER = re.compile(r"^POLIGONO[_ ]?\d*$", re.I)

# The three places the plots cluster, at roughly a kilometre's tolerance.
# Named for what they are rather than for where, because a co-op's catchment
# plus a boundary is close to an address.
_CLUSTERS = [
    ((14.24, -87.92), "north catchment"),
    ((14.11, -87.95), "central catchment"),
    ((14.05, -88.16), "western catchment"),
]


@dataclass(frozen=True)
class Plot:
    """One surveyed boundary, with nothing that names a person."""

    label: str
    ring: tuple[tuple[float, float], ...]
    catchment: str
    hectares: float
    self_intersecting: bool
    duplicate_of: str = ""

    @property
    def wkt(self) -> str:
        return "POLYGON((" + ", ".join(f"{x} {y}" for x, y in self.ring) + "))"

    @property
    def feature(self) -> dict:
        """GeoJSON, in the shape the notebooks' map helpers already take."""
        return {
            "type": "Feature",
            "properties": {"name": self.label, "catchment": self.catchment,
                           "hectares": round(self.hectares, 2)},
            "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in self.ring]]},
        }

    @property
    def centroid(self) -> tuple[float, float]:
        return (sum(p[0] for p in self.ring) / len(self.ring),
                sum(p[1] for p in self.ring) / len(self.ring))


def _hectares(ring: list[tuple[float, float]]) -> float:
    """Shoelace on a local metre grid. Good to a percent at this size."""
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    metres = [((x - lon) * 111_320 * math.cos(math.radians(lat)), (y - lat) * 110_540)
              for x, y in ring]
    twice = sum(metres[i][0] * metres[(i + 1) % len(metres)][1]
                - metres[(i + 1) % len(metres)][0] * metres[i][1]
                for i in range(len(metres)))
    return abs(twice) / 2 / 10_000


def _self_intersects(ring: list[tuple[float, float]]) -> bool:
    """Whether the trace crosses itself, which several of these do."""
    try:
        from shapely.geometry import Polygon  # noqa: PLC0415
    except ImportError:
        return False
    return not Polygon(ring).is_valid


def _catchment(ring: list[tuple[float, float]]) -> str:
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    nearest, best = "unplaced", 1e9
    for (clat, clon), name in _CLUSTERS:
        distance = math.hypot(lat - clat, lon - clon)
        if distance < best:
            nearest, best = name, distance
    return nearest if best < 0.1 else "unplaced"  # noqa: PLR2004


def directory() -> pathlib.Path | None:
    """Where the survey is, if it is anywhere."""
    configured = os.environ.get("HONDURAS_FIELDS_DIR")
    candidate = pathlib.Path(configured).expanduser() if configured else DEFAULT_DIR
    return candidate if candidate.is_dir() and any(candidate.glob("*.kml")) else None


def _rings(path: pathlib.Path) -> list[tuple[str, list[tuple[float, float]]]]:
    text = path.read_text()
    labels = re.findall(r"<name>([^<]*)</name>", text)
    blocks = re.findall(r"<coordinates>\s*(.*?)\s*</coordinates>", text, re.S)
    found = []
    for index, block in enumerate(blocks):
        points = [tuple(float(part) for part in vertex.split(",")[:2])
                  for vertex in block.split()]
        if len(points) < 4:  # noqa: PLR2004
            continue
        label = labels[index + 1] if len(labels) > index + 1 else (labels or [""])[0]
        found.append((label.strip(), points))
    return found


def load() -> list[Plot]:
    """Every distinct boundary in the survey, de-identified and measured.

    Duplicates are kept rather than dropped: two files sharing one vertex list
    is the most interesting thing in the set, and a loader that silently
    de-duplicated would hide it.
    """
    home = directory()
    if home is None:
        return []

    plots: list[Plot] = []
    first_seen: dict[tuple, str] = {}
    unlabelled = 0

    # Sorted by filename for a stable order, and the filename is used for
    # nothing else -- it holds a name and an identity number.
    for path in sorted(home.glob("*.kml")):
        for raw_label, ring in _rings(path):
            key = tuple(ring)
            if _LOOKS_LIKE_AN_IDENTITY.search(raw_label) or _PLACEHOLDER.match(raw_label) \
                    or not raw_label:
                unlabelled += 1
                label = f"unlabelled plot {unlabelled}"
            else:
                label = raw_label
            already = first_seen.get(key, "")
            plots.append(Plot(
                # The two files that share a boundary also share a plot code, so
                # the survey already knows it is one plot; it is the two farmer
                # records behind it that differ. Distinguish the second claim so
                # a reader is not looking at the same label twice.
                label=f"{label} (second claim)" if already else label,
                ring=key, catchment=_catchment(ring),
                hectares=_hectares(ring), self_intersecting=_self_intersects(ring),
                duplicate_of=already,
            ))
            first_seen.setdefault(key, label)
    return plots


def distinct(plots: list[Plot]) -> list[Plot]:
    return [plot for plot in plots if not plot.duplicate_of]


def duplicates(plots: list[Plot]) -> list[tuple[Plot, str]]:
    """(the second registration, the label the boundary was first seen under)."""
    return [(plot, plot.duplicate_of) for plot in plots if plot.duplicate_of]


def by_label(plots: list[Plot], label: str) -> Plot | None:
    return next((plot for plot in plots if plot.label == label), None)


def in_catchment(plots: list[Plot], catchment: str) -> list[Plot]:
    return [plot for plot in distinct(plots) if plot.catchment == catchment]


def describe(plots: list[Plot]) -> str:
    if not plots:
        return ("no survey found; set HONDURAS_FIELDS_DIR to the directory of KML "
                "files, or carry on with the fixture below")
    unique = distinct(plots)
    areas = sorted(plot.hectares for plot in unique)
    return (f"{len(plots)} surveyed plots, {len(unique)} distinct boundaries, "
            f"{areas[0]:.2f}-{areas[-1]:.2f} ha (median {areas[len(areas) // 2]:.2f}), "
            f"{sum(plot.self_intersecting for plot in unique)} self-intersecting")


def show(plots: list[Plot]) -> None:
    """The survey as it arrived, with the awkward parts visible."""
    print(f"  {'plot':22} {'catchment':18} {'ha':>6}  notes")
    for plot in plots:
        notes = []
        if plot.duplicate_of:
            notes.append(f"same boundary as {plot.duplicate_of}")
        if plot.self_intersecting:
            notes.append("trace crosses itself")
        print(f"  {plot.label:22} {plot.catchment:18} {plot.hectares:6.2f}  "
              f"{'; '.join(notes)}")
    print()
    print(f"  {describe(plots)}")
    print("  Loaded without the filenames, which carry a farmer's name and national")
    print("  identity number. This module reads geometry and refuses a plot label")
    print("  that looks like an identity number.")
