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
import textwrap
import os
import re
from urllib.parse import urlparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

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
