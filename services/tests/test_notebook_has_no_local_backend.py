"""The open-science notebook must read from a hosted node, never from itself.

The demo exists to show that a node an operator runs, against rasters that
operator mirrored, will answer a question about a field it was given consent to
look at. An in-process ``terrapipe_os`` produces identical numbers and
demonstrates none of that, and it turns a node outage into a green run.

Four steps used to fall back that way and label themselves LOCAL, which is
honest labelling of the wrong thing to be doing. These tests keep the fallback
from growing back, because the failure is invisible in the output: a notebook
computing everything locally looks exactly like one talking to a node.
"""

from __future__ import annotations

import ast
import collections
import inspect
import re
import textwrap
import os
import io
import contextlib
import pathlib
from urllib.parse import urlparse
import json
import subprocess
import sys
from pathlib import Path

import pytest
import requests

DEMO = Path(__file__).resolve().parents[2] / "dpi-demo"
NOTEBOOK = DEMO / "openscience_dpi_demo.ipynb"
BUILDER = DEMO / "build_openscience_notebook.py"
SUPPORT = DEMO / "openscience_demo.py"

BACKEND = "terrapipe_os"
# Pancake's own adapter package is named after what it talks to. It makes HTTP
# calls to the node and is the local half of this demo by design.
ADAPTER = "pancake_services.tap.adapters.terrapipe_os"


def _notebook_code() -> str:
    if not NOTEBOOK.is_file():
        pytest.skip(f"{NOTEBOOK} has not been generated")
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    return "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")


def _notebook_cells() -> list[str]:
    """Each code cell's source separately, for checks that are per-cell."""
    if not NOTEBOOK.is_file():
        pytest.skip(f"{NOTEBOOK} has not been generated")
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


def _imports(source: str) -> list[str]:
    """Every module name imported anywhere in ``source``, including inside functions."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_the_notebook_never_imports_the_backend() -> None:
    offenders = [
        name
        for name in _imports(_notebook_code())
        if name.split(".")[0] == BACKEND and not name.startswith(ADAPTER)
    ]

    assert not offenders, (
        f"the notebook imports {offenders}. Every reading has to come from "
        "TERRAPIPE_OS_URL over HTTP, or the demo proves nothing about a deployment"
    )


def test_the_builder_never_emits_a_backend_import() -> None:
    """The notebook is generated, so the ban belongs on its source too."""
    if not BUILDER.is_file():
        pytest.skip(f"{BUILDER} is missing")

    offenders = [
        line.strip()
        for line in BUILDER.read_text().splitlines()
        if line.strip().startswith(("from terrapipe_os", "import terrapipe_os"))
    ]

    assert not offenders, f"the builder emits backend imports: {offenders}"


def test_the_support_module_only_reaches_the_backend_over_http() -> None:
    offenders = [name for name in _imports(SUPPORT.read_text()) if name.split(".")[0] == BACKEND]

    assert not offenders, (
        f"openscience_demo.py imports {offenders}; its job is to call the node, not to be one"
    )


def test_the_guard_actually_blocks_the_import() -> None:
    """A rule the notebook states about itself is worth less than one it enforces.

    Run in a subprocess because the block is a meta_path hook and installing it
    in the test process would follow the session into unrelated tests.
    """
    script = f"""
import sys
sys.path.insert(0, {str(DEMO)!r})
import openscience_demo as od
print(od.forbid_local_backend())
for name in ("terrapipe_os", "terrapipe_os.screen", "terrapipe_os.dds"):
    try:
        __import__(name)
    except ImportError:
        print("blocked", name)
    else:
        print("LEAKED", name)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )

    assert result.returncode == 0, result.stderr[-800:]
    assert "LEAKED" not in result.stdout, result.stdout
    for name in ("terrapipe_os", "terrapipe_os.screen", "terrapipe_os.dds"):
        assert f"blocked {name}" in result.stdout, result.stdout


def test_the_guard_leaves_everything_else_importable() -> None:
    """A block that caught more than it was aimed at would be worse than none."""
    script = f"""
import sys
sys.path.insert(0, {str(DEMO)!r})
import openscience_demo as od
od.forbid_local_backend()
import json, requests, httpx
import pancake_services.tap.adapter_base
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )

    assert result.returncode == 0, result.stderr[-800:]
    assert "ok" in result.stdout


# --------------------------------------------------------------------------
# Finding the support module from wherever the notebook was opened
# --------------------------------------------------------------------------


def _bootstrap() -> str:
    """The notebook's first cell, up to where it starts calling services."""
    return _notebook_code().split("STACK =")[0]


def _run_bootstrap(cwd: Path, *, home: Path | None = None) -> subprocess.CompletedProcess:
    probe = cwd / "_bootstrap_probe.py"
    probe.write_text(
        "import sys\n"
        f"src = {_bootstrap()!r}\n"
        "try:\n"
        "    exec(compile(src, 'cell', 'exec'), {'__name__': '__main__'})\n"
        "    print('FOUND')\n"
        "except SystemExit as exc:\n"
        "    print('REFUSED'); print(exc)\n"
        "except ModuleNotFoundError as exc:\n"
        "    print('BARE'); print(exc)\n"
    )
    env = {k: v for k, v in __import__("os").environ.items() if k not in ("PANCAKE_DPI_DEMO", "PYTHONPATH")}
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(probe)], cwd=cwd, env=env, capture_output=True, text=True, timeout=120
    )


@pytest.mark.parametrize(
    "where",
    ["home", "repo_root", "elsewhere_in_the_repo"],
    ids=["from home", "from the pancake root", "from another directory in the repo"],
)
def test_the_notebook_finds_its_support_module_from_a_foreign_directory(where) -> None:
    """The kernel's working directory is not the notebook's directory.

    This was sys.path.insert(0, os.getcwd()) with a comment saying the notebook
    runs from dpi-demo/. It does not always: opening the executed copy archived
    under agstack/workplan/, or launching Jupyter from home, produced a bare
    ModuleNotFoundError with nothing pointing at the cause.
    """
    starts = {
        "home": Path.home(),
        "repo_root": DEMO.parent,
        "elsewhere_in_the_repo": DEMO.parent / "services",
    }
    start = starts[where]
    if not start.is_dir():
        pytest.skip(f"{start} does not exist here")

    result = _run_bootstrap(start)
    try:
        assert "FOUND" in result.stdout, result.stdout + result.stderr[-600:]
        assert str(DEMO) in result.stdout, "it must say which copy it resolved"
    finally:
        (start / "_bootstrap_probe.py").unlink(missing_ok=True)


def test_a_genuinely_missing_module_is_refused_with_instructions(tmp_path) -> None:
    """And the refusal has to be reachable, or it is decoration.

    HOME is moved as well, because the search walks out to the home directory
    and would otherwise find the real checkout and pass for the wrong reason.
    """
    result = _run_bootstrap(tmp_path, home=tmp_path)

    assert "BARE" not in result.stdout, "a bare ModuleNotFoundError is what this replaced"
    assert "REFUSED" in result.stdout, result.stdout + result.stderr[-600:]
    assert "PANCAKE_DPI_DEMO" in result.stdout, "the refusal must name the way out"
    assert "jupyter lab" in result.stdout, "and the other way out"


# --------------------------------------------------------------------------
# Being told which deployment to talk to
# --------------------------------------------------------------------------


def _module():
    sys.path.insert(0, str(DEMO))
    import openscience_demo  # noqa: PLC0415

    return openscience_demo


def _stack(url: str) -> dict:
    return {
        name: {"url": url, "up": False, "detail": "ConnectionError"}
        for name in ("hub", "ar2-node", "pancake", "terrapipe-os")
    }


def test_a_localhost_stack_that_is_down_is_reported_as_configuration() -> None:
    """Four DOWN lines against localhost is not an outage.

    The URLs defaulted to localhost, so a kernel that had not been handed five
    environment variables reported the whole stack down and skipped the run,
    which reads as the services being broken. It is the notebook not having been
    told where to look, and the two need different fixes.
    """
    od = _module()

    said = od.mode(_stack("http://localhost:8200"))

    assert "SKIPPED" in said
    assert "demo.env" in said, "it must name the file that fixes this"
    assert "configuration" in said or "has been named" in said


def test_a_configured_stack_that_is_down_is_reported_as_an_outage() -> None:
    """And the other way, or the advice would be wrong half the time."""
    od = _module()

    said = od.mode(_stack("http://66.220.3.93:8200"))

    assert "outage" in said
    assert "demo.env" not in said, "the file is already read; saying to copy it would mislead"


def test_a_reachable_node_needs_no_advice() -> None:
    od = _module()
    stack = _stack("http://node:8200")
    stack["terrapipe-os"]["up"] = True

    assert od.mode(stack) == "mode: LIVE against the hosted node"


def test_the_example_settings_file_lists_every_key_the_module_reads() -> None:
    """A key the module reads and the example omits is a silent misconfiguration."""
    example = DEMO / "demo.env.example"
    assert example.is_file(), "demo.env.example must be committed; demo.env must not"

    text = example.read_text()
    for key in (
        "HUB_URL",
        "AR2_NODE_URL",
        "PANCAKE_URL",
        "TERRAPIPE_OS_URL",
        "TERRAPIPE_OS_MCP_URL",
        "DEMO_EMAIL",
        "DEMO_PASSWORD",
        "HUB_TOKEN",
        "DEMO_CLIENT_ID",
        "DEMO_CLIENT_SECRET",
    ):
        assert key in text, f"{key} is read by openscience_demo.py but absent from the example"


