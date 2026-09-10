"""No committed artifact in this repository may carry the Honduran plot survey.

This repository is public. The survey is sixteen KML files from a cooperative in
Honduras, walked with phones by the people who farm the plots, and every file is
named for a farmer and their national identity number. The boundaries inside are
exactly the personal data AR2's masking design exists to protect: a smallholder
field boundary, at a tenth of a hectare, in a named cooperative's catchment, is
close to a home address.

The notebooks may *use* the survey -- it is the best fixture available and the
only one that is not ours -- but they read it from outside the tree via
``HONDURAS_FIELDS_DIR`` and the committed copies must be runs where it was
absent. That is easy to get wrong, because it goes wrong by *succeeding*: a
maintainer with the survey on their laptop runs the notebook, gets a better
result than the committed one, and commits it. Nothing looks broken. The
boundaries are simply published.

So the guard is here, in the suite CI runs, rather than in a paragraph asking
people to remember.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "dpi-demo"

# The cooperative's plot codes. Two forms appear in the survey and a third is
# minted by the loader for labels it refuses to pass through.
PLOT_CODE = re.compile(r"\b(?:GCO|GMO)-\d+\b")
UNLABELLED = re.compile(r"unlabelled plot \d+")

# The box the survey sits in, with a small margin. The notebooks' own placed
# fields are Honduran too, but they are at lon -88.87..-86.06 and lat
# 14.24..15.20, so they fall outside this box on longitude in every case. A
# coordinate inside it, at survey precision, came from the survey.
SURVEY_BOX = (-88.20, -87.88, 14.02, 14.29)  # lon min, lon max, lat min, lat max
COORD = re.compile(r"(-8[78]\.\d{4,})[,\s]+\s*(1[34]\.\d{4,})")
LATLON = re.compile(r"(1[34]\.\d{4,})[,\s]+\s*(-8[78]\.\d{4,})")


def _tracked(pattern: str) -> list[Path]:
    """Files git actually tracks. An ignored working copy is not the concern."""
    try:
        out = subprocess.run(["git", "-C", str(REPO), "ls-files", pattern],
                             capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git is not available here")
    return [REPO / line for line in out.splitlines() if line.strip()]


def _notebooks() -> list[Path]:
    found = [path for path in _tracked("dpi-demo/*.ipynb") if path.is_file()]
    if not found:
        pytest.skip("no committed notebooks to check")
    return found


def _outputs(notebook: Path) -> str:
    """Every output stream and rendered payload, which is where a leak lands.

    Sources are excluded deliberately: the builders name the survey and discuss
    it at length, which is fine. It is the *results* of a run against it that
    must not be here.
    """
    cells = json.loads(notebook.read_text())["cells"]
    chunks = []
    for cell in cells:
        for output in cell.get("outputs", []):
            chunks.append("".join(output.get("text") or []))
            for mime, payload in (output.get("data") or {}).items():
                chunks.append("".join(payload) if isinstance(payload, list) else str(payload))
                del mime
    return "\n".join(chunks)


def _in_box(lon: float, lat: float) -> bool:
    lon_min, lon_max, lat_min, lat_max = SURVEY_BOX
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


@pytest.mark.parametrize("notebook", _notebooks(), ids=lambda p: p.name)
def test_no_committed_notebook_names_a_survey_plot(notebook: Path) -> None:
    """A plot code in saved output means the run had the survey mounted."""
    found = PLOT_CODE.findall(_outputs(notebook))
    assert not found, (
        f"{notebook.name} carries cooperative plot codes in its saved output: "
        f"{sorted(set(found))}. Re-run it with HONDURAS_FIELDS_DIR unset so the "
        f"survey sections take their absent path, then commit that."
    )


@pytest.mark.parametrize("notebook", _notebooks(), ids=lambda p: p.name)
def test_no_committed_notebook_carries_survey_geometry(notebook: Path) -> None:
    """The boundaries themselves. A map cell renders every vertex into the HTML.

    This is the expensive half: the plot codes are identifying, but the vertex
    lists are the personal data, and they arrive through folium rather than
    through anything a reviewer reads.
    """
    text = _outputs(notebook)
    hits = {(lon, lat) for lon, lat in COORD.findall(text)
            if _in_box(float(lon), float(lat))}
    hits |= {(lon, lat) for lat, lon in LATLON.findall(text)
             if _in_box(float(lon), float(lat))}
    assert not hits, (
        f"{notebook.name} carries {len(hits)} coordinate(s) inside the survey's "
        f"bounding box, e.g. {sorted(hits)[:3]}. These are real smallholder "
        f"boundaries; they must not be published."
    )


@pytest.mark.parametrize("notebook", _notebooks(), ids=lambda p: p.name)
def test_no_committed_notebook_carries_a_loader_placeholder(notebook: Path) -> None:
    """``unlabelled plot 1`` only exists because a real label was refused."""
    found = UNLABELLED.findall(_outputs(notebook))
    assert not found, (
        f"{notebook.name} carries {sorted(set(found))}, which the survey loader "
        f"mints for plots whose own label looked like a national identity number."
    )


def test_no_kml_is_tracked() -> None:
    """The files themselves, under any name, anywhere in the tree."""
    tracked = _tracked("*.kml")
    assert not tracked, (
        f"KML files are tracked: {[p.name for p in tracked]}. The survey filenames "
        f"alone carry a farmer's name and national identity number."
    )


def test_the_loader_itself_is_not_a_copy_of_the_survey() -> None:
    """A future edit could vendor the coordinates into the loader as a fallback."""
    loader = DEMO / "honduras_fields.py"
    if not loader.is_file():
        pytest.skip("honduras_fields.py is not present")
    text = loader.read_text()
    hits = {(lon, lat) for lon, lat in COORD.findall(text)
            if _in_box(float(lon), float(lat))}
    assert not hits, (
        f"honduras_fields.py contains survey coordinates: {sorted(hits)[:3]}. It "
        f"must read them from HONDURAS_FIELDS_DIR, never hold them."
    )


def test_the_loader_returns_no_identifying_field() -> None:
    """The Plot record must have nowhere to put a name or an identity number."""
    loader = DEMO / "honduras_fields.py"
    if not loader.is_file():
        pytest.skip("honduras_fields.py is not present")
    import ast

    tree = ast.parse(loader.read_text())
    plot = next((node for node in ast.walk(tree)
                 if isinstance(node, ast.ClassDef) and node.name == "Plot"), None)
    assert plot is not None, "honduras_fields.Plot has been renamed or removed"
    fields = {node.target.id for node in plot.body if isinstance(node, ast.AnnAssign)}
    forbidden = {"filename", "path", "file", "owner", "farmer", "name",
                 "national_id", "identity", "holder"}
    assert not fields & forbidden, (
        f"honduras_fields.Plot gained {sorted(fields & forbidden)}. The loader "
        f"returns geometry and a plot code; anything that can hold a farmer's "
        f"name or national identity number does not belong on it."
    )
