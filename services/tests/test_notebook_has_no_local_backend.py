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