def test_the_real_settings_file_is_not_committed() -> None:
    """It names a deployment and can hold a password."""
    ignored = subprocess.run(
        ["git", "check-ignore", "dpi-demo/demo.env"],
        cwd=DEMO.parent,
        capture_output=True,
        text=True,
    )

    assert ignored.returncode == 0, "dpi-demo/demo.env must be gitignored"


def test_the_environment_wins_over_the_file() -> None:
    """So a single run can be pointed elsewhere without editing anything."""
    od = _module()
    settings = od.SETTINGS_FILE
    if not settings.is_file():
        pytest.skip("no demo.env here to be overridden")

    key = "TERRAPIPE_OS_URL"
    import os as _os

    before = _os.environ.get(key)
    _os.environ[key] = "http://set-by-the-environment:9999"
    try:
        applied, overridden = od._load_settings(settings)
        assert key not in applied, "the file overwrote a variable that was already set"
        assert key in overridden, "an overridden key should still be reported as declared"
        assert _os.environ[key] == "http://set-by-the-environment:9999"
    finally:
        if before is None:
            _os.environ.pop(key, None)
        else:
            _os.environ[key] = before


def test_an_expired_token_is_not_passed_on_as_if_it_were_good() -> None:
    """An expired HUB_TOKEN produces 401s that read as the services refusing us.

    Cost a wrong inference on 2026-09-06: a stale token in a long-lived shell
    looked like AR2 accepting expired credentials.
    """
    od = _module()
    import base64 as _b64
    import json as _json
    import time as _time

    def token(exp: float) -> str:
        claims = _b64.urlsafe_b64encode(_json.dumps({"exp": exp}).encode()).decode().rstrip("=")
        return f"header.{claims}.signature"

    assert od._expired(token(_time.time() - 60)) is True
    assert od._expired(token(_time.time() + 3600)) is False
    assert od._expired("not-a-jwt") is False, "let the services judge what we cannot read"


# --------------------------------------------------------------------------
# The maps
# --------------------------------------------------------------------------

HONDURAS = (-89.4, 12.9, -83.1, 16.6)  # lon/lat bounds, generous


def _in_honduras(lat: float, lon: float) -> bool:
    west, south, east, north = HONDURAS
    return south <= lat <= north and west <= lon <= east


def test_the_drawn_ring_is_in_honduras_not_the_indian_ocean() -> None:
    """Leaflet takes [lat, lon]; GeoJSON stores [lon, lat].

    Swapping them is the classic silent error: the map renders happily, and the
    fields sit off the coast of Somalia. Nothing else in the notebook would
    notice, because the screens key off GeoIDs rather than off what is drawn.
    """
    od = _module()

    for feature in od.demo_fields():
        for lat, lon in od._ring_of(feature):
            assert _in_honduras(lat, lon), (
                f"{feature['properties']['name']} drawn at {lat}, {lon}, "
                "which is not Honduras -- the coordinate pair is probably swapped"
            )


def test_the_s2_cell_ring_lands_on_the_field_it_describes() -> None:
    """The cell drawn under a field has to be the cell the field is in."""
    od = _module()

    for feature in od.demo_fields():
        lon, lat = feature["properties"]["centroid"]
        ring = od.s2_cell_ring(feature["properties"]["s2_token"])
        lats = [point[0] for point in ring]
        lons = [point[1] for point in ring]

        assert min(lats) <= lat <= max(lats), "the field's centroid is outside its own S2 cell"
        assert min(lons) <= lon <= max(lons), "the field's centroid is outside its own S2 cell"


def test_the_ring_closes() -> None:
    """An unclosed ring renders as a wedge rather than a field."""
    od = _module()

    for feature in od.demo_fields():
        ring = od._ring_of(feature)
        assert ring[0] == ring[-1], f"{feature['properties']['name']} is not a closed ring"


def test_every_map_cell_checks_for_folium_first() -> None:
    """A reader without folium gets the tables, not a traceback.

    The maps are an aid to reading. Making them a hard dependency would mean a
    missing optional package takes down the parts of the notebook that carry
    the actual argument.
    """
    cells = [
        source
        for source in _notebook_cells()
        if "od.field_map(" in source or "od.consent_map(" in source
    ]
    assert len(cells) == 3, f"expected three map cells, found {len(cells)}"

    for source in cells:
        assert "od.have_folium()" in source, f"a map cell does not check for folium:\n{source}"
        assert "od.maps_unavailable()" in source, (
            f"a map cell does not say what to install when folium is missing:\n{source}"
        )


def test_the_map_helpers_do_not_reach_the_backend() -> None:
    """Geometry is computed from s2sphere; nothing about the data is local."""
    od = _module()
    source = Path(od.__file__).read_text()
    start = source.index("def s2_cell_ring")
    end = source.index("def _legend")

    assert "terrapipe_os" not in source[start:end]


def test_every_layer_is_either_drawn_or_named_as_not_drawn() -> None:
    """A coverage map that quietly omits layers is the failure it illustrates.

    The map exists to show that ``outside_coverage`` is a real statement about
    extent. If some layers were dropped without a word -- the ones declaring no
    bbox, or the ones wider than the view -- the picture would imply the library
    is smaller than it is, which is the same silent-absence problem the readings
    are careful about.
    """

    od = _module()
    pytest.importorskip("folium")

    layers = [
        {"layer_id": "national_a", "coverage": {"bbox": [-89.4, 12.9, -83.1, 17.5]}},
        {"layer_id": "national_b", "coverage": {"bbox": [-89.4, 12.9, -83.1, 17.5]}},
        {"layer_id": "regional", "coverage": {"bbox": [-88.7, 14.6, -84.2, 16.0]}},
        {"layer_id": "global_belt", "coverage": {"bbox": [-180.0, -30.0, 180.0, 30.0]}},
        {"layer_id": "undeclared", "coverage": {}},
    ]

    accounted = _legend_of(od.coverage_map(od.demo_fields(), layers))

    assert "2 layers sharing one extent" in accounted, "identical extents should be drawn once"
    assert "regional" in accounted
    assert "1 wider than this map, not drawn" in accounted
    assert "1 declaring no extent, not drawn" in accounted


def test_identical_extents_are_drawn_once_not_stacked() -> None:
    """Four rectangles on the same four corners is one muddy outline, not four."""
    od = _module()
    pytest.importorskip("folium")

    same = [-89.4, 12.9, -83.1, 17.5]
    layers = [{"layer_id": f"layer_{n}", "coverage": {"bbox": same}} for n in range(4)]

    drawn = od.coverage_map(od.demo_fields(), layers)._repr_html_()

    assert drawn.count("L.rectangle") == 1


def test_the_cover_map_separates_the_field_cell_from_its_refinement() -> None:
    """The whole point of the picture: which cells are the skirt.

    A cover is the field's own cell plus much smaller cells tracing the
    boundary, and it is that skirt which explains why a screen lands near what
    was placed rather than exactly on it. Colouring them alike would lose the
    argument the map is there to make.
    """

    od = _module()
    pytest.importorskip("folium")

    field = od.demo_fields()[0]
    token = field["properties"]["s2_token"]
    import s2sphere  # noqa: PLC0415

    core = s2sphere.CellId.from_token(token)
    skirt = [c.to_token() for c in list(core.children())[:2]]

    legend = _legend_of(od.cover_map(field, [token, *skirt]))

    assert "the field's own cell" in legend
    assert "boundary refinement" in legend
    assert "the registered boundary" in legend


# --------------------------------------------------------------------------
# The setup instructions
# --------------------------------------------------------------------------

REQUIREMENTS = DEMO / "requirements.txt"
PYTHON_FLOOR = (3, 10)


def _required_packages() -> set[str]:
    names = set()
    for line in REQUIREMENTS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-e"):
            continue
        names.add(re.split(r"[<>=!\[]", line)[0].strip().lower())
    return names


def test_every_package_the_notebook_needs_is_in_requirements() -> None:
    """A missing line here is a new reader hitting ImportError on a fresh venv.

    The instructions say "pip install -r requirements.txt" and then "run it", so
    that file is the whole contract. An import added to the support module
    without a matching requirement breaks setup for everyone who has not been
    carrying the package around already, and is invisible to us because our own
    environments have it.
    """
    third_party = {
        "folium": "folium",
        "httpx": "httpx",
        "mcp": "mcp",
        "requests": "requests",
        "s2sphere": "s2sphere",
    }
    source = (DEMO / "openscience_demo.py").read_text()
    declared = _required_packages()

    for module, package in third_party.items():
        if f"import {module}" in source:
            assert package in declared, (
                f"openscience_demo.py imports {module} but requirements.txt does not "
                f"list {package}; a fresh install would fail on it"
            )


def test_the_notebook_refuses_a_python_older_than_the_instructions_promise() -> None:
    """Stock macOS is 3.9, and the failure without this is unhelpful.

    Without the guard the first sign is pip refusing mcp with a wall of version
    numbers, or -- worse, if the packages came from somewhere else -- an import
    error several cells in that says nothing about the interpreter.
    """
    first = _notebook_cells()[0]

    assert "sys.version_info < (3, 10)" in first, "the version guard is gone"
    assert "3.10" in first

    # Without dropping the cell's own imports the exec below rebinds sys to the
    # real module and the guard cheerfully passes.
    guard = "\n".join(
        line
        for line in first[: first.index("def _find_support_module")].splitlines()
        if not line.startswith(("import ", "from "))
    )

    # A plain tuple compares the same way but has no .major/.minor, which the
    # message uses; sys.version_info is a named tuple, so the stub must be too.
    VersionInfo = collections.namedtuple("VersionInfo", "major minor micro")

    class NineDotNine:
        """Stands in for the sys a 3.9 kernel would hand the cell."""

        version_info = VersionInfo(3, 9, 6)

    with pytest.raises(SystemExit) as refused:
        exec(  # noqa: S102 - executing our own generated cell is the point
            compile(guard, "<cell>", "exec"),
            {"sys": NineDotNine, "os": os, "json": json, "textwrap": textwrap, "Path": Path},
        )

    said = str(refused.value)
    assert "3.10 or newer" in said
    assert "3.9" in said, "it should name the version actually in use"


