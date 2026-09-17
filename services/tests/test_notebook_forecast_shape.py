"""The notebook reads a forecast step the way terrapipe-os serialises one.

This is the check for AG-039, and the fault it blocks is worth stating exactly
because it is not the obvious one. The open-science notebook's GFS cell did::

    t2m = [x['values']['t2m'] - 273.15 for x in steps if 't2m' in x['values']]

``terrapipe_os.gfs.ForecastStep`` really does have a ``values`` field, so that
line reads correctly against the *dataclass*. What crosses the wire is
``GfsForecast.to_dict``, which flattens it::

    {"valid_time": s.valid_time, "forecast_hour": s.forecast_hour, **s.values}

so a serialised step carries ``t2m`` at the top level and has no ``values`` key
at all. The cell raised ``KeyError('values')`` on a perfectly good HTTP 200 and
had never worked once -- the endpoint answered 200 with 55 steps of real data
every time it was asked.

Two things kept it alive for as long as it was. The notebook's step recorder
caught the exception and badged the step FAILED, and ``nbconvert`` still exits
0, so a run carrying the failure could be archived as evidence unless a person
read the ledger. And the mistake is invisible from inside the notebook: the
shape it reads is a real shape in the codebase, just not the one the HTTP
boundary uses.

So this test pins the two sides together *statically*. It does not need a node,
which matters: the contract test that does spin one up skips when terrapipe-os
is absent, and a skip is exactly how this would go unnoticed again.

The negative is verified rather than assumed. ``test_the_serialiser_check_can_fire``
runs the same search against text that does contain the nested read, so a
silently-empty search cannot pass as a clean bill of health.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

PANCAKE = Path(__file__).resolve().parents[2]
DEMO = PANCAKE / "dpi-demo"
BUILDER = DEMO / "build_openscience_notebook.py"
NOTEBOOK = DEMO / "openscience_dpi_demo.ipynb"

TERRAPIPE_OS = Path(
    os.environ.get("TERRAPIPE_OS_DIR") or Path(__file__).resolve().parents[3] / "terrapipe-os"
)
GFS = TERRAPIPE_OS / "src" / "terrapipe_os" / "gfs.py"

# A forecast step being indexed by a nested 'values' key: x['values'], with
# either quote style and optional whitespace. This is the defect's signature.
NESTED_READ = re.compile(r"""\[\s*['"]values['"]\s*\]""")

# The serialiser spreading the variables onto the step. If this stops being
# true the notebook's flat read is the wrong one and this test should say so
# rather than keep asserting the flat form.
FLATTENED = re.compile(r"""["']forecast_hour["']\s*:\s*s\.forecast_hour\s*,\s*\*\*s\.values""")


def _without_comments(line: str) -> str:
    """The line with any trailing ``#`` comment removed, quotes respected.

    Needed because the fix for AG-039 carries a comment that *quotes* the
    defective expression in order to explain it, and a naive search matched the
    explanation and reported the bug it documents. Scanning source for a
    forbidden expression has to ignore prose about that expression or the first
    person to write the comment gets a failure they cannot act on.

    Done per line rather than with ``tokenize`` on purpose: the builder embeds
    the notebook's code inside triple-quoted strings, so a tokenizer sees one
    STRING token and no comments at all. Comments inside those strings are the
    ones that matter here.
    """
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _code_cells(path: Path) -> list[str]:
    document = json.loads(path.read_text())
    cells = []
    for cell in document.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        cells.append("".join(source) if isinstance(source, list) else str(source))
    return cells


@pytest.mark.skipif(not GFS.is_file(), reason="terrapipe-os is not checked out beside pancake")
def test_the_node_flattens_the_variables_onto_the_step():
    """The premise. If this fails, the rest of this file is asserting the wrong shape."""
    text = GFS.read_text()
    assert FLATTENED.search(text), (
        "terrapipe_os.gfs.GfsForecast.to_dict no longer spreads **s.values onto the "
        "step. The serialised shape has changed, so re-read it and fix the notebook "
        "to match -- do not just relax this test."
    )


@pytest.mark.skipif(not GFS.is_file(), reason="terrapipe-os is not checked out beside pancake")
def test_the_serialised_step_has_no_values_key():
    """Stated as an assertion about the serialiser, not about a captured response."""
    text = GFS.read_text()
    match = FLATTENED.search(text)
    assert match is not None
    # The dict literal that becomes one step, up to the closing brace.
    literal = text[match.start() - 200 : match.end() + 40]
    assert "'values':" not in literal and '"values":' not in literal, (
        f"the serialised step appears to carry a 'values' key after all: {literal!r}"
    )


def test_the_builder_does_not_read_a_nested_values_key():
    assert BUILDER.is_file(), f"no builder at {BUILDER}"
    offenders = [
        (number, line)
        for number, line in enumerate(BUILDER.read_text().splitlines(), 1)
        if NESTED_READ.search(_without_comments(line))
    ]
    assert not offenders, (
        "build_openscience_notebook.py reads a nested 'values' key from a forecast "
        "step. The node flattens the variables onto the step, so this raises "
        "KeyError('values') against a successful response. Offending lines: "
        + "; ".join(f"{n}: {line.strip()}" for n, line in offenders)
    )


@pytest.mark.skipif(not NOTEBOOK.is_file(), reason="the generated notebook is not present")
def test_the_generated_notebook_agrees_with_the_builder():
    """The executed copy is the artifact people read, and it is generated.

    Checked separately from the builder because the two drift: the fix lands in
    the builder and the committed .ipynb keeps the old cell until somebody
    regenerates it. A reviewer opening the notebook would still see the defect.
    """
    offenders = [
        cell
        for cell in _code_cells(NOTEBOOK)
        if any(NESTED_READ.search(_without_comments(line)) for line in cell.splitlines())
    ]
    assert not offenders, (
        f"{NOTEBOOK.name} still contains {len(offenders)} cell(s) reading a nested "
        f"'values' key. Regenerate it: make -C dpi-demo openscience-notebook-source"
    )


def test_the_serialiser_check_can_fire():
    """The negative control.

    Every assertion above passes when its search finds nothing, which is also
    what a broken regex looks like. So each pattern is run against text that
    must match it.
    """
    assert NESTED_READ.search("t2m = [x['values']['t2m'] for x in steps]"), (
        "NESTED_READ does not match the defect it was written for"
    )
    assert NESTED_READ.search('rain = sum(x["values"].get("tp", 0.0) for x in steps)'), (
        "NESTED_READ misses the double-quoted spelling"
    )
    assert not NESTED_READ.search("t2m = [x['t2m'] for x in steps]"), (
        "NESTED_READ matches the corrected form, so it would never go green"
    )
    assert FLATTENED.search(
        '{"valid_time": s.valid_time, "forecast_hour": s.forecast_hour, **s.values}'
    ), "FLATTENED does not match the serialiser line it was written for"


def test_comments_about_the_defect_are_not_read_as_the_defect():
    """The comment stripper, which this file needed before it could go green.

    The first run of this test failed on the very comment explaining the fix,
    because the comment quotes ``x['values']['t2m']`` in order to name what
    went wrong. A check that cannot tell code from prose about code makes the
    documentation the liability.
    """
    explanation = "    # with no 'values' key. This read was x['values']['t2m'], which is"
    assert not NESTED_READ.search(_without_comments(explanation)), (
        "a comment quoting the defect is still read as the defect"
    )

    # And the stripper must not blind the check to real code on a line that
    # also carries a comment.
    real = "    t2m = [x['values']['t2m'] for x in steps]  # reads the nested key"
    assert NESTED_READ.search(_without_comments(real)), (
        "stripping comments also removed the code before them"
    )

    # A '#' inside a string is not a comment.
    assert _without_comments("url = 'http://x/#frag'") == "url = 'http://x/#frag'", (
        "a # inside a string literal was treated as a comment"
    )
