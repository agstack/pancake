"""Support for the open-science DPI notebook: honest badges, and a local fallback.

The notebook is meant to be read by people who will not run it, so its
committed output has to be trustworthy on its own. That puts one requirement
above the others: **a cell that did not really run must not look like one that
did.** Every step goes through :func:`step`, which records LIVE, LOCAL,
SKIPPED or FAILED along with the reason, and the last cell prints the ledger.
A reader can therefore tell, without rerunning anything, exactly which claims
in the notebook were demonstrated and which were not.

Three modes, and the notebook says which it is in at every step:

``LIVE``
    The full stack is up. AR2 mints the GeoID, Pancake issues the grant, the
    terrapipe-os node answers over HTTP. This is the real thing.

``LOCAL``
    No stack, but terrapipe-os is importable and the mirrored rasters are
    mounted. The data plane runs in process against the real national stores,
    so the deforestation numbers are real; the identity and consent plane is
    stood in for, and every affected cell says so.

``SKIPPED``
    Neither. The cell prints what it would have done and what to start.

Nothing here fabricates a reading. Where a number cannot be obtained the step
is skipped and the ledger says why, because a plausible number in a notebook
about compliance is worse than a gap.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import sys
import textwrap
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from branca.element import MacroElement
from jinja2 import Template

import requests

SETTINGS_FILE = Path(__file__).resolve().parent / "demo.env"
"""Where the notebook reads which deployment to talk to.

The URLs used to default to localhost, so opening the notebook in a kernel that
had not been handed five environment variables produced four lines of DOWN and a
SKIPPED run -- with nothing saying that the addresses were wrong rather than the
services. A demo whose failure mode is "everything is down" teaches the reader
the wrong thing.

Not committed, because it names a deployment and can hold a token.
``demo.env.example`` is the committed copy with the keys and no values.
"""


def _load_settings(path: Path = SETTINGS_FILE) -> tuple[list[str], list[str]]:
    """Read ``KEY=value`` lines into the environment, without overriding it.

    A real environment variable always wins, so a run can be pointed elsewhere
    for one cell without editing the file.

    Returns the keys it set and the keys the file declares that something else
    had already set. Both, rather than just the first, because the notebook
    reloads this module: on the second pass everything is already in the
    environment, nothing is applied, and reporting only what was applied made
    the first cell say "demo.env: not read" about a file it had just read.
    """
    if not path.is_file():
        return [], []
    applied, overridden = [], []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if not (key and value):
            continue
        if os.environ.get(key):
            overridden.append(key)
        else:
            os.environ[key] = value
            applied.append(key)
    return applied, overridden


SETTINGS_APPLIED, SETTINGS_OVERRIDDEN = _load_settings()
SETTINGS_LOADED = [*SETTINGS_APPLIED, *SETTINGS_OVERRIDDEN]
"""Every key demo.env declares, whether this process set it or found it set."""

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8000")
NODE_URL = os.environ.get("AR2_NODE_URL", "http://localhost:8001")
PANCAKE_URL = os.environ.get("PANCAKE_URL", "http://localhost:8100")
TERRAPIPE_OS_URL = os.environ.get("TERRAPIPE_OS_URL", "http://localhost:8200")

# The node's agent-facing surface. Its own port and its own container, so it is
# configured separately rather than derived from the HTTP URL above.
MCP_URL = os.environ.get(
    "TERRAPIPE_OS_MCP_URL",
    TERRAPIPE_OS_URL.rsplit(":", 1)[0] + ":8201/mcp",
)

# The four demo fields, vendored into this repository rather than read out of
# terrapipe-os. terrapipe-os is private; pancake is not. Resolving these only
# from there meant an outside reviewer could not get as far as listing the
# fields, so the notebook's opening section failed on the thing that needs no
# services at all. The vendored copy is preferred even when terrapipe-os is
# present, so the demo behaves the same either way, and
# tests/test_demo_fields_vendored.py fails when the two have drifted apart.
_VENDORED_FIELDS = Path(__file__).resolve().parent / "honduras_demo_fields.geojson"
_UPSTREAM_FIELDS = (
    Path(__file__).resolve().parents[2] / "terrapipe-os" / "examples" / "honduras_demo_fields.geojson"
)
DEMO_FIELDS = Path(
    os.environ.get("DEMO_FIELDS")
    or (_VENDORED_FIELDS if _VENDORED_FIELDS.is_file() else _UPSTREAM_FIELDS)
)

LIVE, LOCAL, SKIPPED, FAILED = "LIVE", "LOCAL", "SKIPPED", "FAILED"

EMPTY = "EMPTY"
"""The service answered, and its answer was that it holds nothing.

A fifth outcome, because the first four could not say this and the ledger
therefore said something false. On 2026-09-06 the NDVI and GFS steps both got
``404 {"reason": "no_data"}`` -- the node has neither layer for any demo field
-- and both were recorded LIVE, because ``step`` records LIVE unless an
exception is raised and a 404 is not an exception. A reader scanning the
ledger saw

    [x] NDVI for a field          LIVE
    [x] GFS forecast for a field  LIVE

and concluded that vegetation and weather had been demonstrated. They had not.

None of the other four fits. It is not LIVE: nothing was shown. It is not
FAILED: nothing is broken, and calling a correct "I have no data" a failure
would train the reader to ignore failures. It is not SKIPPED: the call was
made. It is not LOCAL. The distinction it draws -- *the request worked and the
cupboard is bare* -- is exactly the one that tells you to go and fill the
cupboard, so it needs its own word.
"""


# --------------------------------------------------------------------------
# the ledger
# --------------------------------------------------------------------------


@dataclass
class Step:
    name: str
    outcome: str
    detail: str = ""
    seconds: float = 0.0


@dataclass
class Ledger:
    steps: list[Step] = field(default_factory=list)

    def record(self, name: str, outcome: str, detail: str = "", seconds: float = 0.0) -> None:
        """Record a step, replacing any earlier record of the same step.

        Replacing rather than appending, because a notebook is re-run in
        pieces. Someone reads section 5, scrolls back, runs the cell again to
        watch it happen -- and on 2026-09-06 that turned one step into two
        rows and the closing count from "15 against live services" into 18.
        The ledger exists to be the one part of this document that cannot
        overstate what ran, so counting a repeat as a second demonstration is
        the specific thing it must not do.

        The latest attempt wins, and keeps its original position: a step that
        succeeded and then failed on re-run should read as failed, and a
        reader following the narrative should still find it where it was.
        """
        fresh = Step(name, outcome, detail, seconds)
        for i, existing in enumerate(self.steps):
            if existing.name == name:
                self.steps[i] = fresh
                return
        self.steps.append(fresh)

    def checklist(self) -> str:
        """What actually happened, generated from what actually happened.

        Written from the ledger rather than typed by hand, because a
        hand-written summary of a notebook is a claim about a previous run.
        """
        if not self.steps:
            return "No steps were recorded."
        width = max(len(s.name) for s in self.steps)
        # EMPTY gets an unticked box. It is not a success, and a ticked box is
        # read as one however the word beside it reads.
        mark = {LIVE: "[x]", LOCAL: "[x]", EMPTY: "[ ]", SKIPPED: "[ ]", FAILED: "[!]"}
        lines = [f"{mark[s.outcome]} {s.name.ljust(width)}  {s.outcome:8}{('  ' + s.detail) if s.detail else ''}"
                 for s in self.steps]
        counts = {o: sum(1 for s in self.steps if s.outcome == o)
                  for o in (LIVE, LOCAL, EMPTY, SKIPPED, FAILED)}
        lines.append("")
        lines.append(
            f"{counts[LIVE]} against live services, {counts[LOCAL]} against local data, "
            f"{counts[EMPTY]} answered with no data, {counts[SKIPPED]} skipped, "
            f"{counts[FAILED]} failed."
        )
        if counts[EMPTY]:
            lines.append(
                "A step marked EMPTY reached the node and the node holds nothing for it. "
                "Nothing is broken and nothing was demonstrated; the layer needs ingesting."
            )
        if counts[SKIPPED]:
            lines.append("A skipped step demonstrated nothing. Bring the stack up to close the gap.")
        if counts[FAILED]:
            lines.append("A failed step is a real defect or a misconfiguration; read its reason above.")
        return "\n".join(lines)


LEDGER = Ledger()


@contextmanager
def step(name: str, *, outcome: str = LIVE) -> Iterator[dict[str, Any]]:
    """Run a step, record what became of it, and never let it stop the notebook.

    A raised exception is recorded as FAILED and swallowed, so that one
    unavailable service does not truncate the document. The ledger is what
    makes that safe: a swallowed failure is still visible at the end.
    """
    state: dict[str, Any] = {"outcome": outcome, "detail": ""}
    started = time.time()
    try:
        yield state
    except Exception as exc:  # noqa: BLE001 - reported, not hidden
        state["outcome"] = FAILED
        state["detail"] = f"{type(exc).__name__}: {exc}"[:200]
        print(f"  {FAILED}: {state['detail']}")
    finally:
        LEDGER.record(name, state["outcome"], state["detail"], time.time() - started)
        print(f"  -> {name}: {state['outcome']}{('  (' + state['detail'] + ')') if state['detail'] else ''}")


def skip(state: dict[str, Any], reason: str) -> None:
    state["outcome"] = SKIPPED
    state["detail"] = reason
    print(f"  skipped: {reason}")


def empty(state: dict[str, Any], reason: str) -> None:
    """The call was made and the node holds no data for it. See EMPTY."""
    state["outcome"] = EMPTY
    state["detail"] = reason
    print(f"  no data: {reason}")


def holds_data(response, state: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Whether a read actually returned a reading, and why not if it did not.

    terrapipe-os is careful to distinguish "I have no value for you" from "your
    request was wrong", and answers the first with 404 and ``reason: no_data``.
    That is good API design and it defeated the ledger, which treats any
    non-exception as a success. So the classification happens here, once, and
    the steps that read data call it rather than each deciding for itself.

    Passing ``state`` marks the step EMPTY as a side effect, which is the
    common case and keeps the calling cell to one line.
    """
    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.status_code == HTTP_OK and body.get("reason") != "no_data":
        return True, "the node returned a reading"

    why = body.get("detail") or body.get("reason") or f"HTTP {response.status_code}"
    if state is not None:
        # A wrong request is a defect in this notebook, not a bare cupboard,
        # and must not be filed under the same word.
        if body.get("reason") == "invalid_request":
            state["outcome"] = FAILED
            state["detail"] = str(why)[:200]
            print(f"  bad request: {why}")
        else:
            empty(state, str(why)[:200])
    return False, str(why)


def local(state: dict[str, Any], reason: str) -> None:
    state["outcome"] = LOCAL
    state["detail"] = reason


# --------------------------------------------------------------------------
# what is reachable
# --------------------------------------------------------------------------


def _reachable(url: str, path: str = "/health", timeout: float = 2.0) -> tuple[bool, str]:
    try:
        response = requests.get(f"{url}{path}", timeout=timeout)
        return response.status_code < 500, f"HTTP {response.status_code}"
    except requests.RequestException as exc:
        return False, type(exc).__name__


def services() -> dict[str, dict[str, Any]]:
    """Which parts of the stack answer right now."""
    checks = {
        "hub": (HUB_URL, "/.well-known/jwks.json"),
        "ar2-node": (NODE_URL, "/docs"),
        "pancake": (PANCAKE_URL, "/healthz"),
        "terrapipe-os": (TERRAPIPE_OS_URL, "/health"),
    }
    out = {}
    for name, (url, path) in checks.items():
        up, detail = _reachable(url, path)
        out[name] = {"url": url, "up": up, "detail": detail}
    return out


def mode(stack: dict[str, dict[str, Any]]) -> str:
    """Whether the notebook can run, and if not, which of two problems it is.

    Four DOWN lines against localhost mean the notebook was never told which
    deployment to talk to. That is a different problem from an outage, and until
    2026-09-06 it read as the same one: the URLs defaulted to localhost, so a
    kernel that had not been handed five environment variables reported the
    whole stack down and skipped the run.
    """
    if stack["terrapipe-os"]["up"]:
        return "mode: LIVE against the hosted node"

    down = [name for name, info in stack.items() if not info["up"]]
    head = (
        "mode: SKIPPED. Nothing here computes a reading in this process, "
        "by design, so there is no substitute for the node."
    )

    # Third case, and the likeliest one for somebody's first run: demo.env was
    # copied from the example and never edited, so the addresses are the
    # template's angle-bracketed placeholders. Saying "this looks like a real
    # outage" about <node-host> sends them to ask an operator why the deployment
    # is down.
    unfilled = [name for name in down if "<" in stack[name]["url"]]
    if unfilled:
        return (
            f"{head}\n\n"
            f"{SETTINGS_FILE.name} still has the example's placeholders in it "
            f"({stack[unfilled[0]]['url']}).\n"
            "Replace the angle-bracketed parts with the addresses of a real deployment\n"
            "and restart the kernel. See README-openscience.md."
        )

    local = ("localhost", "127.0.0.1")
    if all(any(host in stack[name]["url"] for host in local) for name in down):
        return (
            f"{head}\n\n"
            "Every address above is localhost, which is the default when no deployment\n"
            "has been named. This is far more likely to be configuration than an outage:\n\n"
            f"    cd {SETTINGS_FILE.parent}\n"
            f"    cp demo.env.example {SETTINGS_FILE.name}   # then fill it in\n\n"
            "and restart the kernel. A real environment variable overrides the file."
        )
    return (
        f"{head}\n\nThe addresses came from settings, so this looks like a real outage.\n"
        f"Not answering: {', '.join(down)}."
    )