def test_the_setup_section_names_both_platforms_and_the_python_floor() -> None:
    """The instructions are the deliverable for a reader who has never run this."""
    setup = "\n".join(
        "".join(c["source"])
        for c in json.loads(NOTEBOOK.read_text())["cells"]
        if c["cell_type"] == "markdown" and "Setting this up" in "".join(c["source"])
    )
    assert setup, "the notebook has no setup section"

    for needed in (
        "3.10",
        "requirements.txt",
        "demo.env",
        "venv",
        "Windows",
        "ipykernel",
    ):
        assert needed in setup, f"the setup section never mentions {needed}"

    assert "source .venv/bin/activate" in setup, "no POSIX activation line"
    assert "Activate.ps1" in setup, "no Windows activation line"


def test_the_clone_url_is_the_real_remote() -> None:
    """An instruction that starts with a wrong git clone wastes the whole visit."""
    setup = NOTEBOOK.read_text()
    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=DEMO.parent,
        capture_output=True,
        text=True,
    )
    if remote.returncode != 0:
        pytest.skip("no origin remote here")

    url = remote.stdout.strip()
    assert url in setup, f"the setup section does not clone {url}"


def test_the_notebook_reloads_its_support_module() -> None:
    """Python caches modules; a long-lived kernel runs code that no longer exists.

    Reported on 2026-09-06 as ``AttributeError: module 'openscience_demo' has no
    attribute 'have_folium'`` for a function plainly present in the file. The
    kernel had imported the module before the map helpers were added, and
    ``import openscience_demo`` is a no-op once it is in sys.modules -- so the
    notebook silently ran the old code and blamed the source.
    """
    first = _notebook_cells()[0]

    assert "importlib.reload(od)" in first, (
        "the first cell must reload the support module, or an edited helper "
        "will not reach a kernel that has already imported it"
    )


def test_reloading_does_not_stack_import_hooks() -> None:
    """The guard identifies itself by name because reload rebinds the class.

    ``isinstance(hook, _NoLocalBackend)`` is False against an instance created
    before a reload, so the already-installed check would miss and every reload
    would add another hook to sys.meta_path.
    """
    import importlib  # noqa: PLC0415

    od = _module()

    def installed() -> int:
        return sum(1 for hook in sys.meta_path if type(hook).__name__ == "_NoLocalBackend")

    before = installed()
    od.forbid_local_backend()
    once = installed()

    for _ in range(3):
        od = importlib.reload(od)
        od.forbid_local_backend()

    assert once <= before + 1
    assert installed() == once, "each reload stacked another copy of the guard"


def test_unedited_placeholders_are_not_reported_as_an_outage() -> None:
    """The likeliest first run: demo.env copied from the example, never edited.

    Telling someone that <node-host> "looks like a real outage" sends them to
    ask an operator why the deployment is down. Found by running the README's
    own instructions verbatim in a fresh clone.
    """
    od = _module()
    stack = {
        name: {"url": f"http://<{name}-host>:8200", "up": False, "detail": "ConnectionError"}
        for name in ("hub", "ar2-node", "pancake", "terrapipe-os")
    }

    said = od.mode(stack)

    assert "placeholder" in said
    assert "outage" not in said
    assert "README-openscience.md" in said


def test_the_three_reasons_a_run_cannot_start_are_told_apart() -> None:
    """Placeholders, no settings at all, and a genuine outage need different fixes."""
    od = _module()

    def stack(url: str) -> dict:
        return {
            name: {"url": url, "up": False, "detail": "ConnectionError"}
            for name in ("hub", "ar2-node", "pancake", "terrapipe-os")
        }

    placeholders = od.mode(stack("http://<node-host>:8200"))
    unconfigured = od.mode(stack("http://localhost:8200"))
    outage = od.mode(stack("http://66.220.3.83:8200"))

    assert len({placeholders, unconfigured, outage}) == 3, "two of these give the same advice"
    assert "placeholder" in placeholders
    assert "demo.env" in unconfigured and "placeholder" not in unconfigured
    assert "outage" in outage


def test_the_readme_covers_every_step_of_getting_started() -> None:
    """The page someone is handed. A missing step is a stranger stuck."""
    readme = DEMO / "README-openscience.md"
    assert readme.is_file(), "README-openscience.md must exist"
    text = readme.read_text()

    for step in (
        "python3 --version",
        "git clone",
        "-m venv .venv",
        "source .venv/bin/activate",
        "Activate.ps1",
        "pip install -r requirements.txt",
        "ipykernel install",
        "demo.env",
        "jupyter lab openscience_dpi_demo.ipynb",
        "3.10",
        "Set-ExecutionPolicy",
    ):
        assert step in text, f"README-openscience.md never mentions {step}"


def test_the_readme_troubleshoots_every_failure_we_have_actually_hit() -> None:
    """Each of these cost somebody a debugging session; none should cost a second."""
    text = (DEMO / "README-openscience.md").read_text()

    for symptom in (
        "AttributeError",  # stale module in a long-lived kernel
        "ModuleNotFoundError",  # support module not found from a foreign cwd
        "localhost",  # never told which deployment
        "folium",  # maps missing
        "SKIPPED",  # honest degradation, not a fault
    ):
        assert symptom in text, f"the README does not cover {symptom}"


def test_the_readme_points_at_the_same_requirements_the_notebook_installs() -> None:
    """Two sets of install instructions that can disagree is one too many."""
    text = (DEMO / "README-openscience.md").read_text()

    assert "requirements.txt" in text
    assert "pip install folium" not in text, (
        "naming a single package here duplicates requirements.txt and will drift"
    )


def _legend_of(canvas) -> str:
    """The legend's labels, read off the stable class rather than its styling."""
    import html as html_module

    drawn = html_module.unescape(canvas._repr_html_())
    return " ".join(re.findall(r'class="legend-label">([^<]*)</span>', drawn))


def _body_of(name: str) -> str:
    """The source of one top-level function in the support module.

    Slicing between two hand-picked strings looked fine and was not: the second
    anchor for inclusion_proof also appeared earlier in the file, so the slice
    came back empty and the assertions in it all passed against nothing. A check
    that cannot fail is indistinguishable from a passing one.
    """
    source = pathlib.Path(_module().__file__).read_text()
    start = source.index(f"def {name}(")
    rest = source[start:]
    following = re.search(r"\n(?:def |class |@dataclass\n)", rest)
    body = rest[: following.start()] if following else rest
    assert body.strip(), f"no body found for {name}"
    return body


def _rendered(canvas) -> str:
    import html as html_module

    return html_module.unescape(canvas._repr_html_())


def _every_map():
    """One of each map, with the arguments the notebook passes."""
    import s2sphere

    od = _module()
    fields = od.demo_fields()
    token = fields[0]["properties"]["s2_token"]
    skirt = [c.to_token() for c in s2sphere.CellId.from_token(token).children()][:4]
    verdicts = ["no_deforestation_detected", "deforestation_detected", "inconclusive",
                "no_deforestation_detected"]
    screens = {
        field["properties"]["name"]: {
            "verdict": verdict, "scope": "field", "cutoff_year": 2020,
            "deforested_fraction": 0.0, "coverage_fraction": 0.9,
        }
        for field, verdict in zip(fields, verdicts, strict=False)
    }
    layers = [
        {"layer_id": "icf_a", "coverage": {"bbox": [-89.4, 12.9, -83.1, 16.6]}},
        {"layer_id": "icf_b", "coverage": {"bbox": [-89.4, 12.9, -83.1, 16.6]}},
        {"layer_id": "palm", "coverage": {"bbox": [-88.5, 15.0, -84.0, 16.2]}},
        {"layer_id": "gfs", "coverage": {"bbox": [-180, -90, 180, 90]}},
    ]
    return {
        "field_map": od.field_map(fields),
        "field_map with verdicts": od.field_map(fields, screens=screens),
        "consent_map": od.consent_map(fields[0]),
        "cover_map": od.cover_map(fields[0], [token, *skirt]),
        "coverage_map": od.coverage_map(fields, layers),
    }


def test_every_basemap_is_black_and_white() -> None:
    """Coloured imagery hid the overlays; grey is the point, not a preference.

    Scoped to Leaflet's tile pane, so the imagery layer is desaturated too and
    the drawn shapes stay the only coloured thing on any base layer.
    """
    pytest.importorskip("folium")

    for name, canvas in _every_map().items():
        drawn = _rendered(canvas)
        assert "grayscale(100%)" in drawn, f"{name} does not desaturate its tiles"
        assert ".leaflet-tile-pane" in drawn, (
            f"{name} filters more than the tiles, which would grey out the overlays too"
        )


def test_no_basemap_needs_an_api_key() -> None:
    """folium's cartodbpositron warns that CartoDB now requires a key.

    A basemap that silently stops loading for a later reader is worse than one
    that was never offered, and this is not the kind of thing that fails at the
    time you change it.
    """
    pytest.importorskip("folium")

    # An allow-list of hosts, not a deny-list of one vendor. Spelling CartoDB's
    # name was not enough: folium renders that basemap from basemaps.cartocdn.com,
    # so a check looking for "cartodb" passed while the map used it.
    keyless = {"server.arcgisonline.com"}

    for name, canvas in _every_map().items():
        urls = re.findall(r'L\.tileLayer\(\s*"([^"]+)"', _rendered(canvas))
        assert urls, f"{name} renders no tile layer at all"
        for url in urls:
            host = urlparse(url.replace("{s}.", "")).netloc
            assert host in keyless, (
                f"{name} loads tiles from {host}, which is not a host we have "
                f"confirmed serves without an API key"
            )


