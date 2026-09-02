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

DEMO_FIELDS = Path(
    os.environ.get(
        "DEMO_FIELDS",
        str(Path(__file__).resolve().parents[2] / "terrapipe-os" / "examples" / "honduras_demo_fields.geojson"),
    )
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
        "pancake": (PANCAKE_URL, "/health"),
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
        raise FileNotFoundError(f"{DEMO_FIELDS} not found; run bin/place-demo-fields in terrapipe-os")
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

    absent = _absent_layers(screen)
    if absent:
        print(f"{indent}not mirrored     {', '.join(absent)}")
        print(f"{indent}                 (absent, which is not the same as zero)")
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


def _absent_layers(screen: dict[str, Any]) -> list[str]:
    return [e["layer_id"] for e in evidence_rows(screen) if e.get("absent")]


def compare(expected: dict[str, Any], screen: dict[str, Any]) -> list[str]:
    """Check the screen against what the placer recorded when it chose this field.

    The demo fields were selected by reading the stores, so the screen has to
    agree with what was read. A mismatch means the store changed under us or
    the screen changed its mind, and either is worth knowing about in front of
    an audience rather than after.
    """
    notes = []
    got = screen.get("deforested_fraction")
    want = expected.get("deforested_after_2020_fraction")
    if want is not None and got is not None and abs(got - want) > 1e-3:
        notes.append(f"cleared-after-cutoff {got:.4f} but the placer recorded {want:.4f}")
    commodity = (screen.get("commodity") or {}).get("coffee_fraction")
    want_coffee = expected.get("coffee_fraction")
    if want_coffee is not None and commodity is not None and abs(commodity - want_coffee) > 1e-3:
        notes.append(f"coffee {commodity:.4f} but the placer recorded {want_coffee:.4f}")
    return notes


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