class _NoLocalBackend:
    """Import hook that refuses to load the terrapipe-os backend in this kernel."""

    BLOCKED = ("terrapipe_os",)

    def find_module(self, fullname, path=None):  # pragma: no cover - legacy protocol
        return self.find_spec(fullname, path)

    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root in self.BLOCKED:
            raise ImportError(
                f"{fullname} must not be imported by this notebook. Every reading "
                "here comes from the hosted node over HTTP; computing the same "
                "numbers in this process would prove nothing about the operator's "
                "deployment. See openscience_demo.forbid_local_backend()."
            )
        return None


def forbid_local_backend() -> str:
    """Make a local backend impossible rather than merely unused.

    Every reading in this notebook has to come from the hosted node, because
    that is the thing being demonstrated: a node an operator runs, against
    rasters an operator mirrored, answering about a field it was given consent
    to look at. Computing the same numbers in this process would produce
    identical output while proving none of it, and would turn a node outage into
    a green run.

    The notebook did exactly that until 2026-09-06 -- four steps fell back to an
    in-process terrapipe_os and reported LOCAL, which is honest labelling of the
    wrong thing to be doing. Saying "nothing below imports it" would be a claim
    about code a reader has to go and verify. This makes the claim enforceable:
    if any cell below reaches for the backend, it raises.
    """
    # By name rather than isinstance: the notebook reloads this module, which
    # rebinds _NoLocalBackend to a new class object, and an isinstance check
    # against the old one would miss the hook already installed and stack a
    # second copy on every reload.
    already_blocked = any(type(hook).__name__ == "_NoLocalBackend" for hook in sys.meta_path)
    installed = False
    if not already_blocked:
        try:
            installed = importlib.util.find_spec("terrapipe_os") is not None
        except ImportError:
            installed = False
        sys.meta_path.insert(0, _NoLocalBackend())
    for name in list(sys.modules):
        if name.split(".")[0] in _NoLocalBackend.BLOCKED:
            del sys.modules[name]
    where = (
        "it is installed in this kernel, and is now unimportable"
        if installed
        else "it is not installed here either"
    )
    return f"local terrapipe-os backend blocked: {where}"


# --------------------------------------------------------------------------
# the demo fields
# --------------------------------------------------------------------------


def demo_fields() -> list[dict[str, Any]]:
    """Four Honduran fields, placed by what the real rasters actually say.

    Their boundaries are synthetic and each one says so in its own
    ``boundary`` property: they are S2 cells, not surveyed farms. What is not
    synthetic is where they are. ``bin/place-demo-fields`` scanned the ingested
    national rasters for cells that genuinely tell each story -- coffee never
    cleared, coffee cleared after the cut-off, coffee cleared decades ago --
    so the screen results below are real readings of real public data about
    real places.
    """
    if not DEMO_FIELDS.is_file():
        raise FileNotFoundError(
            f"{DEMO_FIELDS} not found. A copy is vendored at dpi-demo/honduras_demo_fields.geojson; "
            "if it is missing here, regenerate it with bin/place-demo-fields in terrapipe-os."
        )
    return json.loads(DEMO_FIELDS.read_text())["features"]


def mcp_tools(token: str | None = None) -> list[tuple[str, str]]:
    """The agent-facing tools, asked of the hosted MCP server over HTTP.

    Built in process against a local terrapipe_os until 2026-09-06, which listed
    the tools this checkout defines rather than the ones the operator's node
    actually offers. Those are different claims, and only the second is worth
    demonstrating.
    """
    import httpx  # noqa: PLC0415
    from mcp.client.session import ClientSession  # noqa: PLC0415
    from mcp.client.streamable_http import streamable_http_client  # noqa: PLC0415

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def ask() -> list[tuple[str, str]]:
        async with httpx.AsyncClient(headers=headers, timeout=60) as http:
            async with streamable_http_client(MCP_URL, http_client=http) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    return sorted(
                        (t.name, (t.description or "").split(".")[0].strip()) for t in listed.tools
                    )

    return run_async(ask)


def publication_gate(token: str | None = None) -> tuple[int, str]:
    """Ask the hosted node to publish a layer without a publish credential.

    The point is the refusal and where it comes from. Read out of a local gate
    object until 2026-09-06, which demonstrated that this checkout contains a
    rule, not that the operator's node enforces one.
    """
    response = post(
        f"{TERRAPIPE_OS_URL}/layers",
        token=token,
        json={"layer_id": "demo_probe_not_a_real_layer", "title": "probe"},
    )
    try:
        body = response.json()
        detail = body.get("detail") or body.get("reason") or json.dumps(body)[:200]
    except ValueError:
        detail = response.text[:200]
    return response.status_code, str(detail)


def dds_export(
    geojson: dict[str, Any],
    *,
    country: str,
    token: str | None = None,
    grants: dict[str, str] | None = None,
    include_producer_name: bool = False,
) -> dict[str, Any]:
    """Turn screened plots into a DDS-ready GeoJSON, on the hosted node.

    ``grants`` maps GeoID to the credential that unlocks it. The node screens
    each plot as it goes, so a plot without a grant comes back with its geometry
    and no finding rather than a field-scoped verdict nobody consented to. The
    grant travels in the body here, one per GeoID, because a filing can span
    fields belonging to different owners.
    """
    response = post(
        f"{TERRAPIPE_OS_URL}/dds",
        token=token,
        json={
            "collection": geojson,
            "producer_country": country,
            "grants": grants or {},
            "include_producer_name": include_producer_name,
        },
    )
    if not response.ok:
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        raise RuntimeError(
            f"POST /dds returned {response.status_code} "
            f"({body.get('reason', 'no reason given')}): {body.get('detail', response.text[:200])}"
        )
    return response.json()


# --------------------------------------------------------------------------
# presenting a screen
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# maps
# --------------------------------------------------------------------------
#
# A field, a verdict and a neighbourhood cell are all shapes on the ground, and
# a table of decimals is a poor way to show a reader what "the screen covered
# 80 km² instead of your 8 ha" means. Leaflet, via folium, because it renders
# from the saved notebook without a running kernel or a widget extension.
#
# Optional throughout: a reader without folium gets the tables and a line saying
# what to install. Nothing below is on the path to any reading.

VERDICT_COLOUR = {
    "deforestation_detected": "#c0392b",
    "no_deforestation_detected": "#1e8449",
    "inconclusive": "#b7791f",
}

SATELLITE = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
SATELLITE_ATTRIBUTION = "Imagery: Esri, Maxar, Earthstar Geographics, GIS User Community"

GREY = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/"
    "World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
)
GREY_ATTRIBUTION = "Esri, HERE, Garmin, © OpenStreetMap contributors"
"""Esri's Light Gray Canvas, named by URL rather than through folium's shorthand.

folium's built-in ``cartodbpositron`` would have been the obvious grey basemap,
and it emits a warning that CartoDB now requires an API key -- a demo whose
basemap silently stops loading for the next reader is worse than one that never
offered it. This is keyless, and it is the same provider as the satellite layer
already here, so it adds no new dependency to be down.
"""

ACCENT = "#d81b60"
"""One colour for every drawn shape, so the basemap carries none of the meaning.

Satellite imagery of the Honduran coffee belt is green, brown and mottled, and a
thin green polygon on it is invisible -- which is what these maps looked like
until 2026-09-06. The fix is on both sides: the tiles are desaturated to grey,
and everything drawn on top is this one saturated colour. Where two shapes need
telling apart they differ in weight, dash and fill rather than in hue, because a
second hue is a second thing for the reader to decode.

The exception is a colour that carries a reading rather than a distinction --
the verdicts below. Those are the map's content, the same way a raster's own
palette is.
"""

ACCENT_TINT = "#f48fb1"
"""The same hue, lighter, for the secondary half of a pair on one map."""

OUTLINE = "#1a1a1a"
"""For an outline that must read against a coloured fill.

White worked on satellite imagery and disappears on a light grey basemap, which
is the kind of thing that only shows up when you look at the rendered map.
"""

TILE_GREYSCALE = "<style>.leaflet-tile-pane{filter:grayscale(100%) contrast(0.85) opacity(0.9);}</style>"
"""Desaturate the tiles and nothing else.

Leaflet keeps basemap tiles in ``.leaflet-tile-pane`` and drawn vectors in the
overlay pane above it, so a filter scoped to that one pane turns every basemap
black and white -- including the satellite imagery -- while leaving the polygons
their full colour. Doing it in CSS rather than by choosing grey tiles means the
imagery stays available as a base layer instead of being dropped.
"""


def have_folium() -> bool:
    return importlib.util.find_spec("folium") is not None


def maps_unavailable() -> str:
    """Why there is no map here, and the one command that fixes it.

    The first cell installs everything in requirements.txt, so reaching this at
    all means either that cell was skipped or the install failed. Naming the
    requirements file rather than `pip install folium` keeps one declaration of
    what this notebook needs instead of two that can disagree.
    """
    return (
        f"maps need folium, which is not installed in this kernel.\n"
        f"  Run the first cell, which installs everything in requirements.txt, or:\n"
        f"      cd {SETTINGS_FILE.parent} && pip install -r requirements.txt\n"
        f"  Everything else in this notebook runs without it."
    )


def s2_cell_ring(token: str) -> list[list[float]]:
    """The four corners of an S2 cell as [lat, lon] pairs, for drawing.

    Computed here rather than asked of the node: it is geometry, not a reading,
    and s2sphere is the same library the node uses. Nothing about the *data*
    is decided locally.
    """
    import s2sphere  # noqa: PLC0415

    cell = s2sphere.Cell(s2sphere.CellId.from_token(token))
    ring = []
    for corner in range(4):
        point = s2sphere.LatLng.from_point(cell.get_vertex(corner))
        ring.append([point.lat().degrees, point.lng().degrees])
    ring.append(ring[0])
    return ring


def _ring_of(feature: dict[str, Any]) -> list[list[float]]:
    """A GeoJSON polygon's outer ring as [lat, lon], which is Leaflet's order.

    GeoJSON positions are [lon, lat]; Leaflet wants [lat, lon]. Swapping them
    silently puts Honduras in the Indian Ocean, so it happens in one place.
    """
    return [[lat, lon] for lon, lat in feature["geometry"]["coordinates"][0]]


MASKED_LEVEL = 10
"""The S2 level AR2 masks a GeoID to when no grant is presented.

Not a guess: asked of the deployment on 2026-09-06. ``GET /fetch-field/{id}``
without a grant answers ``MaskingLevel: L0`` and a level-10 cell token; the same
call with a field grant answers ``L1`` and the registered boundary. The maps
draw both, so this constant has to be what AR2 actually does rather than what
the demo would like it to do.
"""

DISCLOSURE = {
    "L0": (
        "#5b6b73",
        "6, 6",
        f"L0 masked: the S2 level-{MASKED_LEVEL} cell AR2 answers with, no grant needed",
    ),
    "L1": (ACCENT, None, "L1 disclosed: the registered boundary, only with a grant"),
}
"""Colour, dash pattern and legend wording per disclosure tier.

The one place hue is allowed to mean something other than "a shape": a reader
should be able to tell a masked answer from a disclosed one without reading a
tooltip. Masked is grey and dotted because it is the *less* informative answer,
and a dotted grey outline looks approximate, which it is -- 81 km² standing in
for three hectares.
"""

MIN_MARGIN = 0.002
"""About 220 m, the smallest margin worth leaving around a fitted shape.

Fitted exactly, a three-hectare field fills the frame corner to corner with no
surroundings to place it against, and Leaflet zooms in past the last tile the
imagery has.
"""


def _bounds(rings: list[list[list[float]]], *, pad: float = 0.12) -> list[list[float]]:
    """The [[south, west], [north, east]] box holding every ring, plus a margin."""
    points = [point for ring in rings for point in ring]
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    south, north, west, east = min(lats), max(lats), min(lons), max(lons)
    down = max((north - south) * pad, MIN_MARGIN)
    across = max((east - west) * pad, MIN_MARGIN)
    return [[south - down, west - across], [north + down, east + across]]


def _basemap(rings: list[list[list[float]]]):
    """A black-and-white basemap, fitted to the shapes about to go on it.

    Fitted rather than given a fixed zoom: these maps run from one three-hectare
    field to the whole of Honduras, and a zoom level hand-picked to frame one of
    them cut the others off at the edge of the view.

    Grey rather than satellite, because the fields sit in the coffee belt and a
    thin coloured polygon over green-and-brown imagery is invisible -- which is
    what these maps looked like until 2026-09-06. The imagery is still here as a
    base layer for anyone who wants to see the ground; the CSS filter desaturates
    it too, so the drawn shapes stay the only coloured thing on any base layer.
    """
    import folium  # noqa: PLC0415

    canvas = folium.Map(tiles=None, control_scale=True)
    folium.TileLayer(GREY, attr=GREY_ATTRIBUTION, name="Grey basemap").add_to(canvas)
    folium.TileLayer(
        SATELLITE, attr=SATELLITE_ATTRIBUTION, name="Satellite imagery", show=False
    ).add_to(canvas)
    canvas.get_root().header.add_child(folium.Element(TILE_GREYSCALE))
    canvas.fit_bounds(_bounds(rings))
    return canvas