def test_every_map_fits_itself_to_what_it_draws() -> None:
    """A fixed zoom framed one map and cut the rest off at the edge of the view."""
    pytest.importorskip("folium")

    for name, canvas in _every_map().items():
        assert "fitBounds" in _rendered(canvas), f"{name} uses a fixed zoom"


def test_the_fitted_box_contains_every_shape_with_room_to_spare() -> None:
    """Fitting to the shapes is only useful if nothing lands outside the box."""
    od = _module()
    fields = od.demo_fields()
    rings = [od._ring_of(field) for field in fields]

    (south, west), (north, east) = od._bounds(rings)

    for ring in rings:
        for lat, lon in ring:
            assert south < lat < north, "a field's latitude is outside the fitted box"
            assert west < lon < east, "a field's longitude is outside the fitted box"


def test_a_single_small_field_still_gets_a_margin() -> None:
    """Fitted exactly, three hectares fills the frame and Leaflet outruns the tiles."""
    od = _module()
    field = od.demo_fields()[0]
    ring = od._ring_of(field)

    (south, west), (north, east) = od._bounds([ring])

    lats = [p[0] for p in ring]
    assert north - max(lats) >= od.MIN_MARGIN * 0.99, "no margin above a small field"
    assert min(lats) - south >= od.MIN_MARGIN * 0.99, "no margin below a small field"


def test_every_overlay_is_a_layer_that_can_be_switched_off() -> None:
    """The reader's question is 'what changes if I turn this off', so let them."""
    pytest.importorskip("folium")

    for name, canvas in _every_map().items():
        drawn = _rendered(canvas)
        assert "L.control.layers" in drawn, f"{name} has no layer control"
        assert drawn.count("L.featureGroup") >= 2, (
            f"{name} draws everything into one layer, so nothing can be switched off"
        )


def test_a_masked_answer_is_drawn_beside_every_disclosed_one() -> None:
    """L0 around L1, so consent is visible rather than described.

    AR2 answers a GeoID without a grant at L0 with an S2 level-10 cell, and with
    a grant at L1 with the boundary. Both confirmed against the deployment on
    2026-09-06.
    """
    pytest.importorskip("folium")
    od = _module()

    field = od.demo_fields()[0]
    ring, _ = od.masked_ring(field)
    # A corner of the masked cell, to six places. Looking for the string "L0"
    # instead passed while the cell was not drawn at all, because the legend
    # still carried the word.
    corner = f"{ring[0][0]:.6f}"[:8]

    maps = _every_map()
    for name in ("field_map", "consent_map", "cover_map"):
        drawn = _rendered(maps[name])
        assert corner in drawn, f"{name} does not draw the masked cell, only mentions it"
        assert f"{od._ring_of(field)[0][0]:.6f}"[:8] in drawn, (
            f"{name} does not draw the disclosed boundary"
        )


def test_the_masked_cell_is_dotted_and_the_disclosed_one_is_not() -> None:
    """Told apart by shape as well as hue, for the same reason a legend has both."""
    pytest.importorskip("folium")
    od = _module()

    _, dashes, _ = od.DISCLOSURE["L0"]
    assert dashes, "the masked tier has no dash pattern"
    assert od.DISCLOSURE["L1"][1] is None, "the disclosed tier should be solid"

    drawn = _rendered(_every_map()["consent_map"])
    assert f'"dashArray": "{dashes}"' in drawn or f"'dashArray': '{dashes}'" in drawn, (
        "the masked cell is not drawn dotted"
    )


def test_the_masked_cell_encloses_the_field_it_stands_in_for() -> None:
    """Otherwise it is a rectangle somewhere near the field rather than about it."""
    od = _module()
    field = od.demo_fields()[0]

    ring, token = od.masked_ring(field)

    lats = [p[0] for p in ring]
    lons = [p[1] for p in ring]
    for lat, lon in od._ring_of(field):
        assert min(lats) <= lat <= max(lats), "the field falls outside its own masked cell"
        assert min(lons) <= lon <= max(lons), "the field falls outside its own masked cell"

    import s2sphere

    assert s2sphere.CellId.from_token(token).level() == od.MASKED_LEVEL


def test_the_masked_cell_is_the_level_ar2_actually_answers_with() -> None:
    """Pinned to the deployment, not to what would be convenient to draw.

    Asked on 2026-09-06: fetch-field without a grant returns MaskingLevel L0 and
    a level-10 token. If AR2 changes tier, this constant is wrong and the maps
    quietly illustrate a disclosure that is not being made.
    """
    od = _module()

    assert od.MASKED_LEVEL == 10
    assert f"level-{od.MASKED_LEVEL}" in od.DISCLOSURE["L0"][2], (
        "the legend wording and the drawn level can disagree"
    )


def test_every_map_carries_a_legend_with_a_title() -> None:
    """A colour that means something needs somewhere saying what."""
    pytest.importorskip("folium")

    for name, canvas in _every_map().items():
        drawn = _rendered(canvas)
        assert "font-weight:600" in drawn, f"{name} has an untitled legend"
        assert "position:fixed" in drawn, f"{name} has no legend at all"


def test_the_legend_shows_a_dotted_swatch_for_a_dotted_shape() -> None:
    """A solid block in the legend for a dotted outline is a legend that misleads."""
    pytest.importorskip("folium")
    od = _module()

    drawn = _rendered(_every_map()["consent_map"])

    assert "border-top:3px dashed" in drawn, "the legend has no dashed swatch"
    assert od.DISCLOSURE["L0"][0] in drawn


def test_drawn_shapes_use_one_colour_unless_the_colour_is_a_reading() -> None:
    """Hue is reserved for meaning: disclosure tier and verdict, nothing else.

    Before this the maps used five unrelated colours for five kinds of shape,
    which gave the reader a key to memorise and no information in return.
    """
    pytest.importorskip("folium")
    od = _module()

    allowed = {
        od.ACCENT.lower(), od.ACCENT_TINT.lower(), od.OUTLINE.lower(),
        od.DISCLOSURE["L0"][0].lower(), "#bdc3c7",
        *(colour.lower() for colour in od.VERDICT_COLOUR.values()),
    }

    for name, canvas in _every_map().items():
        drawn = _rendered(canvas)
        used = {
            match.lower()
            for match in re.findall(r'"(?:color|fillColor)": "(#[0-9a-fA-F]{6})"', drawn)
        }
        assert used <= allowed, f"{name} draws in unexplained colours: {sorted(used - allowed)}"


def test_fields_stay_visible_when_the_whole_country_is_in_view() -> None:
    """Three hectares at national zoom is under one pixel.

    The verdict map's job is to show all four verdicts at once, and it could not:
    the polygons were there and invisible until you zoomed into each field, so
    the map answered a question nobody could ask of it. A circle marker is sized
    in pixels rather than degrees, so it survives every zoom.
    """
    pytest.importorskip("folium")
    od = _module()
    fields = od.demo_fields()

    for name in ("field_map", "field_map with verdicts", "coverage_map"):
        drawn = _rendered(_every_map()[name])
        assert drawn.count("L.circleMarker") >= len(fields), (
            f"{name} spans the country but draws no marker for each field"
        )


def test_a_marker_sits_on_the_field_it_marks() -> None:
    """A dot near the field rather than on it is worse than no dot."""
    pytest.importorskip("folium")
    od = _module()

    field = od.demo_fields()[0]
    ring = od._ring_of(field)
    lats = [point[0] for point in ring]
    lons = [point[1] for point in ring]

    drawn = _rendered(od.field_map([field]))
    centres = re.findall(r"L\.circleMarker\(\s*\[([-\d.]+),\s*([-\d.]+)\]", drawn)

    assert centres, "no marker was drawn"
    for lat, lon in centres:
        assert min(lats) <= float(lat) <= max(lats), "a marker is off its field"
        assert min(lons) <= float(lon) <= max(lons), "a marker is off its field"


def test_the_demo_fields_are_polygons_not_points() -> None:
    """The dots on the map are a stand-in, and there has to be a thing behind them.

    Each field is a four-cornered S2 level-15 cell of about eight hectares. If
    these ever became points, the maps would be drawing a boundary that does not
    exist and the area figures would have nothing to come from.
    """
    od = _module()

    for field in od.demo_fields():
        assert field["geometry"]["type"] == "Polygon", "a demo field is not a polygon"
        ring = field["geometry"]["coordinates"][0]
        assert len(ring) >= 4, "a polygon needs at least three corners and a repeat"
        assert ring[0] == ring[-1], "the ring does not close"
        assert field["properties"]["area_ha"] > 0


def test_the_dot_gives_way_to_the_boundary_when_you_zoom_in() -> None:
    """A 12-pixel disc on top of an eight-hectare polygon shows a point, not a shape.

    The marker exists only because the polygon is sub-pixel at national zoom.
    Once the boundary is legible the marker is in the way, so it fades.
    """
    pytest.importorskip("folium")
    od = _module()

    for name in ("field_map", "field_map with verdicts", "coverage_map"):
        drawn = _rendered(_every_map()[name])
        assert "L.CircleMarker" in drawn, f"{name} never fades its markers"
        assert f"map.getZoom() >= {od.PIN_UNTIL_ZOOM}" in drawn, (
            f"{name} does not hand over at the documented zoom"
        )


