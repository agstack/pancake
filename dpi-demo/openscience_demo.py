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

import json
import os
import textwrap
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

import requests

HUB_URL = os.environ.get("HUB_URL", "http://localhost:8000")
NODE_URL = os.environ.get("AR2_NODE_URL", "http://localhost:8001")
PANCAKE_URL = os.environ.get("PANCAKE_URL", "http://localhost:8100")
TERRAPIPE_OS_URL = os.environ.get("TERRAPIPE_OS_URL", "http://localhost:8200")

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
        self.steps.append(Step(name, outcome, detail, seconds))

    def checklist(self) -> str:
        """What actually happened, generated from what actually happened.

        Written from the ledger rather than typed by hand, because a
        hand-written summary of a notebook is a claim about a previous run.
        """
        if not self.steps:
            return "No steps were recorded."
        width = max(len(s.name) for s in self.steps)
        mark = {LIVE: "[x]", LOCAL: "[x]", SKIPPED: "[ ]", FAILED: "[!]"}
        lines = [f"{mark[s.outcome]} {s.name.ljust(width)}  {s.outcome:8}{('  ' + s.detail) if s.detail else ''}"
                 for s in self.steps]
        counts = {o: sum(1 for s in self.steps if s.outcome == o) for o in (LIVE, LOCAL, SKIPPED, FAILED)}
        lines.append("")
        lines.append(
            f"{counts[LIVE]} against live services, {counts[LOCAL]} against local data, "
            f"{counts[SKIPPED]} skipped, {counts[FAILED]} failed."
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


def share_mounted() -> tuple[bool, str]:
    """Whether the mirrored rasters are where this process can read them."""
    root = os.environ.get("TERRAPIPE_SHARE")
    if not root:
        return False, "TERRAPIPE_SHARE is not set"
    path = Path(root)
    if not path.is_dir():
        return False, f"{root} is not a directory"
    stores = sorted(p.name for p in path.iterdir() if p.is_dir())
    if not stores:
        return False, f"{root} is empty; nothing has been ingested"
    return True, f"{root}: {', '.join(stores)}"


def terrapipe_os_importable() -> tuple[bool, str]:
    try:
        import terrapipe_os  # noqa: F401,PLC0415

        return True, "terrapipe_os is importable"
    except ImportError as exc:
        return False, str(exc)


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


def local_cover(feature: dict[str, Any], geo_id: str) -> Any:
    """The cover AR2 would return for this field, without asking AR2.

    Legitimate only because these particular fields *are* S2 cells: each one
    carries the token it was cut from, so its cover is that token exactly and
    nothing is being approximated. A surveyed boundary is different -- AR2
    computes its covering and decides how much of it to disclose -- and this
    shortcut would be wrong there.
    """
    from terrapipe_os.ar2 import Cover  # noqa: PLC0415

    token = feature["properties"].get("s2_token")
    if not token:
        raise ValueError("this field is not an S2 cell; a cover has to come from AR2")
    return Cover(geo_id=geo_id, tier="precise", tokens=(token,), masking_level="L1")


def local_registry() -> Any:
    from terrapipe_os.registry import Registry  # noqa: PLC0415

    library = Path(os.environ.get("TERRAPIPE_LAYERS", "")) if os.environ.get("TERRAPIPE_LAYERS") else None
    if library is None:
        library = Path(__file__).resolve().parents[2] / "terrapipe-os" / "layers" / "layers.json"
    return Registry.load(library)


# --------------------------------------------------------------------------
# presenting a screen
# --------------------------------------------------------------------------


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


def post(url: str, *, token: str | None = None, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
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


def hub_token() -> tuple[str | None, str]:
    """A bearer token from the hub, and how it was obtained.

    The hub issues these from client credentials at ``POST /users/token``. The
    notebook used to read ``HUB_TOKEN`` from the environment and carry on when it
    was empty, which turns every authenticated call into a 401 that the notebook
    then reports as the service being down.

    Returns the token and a sentence naming its source, so a cell can say which
    of the two it got rather than only whether it has one.
    """
    preset = os.environ.get("HUB_TOKEN", "").strip()
    if preset:
        return preset, "HUB_TOKEN from the environment"

    client_id = os.environ.get("DEMO_CLIENT_ID", "").strip()
    client_secret = os.environ.get("DEMO_CLIENT_SECRET", "").strip()
    if not (client_id and client_secret):
        return None, (
            "no HUB_TOKEN, and no DEMO_CLIENT_ID/DEMO_CLIENT_SECRET to exchange for one. "
            "Authenticated calls below will be refused rather than skipped, which is the "
            "truthful outcome"
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


def field_grant(geo_ids: list[str], token: str, *, purpose: str = "open-science demo") -> tuple[str | None, str]:
    """A field-access credential for these GeoIDs, and how it went.

    Two calls, not one. Pancake has no ``POST /grants``: a grant is issued
    against a *field list*, so the list is created first at ``POST /fieldlists``
    and its ``list_id`` names the subject of the grant at
    ``POST /grants/issue``. The notebook posted to ``/grants`` and got a 404,
    which it reported as the grant being unavailable.
    """
    try:
        made = post(
            f"{PANCAKE_URL}/fieldlists",
            token=token,
            json={"name": "openscience-demo", "geoids": geo_ids},
        )
    except requests.RequestException as exc:
        return None, f"Pancake at {PANCAKE_URL} could not be reached: {exc.__class__.__name__}"
    if not made.ok:
        return None, f"the field list was refused: HTTP {made.status_code} {made.text[:160]}"
    list_id = (made.json() or {}).get("list_id")
    if not list_id:
        return None, f"the field list came back without a list_id: {made.text[:160]}"

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
        return None, f"the grant was refused: {_why_the_grant_failed(issued)}"
    credential = (issued.json() or {}).get("credential")
    if not credential:
        return None, f"the grant came back without a credential: {issued.text[:160]}"
    return credential, f"list {list_id[:12]}... granted at L1 for {purpose!r}"


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