PIN_UNTIL_ZOOM = 12
"""Above this zoom the dots fade and the boundaries speak for themselves.

Every field here is a polygon -- a four-cornered S2 level-15 cell of about eight
hectares -- and the dot exists only because eight hectares at national zoom is
smaller than one screen pixel. Left on as you zoom in it becomes the opposite
problem: a fixed 12-pixel disc sitting on top of the boundary it was standing in
for, so the reader sees a point where there is a shape.

Around zoom 12 a field is a few pixels across and starting to read as an area,
which is the moment to hand over.
"""


def _pin(group, feature: dict[str, Any], colour: str, tooltip: str, popup=None) -> None:
    """A fixed-size dot on the field, for the maps that show the whole country.

    Eight hectares at national zoom is smaller than one screen pixel, so on the
    verdict map the four fields were invisible until you zoomed into each one --
    which defeats a map whose job is to show all four verdicts at once. A circle
    marker is sized in pixels rather than in degrees, so it stays legible where
    the polygon cannot be.

    It is a stand-in, not the thing, so it gets out of the way: see
    ``_hand_over_to_the_boundaries``.
    """
    import folium  # noqa: PLC0415

    ring = _ring_of(feature)
    centre = [
        sum(point[0] for point in ring) / len(ring),
        sum(point[1] for point in ring) / len(ring),
    ]
    folium.CircleMarker(
        location=centre,
        radius=6,
        color=colour,
        weight=2,
        fill=True,
        fill_color=colour,
        fill_opacity=0.9,
        tooltip=tooltip,
        popup=popup,
    ).add_to(group)


def _hand_over_to_the_boundaries(canvas, threshold: int = PIN_UNTIL_ZOOM) -> None:
    """Fade the dots out once the polygons are big enough to see.

    Leaflet has no declarative way to say "this layer applies below zoom N", so
    this is a zoomend handler. It walks into feature groups because the markers
    are inside them rather than directly on the map, and it leaves the polygons
    alone -- only ``CircleMarker`` is touched, and ``L.Circle`` is excluded
    because Leaflet makes it a subclass and it is measured in metres, not pixels.

    Nothing here decides anything about the data; it is presentation, and if the
    script fails the map is still correct, just with a dot on top of a boundary.
    """
    # A MacroElement on the map, rather than an Element on the figure. Both of
    # the obvious placements run too early: figure.html renders into the body
    # ahead of the map's script block, and figure.script renders ahead of it too
    # -- measured, after the first attempt blanked the map completely. The
    # reference to an undefined map variable threw, which aborted the rest of
    # that script block, which included the call that sets the view and loads
    # the tiles. A MacroElement's script macro is emitted inside the map's own
    # block, after everything added before it.
    canvas.add_child(_HandOver(threshold))


class _HandOver(MacroElement):
    """The zoomend handler above, placed so that it runs after the map exists."""

    _template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
            var map = {{ this._parent.get_name() }};
            function fade(layer, hidden) {
                if (layer instanceof L.CircleMarker && !(layer instanceof L.Circle)) {
                    layer.setStyle({
                        opacity: hidden ? 0 : 1,
                        fillOpacity: hidden ? 0 : 0.9,
                    });
                } else if (layer.eachLayer) {
                    layer.eachLayer(function (inner) { fade(inner, hidden); });
                }
            }
            function tune() {
                // Guarded: this is decoration, and an exception here would take
                // the rest of the map's script down with it.
                try {
                    var hidden = map.getZoom() >= {{ this.threshold }};
                    map.eachLayer(function (layer) { fade(layer, hidden); });
                } catch (e) { /* no view yet; zoomend will call again */ }
            }
            map.on('zoomend', tune);
            map.on('overlayadd', tune);
            map.whenReady(tune);
        })();
        {% endmacro %}
    """)

    def __init__(self, threshold: int) -> None:
        super().__init__()
        self._name = "HandOverToTheBoundaries"
        self.threshold = threshold


def _cell_area_km2(token: str) -> float:
    """A cell's area on the sphere, so a legend can say what "L10" is worth."""
    import s2sphere  # noqa: PLC0415

    return s2sphere.Cell(s2sphere.CellId.from_token(token)).exact_area() * EARTH_RADIUS_KM**2


EARTH_RADIUS_KM = 6371.0088


def masked_ring(feature: dict[str, Any], level: int = MASKED_LEVEL) -> tuple[list[list[float]], str]:
    """The cell a reader without a grant would be given instead of this field."""
    import s2sphere  # noqa: PLC0415

    cell = s2sphere.CellId.from_token(feature["properties"]["s2_token"]).parent(level)
    return s2_cell_ring(cell.to_token()), cell.to_token()


def _add_masked(canvas, features: list[dict[str, Any]], *, show: bool = True) -> list[list[float]]:
    """Draw the L0 cell around every field, as its own layer, and return the rings.

    Every map that shows a boundary also shows what is released when nobody has
    consented to that boundary being seen. Keeping it a separate layer means a
    reader can switch between the two answers rather than take the caption's
    word for the difference.
    """
    import folium  # noqa: PLC0415

    colour, dashes, _ = DISCLOSURE["L0"]
    group = folium.FeatureGroup(name=f"L0 masked cells (S2 level {MASKED_LEVEL})", show=show)
    rings = []
    for feature in features:
        ring, token = masked_ring(feature)
        rings.append(ring)
        folium.Polygon(
            locations=ring,
            color=colour,
            weight=2,
            dash_array=dashes,
            fill=True,
            fill_opacity=0.05,
            tooltip=(
                f"L0: {token}, S2 level {MASKED_LEVEL}, {_cell_area_km2(token):,.0f} km²"
                f" &mdash; what AR2 answers for {feature['properties']['title']} without a grant"
            ),
        ).add_to(group)
    group.add_to(canvas)
    return rings


def field_map(features: list[dict[str, Any]], *, screens: dict[str, dict[str, Any]] | None = None):
    """The demo fields on a satellite basemap, coloured by verdict if screened.

    Before the screens exist this is a map of where the four fields are. After
    they exist, pass ``screens`` and each field takes its verdict's colour, so
    the result of the whole notebook is legible in one picture.
    """
    import folium  # noqa: PLC0415

    rings = [_ring_of(feature) for feature in features]
    canvas = _basemap(rings)
    # Fitted to the fields, not to the masked cells around them. The cells are
    # context and they are enormous -- 81 km² against eight hectares -- so
    # including them in the fit pulled a single-field map out to a zoom where
    # the boundary was two pixels and the dot never handed over to it.
    _add_masked(canvas, features, show=not screens)
    canvas.fit_bounds(_bounds(rings))

    # One layer per verdict, so a reader can isolate the cleared fields; one
    # layer for everything when there are no verdicts yet.
    groups: dict[str, Any] = {}
    for feature in features:
        name = feature["properties"]["name"]
        screen = (screens or {}).get(name)
        verdict = (screen or {}).get("verdict")
        colour = VERDICT_COLOUR.get(verdict, ACCENT)
        label = f"L1 boundaries: {verdict}" if verdict else "L1 registered boundaries"
        if label not in groups:
            groups[label] = folium.FeatureGroup(name=label, show=True)

        lines = [
            f"<b>{feature['properties']['title']}</b>",
            f"{feature['properties']['area_ha']:.2f} ha",
        ]
        if screen:
            lines += [
                f"verdict: <b>{verdict}</b> ({screen.get('scope')} scope)",
                f"cleared after {screen.get('cutoff_year')}: "
                f"{screen.get('deforested_fraction', 0):.4f}",
                f"measured: {screen.get('coverage_fraction', 0):.1%} of the field",
            ]
        else:
            lines.append(f"<i>{feature['properties']['narrative'][:160]}</i>")

        folium.Polygon(
            locations=_ring_of(feature),
            color=colour,
            weight=2,
            fill=True,
            fill_opacity=0.35,
            popup=folium.Popup("<br>".join(lines), max_width=320),
            tooltip=feature["properties"]["title"],
        ).add_to(groups[label])
        _pin(
            groups[label],
            feature,
            colour,
            feature["properties"]["title"],
            popup=folium.Popup("<br>".join(lines), max_width=320),
        )

    for group in groups.values():
        group.add_to(canvas)

    entries = [(DISCLOSURE["L0"][2], DISCLOSURE["L0"][0], "dashed")]
    if screens:
        seen = {s.get("verdict") for s in screens.values()}
        entries += [
            (f"L1 disclosed: {verdict}", colour, "solid")
            for verdict, colour in VERDICT_COLOUR.items()
            if verdict in seen
        ]
    else:
        entries.append((DISCLOSURE["L1"][2], ACCENT, "solid"))
    _legend(canvas, entries, title="Verdict" if screens else "Disclosure tier")
    _hand_over_to_the_boundaries(canvas)
    folium.LayerControl(collapsed=False).add_to(canvas)
    return canvas