def test_the_handover_script_runs_after_the_map_is_created() -> None:
    """The bug this pins blanked the map completely, tiles and all.

    Placed in the figure's html or script section, the handler is emitted before
    the block that creates the map. Referring to the map variable there throws,
    and the exception aborts the rest of that script -- which is where the view
    is set and the tiles are loaded. The failure does not look like a broken
    handler; it looks like an empty white rectangle.
    """
    pytest.importorskip("folium")

    for name, canvas in _every_map().items():
        drawn = canvas._repr_html_()
        handler = drawn.find("function tune")
        if handler == -1:
            continue
        created = drawn.find("L.map(")
        assert created != -1
        assert handler > created, (
            f"{name} emits its zoom handler before the map exists, which throws "
            f"and takes the rest of the map's script down with it"
        )


def test_the_handover_cannot_take_the_map_down_with_it() -> None:
    """Decoration should not be able to break the thing it decorates."""
    pytest.importorskip("folium")

    drawn = _rendered(_every_map()["field_map"])

    body = drawn[drawn.find("function tune"):]
    assert "try {" in body and "catch" in body, (
        "the zoom handler is unguarded, so a future change to it can blank the map"
    )


def test_a_map_of_one_field_frames_the_field_not_the_cell_around_it() -> None:
    """Fitting to the masked cell keeps the boundary too small to hand over to.

    81 km² against eight hectares: including the cell in the fit pulled a
    single-field map out to a zoom where the polygon was two pixels wide and the
    dot never got out of the way.
    """
    pytest.importorskip("folium")
    od = _module()

    field = od.demo_fields()[0]
    ring = od._ring_of(field)
    masked, _ = od.masked_ring(field)

    drawn = _rendered(od.field_map([field]))
    fitted = re.search(r"fitBounds\(\s*\[\[([-\d.]+),\s*([-\d.]+)\],\s*\[([-\d.]+),\s*([-\d.]+)\]",
                       drawn)
    assert fitted, "the map does not fit its bounds"
    south, west, north, east = (float(value) for value in fitted.groups())

    field_height = max(p[0] for p in ring) - min(p[0] for p in ring)
    masked_height = max(p[0] for p in masked) - min(p[0] for p in masked)
    assert north - south < masked_height / 2, "the map is framed on the masked cell"
    assert north - south >= field_height, "the field does not fit in the frame"


def test_every_layer_the_node_serves_is_described_or_named_as_undescribed() -> None:
    """A catalogue that quietly omits an entry misrepresents the library.

    The facts about a layer come from the node; the sentence saying what it is
    for is the notebook's own, and the two live in different places. Anything
    the node adds that this notebook has not met must show up as undescribed
    rather than vanish.
    """
    od = _module()

    catalogue = [
        {"layer_id": "something_new", "title": "A layer added after this was written",
         "source": "Somebody", "licence": "CC0", "coverage": {}},
    ]

    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        od.show_library(catalogue)
    shown = printed.getvalue()

    assert "something_new" in shown
    assert "not described in this notebook" in shown, (
        "an unknown layer is printed as though it were understood"
    )


def test_the_catalogue_describes_the_layers_the_demo_actually_leans_on() -> None:
    """The three a reader has to understand to follow any verdict."""
    od = _module()

    for layer_id in (
        "jrc_tmf_deforestation_year",
        "icf_honduras_cafe_2020",
        "icf_honduras_palma_africana_2020",
    ):
        assert layer_id in od.LAYER_NOTES, f"{layer_id} carries a verdict and is undescribed"
        assert len(od.LAYER_NOTES[layer_id]) > 40, f"{layer_id} has a description that says nothing"


def test_the_catalogue_is_asked_of_the_node_not_written_down() -> None:
    """A hardcoded list is a list that is wrong the first time a layer is added."""
    body = _body_of("library")
    assert "/layers" in body and "requests.get" in body, (
        "the catalogue does not come from the node"
    )

    # The facts a reader would act on must not be invented here.
    for invented in ('"licence":', '"source":', '"title":'):
        assert invented not in body, f"library() fabricates {invented} instead of asking"


def test_the_catalogue_needs_no_token_and_no_geoid() -> None:
    """The point the section makes: a public library, private readings.

    Consent is needed to learn something about a particular field, not to find
    out what could be learned about one. If listing the library started
    requiring a grant, the section's argument would be false.
    """
    body = _body_of("library")

    assert "Authorization" not in body, "listing the library asks for a token"
    assert "grant" not in body.lower(), "listing the library asks for a grant"


def test_the_notebook_credits_the_icf_geoportal_the_layers_came_from() -> None:
    """Five of twelve layers are somebody's national mapping, downloaded from a site."""
    od = _module()
    built = (DEMO / "build_openscience_notebook.py").read_text()

    assert "geoportal.icf.gob.hn" in built, "the ICF layers' origin is not named"
    assert "geoportal.icf.gob.hn" in od.ICF_GEOPORTAL

    icf = [layer for layer in od.LAYER_NOTES if layer.startswith("icf_honduras")]
    assert len(icf) == 5, f"expected the five ICF geoportal downloads, found {icf}"


def test_the_catalogue_does_not_repeat_the_nodes_broken_mirrored_flag() -> None:
    """Fixed in terrapipe-os on 2026-09-06; a node not yet restarted still sends it.

    ``mirrored`` was read off the layer definition, which is the same document on
    every node and cannot know what any one node holds. The demo node reported
    ``mirrored: false`` for ten of twelve layers while answering reads of them
    with real data. Showing that to a reader would tell them the library is
    empty when it is not.
    """
    body = _body_of("show_library")

    assert "mirrored" not in body, (
        "the catalogue prints the node's mirrored flag, which is wrong on any "
        "node running a build from before the fix"
    )


# --------------------------------------------------------------------------
# Consent, shown rather than described
# --------------------------------------------------------------------------


def test_the_disclosure_table_shows_the_scope_beside_every_reading() -> None:
    """A number without its scope is the confusion the whole tier exists to stop.

    0.0116 and 0.4170 are the same clearing measured over 81 km² and over 8.9
    hectares. Printed without saying which, the coarse one reads as a clean
    field.
    """
    od = _module()

    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        od.show_disclosure([
            ("nothing", 200, {"scope": "neighbourhood", "deforested_fraction": 0.0116,
                              "verdict": "deforestation_detected"}),
            ("a field-access grant", 200, {"scope": "field", "deforested_fraction": 0.4170,
                                           "verdict": "deforestation_detected"}),
            ("the same, now revoked", 403, {"reason": "grant_refused"}),
        ])
    shown = printed.getvalue()

    assert "neighbourhood" in shown and "field" in shown
    assert "0.0116" in shown and "0.4170" in shown
    for line in shown.splitlines()[1:]:
        if "0.0116" in line:
            assert "neighbourhood" in line, "a reading is printed away from its scope"


def test_a_revoked_grant_is_refused_rather_than_quietly_downgraded() -> None:
    """Silent fallback would make withdrawal indistinguishable from never granting.

    Confirmed against the deployment on 2026-09-06: the same credential that
    answered at field scope is refused 403 seconds after revocation, rather than
    dropping back to the neighbourhood answer.
    """
    od = _module()

    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        od.show_disclosure([("the same, now revoked", 403, {"reason": "grant_refused"})])
    shown = printed.getvalue()

    assert "403" in shown
    assert "neighbourhood" not in shown, "a refusal is being shown as a coarse answer"


def test_the_notebook_asks_the_same_question_at_every_tier() -> None:
    """The comparison is only worth anything if nothing else changed."""
    body = _body_of("screen_with")

    assert body.count("requests.get") == 1, "the tiers are served by different calls"
    assert "X-Field-Grant" in body
    # The grant is the only difference between the calls.
    assert body.count("/screen/") == 1


def test_revocation_names_the_credential_not_the_list() -> None:
    """Revoking by list would withdraw every grant ever issued over those fields."""
    body = _body_of("revoke")

    assert "jti" in body, "revocation does not name a credential"
    assert "list_id" not in body, "revocation is scoped to a list, not a credential"


def test_a_grant_carries_the_handles_needed_to_withdraw_and_to_trace() -> None:
    """field_grant returns only a credential, which cannot be revoked or traced with."""
    od = _module()

    assert {"credential", "list_id", "jti", "why"} <= set(od.Consent.__dataclass_fields__)


# --------------------------------------------------------------------------
# Trace, as its own use case
# --------------------------------------------------------------------------


def test_trace_runs_in_both_directions_from_different_starting_points() -> None:
    """Back from a lot to its fields; forward from a field to its lots.

    Two different endpoints, because they are two different questions. Trace
    back reads one list. Trace forward has to find every list a field entered,
    which is the direction a recall runs in.
    """
    back = _body_of("trace_back")
    forward = _body_of("lists_containing")

    assert "/traceback" in back and "list_id" in back
    assert "/reverse/" in forward and "geo_id" in forward


def test_tracing_back_needs_the_grant_for_that_list() -> None:
    """AR2 answers an unauthorised trace with 404, and the helper must say why.

    A 403 would confirm the list exists to someone with no right to know it, so
    AR2 masks the authorisation failure as absence. Read naively that reports a
    missing lot, which is a different and much more alarming thing.
    """
    back = _body_of("trace_back")

    assert "X-Grant-Token" in back, "trace back presents no grant"
    assert "HTTP_NOT_FOUND" in back or "404" in back, "the masked refusal is not handled"
    assert "grant does not cover" in back, (
        "a 404 is passed through as absence rather than as the refusal it is"
    )


