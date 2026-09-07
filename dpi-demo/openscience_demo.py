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


def _load_settings(path: Path = SETTINGS_FILE) -> list[str]:
    """Read ``KEY=value`` lines into the environment, without overriding it.

    A real environment variable always wins, so a run can be pointed elsewhere
    for one cell without editing the file.
    """
    if not path.is_file():
        return []
    loaded = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value
            loaded.append(key)
    return loaded


SETTINGS_LOADED = _load_settings()

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
    already_blocked = any(isinstance(hook, _NoLocalBackend) for hook in sys.meta_path)
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