def masked_cell(geo_id: str, token: str) -> tuple[str | None, str]:
    """The cell AR2 hands back for a GeoID when no grant is presented.

    Asked of AR2 rather than derived, so the map below draws the disclosure the
    registry actually made. Deriving it would produce the same token today and
    would still be our claim about AR2's behaviour rather than AR2's behaviour.
    """
    try:
        response = requests.get(
            f"{NODE_URL}/fetch-field/{geo_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return None, f"AR2 could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return None, f"AR2 answered HTTP {response.status_code}"
    body = response.json() or {}
    cell = (body.get("Geo Data") or {}).get("cell_token")
    level = body.get("MaskingLevel")
    if not cell:
        return None, f"AR2 returned no cell token at masking level {level}"
    return cell, f"AR2 masked this GeoID to {cell} at {level}"


def consent_map(
    feature: dict[str, Any],
    *,
    neighbourhood_level: int = 10,
    neighbourhood_token: str | None = None,
):
    """One field, and the neighbourhood cell answered for without a grant.

    This is the picture that makes disclosure tiering obvious: the ungranted
    answer describes the large cell, the granted answer describes the small
    shape inside it, and the ratio between the two areas is why a finding
    inside one field nearly vanishes when diluted across the other.

    Pass ``neighbourhood_token`` to draw the cell AR2 itself returned. Without
    it the cell is derived from the field's own token, which lands in the same
    place but is our arithmetic rather than the registry's answer.
    """
    import folium  # noqa: PLC0415
    import s2sphere  # noqa: PLC0415

    token = feature["properties"]["s2_token"]
    if neighbourhood_token:
        coarse = s2sphere.CellId.from_token(neighbourhood_token)
        neighbourhood_level = coarse.level()
    else:
        coarse = s2sphere.CellId.from_token(token).parent(neighbourhood_level)
    coarse_token = coarse.to_token()
    coarse_ring = s2_cell_ring(coarse_token)
    field_ring = _ring_of(feature)

    canvas = _basemap([coarse_ring, field_ring])

    masked_colour, dashes, masked_label = DISCLOSURE["L0"]
    masked = folium.FeatureGroup(name=f"L0 masked cell (S2 level {neighbourhood_level})", show=True)
    folium.Polygon(
        locations=coarse_ring,
        color=masked_colour,
        weight=2,
        dash_array=dashes,
        fill=True,
        fill_opacity=0.08,
        tooltip=(
            f"L0: {coarse_token}, S2 level {neighbourhood_level}, "
            f"{_cell_area_km2(coarse_token):,.0f} km² &mdash; answered without a grant"
        ),
    ).add_to(masked)
    masked.add_to(canvas)

    disclosed = folium.FeatureGroup(name="L1 registered boundary", show=True)
    folium.Polygon(
        locations=field_ring,
        color=ACCENT,
        weight=2,
        fill=True,
        fill_opacity=0.5,
        tooltip=(
            f"L1: {feature['properties']['area_ha']:.2f} ha &mdash; answered only with a grant"
        ),
    ).add_to(disclosed)
    disclosed.add_to(canvas)

    _legend(
        canvas,
        [
            (masked_label.replace(f"level-{MASKED_LEVEL}", f"level-{neighbourhood_level}"),
             masked_colour, "dashed"),
            (DISCLOSURE["L1"][2], ACCENT, "solid"),
        ],
        title="Disclosure tier",
    )
    folium.LayerControl(collapsed=False).add_to(canvas)
    return canvas


def s2_cover(feature: dict[str, Any], token: str) -> tuple[list[str], str]:
    """The S2 cover AR2 derived for this geometry, asked of AR2.

    Registration is idempotent on the geometry -- an already-registered shape
    comes back in about 70 ms with its cover attached -- so this costs a round
    trip rather than a new field, and returns the registry's own cover instead
    of a second implementation of the covering algorithm that would agree today
    and drift later.
    """
    try:
        response = requests.post(
            f"{NODE_URL}/register-field-boundary",
            json={
                "wkt": wkt_of(feature["geometry"]),
                "return_s2_indices": True,
                "s2_index": "15,20",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return [], f"AR2 could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return [], f"AR2 answered HTTP {response.status_code}"
    cover = ((response.json() or {}).get("S2 Cell Tokens") or {}).get("v2_cover") or []
    if not cover:
        return [], "AR2 returned no v2 cover for this geometry"
    return cover, f"AR2's own v2 cover: {len(cover)} cells"


def cover_map(feature: dict[str, Any], cover: list[str]):
    """The field, and the S2 cells the screen actually read for it.

    The one picture that explains why the numbers do not land exactly on what
    was placed. The placer read a single L15 cell; the screen reads AR2's cover
    of the polygon registered from that cell's corners, which is the L15 cell
    plus a skirt of much smaller cells hugging the boundary. That skirt is real
    ground just outside the original cell, and it pulls the field's figures
    towards its surroundings.
    """
    import folium  # noqa: PLC0415
    import s2sphere  # noqa: PLC0415

    by_level: dict[int, list[str]] = {}
    for cell in cover:
        by_level.setdefault(s2sphere.CellId.from_token(cell).level(), []).append(cell)

    field_ring = _ring_of(feature)
    cover_rings = [s2_cell_ring(cell) for cell in cover]
    canvas = _basemap([field_ring, *cover_rings])

    core = min(by_level) if by_level else None
    # One hue, two weights: the field's own cell and the skirt of refinement
    # around its edge are the same kind of thing at two scales, not two kinds.
    entries = []
    for level, cells in sorted(by_level.items()):
        is_core = level == core
        colour = ACCENT if is_core else ACCENT_TINT
        what = "the field's own cell" if is_core else "boundary refinement"
        label = f"S2 level {level}: {len(cells)} cell{'s' if len(cells) != 1 else ''} ({what})"
        group = folium.FeatureGroup(name=label, show=True)
        for cell in cells:
            folium.Polygon(
                locations=s2_cell_ring(cell),
                color=colour,
                weight=1,
                fill=True,
                fill_opacity=0.2 if is_core else 0.6,
                tooltip=f"S2 level {level}: {cell}",
            ).add_to(group)
        group.add_to(canvas)
        entries.append((label, colour, "solid"))

    boundary = folium.FeatureGroup(name="L1 registered boundary", show=True)
    folium.Polygon(
        locations=field_ring,
        color=OUTLINE,
        weight=2,
        fill=False,
        tooltip="the registered boundary",
    ).add_to(boundary)
    boundary.add_to(canvas)
    entries.append(("L1 disclosed: the registered boundary", OUTLINE, "solid"))

    # Off by default and deliberately not fitted to: the masked cell is some
    # 81 km² against a 300 m field, so framing it would shrink everything this
    # map exists to show into a dot. Available for anyone who wants the scale.
    masked_colour, dashes, masked_label = DISCLOSURE["L0"]
    ring, token = masked_ring(feature)
    away = folium.FeatureGroup(name="L0 masked cell (zoom out to see)", show=False)
    folium.Polygon(
        locations=ring,
        color=masked_colour,
        weight=2,
        dash_array=dashes,
        fill=False,
        tooltip=f"L0: {token}, {_cell_area_km2(token):,.0f} km²",
    ).add_to(away)
    away.add_to(canvas)
    entries.append((masked_label + " (off by default here)", masked_colour, "dashed"))

    _legend(canvas, entries, title="AR2's S2 cover")
    folium.LayerControl(collapsed=False).add_to(canvas)
    return canvas


# A bbox wider than this is not a statement about where the layer is so much as
# a statement that it is everywhere; drawn on a map of Honduras it would be a
# rectangle around the whole view, which tells the reader nothing.
WIDER_THAN_THE_MAP = 60.0


def coverage_map(features: list[dict[str, Any]], layers: list[dict[str, Any]]):
    """Each layer's declared extent, and the fields that fall inside or outside.

    This is what turns ``outside_coverage`` from a word in a refusal into
    something you can see: the oil palm map is a regional band across the north,
    three of the four fields are in the coffee belt to the south of it, and the
    node is right to refuse them rather than report no palm.
    """
    import folium  # noqa: PLC0415

    # Grouped by extent, not by layer: the four ICF layers share one national
    # bbox, and drawing four identical rectangles stacks them into a single
    # muddy outline that claims to be four things.
    shared: dict[tuple[float, ...], list[str]] = {}
    everywhere: list[str] = []
    undeclared: list[str] = []
    for layer in layers:
        bbox = (layer.get("coverage") or {}).get("bbox")
        layer_id = layer.get("layer_id", "?")
        if not bbox:
            undeclared.append(layer_id)
            continue
        west, south, east, north = bbox
        if east - west > WIDER_THAN_THE_MAP:
            everywhere.append(layer_id)
            continue
        shared.setdefault(tuple(bbox), []).append(layer_id)

    field_rings = [_ring_of(feature) for feature in features]
    extent_rings = [
        [[s, w], [n, w], [n, e], [s, e], [s, w]]
        for (w, s, e, n) in shared
    ]
    canvas = _basemap(field_rings + extent_rings)

    # Each extent is a layer of its own: switching the national one off is how a
    # reader sees that the palm band and the coffee belt do not overlap.
    entries = []
    for index, (bbox, ids) in enumerate(shared.items()):
        west, south, east, north = bbox
        colour = ACCENT if index == 0 else ACCENT_TINT
        label = ids[0] if len(ids) == 1 else f"{len(ids)} layers sharing one extent"
        group = folium.FeatureGroup(name=f"extent: {label}", show=True)
        folium.Rectangle(
            bounds=[[south, west], [north, east]],
            color=colour,
            weight=2,
            dash_array="4, 6",
            fill=True,
            fill_opacity=0.05,
            tooltip="declared extent of: " + ", ".join(ids),
        ).add_to(group)
        group.add_to(canvas)
        entries.append((f"{label}: declared extent", colour, "dashed"))

    fields = folium.FeatureGroup(name="L1 registered boundaries", show=True)
    for feature in features:
        folium.Polygon(
            locations=_ring_of(feature),
            color=OUTLINE,
            weight=2,
            fill=True,
            fill_opacity=0.9,
            tooltip=feature["properties"]["title"],
        ).add_to(fields)
        _pin(fields, feature, OUTLINE, feature["properties"]["title"])
    fields.add_to(canvas)
    entries.append(("the four demo fields", OUTLINE, "solid"))

    # Named rather than dropped. A layer missing from a coverage map should not
    # be missing silently, which is the same argument the readings make.
    if everywhere:
        entries.append((f"{len(everywhere)} wider than this map, not drawn", "#bdc3c7", "solid"))
    if undeclared:
        entries.append((f"{len(undeclared)} declaring no extent, not drawn", "#bdc3c7", "solid"))

    _legend(canvas, entries, title="Layer coverage")
    _hand_over_to_the_boundaries(canvas)
    folium.LayerControl(collapsed=False).add_to(canvas)
    return canvas


def _legend(canvas, entries: list[tuple[str, str, str]], *, title: str | None = None) -> None:
    """A plain HTML legend. folium has no first-class one.

    Each entry is (label, colour, style), where style is ``solid`` or
    ``dashed``. The style matters as much as the colour: a masked answer is
    drawn dotted on the map, and a legend that showed it as a solid block would
    not let a reader match the two.
    """
    import folium  # noqa: PLC0415

    rows = []
    for label, colour, style in entries:
        if style == "dashed":
            swatch = (
                f"display:inline-block;width:14px;height:0;margin:0 6px 3px 0;"
                f"vertical-align:middle;border-top:3px dashed {colour}"
            )
        else:
            swatch = (
                f"display:inline-block;width:14px;height:12px;margin-right:6px;"
                f"vertical-align:middle;background:{colour};opacity:0.85"
            )
        # The class is what tests read. Scraping the inline style instead meant
        # that restyling the swatch broke two checks that had no opinion about
        # styling, which is a check that fires on the wrong thing.
        rows.append(
            f'<div class="legend-row" style="margin:3px 0">'
            f'<span class="legend-swatch" data-style="{style}" style="{swatch}"></span>'
            f'<span class="legend-label">{label}</span></div>'
        )

    heading = (
        f'<div style="font-weight:600;margin-bottom:4px">{title}</div>' if title else ""
    )
    canvas.get_root().html.add_child(
        folium.Element(
            f'<div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:white;'
            f'padding:8px 10px;border:1px solid #999;border-radius:4px;font:12px sans-serif;'
            f'max-width:340px;line-height:1.35">{heading}{"".join(rows)}</div>'
        )
    )


def show_screen(screen: dict[str, Any], *, indent: str = "  ") -> None:
    """Print a screen the way it should be read: verdict, then what qualifies it."""
    verdict = screen.get("verdict")
    coverage = screen.get("coverage_fraction")
    print(f"{indent}verdict          {verdict}   (scope: {screen.get('scope')})")
    print(f"{indent}cut-off          {screen.get('cutoff_year')}")
    fraction = screen.get("deforested_fraction")
    print(f"{indent}cleared after    {'-' if fraction is None else format(fraction, '.4f')}")
    print(f"{indent}coverage         {'-' if coverage is None else format(coverage, '.4f')}"
          f"   (threshold {screen.get('coverage_threshold')})")

    commodity = screen.get("commodity") or {}
    if "coffee_fraction" in commodity:
        print(f"{indent}coffee           {commodity['coffee_fraction']:.4f}")

    years = {k: v for k, v in (screen.get("deforested_by_year") or {}).items() if str(k) != "0" and v}
    if years:
        ordered = sorted(years.items(), key=lambda kv: str(kv[0]))
        print(f"{indent}by year          " + ", ".join(f"{y}: {v:.4f}" for y, v in ordered[:8]))

    for layer_id, reason, note in _absent_layers(screen):
        print(f"{indent}no answer from   {layer_id}  ({reason})")
        print(f"{indent}                 {textwrap.shorten(note, 96)}")
        print(f"{indent}                 absent is not zero: it is not counted either way")
    for caveat in screen.get("caveats") or []:
        print(f"{indent}caveat           {caveat}")


def evidence_rows(screen: dict[str, Any]) -> list[dict[str, Any]]:
    """Every layer the screen consulted, flattened the way the node groups them.

    Mirrors ``DeforestationScreen.evidence`` so that "which layers were
    consulted" has one answer here and in the node.
    """
    items = []
    primary = screen.get("primary")
    if isinstance(primary, dict):
        items.append(primary)
    for block in ("second_opinion", "commodity"):
        section = screen.get(block)
        if isinstance(section, dict):
            items.extend(e for e in section.get("evidence", []) if isinstance(e, dict))
    items.extend(e for e in (screen.get("context") or []) if isinstance(e, dict))
    return items


ABSENCE_MEANS = {
    "outside_coverage": "the layer does not cover this field",
    "not_mirrored": "the layer is not on this node's share",
    "no_data": "the layer covers this field but holds no value here",
    "not_in_library": "the layer is not in this node's library",
}


LAYER_NOTES = {
    "ndvi_sentinel2": "Greenness, per date. How a field's vegetation moves through the year.",
    "jrc_tmf_deforestation_year": (
        "The year each pixel was first cleared, 1990-2025. This is the layer the EUDR "
        "cut-off is applied to, and the primary evidence behind every verdict below."
    ),
    "jrc_tmf_degradation_year": "The year each pixel was first degraded, which is not clearing.",
    "jrc_tmf_undisturbed_degraded": "Forest extent, split into undisturbed and degraded.",
    "hansen_treecover_2000": (
        "Percent canopy cover in the year 2000, the baseline most global "
        "deforestation products are differenced against."
    ),
    "esa_worldcover": "Eleven classes of global land cover at 10 m: tree cover, cropland, built-up.",
    "icf_honduras_forest_cover_2024": (
        "Honduras's own national forest-cover map for 2024, with the publisher's legend."
    ),
    "icf_honduras_forest_cover_2018": (
        "The 2018 edition. Its legend is not published, so its classes read as codes."
    ),
    "icf_honduras_forest_cover_2014": (
        "The 2014 edition. Its legend is not published either."
    ),
    "icf_honduras_cafe_2020": (
        "Where coffee is grown, nationally, in 2020. What makes a coffee claim checkable."
    ),
    "icf_honduras_palma_africana_2020": (
        "Where oil palm is grown. A regional band across the north, not a national map, "
        "which is why fields in the southern coffee belt get 'outside coverage' rather "
        "than 'no palm'."
    ),
    "gfs_forecast": "NOAA's global weather forecast on a 0.25 degree grid.",
}
"""What each layer shows, in a sentence, for a reader who has not met it.

Everything factual about a layer -- title, source, licence, extent -- is asked of
the node. This is the one thing the node cannot supply, because it is editorial:
why the layer is in this demo and what a reader should take from it. Layers the
node lists and this dictionary does not know are printed as such rather than
dropped, so the two cannot drift apart quietly.
"""

# The five layers Honduras's forestry authority publishes at
# https://geoportal.icf.gob.hn/geoportal/main, mirrored here.
ICF_GEOPORTAL = "https://geoportal.icf.gob.hn/geoportal/main"


def library() -> tuple[list[dict[str, Any]], str]:
    """Every layer this node serves, asked of the node.

    Unauthenticated and needs no GeoID: the catalogue is public, and only a
    reading about a particular field needs consent. That distinction is worth
    seeing before any field exists.
    """
    try:
        response = requests.get(f"{TERRAPIPE_OS_URL}/layers", timeout=20)
    except requests.RequestException as exc:
        return [], f"the node could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return [], f"the node answered HTTP {response.status_code}"
    layers = response.json() or []
    return layers, f"{len(layers)} layers, asked of {TERRAPIPE_OS_URL}"


def show_library(layers: list[dict[str, Any]]) -> None:
    """Print the catalogue grouped by who publishes it."""
    if not layers:
        print("  the node listed no layers")
        return

    by_source: dict[str, list[dict[str, Any]]] = {}
    for layer in layers:
        by_source.setdefault(layer.get("source") or "source not stated", []).append(layer)

    for source, group in by_source.items():
        print(f"\n{source}")
        print(f"  licence: {group[0].get('licence')}")
        for layer in group:
            note = LAYER_NOTES.get(layer["layer_id"], "(not described in this notebook)")
            print(f"\n  {layer['layer_id']}")
            print(f"      {layer.get('title')}")
            for line in textwrap.wrap(note, 74):
                print(f"      {line}")
            bbox = (layer.get("coverage") or {}).get("bbox")
            extent = "declares no extent, so it is read wherever it has data"
            if bbox:
                west, south, east, north = bbox
                extent = (
                    "global" if east - west > WIDER_THAN_THE_MAP
                    else f"{west:.2f},{south:.2f} to {east:.2f},{north:.2f}"
                )
            print(f"      extent: {extent}")


def _absent_layers(screen: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Each absent layer with its reason, because the reasons are not alike.

    Printed as one undifferentiated "not mirrored" until 2026-09-04, which said
    the node had failed to download something. The commonest reason in this demo
    is the opposite: oil palm is a regional map, the coffee-belt fields sit
    outside its bounds, and the node reports outside_coverage correctly. Calling
    that a missing mirror invents an operational fault out of a layer behaving
    exactly as declared.
    """
    return [
        (e["layer_id"], e["absent"], e.get("note") or ABSENCE_MEANS.get(e["absent"], ""))
        for e in evidence_rows(screen)
        if e.get("absent")
    ]


def compare(expected: dict[str, Any], screen: dict[str, Any]) -> list[str]:
    """Check the screen against what the placer recorded when it chose this field.

    The demo fields were selected by reading the stores, so the screen has to
    agree with what was read. A mismatch means the store changed under us or
    the screen changed its mind, and either is worth knowing about in front of
    an audience rather than after.
    """
    notes = []
    for label, got, want in (
        (
            "cleared-after-cutoff",
            screen.get("deforested_fraction"),
            expected.get("deforested_after_2020_fraction"),
        ),
        (
            "coffee",
            (screen.get("commodity") or {}).get("coffee_fraction"),
            expected.get("coffee_fraction"),
        ),
    ):
        if want is None or got is None:
            continue
        drift = abs(got - want)
        if drift > COVER_FRINGE_TOLERANCE:
            notes.append(
                f"{label} {got:.4f} against {want:.4f} placed, off by {drift:.1%} -- "
                f"more than the boundary fringe accounts for"
            )
    return notes


COVER_FRINGE_TOLERANCE = 0.05
"""How far the screen may sit from the placed figure before it is worth saying.

Not a fudge factor: the two measure different ground. The placer read one S2
L15 cell. The screen reads AR2's cover of the polygon registered from that
cell's corners, and an S2 covering of a polygon is not the single cell it came
from -- for the first demo field AR2 returns the L15 cell *plus* 98 refinement
cells at L20 hugging the boundary, about 9.6% of extra area. Whatever is on that
fringe is real ground, and it dilutes the field's own figures.

Measured on 2026-09-04 against Rajat's node: the four fields drift by 0.2% to
2.1%, all in the direction the fringe predicts. Five per cent leaves room for a
field whose fringe is less like its interior, and still catches a store that has
genuinely changed underneath the demo.

The tolerance existed at 0.1% before, which no field could meet, so every field
reported a mismatch and the check said nothing."""


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------


def get(url: str, *, token: str | None = None, grant: str | None = None, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if grant:
        headers["X-Field-Grant"] = grant
    return requests.get(url, headers=headers, timeout=kwargs.pop("timeout", 60), **kwargs)


def post(url: str, *, token: str | None = None, grant: str | None = None, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if grant:
        headers["X-Field-Grant"] = grant
    return requests.post(url, headers=headers, timeout=kwargs.pop("timeout", 60), **kwargs)


# --------------------------------------------------------------------------
# the three calls that have to be made the way the services actually take them
# --------------------------------------------------------------------------
#
# Each of these was wrong in the notebook until 2026-09-02, and each was wrong
# in the same way: the cell called a route that does not exist, or sent a body
# the route does not accept, and the failure was absorbed into a SKIPPED badge.
# A skip reads as "the stack was not up", so the notebook looked honest while
# demonstrating nothing. They are functions here so that the contract lives in
# one place and tests/test_notebook_routes.py can check it.


def _expired(token: str) -> bool:
    """Whether a JWT is past its expiry, read without verifying it.

    Verification is the services' job. This is only so the notebook can say "the
    token you gave me has expired" instead of reporting four 401s, which is what
    a stale HUB_TOKEN in a long-lived shell looks like from the output.
    """
    try:
        claims = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
    except (IndexError, ValueError, json.JSONDecodeError):
        return False  # not a JWT we can read; let the services judge it
    exp = payload.get("exp")
    return bool(exp) and float(exp) <= time.time()


def _login(email: str, password: str) -> tuple[str | None, str]:
    """The hub's password grant, which is form-encoded rather than JSON."""
    try:
        response = requests.post(
            f"{HUB_URL}/users/login",
            data={"username": email, "password": password},
            timeout=20,
        )
    except requests.RequestException as exc:
        return None, f"the hub at {HUB_URL} could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return None, f"HTTP {response.status_code} {response.text[:120]}"
    return (response.json() or {}).get("access_token"), ""


def _register(email: str, password: str) -> tuple[bool, str]:
    """Create the demo account if it is not there yet.

    The hub wants first and last names, and omitting them is a 422 that reads
    like a rejected password.
    """
    try:
        response = requests.post(
            f"{HUB_URL}/users/register",
            json={
                "email": email,
                "password": password,
                "first_name": "Demo",
                "last_name": "Reader",
                "discoverable": True,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        return False, f"the hub could not be reached: {exc.__class__.__name__}"
    # 400 is "already exists", which is success for our purposes.
    return response.status_code in (200, 201, 400, 409), f"HTTP {response.status_code}"


def hub_token() -> tuple[str | None, str]:
    """A bearer token from the hub, and how it was obtained.

    The hub issues these from client credentials at ``POST /users/token``. The
    notebook used to read ``HUB_TOKEN`` from the environment and carry on when it
    was empty, which turns every authenticated call into a 401 that the notebook
    then reports as the service being down.

    Returns the token and a sentence naming its source, so a cell can say which
    of the two it got rather than only whether it has one.
    """
    # An expired HUB_TOKEN is worse than none: it produces a 401 from every
    # authenticated call, which reads as the services refusing the demo rather
    # than as a stale string in a long-lived shell. So it falls through to the
    # credentials below and says why at the end.
    preset = os.environ.get("HUB_TOKEN", "").strip()
    if preset and not _expired(preset):
        return preset, "HUB_TOKEN, taken as given"

    email = os.environ.get("DEMO_EMAIL", "").strip()
    password = os.environ.get("DEMO_PASSWORD", "").strip()
    if email and password:
        token, why = _login(email, password)
        if token:
            return token, f"logged in as {email}"
        registered, detail = _register(email, password)
        if registered:
            token, why = _login(email, password)
            if token:
                return token, f"registered and logged in as {email}"
        return None, f"could not sign in as {email}: {why or detail}"

    client_id = os.environ.get("DEMO_CLIENT_ID", "").strip()
    client_secret = os.environ.get("DEMO_CLIENT_SECRET", "").strip()
    if not (client_id and client_secret):
        stale = " The HUB_TOKEN in the environment has expired." if preset else ""
        return None, (
            f"no usable hub credential.{stale} Put DEMO_EMAIL and DEMO_PASSWORD in "
            f"{SETTINGS_FILE.name} (see demo.env.example) and restart the kernel. "
            "Authenticated calls below will be refused rather than skipped, which is "
            "the truthful outcome"
        )
    try:
        r = requests.post(
            f"{HUB_URL}/users/token",
            json={"client_id": client_id, "client_secret": client_secret},
            timeout=15,
        )
    except requests.RequestException as exc:
        return None, f"the hub at {HUB_URL} could not be reached: {exc.__class__.__name__}"
    if not r.ok:
        return None, f"the hub refused these client credentials: HTTP {r.status_code} {r.text[:120]}"
    token = (r.json() or {}).get("access_token")
    if not token:
        return None, f"the hub answered {r.status_code} without an access_token"
    return token, f"exchanged client credentials at {HUB_URL}/users/token"


def wkt_of(geometry: dict[str, Any]) -> str:
    """A GeoJSON polygon as the WKT that AR2 registration takes.

    AR2's ``/register-field-boundary`` accepts ``{"wkt": ...}`` and nothing else;
    posting the GeoJSON geometry object, as this notebook did, is a 422. Written
    out rather than delegated to shapely so the axis order is visible: GeoJSON
    positions are [longitude, latitude] and WKT is "longitude latitude", so the
    pairs pass through unswapped, which is the part that goes wrong silently.
    """
    if geometry.get("type") != "Polygon":
        raise ValueError(f"only Polygon is registered here, not {geometry.get('type')!r}")
    rings = []
    for ring in geometry["coordinates"]:
        positions = ", ".join(f"{lon:.8f} {lat:.8f}" for lon, lat in ring)
        rings.append(f"({positions})")
    return f"POLYGON({', '.join(rings)})"


def geoid_of(response: requests.Response) -> str | None:
    """The GeoID out of an AR2 registration response, under either spelling.

    AR2's response model declares aliases, so the serialised key is ``"Geo Id"``
    with a space and a capital. Reading ``geo_id`` returns None against a
    perfectly successful registration -- which the notebook then displayed as a
    refusal. Both spellings are accepted because the hub and the node have
    disagreed about this before.
    """
    if not response.ok:
        return None
    body = response.json() or {}
    for key in ("Geo Id", "geoid", "geo_id"):
        value = body.get(key)
        if value:
            return str(value)
    return None


def _why_the_grant_failed(response: requests.Response) -> str:
    """Translate the one refusal that does not say what it means.

    AR2 guards a list-artifact read with ``AR2_INTERNAL_SHARED_SECRET`` and, on
    a caller it cannot place, returns a 404 that deliberately hides whether the
    artifact exists. Pancake relays that verbatim. What an operator then reads
    is "404 Not Found" for a list artifact that exists, under exactly the id
    just asked for, on a stack where every service is healthy -- which sends
    them looking for a missing artifact for as long as it takes to notice the
    variable. It took an afternoon on 2026-09-03.
    """
    body = response.text[:400]
    looks_like_the_secret = response.status_code == 502 and "list-artifact" in body and "404" in body
    if looks_like_the_secret:
        return (
            "AR2 would not return the list members. Almost always this is "
            "AR2_INTERNAL_SHARED_SECRET: set it to the same value on the AR2 node and on "
            "Pancake and restart both. AR2 guards artifact reads with it, Pancake needs to "
            "read the list in order to issue the first grant for it, and AR2 refuses an "
            "unrecognised caller with a 404 that is indistinguishable from a missing "
            f"artifact. Underlying response: HTTP {response.status_code} {body[:200]}"
        )
    return f"HTTP {response.status_code} {body[:200]}"


@dataclass
class Consent:
    """An issued grant, with the handles needed to use and to withdraw it.

    ``field_grant`` returns only the credential, which is all most of the
    notebook needs. Showing consent being *withdrawn* needs the ``jti`` to
    revoke, and tracing needs the ``list_id`` the grant is scoped to -- a grant
    presented against any other list is refused, and AR2 refuses it as a 404
    rather than a 403 so that asking cannot confirm the list exists.
    """

    credential: str | None
    list_id: str | None
    jti: str | None
    why: str


def consent_for(
    geo_ids: list[str], token: str, *, purpose: str = "open-science demo", name: str = "openscience-demo"
) -> Consent:
    """Create a field list and issue a grant over it.

    Two calls, not one. Pancake has no ``POST /grants``: a grant is issued
    against a *field list*, so the list is created first at ``POST /fieldlists``
    and its ``list_id`` names the subject of the grant at
    ``POST /grants/issue``. The notebook posted to ``/grants`` and got a 404,
    which it reported as the grant being unavailable.
    """
    try:
        made = post(f"{PANCAKE_URL}/fieldlists", token=token, json={"name": name, "geoids": geo_ids})
    except requests.RequestException as exc:
        return Consent(None, None, None, f"Pancake at {PANCAKE_URL} could not be reached: {exc.__class__.__name__}")
    if not made.ok:
        return Consent(None, None, None, f"the field list was refused: HTTP {made.status_code} {made.text[:160]}")
    list_id = (made.json() or {}).get("list_id")
    if not list_id:
        return Consent(None, None, None, f"the field list came back without a list_id: {made.text[:160]}")

    issued = post(
        f"{PANCAKE_URL}/grants/issue",
        token=token,
        json={
            "list_id": list_id,
            "grantee_account": "self",
            "purpose": purpose,
            "validity_days": 30,
            "masking_level": "L1",
        },
    )
    if not issued.ok:
        return Consent(None, list_id, None, f"the grant was refused: {_why_the_grant_failed(issued)}")
    credential = (issued.json() or {}).get("credential")
    if not credential:
        return Consent(None, list_id, None, f"the grant came back without a credential: {issued.text[:160]}")
    return Consent(
        credential,
        list_id,
        _jti_of(credential),
        f"list {list_id[:12]}... granted at L1 for {purpose!r}",
    )


def _jti_of(credential: str) -> str | None:
    """The credential's own identifier, which is what revocation names.

    An SD-JWT is the issuer-signed JWT, then a tilde, then the disclosures. Read
    without verifying: verification is Pancake's and AR2's job, and this only
    needs to know which credential to ask Pancake to withdraw.
    """
    try:
        claims = credential.split("~")[0].split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
    except (IndexError, ValueError, json.JSONDecodeError):
        return None
    return payload.get("jti")


def revoke(jti: str, token: str) -> tuple[bool, str]:
    """Withdraw a grant, by the credential's own identifier."""
    try:
        response = post(f"{PANCAKE_URL}/grants/revoke", token=token, json={"jti": jti})
    except requests.RequestException as exc:
        return False, f"Pancake could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return False, f"the revocation was refused: HTTP {response.status_code} {response.text[:160]}"
    status = (response.json() or {}).get("status", "revoked")
    return True, f"{jti} is now {status}"


def screen_with(geo_id: str, token: str, grant: str | None = None) -> tuple[int, dict[str, Any]]:
    """Screen a field, with or without presenting a grant.

    The same call either way -- that is the point of the three-way comparison
    in the notebook. What changes is one header, and what changes in the answer
    is its *scope*, not whether there is one.
    """
    headers = {"Authorization": f"Bearer {token}"}
    if grant:
        headers["X-Field-Grant"] = grant
    try:
        response = requests.get(f"{TERRAPIPE_OS_URL}/screen/{geo_id}", headers=headers, timeout=120)
    except requests.RequestException as exc:
        return 0, {"reason": exc.__class__.__name__}
    return response.status_code, (response.json() if response.content else {})


def show_disclosure(rows: list[tuple[str, int, dict[str, Any]]]) -> None:
    """The same question at each disclosure tier, side by side.

    The paragraph under this table in the notebook says the granted row
    succeeded and the revoked one did not. That is markdown: it says the same
    thing whatever the table above it shows, and on 2026-09-06 it said it over
    a table where the granted row was a 403. So the table checks the claim
    being made about it, and says so here if it does not hold.
    """
    print(f"{'presented':22} {'HTTP':5} {'scope':14} {'cleared after cut-off':>21}   verdict")
    for label, status, body in rows:
        scope = body.get("scope") or "-"
        fraction = body.get("deforested_fraction")
        reading = "-" if fraction is None else f"{fraction:.4f}"
        verdict = body.get("verdict") or body.get("reason") or body.get("detail") or "refused"
        print(f"{label:22} {status:<5} {scope:14} {reading:>21}   {str(verdict)[:38]}")

    for note in _where_the_table_disagrees_with_the_text(rows):
        print(f"\n  NOTE: {note}")


def _where_the_table_disagrees_with_the_text(
    rows: list[tuple[str, int, dict[str, Any]]],
) -> list[str]:
    """The claims the surrounding prose makes, checked against the rows.

    Kept separate from the printing so the tests can assert on the findings
    rather than on formatting.
    """
    by_label = {label: (status, body) for label, status, body in rows}
    notes = []

    granted = by_label.get("a field-access grant")
    if granted and granted[0] != HTTP_OK:
        notes.append(
            f"the granted row came back HTTP {granted[0]}, not 200, so this run does not "
            "show a grant widening the answer. The paragraph below assumes it did."
        )
    elif granted and granted[1].get("scope") != "field":
        notes.append(
            f"the granted row answered at {granted[1].get('scope')!r} scope rather than "
            "'field', so the grant did not do what the paragraph below says it does."
        )

    revoked = by_label.get("the same, now revoked")
    if revoked and revoked[0] == HTTP_OK:
        notes.append(
            "the revoked credential was still answered. That is the silent downgrade the "
            "paragraph below says does not happen, and it is a defect in the node."
        )

    plain = by_label.get("nothing")
    if plain and granted and plain[0] == granted[0] == HTTP_OK:
        coarse, fine = plain[1].get("deforested_fraction"), granted[1].get("deforested_fraction")
        if coarse is not None and fine is not None and coarse == fine:
            notes.append(
                "the coarse and the precise reading are identical, so this field does not "
                "illustrate the difference in scope the paragraph below draws."
            )
    return notes


def trace_back(list_id: str, token: str, grant: str) -> tuple[dict[str, Any], str]:
    """From a lot, the fields it was drawn from.

    The grant has to be the one scoped to *this* list. AR2 answers an
    unauthorised request with 404 rather than 403, deliberately: a 403 would
    confirm the list exists to someone with no right to know that.
    """
    try:
        response = requests.get(
            f"{NODE_URL}/list-artifact/{list_id}/traceback",
            headers={"Authorization": f"Bearer {token}", "X-Grant-Token": grant},
            timeout=30,
        )
    except requests.RequestException as exc:
        return {}, f"AR2 could not be reached: {exc.__class__.__name__}"
    if response.status_code == HTTP_NOT_FOUND:
        return {}, "AR2 answered 404, which here means the grant does not cover this list"
    if not response.ok:
        return {}, f"AR2 answered HTTP {response.status_code}"
    body = response.json() or {}
    return body, f"{len(body.get('hops') or [])} hop(s) back from {list_id[:12]}..."


def lists_containing(geo_id: str, token: str) -> tuple[list[str], str]:
    """From a field, the lots it went into.

    The other direction, and the one a recall runs in: this field turned out to
    be a problem, so what did it end up in.
    """
    try:
        response = requests.get(
            f"{NODE_URL}/list-artifact/reverse/{geo_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return [], f"AR2 could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return [], f"AR2 answered HTTP {response.status_code}"
    ids = (response.json() or {}).get("list_ids") or []
    return ids, f"{len(ids)} list(s) contain {geo_id[:12]}..."


def inclusion_proof(list_id: str, geo_id: str, token: str) -> tuple[list[dict[str, Any]], str]:
    """Proof that a field is in a list, without revealing the rest of the list."""
    try:
        response = requests.get(
            f"{PANCAKE_URL}/fieldlists/{list_id}/proof/{geo_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        return [], f"Pancake could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return [], f"Pancake answered HTTP {response.status_code}"
    proof = (response.json() or {}).get("proof") or []
    return proof, f"{len(proof)} sibling hashes, so a list of {2 ** len(proof)} could be proved this way"


HTTP_OK = 200
HTTP_NOT_FOUND = 404


def field_grant(geo_ids: list[str], token: str, *, purpose: str = "open-science demo") -> tuple[str | None, str]:
    """Just the credential, for the steps that do not need to revoke or trace."""
    got = consent_for(geo_ids, token, purpose=purpose)
    return got.credential, got.why


def run_async(make_coroutine: Callable[[], Any]) -> Any:
    """Run a coroutine from a notebook cell.

    ``asyncio.run`` refuses inside a Jupyter kernel, which already has a loop
    running. Rather than patch the kernel's loop, give the coroutine a thread
    and a loop of its own: nothing here is long-lived enough to want otherwise,
    and a patched loop is a surprise for whoever runs the next cell.
    """
    import asyncio  # noqa: PLC0415
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(make_coroutine())).result()


def brief(value: Any, limit: int = 600) -> str:
    text = json.dumps(value, indent=2, default=str)
    return text if len(text) <= limit else text[:limit] + f"\n  ... ({len(text)} characters in all)"


def run_or_skip(state: dict[str, Any], condition: bool, reason: str, thunk: Callable[[], Any]) -> Any:
    if not condition:
        skip(state, reason)
        return None
    return thunk()


# ==========================================================================
# Legality verification: a population, and a draw anyone can check
# ==========================================================================

DETECTION_TABLE = {
    # Interviews needed to detect a problem affecting one in N of the
    # population, nineteen times in twenty. From the legality verification
    # guide (survey based), DRAFT, page 10. Transcribed rather than computed,
    # so that the notebook shows the guide's own figures and any disagreement
    # with a formula is visible rather than papered over.
    #                 1 in 5  1 in 7  1 in 10  1 in 20
    100:             (13,     17,     25,      45),
    200:             (13,     18,     27,      51),
    500:             (14,     19,     28,      56),
    1_000:           (14,     19,     29,      57),
    2_000:           (14,     19,     29,      58),
    5_000:           (14,     19,     29,      59),
    20_000:          (14,     19,     29,      59),
    50_000:          (14,     19,     29,      59),
    100_000:         (14,     19,     29,      59),
    1_000_000:       (14,     19,     29,      59),
}

AFFECTED_SHARES = (5, 7, 10, 20)

PREVALENCE_TABLE = {
    # Interviews needed for a percentage within five points of the truth.
    100: 80, 200: 132, 500: 217, 1_000: 278, 2_000: 322,
    5_000: 357, 20_000: 377, 50_000: 381, 100_000: 383, 1_000_000: 384,
}


def interviews_needed(population: int, one_in: int = 10) -> tuple[int, int, str]:
    """How many interviews to detect a problem, and to measure how common it is.

    The counterintuitive part, and the reason for showing it: both numbers stop
    growing. Detecting a problem affecting one farm in ten takes 29 interviews
    at a population of a thousand and 29 at a million. Sampling cost is set by
    the confidence wanted, not by the size of the supply base -- which is the
    answer to "we have ten thousand smallholders, this cannot be done".
    """
    if one_in not in AFFECTED_SHARES:
        raise ValueError(f"the guide tabulates {AFFECTED_SHARES}, not 1 in {one_in}")
    # The next tabulated population at or above this one: the guide's tables are
    # steps, and rounding down would understate the sample.
    banded = min((p for p in DETECTION_TABLE if p >= population), default=max(DETECTION_TABLE))
    detect = DETECTION_TABLE[banded][AFFECTED_SHARES.index(one_in)]
    prevalence = PREVALENCE_TABLE[min((p for p in PREVALENCE_TABLE if p >= population),
                                      default=max(PREVALENCE_TABLE))]
    return detect, prevalence, (
        f"population {population:,}, read off the guide's {banded:,} row"
    )


@dataclass
class Beacon:
    """A public random value nobody involved in the audit could have chosen."""

    source: str
    round: int
    value: str

    @property
    def citation(self) -> str:
        return f"{self.source} round {self.round}"


def beacon(timeout: int = 30) -> Beacon | None:
    """The latest value from drand, the League of Entropy's public beacon.

    Public, unauthenticated, one value every thirty seconds, and every past
    round stays retrievable and signed -- so a draw published today can still
    be rechecked in five years, which is the whole requirement.

    Returns None rather than raising, because a beacon being unreachable is a
    reason to record a weaker draw honestly, not to fail.
    """
    try:
        response = requests.get("https://api.drand.sh/public/latest", timeout=timeout)
        if response.status_code != HTTP_OK:
            return None
        body = response.json()
        return Beacon("drand", int(body["round"]), str(body["randomness"]))
    except (requests.RequestException, ValueError, KeyError):
        return None


def beacon_at(round_number: int, timeout: int = 30) -> Beacon | None:
    """One specific past round, which is how a published draw is rechecked."""
    try:
        response = requests.get(f"https://api.drand.sh/public/{round_number}", timeout=timeout)
        if response.status_code != HTTP_OK:
            return None
        body = response.json()
        return Beacon("drand", int(body["round"]), str(body["randomness"]))
    except (requests.RequestException, ValueError, KeyError):
        return None


@dataclass
class Draw:
    """A sample, and everything Step 8 has to report about how it was chosen."""

    list_id: str
    seed: str
    seed_description: str
    grindable: bool
    size: int
    sample: list[str]
    reserves: list[str]
    stratum: str = ""

    @property
    def recipe(self) -> str:
        """What somebody else runs to get the same names."""
        return (
            f"rank every member of list {self.list_id[:16]}... by "
            f"SHA-256('{self.seed_description}' + ':' + geo_id), take the first {self.size}"
        )


def verifiable_sample(seed: str, members: list[str], size: int) -> list[str]:
    """Draw ``size`` members as a pure function of ``seed``.

    Step 7 of the legality guide requires the selection be random, and Step 8
    requires reporting how it was made. The methods it offers are "a random
    number generator, drawing lots, spinning a bottle, or any equivalent
    method". Every one of them is unfalsifiable after the fact: an auditor
    handed a list of twenty-nine farms cannot tell a spun bottle from a
    convenient choice, and the guide's reporting requirement therefore collects
    an assertion rather than evidence.

    Each member is scored SHA-256(seed || member) and the lowest scores are
    taken. Sorting by a hash of the pair rather than shuffling with a seeded
    generator keeps the result independent of Python's RNG, an implementation
    detail that has changed before and would silently invalidate every
    previously published draw.

    What ``seed`` should be is the whole question, and it is answered by
    ``draw``, not here.
    """
    return [member for _, member in _ranked(seed, members)][:size]


def _ranked(seed: str, members: list[str]) -> list[tuple[str, str]]:
    """(score, member) for every member, lowest score first."""
    import hashlib  # noqa: PLC0415

    scored = [
        (hashlib.sha256(f"{seed}:{member}".encode()).hexdigest(), member)
        for member in members
    ]
    # Sorted on the score first and the member second, so that two members
    # colliding on a score still order deterministically rather than by the
    # order they happened to arrive in.
    return sorted(scored)


def draw(list_id: str, members: list[str], size: int,
         entropy: Beacon | str | None = None, stratum: str = "") -> Draw:
    """Draw a sample, and record honestly how much the draw is worth.

    **A list_id alone is not enough, and the first version of this said it
    was.** It read: the identifier is derived from the membership, so it "cannot
    be edited to suit" the draw. It can. Editing the membership changes the
    identifier, which changes the draw completely -- so whoever composes the
    population can add a member, recompute, see whether the farms they would
    rather not have visited came up, and try again. Each attempt is a fresh
    independent draw and costs nothing.

    The arithmetic makes it worse rather than better. With a thousand farms and
    a sample of twenty-nine, any one farm is drawn 2.9% of the time, so a
    grinder wanting one farm left out succeeds on the first try nineteen times
    in twenty without trying at all. Wanting a hundred particular farms all
    left out succeeds about one attempt in twenty: twenty recomputations, a
    fraction of a second.

    What the list_id genuinely gives is **binding**: the draw belongs to one
    exact population and cannot be presented as a draw from another, and any
    holder recomputes it. That is worth having. What it does not give is
    protection against the population being chosen to produce a convenient
    draw. It moves the trust rather than removing it -- out of the draw, into
    the population definition, which is where Step 3 already puts it. Honest,
    and less than was claimed.

    Removing it needs a value the composer could not have known when the
    membership was fixed:

    - **a public beacon.** Commit the list_id, then draw on a round published
      afterwards. Grinding would require predicting drand, and the round stays
      retrievable so the draw is recheckable for as long as the audit matters.
    - **a nonce from the auditor,** handed over after the list is committed.
      No external dependency, and it trusts the auditor -- usually reasonable,
      since their incentive runs the other way, and they are already trusted
      with the interviews.

    ``entropy=None`` still works and is still reproducible. It is recorded as
    ``grindable`` so that a report cannot quietly claim more than it has.
    """
    if isinstance(entropy, Beacon):
        seed_description, extra, grindable = entropy.citation, entropy.value, False
    elif entropy:
        seed_description, extra, grindable = "auditor nonce", str(entropy), False
    else:
        seed_description, extra, grindable = "list_id alone", "", True

    # The stratum name is part of the seed so that each subgroup draws
    # independently; without it, a member's rank would be the same in every
    # stratum it appeared in.
    seed = ":".join(part for part in (list_id, extra, stratum) if part)
    ranking = [member for _, member in _ranked(seed, members)]
    wanted = min(size, len(ranking))
    return Draw(
        list_id=list_id,
        seed=seed,
        seed_description=f"{list_id[:16]}...{(' + ' + seed_description) if extra else ''}"
                         + (f" + {stratum}" if stratum else ""),
        grindable=grindable,
        size=wanted,
        sample=ranking[:wanted],
        reserves=ranking[wanted:],
        stratum=stratum,
    )


def draw_by_subgroup(list_id: str, strata: dict[str, list[str]], sizes: dict[str, int],
                     entropy: Beacon | str | None = None) -> dict[str, Draw]:
    """A separate draw within each subgroup, which is what Step 7 asks for.

    Step 5: "each subgroup requires a full sample within each one, and every
    member of the total population must fall into one of the subgroups". The
    second half is checked here, because a member belonging to no subgroup or
    to two is a defect in the population definition that would otherwise show
    up as a quietly wrong denominator.
    """
    seen: dict[str, str] = {}
    for name, members in strata.items():
        for member in members:
            if member in seen:
                raise ValueError(
                    f"{member[:16]}... is in both '{seen[member]}' and '{name}'; "
                    "subgroups must partition the population"
                )
            seen[member] = name
    return {
        name: draw(list_id, members, sizes.get(name, 0), entropy=entropy, stratum=name)
        for name, members in strata.items()
    }


def draw_with_reserves(list_id: str, members: list[str], size: int) -> tuple[list[str], list[str]]:
    """The sample and the reserves, in the order to use them.

    Reserves are the next names in the same ranking rather than a second draw,
    so replacing an absentee does not need a new seed and cannot be used to
    steer the sample: whoever checks recomputes the whole ranking and sees
    which replacement was due.
    """
    made = draw(list_id, members, size)
    return made.sample, made.reserves


def show_draw(made: Draw, population: int) -> None:
    """The draw, what it is worth, and how to check it."""
    print(f"population        {population} fields in list {made.list_id[:16]}...")
    print(f"seeded by         {made.seed_description}")
    print(f"drawn             {made.size}")
    print(f"held in reserve   {len(made.reserves)}")
    print()
    print("  the draw, in the order the ranking put them:")
    for position, member in enumerate(made.sample, start=1):
        print(f"    {position:3}. {member[:24]}...")
    if made.reserves:
        print(f"    next in line: {made.reserves[0][:24]}...")
    print()
    print(f"  to check it: {made.recipe}")

    if made.grindable:
        print()
        print("  NOTE: seeded by the list_id alone, so this draw is reproducible but")
        print("  not unpredictable. Whoever composed the population could have added")
        print("  or dropped a member, recomputed, and tried again until the sample")
        print("  suited them. Binding the draw to a beacon round published after the")
        print("  population was committed is what removes that, and is not done here.")


# ==========================================================================
# The same field, across three national vintages
# ==========================================================================

ICF_VINTAGES = ("icf_honduras_forest_cover_2014",
                "icf_honduras_forest_cover_2018",
                "icf_honduras_forest_cover_2024")

ICF_CODEBOOKS: dict[str, dict[int, str]] = {
    # Only the codes this notebook actually resolves. Transcribed from the
    # publisher's own legends in Rajat's T13 run of 2026-09-07: the 2018 names
    # from the sidecar .dbf, the 2014 names from the GDAL raster attribute
    # table inside class_rapideye_hn_05ha.img.
    #
    # Kept here, and marked as a stopgap, because the node should be declaring
    # these. It answers `unlabelled_12` and `unlabelled_14` today, which is the
    # correct thing to say when a legend has not been declared -- inventing a
    # label to satisfy a schema is how a wrong one becomes permanent. The fix
    # belongs in the layer definitions, not in a demo.
    "icf_honduras_forest_cover_2018": {
        10: "Pino Plagado", 11: "Arboles Dispersos", 12: "Cafetales",
        13: "Frutales", 14: "Vegetación Secundaria Húmeda",
        15: "Vegetación Secundaria Decidua", 16: "Sabanas",
        17: "Palma Africana", 18: "Otras especies de Palma", 19: "Musácea",
    },
    "icf_honduras_forest_cover_2014": {
        12: "Pastos/Cultivos", 13: "Sabanas", 14: "Cafetales",
        15: "Palma Africana",
    },
}
"""Why the same number means different things in different years.

Code 12 is Cafetales in 2018 and Pastos/Cultivos in 2014. Cafetales is 14 in
2014, where 14 is Vegetación Secundaria Húmeda in 2018. Of the 26 codes present
in both vintages, three carry the same label. Subtracting one year from another
by raw code reads coffee as pasture, and the arithmetic gives no sign of it.
"""

COFFEE_LABELS = {"Cafetales", "cafe", "café"}


def resolve_label(layer_id: str, label: str) -> tuple[str, bool]:
    """Turn ``unlabelled_12`` into a class name, where the vintage is known.

    Returns the label and whether it had to be resolved here rather than being
    declared by the node, because that difference is the point of the section
    it appears in.
    """
    if not label.startswith("unlabelled_"):
        return label, False
    try:
        code = int(label.removeprefix("unlabelled_"))
    except ValueError:
        return label, False
    named = ICF_CODEBOOKS.get(layer_id, {}).get(code)
    return (named, True) if named else (label, False)


def vintages(geo_id: str, token: str, grant: str | None) -> list[dict[str, Any]]:
    """What the national map called this field, in each year it was made."""
    readings = []
    for layer_id in ICF_VINTAGES:
        response = get(f"{TERRAPIPE_OS_URL}/data/{geo_id}/{layer_id}", token=token, grant=grant)
        got, why = holds_data(response)
        year = layer_id[-4:]
        if not got:
            readings.append({"year": year, "layer_id": layer_id, "classes": {}, "why": why})
            continue
        classes = (response.json() or {}).get("value") or {}
        readings.append({"year": year, "layer_id": layer_id, "classes": classes, "why": ""})
    return readings


def show_vintages(readings: list[dict[str, Any]]) -> None:
    """The three vintages side by side, with the codes resolved where they can be."""
    print(f"{'year':6} {'as the node answers':30} {'what the code means':32} share")
    for reading in readings:
        if not reading["classes"]:
            print(f"{reading['year']:6} {'-':30} {reading['why'][:32]:32} -")
            continue
        for raw, share in sorted(reading["classes"].items(), key=lambda kv: -kv[1]):
            named, resolved = resolve_label(reading["layer_id"], raw)
            note = named if resolved else ("as declared" if named == raw else named)
            print(f"{reading['year']:6} {raw[:30]:30} {note[:32]:32} {share:.1%}")
        print()

    for note in _what_the_vintages_show(readings):
        print(f"  NOTE: {note}")


def _what_the_vintages_show(readings: list[dict[str, Any]]) -> list[str]:
    """Whether the story the section tells is the story this run produced."""
    notes = []
    coffee_years: list[str] = []
    bare_number_years: list[str] = []
    unresolved: list[tuple[str, str]] = []

    for reading in readings:
        for raw, share in reading["classes"].items():
            named, resolved = resolve_label(reading["layer_id"], raw)
            if share > 0.5 and named in COFFEE_LABELS:  # noqa: PLR2004
                coffee_years.append(reading["year"])
            # Three states, not two. The node answered with a bare number; this
            # module could put a name to it; neither. Collapsing the last two
            # made "unlabelled_1, which is not in the partial codebook here"
            # print as "the node has declared its legends", which is the
            # opposite of what the run showed.
            if raw.startswith("unlabelled_"):
                bare_number_years.append(reading["year"])
                if not resolved:
                    unresolved.append((reading["year"], raw))

    if len(set(coffee_years)) == len(ICF_VINTAGES):
        notes.append(
            "every vintage calls this field coffee, and the older two say so with a bare "
            "number. A comparison by raw code would read land-use changes that did not happen."
        )
    elif coffee_years:
        notes.append(
            f"coffee is the majority class in {', '.join(sorted(set(coffee_years)))} but not in "
            "every vintage, so this field does not illustrate the unchanged-crop case."
        )
    if not bare_number_years:
        notes.append(
            "no vintage came back with a bare number, so the node's legends have been declared "
            "since this was written and this section no longer shows what it describes."
        )
    if unresolved:
        listed = ", ".join(f"{code} in {year}" for year, code in sorted(set(unresolved))[:4])
        notes.append(
            f"the node answered with codes this notebook cannot name: {listed}. Only the codes "
            "needed for the fields shown here were transcribed from the publisher's legends; "
            "the rest wait on the node declaring them, which is where they belong."
        )
    return notes


# ==========================================================================
# When the national map and a global product disagree
# ==========================================================================

GLOBAL_FOREST_LAYERS = ("esa_worldcover", "hansen_treecover_2000")


def national_against_global(geo_id: str, token: str, grant: str | None) -> dict[str, Any]:
    """What the national crop map says, beside what the global products say.

    The legality guide names this case directly: *the potential for false
    positives; agroforestry systems, including where crops are grown under tree
    cover, are not to be considered forests.* Honduran coffee is largely
    shade-grown, so a global canopy product reads the shade trees as forest and
    their removal as deforestation. Reported as a verdict that is an accusation
    against a farmer; reported as a disagreement it is the follow-up case the
    guide asks for.
    """
    out: dict[str, Any] = {"national": {}, "global": {}, "why": ""}

    national = get(f"{TERRAPIPE_OS_URL}/data/{geo_id}/icf_honduras_forest_cover_2024",
                   token=token, grant=grant)
    got, why = holds_data(national)
    if got:
        out["national"] = (national.json() or {}).get("value") or {}
    else:
        out["why"] = why

    for layer_id in GLOBAL_FOREST_LAYERS:
        response = get(f"{TERRAPIPE_OS_URL}/data/{geo_id}/{layer_id}", token=token, grant=grant)
        got, why = holds_data(response)
        out["global"][layer_id] = (response.json() or {}).get("value") if got else None
    return out


def show_disagreement(reading: dict[str, Any]) -> None:
    """The national reading, the global readings, and what to make of the pair."""
    national = reading["national"]
    if not national:
        print(f"  the national map returned nothing: {reading['why']}")
        return

    crop, share = max(national.items(), key=lambda kv: kv[1])
    print(f"  national map (ICF 2024)   {crop} over {share:.1%} of the field")
    for layer_id, value in reading["global"].items():
        if value is None:
            print(f"  {layer_id:25} no reading")
        elif isinstance(value, dict):
            top, top_share = max(value.items(), key=lambda kv: kv[1])
            print(f"  {layer_id:25} {top} over {top_share:.1%}")
        else:
            print(f"  {layer_id:25} {value:.1f}")

    if verdict := agroforestry_case(reading):
        print()
        print(f"  {verdict}")


def register(feature: dict[str, Any], token: str) -> str | None:
    """Register one boundary and return the GeoID, or None if it was refused.

    Thin, because registration is idempotent on the geometry: sending a plot
    that is already known costs a round trip and returns the same name. Callers
    that need the S2 cover want ``s2_cover`` instead.
    """
    try:
        response = requests.post(
            f"{NODE_URL}/register-field-boundary",
            json={"wkt": wkt_of(feature["geometry"])},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
    except requests.RequestException:
        return None
    return geoid_of(response) if response.ok else None


@dataclass
class CanopyReading:
    """One plot, as the national crop map and the global canopy each see it."""

    label: str
    hectares: float
    crop: str
    crop_share: float
    canopy: str
    canopy_share: float

    @property
    def is_coffee(self) -> bool:
        return self.crop.lower() in {c.lower() for c in COFFEE_LABELS}

    @property
    def reads_as_tree(self) -> bool:
        return self.canopy == "tree_cover" and self.canopy_share > 0.5  # noqa: PLR2004

    @property
    def false_positive(self) -> bool:
        """Coffee to the country, forest to the world -- the guide's own case."""
        return self.is_coffee and self.crop_share > 0.5 and self.reads_as_tree  # noqa: PLR2004


def canopy_against_crop(label: str, hectares: float, geo_id: str, token: str,
                        grant: str | None) -> CanopyReading:
    """The one comparison, for one plot, in the form a table can hold.

    ``national_against_global`` above answers this in depth for a single field.
    This is the same question asked across a whole survey, where what matters is
    not any one plot's numbers but how many of them the global product would
    flag.
    """
    def dominant(layer_id: str) -> tuple[str, float]:
        response = get(f"{TERRAPIPE_OS_URL}/data/{geo_id}/{layer_id}", token=token, grant=grant)
        got, _ = holds_data(response)
        value = (response.json() or {}).get("value") if got else None
        if not isinstance(value, dict) or not value:
            return "no reading", 0.0
        return max(value.items(), key=lambda kv: kv[1])

    crop, crop_share = dominant("icf_honduras_cafe_2020")
    canopy, canopy_share = dominant("esa_worldcover")
    return CanopyReading(label, hectares, crop, crop_share, canopy, canopy_share)


def show_canopy_against_crop(readings: list[CanopyReading]) -> None:
    """Every plot in the survey, and the count that is the actual finding."""
    print(f"  {'plot':24} {'ha':>5}  {'national coffee map':28} {'global canopy':22} flag")
    for row in readings:
        flag = "FALSE POSITIVE" if row.false_positive else ""
        print(f"  {row.label:24} {row.hectares:5.2f}  "
              f"{row.crop + ' ' + format(row.crop_share, '.0%'):28} "
              f"{row.canopy + ' ' + format(row.canopy_share, '.0%'):22} {flag}")

    tree = sum(row.reads_as_tree for row in readings)
    coffee = sum(row.is_coffee and row.crop_share > 0.5 for row in readings)  # noqa: PLR2004
    flagged = sum(row.false_positive for row in readings)
    answered = sum(row.canopy != "no reading" for row in readings)
    print()
    print(f"  {answered} of {len(readings)} plots got a reading from the global product")
    print(f"  {tree} of {len(readings)} read as tree cover")
    print(f"  {coffee} of {len(readings)} are majority coffee to Honduras's own map")
    print(f"  {flagged} of {len(readings)} are the guide's named false positive: coffee "
          f"to the country, forest to the world")
    if tree == len(readings) and len(readings) > 1:
        print()
        print("  Every plot. There is no threshold on the global layer that separates")
        print("  the coffee from the rest of them, because it is not measuring crop.")


def agroforestry_case(reading: dict[str, Any]) -> str:
    """The guide's named false positive, if this field is one.

    Deliberately not a score. The whole point is that neither product is wrong
    and the disagreement is the finding, so this returns the sentence a human
    has to act on rather than a number that would be averaged into something.
    """
    national = reading["national"]
    if not national:
        return ""
    crop, share = max(national.items(), key=lambda kv: kv[1])
    if crop.lower() not in {c.lower() for c in COFFEE_LABELS} or share <= 0.5:  # noqa: PLR2004
        return ""

    canopy = reading["global"].get("esa_worldcover") or {}
    tree_share = canopy.get("tree_cover", 0) if isinstance(canopy, dict) else 0
    if tree_share <= 0.5:  # noqa: PLR2004
        return ""

    return (
        f"AGROFORESTRY FALSE-POSITIVE CASE. The national crop map calls this field "
        f"{crop} over {share:.0%} of its area; the global land-cover product calls the "
        f"same ground tree cover over {tree_share:.1%}. Both are right: this is "
        f"shade-grown coffee. The guide is explicit that agroforestry is not forest, so "
        f"a canopy change here needs a human, not a verdict."
    )


# ==========================================================================
# Asking the node as an agent would
# ==========================================================================


def ask_the_node(script: list[tuple[str, str, dict[str, Any]]], token: str | None = None):
    """Run a scripted sequence of MCP tool calls and return the exchange.

    A scripted turn rather than a language model. A model call needs a key,
    costs money, and returns something different every run, so the committed
    output would stop being a record of what the node does and become a record
    of what a model said about it. What is worth demonstrating here is the tool
    surface -- that an agent can reach this node, choose a tool by reading its
    description, and get back something structured enough to answer with.

    The questions are written by hand and the answers are not: each is the
    node's own JSON, rendered.
    """
    import httpx  # noqa: PLC0415
    from mcp.client.session import ClientSession  # noqa: PLC0415
    from mcp.client.streamable_http import streamable_http_client  # noqa: PLC0415

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def converse():
        exchange = []
        async with httpx.AsyncClient(headers=headers, timeout=120) as http:
            async with streamable_http_client(MCP_URL, http_client=http) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    for question, tool, arguments in script:
                        try:
                            result = await session.call_tool(tool, arguments)
                            answer = "\n".join(
                                getattr(item, "text", "") for item in result.content
                            )
                        except Exception as exc:  # noqa: BLE001 - reported in the transcript
                            answer = f"{type(exc).__name__}: {exc}"
                        exchange.append((question, tool, arguments, answer))
        return exchange

    return run_async(converse)


def show_exchange(exchange, limit: int = 460) -> None:
    """The scripted turn, rendered as the conversation it stands in for."""
    for question, tool, arguments, answer in exchange:
        named = ", ".join(f"{k}={_short(v)}" for k, v in arguments.items())
        print(f"\n  ask   {question}")
        print(f"  tool  {tool}({named})")
        body = _readable_answer(answer)
        for line in body.splitlines()[:14]:
            print(f"        {line[:100]}")
        if len(body) > limit:
            print(f"        ... ({len(body)} characters in all)")


def _short(value: Any, keep: int = 18) -> str:
    text = str(value)
    return text if len(text) <= keep else f"{text[:keep]}..."


def _readable_answer(answer: str) -> str:
    """The tool's reply, pretty-printed if it is JSON and left alone if not."""
    try:
        return json.dumps(json.loads(answer), indent=2)[:1400]
    except (ValueError, TypeError):
        return answer[:1400]


def the_coffee_field(geo_ids: dict[str, str], token: str, grant: str | None) -> tuple[str, str]:
    """The field the national map calls coffee, for the sections about coffee.

    Chosen by asking rather than by hard-coding a name, so that changing the
    demo fields cannot leave a section quietly illustrating something else.
    Sections 7 and 8 are about shade-grown coffee specifically -- the codebook
    trap and the agroforestry false positive both need a coffee field -- and
    running them on whichever field came first showed a pasture field and drew
    no conclusion.
    """
    for name, geo_id in geo_ids.items():
        if not geo_id:
            continue
        response = get(f"{TERRAPIPE_OS_URL}/data/{geo_id}/icf_honduras_forest_cover_2024",
                       token=token, grant=grant)
        got, _ = holds_data(response)
        if not got:
            continue
        classes = (response.json() or {}).get("value") or {}
        if not classes:
            continue
        top, share = max(classes.items(), key=lambda kv: kv[1])
        if top.lower() in {c.lower() for c in COFFEE_LABELS} and share > 0.5:  # noqa: PLR2004
            return geo_id, f"{name}, which ICF's 2024 map calls {top} over {share:.0%} of its area"
    return "", "no demo field is majority coffee in the 2024 national map"


# ==========================================================================
# The time trend, and an honest scoreboard of what the demo set out to cover
# ==========================================================================


def have_plotly() -> bool:
    import importlib.util  # noqa: PLC0415

    return importlib.util.find_spec("plotly") is not None


CLASS_COLOURS = {
    "forest": "#2d6a4f",
    "coffee": "#9c6644",
    "agriculture": "#c9a227",
    "other": "#8d99ae",
    "no reading": "#e5e5e5",
}


def _class_family(label: str) -> str:
    """Group a publisher's label into something a colour can mean.

    The vintages use three different legends, so the raw labels do not line up
    across years -- which is the codebook trap, and exactly why a chart of raw
    labels would show change that is not there. Grouping to a family is what
    makes the three years comparable at all, and the grouping is this
    notebook's editorial act rather than the publisher's.
    """
    if not label:
        return "no reading"
    lowered = label.lower()
    if "caf" in lowered or "coffee" in lowered:
        return "coffee"
    if "bosque" in lowered or "forest" in lowered:
        return "forest"
    if any(word in lowered for word in ("agr", "cultiv", "pasto", "palma")):
        return "agriculture"
    return "other"


def trend_rows(readings_by_field: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """One row per field per vintage, with the label and the family it grouped to."""
    rows = []
    for field_name, readings in readings_by_field.items():
        for reading in readings:
            classes = reading.get("classes") or {}
            label = ""
            if classes:
                # The dominant class: the one covering most of the field.
                label = max(classes.items(), key=lambda kv: kv[1])[0]
                # resolve_label also reports whether this notebook had to name
                # the code itself, which the vintage section shows and the
                # chart does not; only the label is wanted here.
                label, _ = resolve_label(reading["layer_id"], label)
            rows.append({
                "field": field_name,
                "year": reading["year"],
                "label": label or "no reading",
                "family": _class_family(label),
                "why": reading.get("why", ""),
            })
    return rows


def trend_chart(rows: list[dict[str, Any]]):
    """A decade of the national map, one strip per field.

    Not a line chart, because the readings are categorical: what changes is
    which class the publisher assigned, not a number that can go up or down.
    """
    if not have_plotly() or not rows:
        return None
    import plotly.graph_objects as go  # noqa: PLC0415

    fields = sorted({row["field"] for row in rows})
    years = sorted({row["year"] for row in rows})
    figure = go.Figure()

    for family, colour in CLASS_COLOURS.items():
        marked = [row for row in rows if row["family"] == family]
        if not marked:
            continue
        figure.add_trace(go.Scatter(
            x=[row["year"] for row in marked],
            y=[row["field"] for row in marked],
            mode="markers", name=family,
            marker={"size": 26, "symbol": "square", "color": colour,
                    "line": {"width": 1, "color": "#333"}},
            text=[row["label"] for row in marked],
            hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
        ))

    figure.update_layout(
        title="What the national map called each field, by vintage",
        xaxis={"title": "ICF vintage", "type": "category",
               "categoryorder": "array", "categoryarray": years},
        yaxis={"title": "", "categoryorder": "array", "categoryarray": fields[::-1]},
        template="simple_white", height=90 + 60 * len(fields),
        legend={"title": "grouped class"},
    )
    return figure


@dataclass
class Coverage:
    """One of the data categories this notebook set out to demonstrate."""

    category: str
    layers: str
    outcome: str
    detail: str


def coverage_scoreboard(ledger: "Ledger") -> list[Coverage]:
    """What was asked for against what the run could actually show.

    Written from the ledger rather than by hand, so it cannot claim a category
    the run did not demonstrate. The four categories are the ones this notebook
    was scoped to: deforestation rasters, pest and disease, weather, and
    satellite vegetation.
    """
    def outcome_of(fragment: str) -> tuple[str, str]:
        for entry in ledger.steps:
            if fragment in entry.name:
                return entry.outcome, entry.detail
        return SKIPPED, "no step in this run covered it"

    deforestation, why_def = outcome_of("screen each field")
    ndvi, why_ndvi = outcome_of("NDVI")
    weather, why_weather = outcome_of("GFS")

    return [
        Coverage("deforestation rasters", "JRC TMF, Hansen, ESA WorldCover, ICF Honduras",
                 deforestation, why_def or "read for every field"),
        Coverage("pest and disease", "none mounted", SKIPPED,
                 "no layer of field-resolution pest or disease observations exists to "
                 "mount; see AG-013b"),
        Coverage("weather", "gfs_forecast", weather, why_weather),
        Coverage("satellite vegetation", "ndvi_sentinel2", ndvi, why_ndvi),
    ]


def show_coverage(scoreboard: list[Coverage]) -> None:
    """The scoreboard, with the gaps as visible as the successes."""
    print(f"  {'category':24} {'outcome':9} {'layers':44}")
    for row in scoreboard:
        print(f"  {row.category:24} {row.outcome:9} {row.layers[:44]}")
    print()
    for row in scoreboard:
        if row.outcome not in (LIVE, LOCAL):
            print(f"  {row.category}: {row.detail}")