def test_the_screening_narrative_runs_to_the_ledger_uninterrupted() -> None:
    """Trace moved to its own notebook; what is left must still read in order.

    Replaces a test that asserted trace sat last. It did, for the right reason
    -- a consignment is a different question from a field -- and that reason is
    why it is now N3's.
    """
    built = (DEMO / "build_openscience_notebook.py").read_text()

    verdicts = built.index("## 6. The four verdicts")
    vintages = built.index("## 7. The same field, in three national maps")
    dds = built.index("## 13. Out to the regulator")
    ledger = built.index("## 16. What this run actually demonstrated")

    assert verdicts < vintages < dds < ledger
    assert ledger == max(built.index(h) for h in re.findall(r"^## \d+\. .+$", built, re.M)), (
        "the ledger must come last; it summarises the run"
    )


def test_the_sections_are_numbered_without_a_gap() -> None:
    """A renumber that skips one is the sort of thing nobody notices in review."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    numbers = [int(n) for n in re.findall(r'^## (\d+)\. ', built, re.M)]

    assert numbers == sorted(numbers), f"sections are out of order: {numbers}"
    assert numbers == list(range(len(numbers))), f"a section number is missing: {numbers}"


def test_an_inclusion_proof_reveals_no_other_member() -> None:
    """The point of proving membership with a Merkle path rather than the list."""
    body = _body_of("inclusion_proof")

    assert "/proof/" in body
    assert "geoids" not in body and "members" not in body, (
        "the proof helper reads the list's membership, which defeats the purpose"
    )


# --------------------------------------------------------------------------
# The ledger, and the cell that used to break it
# --------------------------------------------------------------------------


def test_re_running_a_step_does_not_count_it_twice() -> None:
    """A reader re-runs a cell to watch it happen. That is not a second demo.

    From the run of 2026-09-06: five cells were re-run and the closing line
    read "18 against live services, 5 against local data" for a notebook with
    fifteen live steps and three local ones.
    """
    od = _module()
    ledger = od.Ledger()

    ledger.record("screen each field", od.LIVE)
    ledger.record("turn a screen into a BITE", od.LOCAL, "Pancake's adapter")
    ledger.record("screen each field", od.LIVE)

    assert len(ledger.steps) == 2
    assert ledger.checklist().count("screen each field") == 1
    assert "1 against live services, 1 against local data" in ledger.checklist()


def test_a_re_run_step_reports_its_latest_outcome() -> None:
    """Succeeded once and failed since is failed, not succeeded."""
    od = _module()
    ledger = od.Ledger()

    ledger.record("screen each field", od.LIVE)
    ledger.record("screen each field", od.FAILED, "ConnectionError")

    assert [s.outcome for s in ledger.steps] == [od.FAILED]
    assert "ConnectionError" in ledger.checklist()


def test_a_re_run_step_keeps_its_place_in_the_narrative() -> None:
    """The ledger reads in the order of the document, not of the reader's clicks."""
    od = _module()
    ledger = od.Ledger()

    for name in ("register boundaries", "issue a grant", "screen each field"):
        ledger.record(name, od.LIVE)
    ledger.record("issue a grant", od.LIVE)

    assert [s.name for s in ledger.steps] == [
        "register boundaries", "issue a grant", "screen each field",
    ]


def test_the_consent_cell_does_not_revoke_the_notebooks_own_grant() -> None:
    """It ends by revoking what it holds, so it must not hold the shared one.

    This is what made the 2026-09-06 run show a 403 in the row that carries the
    entire consent argument.
    """
    built = (DEMO / "build_openscience_notebook.py").read_text()
    start = built.index('with od.step("the same screen at three disclosure tiers")')
    cell = built[start:built.index('od.show_disclosure(DISCLOSURE)', start)]

    assert "od.revoke(" in cell, "the cell no longer demonstrates revocation"
    assert "od.revoke(CONSENT.jti" not in cell, (
        "the cell revokes the notebook's shared consent, so running it twice "
        "asks with a credential its own previous run destroyed"
    )
    assert "TIERS = od.consent_for(" in cell, "the cell does not mint its own consent"
    assert "od.revoke(TIERS.jti" in cell


def test_the_notebook_no_longer_needs_to_repair_its_own_grant() -> None:
    """The reissue step existed only to undo damage this cell should not do."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    assert "reissue the grant" not in built, (
        "a cell repairs the credential another cell broke; the break is the defect"
    )


def test_the_table_contradicts_the_prose_out_loud() -> None:
    """Markdown says the same thing whatever the table above it shows."""
    od = _module()

    notes = od._where_the_table_disagrees_with_the_text([
        ("nothing", 200, {"scope": "neighbourhood", "deforested_fraction": 0.0116}),
        ("a field-access grant", 403, {"reason": "grant_refused"}),
        ("the same, now revoked", 403, {"reason": "grant_refused"}),
    ])

    assert notes, "the run of 2026-09-06 would still pass without comment"
    assert any("403" in n and "not 200" in n for n in notes)


def test_a_good_run_is_not_nagged() -> None:
    """A check that fires on correct runs gets ignored, then deleted."""
    od = _module()

    notes = od._where_the_table_disagrees_with_the_text([
        ("nothing", 200, {"scope": "neighbourhood", "deforested_fraction": 0.0116}),
        ("a field-access grant", 200, {"scope": "field", "deforested_fraction": 0.4170}),
        ("the same, now revoked", 403, {"reason": "grant_refused"}),
    ])

    assert notes == []


def test_a_revoked_credential_that_still_answers_is_called_a_defect() -> None:
    """The silent downgrade the section exists to rule out."""
    od = _module()

    notes = od._where_the_table_disagrees_with_the_text([
        ("nothing", 200, {"scope": "neighbourhood", "deforested_fraction": 0.0116}),
        ("a field-access grant", 200, {"scope": "field", "deforested_fraction": 0.4170}),
        ("the same, now revoked", 200, {"scope": "neighbourhood", "deforested_fraction": 0.0116}),
    ])

    assert any("still answered" in n for n in notes)


def test_a_grant_that_does_not_widen_the_scope_is_reported() -> None:
    """A 200 at neighbourhood scope is a refusal wearing a success code.

    The readings differ so that only the scope check can produce a note. With
    them equal this passed against a deliberately disabled scope check, because
    the note about identical readings also contains the word "scope".
    """
    od = _module()

    notes = od._where_the_table_disagrees_with_the_text([
        ("nothing", 200, {"scope": "neighbourhood", "deforested_fraction": 0.0116}),
        ("a field-access grant", 200, {"scope": "neighbourhood", "deforested_fraction": 0.0223}),
    ])

    assert any("'neighbourhood' scope rather than" in n for n in notes)


# --------------------------------------------------------------------------
# "The node holds nothing for this" is not a demonstration
# --------------------------------------------------------------------------


def test_a_node_holding_no_data_is_not_recorded_as_a_demonstration() -> None:
    """The failure this outcome exists for.

    On 2026-09-06 the NDVI and GFS steps both got 404 with reason no_data --
    the node has neither layer for any demo field -- and the ledger recorded
    both LIVE, because step() records LIVE unless an exception is raised.
    """
    od = _module()
    state = {"outcome": od.LIVE, "detail": ""}

    got, why = od.holds_data(
        _Response(404, {"reason": "no_data", "detail": "layer ndvi_sentinel2 has no data"}), state
    )

    assert got is False
    assert state["outcome"] == od.EMPTY
    assert "no data" in state["detail"]


def test_a_reading_is_still_a_reading() -> None:
    """A check that fires on good data would make the badge meaningless."""
    od = _module()
    state = {"outcome": od.LIVE, "detail": ""}

    got, _ = od.holds_data(_Response(200, {"value": 0.62, "layer_id": "ndvi_sentinel2"}), state)

    assert got is True
    assert state["outcome"] == od.LIVE


def test_a_malformed_request_is_a_failure_not_an_empty_cupboard() -> None:
    """Asking wrongly is a defect in the notebook. Different word, different fix."""
    od = _module()
    state = {"outcome": od.LIVE, "detail": ""}

    od.holds_data(
        _Response(422, {"reason": "invalid_request",
                        "detail": "layer ndvi_sentinel2 partitions by day"}), state
    )

    assert state["outcome"] == od.FAILED, (
        "a request the node rejected as malformed is filed as a bare cupboard"
    )


def test_a_two_hundred_that_says_no_data_is_still_no_data() -> None:
    """The status code is not the whole answer."""
    od = _module()
    state = {"outcome": od.LIVE, "detail": ""}

    got, _ = od.holds_data(_Response(200, {"reason": "no_data", "detail": "nothing here"}), state)

    assert got is False
    assert state["outcome"] == od.EMPTY


def test_the_empty_outcome_is_counted_and_explained() -> None:
    """A count that omits it would let the reader add up the wrong total."""
    od = _module()
    ledger = od.Ledger()
    ledger.record("screen each field", od.LIVE)
    ledger.record("NDVI for a field", od.EMPTY, "no data for this GeoID")

    text = ledger.checklist()

    assert "1 answered with no data" in text
    assert "needs ingesting" in text


def test_an_empty_step_does_not_get_a_ticked_box() -> None:
    """A ticked box reads as success whatever word sits beside it."""
    od = _module()
    ledger = od.Ledger()
    ledger.record("NDVI for a field", od.EMPTY, "no data")

    assert ledger.checklist().startswith("[ ]")


def test_every_step_that_reads_a_layer_classifies_the_answer() -> None:
    """Any read can come back empty, so any read must be able to say so."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    for endpoint in ("/data/", "/forecast/"):
        for start in _positions_of(built, endpoint):
            cell = built[max(0, start - 1200):start + 600]
            assert "holds_data" in cell, (
                f"a read of {endpoint} does not classify its answer, so a node "
                "holding nothing would be recorded as a demonstration"
            )


