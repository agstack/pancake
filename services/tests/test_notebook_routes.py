"""Every URL the open-science notebook builds is a route something serves.

The notebook is the demo an outside reviewer runs, and it is generated from
``dpi-demo/build_openscience_notebook.py``. Three of its calls were wrong until
2026-09-02, and the shape of the mistake is what makes this test worth having:

* it posted a GeoJSON geometry to AR2's ``/register-field-boundary``, which
  accepts ``{"wkt": ...}`` and answers 422 to anything else;
* it read the new identifier from ``geo_id``, where AR2's response model puts it
  under the alias ``"Geo Id"``, so a successful registration returned None;
* it posted to ``POST /grants``, which Pancake does not serve at all. A grant is
  issued against a field list, so the list has to be created first.

None of the three raised in a way anybody saw. The cells were wrapped in a step
recorder that catches the failure and prints SKIPPED, and a skip reads as "the
stack was not up" -- so the notebook looked honest while demonstrating nothing.
That is the specific failure this file exists to stop, and prose in a review
document would not have stopped it.

Checked against the routes the services declare, not against a list kept here:
a list would be a second place to update and would agree with the notebook long
after both had stopped agreeing with the code.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PANCAKE = Path(__file__).resolve().parents[2]
DEMO = PANCAKE / "dpi-demo"
BUILDER = DEMO / "build_openscience_notebook.py"
SUPPORT = DEMO / "openscience_demo.py"

# Sibling repositories, by the same convention test_terrapipe_os_contract.py uses.
AR2 = PANCAKE.parent / "ar2"
AR2_HUB = PANCAKE.parent / "ar2-hub"
TERRAPIPE_OS = PANCAKE.parent / "terrapipe-os"

# The support module's names for each service, and where that service's routes
# are declared. A URL built on od.NODE_URL is a claim about AR2.
SERVICE_OF_VARIABLE = {
    "NODE_URL": "ar2",
    "HUB_URL": "ar2-hub",
    "PANCAKE_URL": "pancake",
    "TERRAPIPE_OS_URL": "terrapipe-os",
}

# f"{od.PANCAKE_URL}/grants/issue" in the notebook, and f"{PANCAKE_URL}/fieldlists"
# inside the support module itself, where the names are unqualified.
CALL = re.compile(r"""\{(?:od\.)?(\w+_URL)\}(/[^"'\s]*)""")

DECORATOR = re.compile(r"""@(?:app|router)\.(?:get|post|put|patch|delete)\(\s*["']([^"']*)["']""")
ROUTER_PREFIX = re.compile(r"""APIRouter\([^)]*prefix\s*=\s*["']([^"']*)["']""", re.DOTALL)


def _placeholders_out(path: str) -> str:
    """``/screen/{GEOIDS[SUBJECT]}`` and ``/screen/{geo_id}`` are the same route."""
    path = re.sub(r"\{[^}]*\}", "{}", path)
    return path.rstrip("/") or "/"


def _matches(call: str, route: str) -> bool:
    """Whether a called path is served by a route, segment by segment.

    A route's path parameter takes any single segment, so the notebook asking
    for ``/data/{}/ndvi_sentinel2`` -- where the layer id is a literal, because
    the notebook knows which layer it wants -- is served by ``/data/{}/{}``.
    Comparing the strings would call that a missing route.
    """
    called, served = call.strip("/").split("/"), route.strip("/").split("/")
    if len(called) != len(served):
        return False
    return all(s == "{}" or s == c for c, s in zip(called, served, strict=True))


def _routes_from_source(root: Path) -> set[str]:
    """Paths declared by FastAPI decorators under a repository, prefixes applied.

    Read from source rather than by importing, because these services pull in
    geopandas, a database driver and a hub connection at import time, and a test
    that can only run where all of that is installed is a test that gets skipped.
    """
    found: set[str] = set()
    for file in sorted(root.rglob("*.py")):
        if any(part in {".venv", "site-packages", "build", "node_modules"} for part in file.parts):
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "@app." not in text and "@router." not in text:
            continue
        prefix = ""
        match = ROUTER_PREFIX.search(text)
        if match:
            prefix = match.group(1)
        for path in DECORATOR.findall(text):
            found.add(_placeholders_out(prefix + path))
    return found


def _calls() -> set[tuple[str, str]]:
    """Every (service, path) the notebook and its support module build."""
    calls: set[tuple[str, str]] = set()
    for file in (BUILDER, SUPPORT):
        for variable, path in CALL.findall(file.read_text(encoding="utf-8")):
            service = SERVICE_OF_VARIABLE.get(variable)
            assert service, f"{file.name} builds a URL on unknown {variable}"
            calls.add((service, _placeholders_out(path)))
    return calls


ROOTS = {"ar2": AR2, "ar2-hub": AR2_HUB, "terrapipe-os": TERRAPIPE_OS, "pancake": PANCAKE}


@pytest.fixture(scope="module")
def served() -> dict[str, set[str]]:
    routes = {}
    for service, root in ROOTS.items():
        if root.exists():
            routes[service] = _routes_from_source(root)
    return routes


def test_the_notebook_makes_calls_at_all() -> None:
    """If the extraction breaks, every assertion below passes vacuously."""
    calls = _calls()
    assert len(calls) >= 6, f"only found {calls}; the URL pattern has probably stopped matching"
    assert ("pancake", "/grants/issue") in calls
    assert ("ar2", "/register-field-boundary") in calls


def test_every_route_source_was_actually_found(served) -> None:
    """A repository whose routes came back empty would clear every check below."""
    missing = [s for s, root in ROOTS.items() if root.exists() and not served.get(s)]
    assert not missing, f"found no routes for {missing}; the decorator pattern has stopped matching"


@pytest.mark.parametrize("service,path", sorted(_calls()))
def test_the_notebook_calls_a_route_that_exists(service, path, served) -> None:
    """The check that would have caught POST /grants."""
    if service not in served:
        pytest.skip(f"{service} is not cloned beside pancake")
    assert any(_matches(path, route) for route in served[service]), (
        f"the notebook calls {service} {path}, which that service does not serve. "
        f"Under the same first segment it serves: "
        f"{sorted(p for p in served[service] if p.split('/')[1:2] == path.split('/')[1:2]) or 'nothing'}"
    )


def test_a_route_nothing_serves_would_be_caught(served) -> None:
    """The gate, proven able to fire.

    Without this, a change that quietly stopped the extraction from matching
    would leave every parametrised case passing and nothing would say so.
    """
    if "pancake" not in served:
        pytest.skip("pancake routes were not read")

    assert _placeholders_out("/grants") not in served["pancake"], (
        "POST /grants now exists, so the example this test is built on is stale; "
        "pick another route Pancake does not serve"
    )


# --------------------------------------------------------------------------
# the request bodies, for the two calls whose shape was wrong
# --------------------------------------------------------------------------


def test_registration_sends_wkt_and_not_a_geojson_geometry() -> None:
    source = BUILDER.read_text(encoding="utf-8")
    call = source[source.index("/register-field-boundary") :][:400]

    assert "od.wkt_of(" in call, "registration must send WKT; AR2 answers 422 to a geometry object"
    assert "'geometry':" not in call and '"geometry":' not in call


def test_the_geoid_is_read_under_the_alias_ar2_actually_returns() -> None:
    """AR2's response model aliases it to "Geo Id"; geo_id reads as None."""
    assert "def geoid_of" in SUPPORT.read_text(encoding="utf-8")
    source = BUILDER.read_text(encoding="utf-8")
    call = source[source.index("/register-field-boundary") :][:600]

    assert "od.geoid_of(" in call
    assert ".get('geo_id')" not in call


def test_the_grant_is_issued_against_a_field_list() -> None:
    support = SUPPORT.read_text(encoding="utf-8")
    issue = support.index("/grants/issue")
    fieldlists = support.index("/fieldlists")

    assert fieldlists < issue, "the field list has to be created before a grant can name it"
    assert "list_id" in support[fieldlists:issue]


def test_the_hub_token_is_fetched_rather_than_assumed_present() -> None:
    """Reading HUB_TOKEN and carrying on turns every call into a 401."""
    assert "/users/token" in SUPPORT.read_text(encoding="utf-8")
    assert "os.environ.get('HUB_TOKEN')" not in BUILDER.read_text(encoding="utf-8")