def _positions_of(text: str, needle: str) -> list[int]:
    out, at = [], text.find(needle)
    while at != -1:
        out.append(at)
        at = text.find(needle, at + 1)
    return out


class _Response:
    """The two bits of a requests.Response that holds_data looks at."""

    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


# --------------------------------------------------------------------------
# N2: a verifiable draw, three vintages, and a disagreement worth keeping
# --------------------------------------------------------------------------

_LIST_ID = "aced0d668cf579b5e5c2f1a0b7d3e8c491f26a7b0d3e5f8a1c4b7d0e3f6a9c2b"
_MEMBERS = [f"{n:064x}" for n in range(40)]


def test_the_draw_is_the_same_for_everyone_who_holds_the_list() -> None:
    """The whole claim. If it is not reproducible it is no better than a bottle."""
    od = _module()

    mine = od.verifiable_sample(_LIST_ID, _MEMBERS, 9)
    yours = od.verifiable_sample(_LIST_ID, list(reversed(_MEMBERS)), 9)

    assert mine == yours, "the draw depends on the order the members were handed over"


def test_a_shuffled_population_cannot_change_the_draw() -> None:
    """An auditor's copy of the list will not be in the drawer's order."""
    od = _module()
    import random

    shuffled = list(_MEMBERS)
    random.Random(7).shuffle(shuffled)

    assert od.verifiable_sample(_LIST_ID, shuffled, 9) == od.verifiable_sample(
        _LIST_ID, _MEMBERS, 9
    )


def test_a_different_list_draws_different_names() -> None:
    """If the seed did not bind the draw to the population, it would prove nothing."""
    od = _module()

    other = _LIST_ID[:-1] + ("f" if _LIST_ID[-1] != "f" else "0")

    assert od.verifiable_sample(other, _MEMBERS, 9) != od.verifiable_sample(
        _LIST_ID, _MEMBERS, 9
    )


def test_the_draw_does_not_lean_on_pythons_random_number_generator() -> None:
    """Its algorithm has changed before, which would void every published draw."""
    od = _module()
    # The docstring names the very thing being ruled out, and the function is
    # itself called ...sample(, so both have to come off before searching.
    body = _code_only(od.verifiable_sample) + _code_only(od._ranked)

    for banned in ("random.", "Random(", ".shuffle", "random.sample"):
        assert banned not in body, (
            f"the draw uses {banned}, so it is only reproducible on one Python"
        )
    assert "hashlib.sha256" in body, "the draw is not seeded by a stable hash"


def _code_only(function) -> str:
    """A function's source with its docstring removed."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    node = tree.body[0]
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)):
        node.body = node.body[1:]
    return ast.unparse(tree)


def test_the_reserves_carry_on_where_the_sample_stopped() -> None:
    """The guide asks for spare names so absences do not shrink the sample."""
    od = _module()

    sample, reserves = od.draw_with_reserves(_LIST_ID, _MEMBERS, 9)

    assert len(sample) == 9
    assert len(sample) + len(reserves) == len(_MEMBERS)
    assert not set(sample) & set(reserves)
    # The reserve order is the same ranking continued, so a replacement is due
    # to somebody in particular rather than chosen.
    assert od.verifiable_sample(_LIST_ID, _MEMBERS, 10)[-1] == reserves[0]


def test_everyone_in_the_population_can_be_drawn() -> None:
    """A draw that could never pick some members is not a random sample."""
    od = _module()

    reachable = set()
    for size in range(1, len(_MEMBERS) + 1):
        reachable |= set(od.verifiable_sample(_LIST_ID, _MEMBERS, size))

    assert reachable == set(_MEMBERS)


def test_the_sample_sizes_are_the_guides_own_figures() -> None:
    """Transcribed, so a disagreement with a formula is visible not silent."""
    od = _module()

    assert od.interviews_needed(1_000, one_in=10)[0] == 29
    assert od.interviews_needed(1_000_000, one_in=10)[0] == 29
    assert od.interviews_needed(100, one_in=10)[0] == 25
    assert od.interviews_needed(1_000)[1] == 278


def test_a_population_between_two_rows_is_rounded_up() -> None:
    """Rounding down would report a sample smaller than the guide requires."""
    od = _module()

    detect, prevalence, why = od.interviews_needed(700, one_in=10)

    assert (detect, prevalence) == od.interviews_needed(1_000, one_in=10)[:2]
    assert "1,000 row" in why


def test_a_share_the_guide_does_not_tabulate_is_refused() -> None:
    """Interpolating between its rows would be this notebook's arithmetic, not the guide's."""
    od = _module()

    with pytest.raises(ValueError, match="tabulates"):
        od.interviews_needed(1_000, one_in=3)


def test_a_bare_code_is_resolved_from_the_publishers_own_legend() -> None:
    """Both vintages, because the same number means different things in each."""
    od = _module()

    assert od.resolve_label("icf_honduras_forest_cover_2018", "unlabelled_12") == (
        "Cafetales", True
    )
    assert od.resolve_label("icf_honduras_forest_cover_2014", "unlabelled_14") == (
        "Cafetales", True
    )


def test_the_codebooks_disagree_where_the_publishers_legends_disagree() -> None:
    """The finding this section exists for, pinned so a tidy-up cannot erase it.

    Code 12 is Cafetales in 2018 and Pastos/Cultivos in 2014. If these ever
    agree, either a transcription was wrong or the trap has gone away, and
    both are worth stopping for.
    """
    od = _module()

    assert od.ICF_CODEBOOKS["icf_honduras_forest_cover_2018"][12] == "Cafetales"
    assert od.ICF_CODEBOOKS["icf_honduras_forest_cover_2014"][12] == "Pastos/Cultivos"
    assert od.ICF_CODEBOOKS["icf_honduras_forest_cover_2014"][14] == "Cafetales"


def test_a_code_no_legend_covers_is_left_as_it_came() -> None:
    """Inventing a label to fill a gap is how a wrong one becomes permanent."""
    od = _module()

    assert od.resolve_label("icf_honduras_forest_cover_2014", "unlabelled_99") == (
        "unlabelled_99", False
    )
    assert od.resolve_label("icf_honduras_forest_cover_2024", "cafe") == ("cafe", False)


def test_a_code_this_notebook_cannot_name_is_said_out_loud() -> None:
    """The bug this replaced: unnameable read as "the node has declared it"."""
    od = _module()

    notes = od._what_the_vintages_show([
        {"year": "2014", "layer_id": "icf_honduras_forest_cover_2014",
         "classes": {"unlabelled_1": 1.0}, "why": ""},
    ])

    assert any("cannot name" in note for note in notes)
    assert not any("legends have been declared" in note for note in notes), (
        "a code this notebook cannot resolve is reported as one the node has declared"
    )


def test_the_unchanged_crop_case_is_only_claimed_when_the_run_shows_it() -> None:
    od = _module()
    coffee_everywhere = [
        {"year": "2014", "layer_id": "icf_honduras_forest_cover_2014",
         "classes": {"unlabelled_14": 0.99}, "why": ""},
        {"year": "2018", "layer_id": "icf_honduras_forest_cover_2018",
         "classes": {"unlabelled_12": 1.0}, "why": ""},
        {"year": "2024", "layer_id": "icf_honduras_forest_cover_2024",
         "classes": {"cafe": 0.96}, "why": ""},
    ]

    assert any("did not happen" in n for n in od._what_the_vintages_show(coffee_everywhere))

    pasture = list(coffee_everywhere)
    pasture[2] = {"year": "2024", "layer_id": "icf_honduras_forest_cover_2024",
                  "classes": {"pastizales": 0.76}, "why": ""}
    notes = od._what_the_vintages_show(pasture)
    assert any("not in\nevery vintage" in n or "not in every vintage" in n for n in notes)
    assert not any("did not happen" in n for n in notes)


def test_the_vintage_section_reads_the_field_it_is_about() -> None:
    """It ran on whichever field came first, which was pasture, and showed nothing."""
    built = (DEMO / "build_openscience_notebook.py").read_text()
    section = built[built.index("read three vintages"):built.index("A population, and a draw")]

    assert "the_coffee_field" in section
    assert "COFFEE_ID" in section
    assert "SUBJECT_ID" not in section, (
        "the coffee sections read whichever field the notebook happened to pick first"
    )


def test_the_coffee_field_is_chosen_by_asking_not_by_name() -> None:
    """Hard-coding it would let a change to the demo fields go unnoticed."""
    od = _module()
    body = inspect.getsource(od.the_coffee_field)

    assert "compliant_coffee" not in body
    assert "icf_honduras_forest_cover_2024" in body


def test_shade_grown_coffee_read_as_forest_is_named_not_scored() -> None:
    """The guide's false positive. A number here would get averaged into something."""
    od = _module()

    verdict = od.agroforestry_case({
        "national": {"cafe": 0.963},
        "global": {"esa_worldcover": {"tree_cover": 0.999}, "hansen_treecover_2000": 71.2},
        "why": "",
    })

    assert "AGROFORESTRY FALSE-POSITIVE" in verdict
    assert "agroforestry is not forest" in verdict
    assert "needs a human" in verdict


def test_a_field_that_is_not_agroforestry_is_not_flagged() -> None:
    """A warning that fires on everything is one nobody reads."""
    od = _module()

    assert not od.agroforestry_case({
        "national": {"pastizales": 0.76},
        "global": {"esa_worldcover": {"tree_cover": 0.975}},
        "why": "",
    }), "pasture under canopy is reported as the shade-coffee case"

    assert not od.agroforestry_case({
        "national": {"cafe": 0.96},
        "global": {"esa_worldcover": {"grassland": 0.9, "tree_cover": 0.1}},
        "why": "",
    }), "coffee with no canopy reading is reported as a disagreement"


def test_the_notebook_does_not_invent_a_pest_layer() -> None:
    """Asked for, absent, and the absence is the finding.

    GBIF holds two records of coffee leaf rust for the whole of Honduras. A
    risk score built on that would look like the others and mean nothing.
    """
    built = (DEMO / "build_openscience_notebook.py").read_text()

    assert "no open field-level pest surveillance layer" in built
    for invented in ("pest_risk", "rust_risk", "disease_pressure", "pest_score"):
        assert invented not in built, f"a {invented} layer appears from nowhere"


def test_the_agent_is_shown_being_refused_and_then_allowed() -> None:
    """The same tool, differing only in the credential. That is the whole point."""
    built = (DEMO / "build_openscience_notebook.py").read_text()
    turn = built[built.index("ask the node four questions"):]
    turn = turn[:turn.index('""")')]

    reads = turn.count('"read_layer"')
    assert reads == 2, f"the grant/no-grant contrast needs two read_layer calls, found {reads}"
    assert '"field_grant": GRANT' in turn
    assert turn.index('"read_layer"') < turn.index('"field_grant": GRANT'), (
        "the grant is presented before the refusal, so the contrast reads backwards"
    )


def test_the_agent_turn_is_not_a_language_model() -> None:
    """A model call would make the committed output a record of what a model said."""
    od = _module()
    body = inspect.getsource(od.ask_the_node)

    for absent in ("openai", "anthropic", "OPENAI_API_KEY", "completion"):
        assert absent not in body


def test_the_notebook_points_at_its_two_companions() -> None:
    """Split into three, so each has to say where the rest went."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    assert "ar2_field_identity_demo.ipynb" in built
    assert "traceability_demo.ipynb" in built


def test_trace_has_moved_out_to_its_own_notebook() -> None:
    """A different question, and it was the last section for that reason."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    assert "traceback" not in built.lower().replace("trace-back", "")
    assert "inclusion_proof" not in built


def test_the_sections_are_numbered_in_the_order_they_are_read() -> None:
    """Three were inserted and two moved out; a stale number sends readers astray."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    numbers = [int(n) for n in re.findall(r"^## (\d+)\. ", built, re.M)]

    assert numbers == list(range(len(numbers))), f"sections run {numbers}"


# --------------------------------------------------------------------------
# AG-014: the draw is grindable unless something unpredictable seeds it
# --------------------------------------------------------------------------


def test_a_draw_seeded_by_the_list_alone_admits_it_is_grindable() -> None:
    """The correction. The first version claimed the list_id was enough."""
    od = _module()

    made = od.draw(_LIST_ID, _MEMBERS, 9)

    assert made.grindable is True


def test_a_beacon_bound_draw_is_not_grindable() -> None:
    od = _module()

    made = od.draw(_LIST_ID, _MEMBERS, 9, entropy=od.Beacon("drand", 6_446_150, "ab" * 32))

    assert made.grindable is False
    assert "drand round 6446150" in made.seed_description


def test_an_auditors_nonce_also_removes_the_grind() -> None:
    """A different trust assumption, and the guide already trusts the auditor."""
    od = _module()

    made = od.draw(_LIST_ID, _MEMBERS, 9, entropy="nonce-handed-over-at-the-meeting")

    assert made.grindable is False
    assert "auditor nonce" in made.seed_description


def test_a_grindable_draw_says_so_where_a_reader_will_see_it() -> None:
    """A flag nobody prints is a flag nobody acts on."""
    od = _module()
    shown = io.StringIO()

    with contextlib.redirect_stdout(shown):
        od.show_draw(od.draw(_LIST_ID, _MEMBERS, 5), len(_MEMBERS))

    text = shown.getvalue()
    assert "NOTE" in text
    assert "not unpredictable" in text


def test_a_beacon_bound_draw_is_not_nagged() -> None:
    """A warning printed on every draw is one nobody reads."""
    od = _module()
    shown = io.StringIO()

    with contextlib.redirect_stdout(shown):
        od.show_draw(
            od.draw(_LIST_ID, _MEMBERS, 5, entropy=od.Beacon("drand", 1, "cd" * 32)),
            len(_MEMBERS),
        )

    assert "NOTE" not in shown.getvalue()


def test_a_different_beacon_round_draws_different_names() -> None:
    """If the beacon did not change the draw, it would be decoration."""
    od = _module()

    first = od.draw(_LIST_ID, _MEMBERS, 9, entropy=od.Beacon("drand", 1, "ab" * 32))
    second = od.draw(_LIST_ID, _MEMBERS, 9, entropy=od.Beacon("drand", 2, "ef" * 32))

    assert first.sample != second.sample


def test_the_same_round_redraws_the_same_names_from_nothing_but_the_inputs() -> None:
    """What an auditor does years later: fetch the cited round and recompute."""
    od = _module()
    cited = od.Beacon("drand", 6_446_150, "ab" * 32)

    original = od.draw(_LIST_ID, _MEMBERS, 9, entropy=cited)
    auditor = od.draw(_LIST_ID, list(reversed(_MEMBERS)), 9,
                      entropy=od.Beacon("drand", 6_446_150, "ab" * 32))

    assert auditor.sample == original.sample


def test_the_recipe_names_everything_needed_to_recheck_it() -> None:
    """Step 8 asks how the sample was chosen. A recipe missing a term is not one."""
    od = _module()

    recipe = od.draw(_LIST_ID, _MEMBERS, 9,
                     entropy=od.Beacon("drand", 6_446_150, "ab" * 32)).recipe

    assert _LIST_ID[:16] in recipe
    assert "6446150" in recipe
    assert "9" in recipe


def test_subgroups_draw_independently_of_each_other() -> None:
    """Without the stratum in the seed, a field ranks the same in every group."""
    od = _module()

    # The same members under two stratum names. draw_by_subgroup rightly
    # refuses that as a non-partition, so the stratum is exercised through
    # draw() directly -- what is under test is whether the name reaches the seed.
    steep = od.draw(_LIST_ID, _MEMBERS, 5, stratum="steep")
    flat = od.draw(_LIST_ID, _MEMBERS, 5, stratum="flat")

    assert steep.sample != flat.sample, (
        "the same population drawn under two subgroup names gives the same "
        "names, so the subgroup is not reaching the seed"
    )


def test_the_subgroups_of_a_real_partition_each_draw_from_their_own_members() -> None:
    od = _module()

    both = od.draw_by_subgroup(
        _LIST_ID, {"steep": _MEMBERS[:20], "flat": _MEMBERS[20:]}, {"steep": 5, "flat": 5}
    )

    assert set(both["steep"].sample) <= set(_MEMBERS[:20])
    assert set(both["flat"].sample) <= set(_MEMBERS[20:])
    assert not set(both["steep"].sample) & set(both["flat"].sample)


def test_a_population_whose_subgroups_overlap_is_refused() -> None:
    """Step 5: every member must fall into one subgroup. One, not two."""
    od = _module()

    with pytest.raises(ValueError, match="partition"):
        od.draw_by_subgroup(
            _LIST_ID, {"a": _MEMBERS[:20], "b": _MEMBERS[15:]}, {"a": 3, "b": 3}
        )


def test_a_sample_larger_than_its_subgroup_does_not_invent_members() -> None:
    od = _module()

    made = od.draw(_LIST_ID, _MEMBERS[:3], 10)

    assert made.size == 3
    assert len(made.sample) == 3


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(lambda *a, **k: (_ for _ in ()).throw(_Timeout("no route")), id="timeout"),
        pytest.param(lambda *a, **k: _Response(503, {}), id="unavailable"),
        pytest.param(lambda *a, **k: _Response(200, {"nonsense": True}), id="unexpected-shape"),
    ],
)
def test_an_unreachable_beacon_is_reported_rather_than_raised(monkeypatch, failure) -> None:
    """A beacon outage downgrades the claim; it does not fail the run.

    Behaviour rather than a text search. The text version passed while the
    except clause re-raised, because the function returns None elsewhere too.
    """
    od = _module()
    monkeypatch.setattr(od.requests, "get", failure)

    assert od.beacon() is None
    assert od.beacon_at(6_446_150) is None


class _Timeout(requests.RequestException):
    """The exception the module's except clause is written to catch."""


def test_a_working_beacon_carries_the_round_it_came_from() -> None:
    """The other half. A citation missing the round cannot be rechecked."""
    od = _module()

    assert od.Beacon("drand", 6_446_150, "ab" * 32).citation == "drand round 6446150"


def test_the_notebook_shows_the_grind_before_it_shows_the_cure() -> None:
    """The argument only lands in that order, and the overstatement came first."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    naive = built.index("seeded by the list alone")
    grind = built.index("measure how cheap it is to grind")
    cure = built.index("bound to a beacon round nobody could predict")

    assert naive < grind < cure


def test_the_notebook_no_longer_claims_the_list_id_cannot_be_edited() -> None:
    """The claim that was wrong, pinned so it cannot come back."""
    built = " ".join((DEMO / "build_openscience_notebook.py").read_text().split())

    assert "cannot be edited to suit it" not in built
    assert '"cannot be edited to suit" the draw. It can.' in built


def test_the_draft_says_it_is_a_draft() -> None:
    """Nobody who does legality audits has been asked whether this passes."""
    built = (DEMO / "build_openscience_notebook.py").read_text()

    assert "AG-014" in built
    assert "nobody who does this work has been asked yet" in built
