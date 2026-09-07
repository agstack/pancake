"""The traceability notebook must show the gate and the way around it.

A demonstration of a permission model that only exercises the permitted path is
advertising. The checks below fall into three groups: that the chain has the
shape the argument needs, that each claim about who may ask is read from what
the node answered rather than from the prose, and that the section reporting
AG-015 cannot quietly lose it.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import inspect
import io
import re
import sys
import textwrap
from pathlib import Path


DEMO = Path(__file__).resolve().parents[2] / "dpi-demo"


def _module():
    """Load trace_demo.py without needing the demo to be an installed package."""
    if str(DEMO) not in sys.path:
        sys.path.insert(0, str(DEMO))
    spec = importlib.util.spec_from_file_location("trace_demo_under_test",
                                                  DEMO / "trace_demo.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["trace_demo_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _built() -> str:
    return (DEMO / "build_trace_notebook.py").read_text()


def _code_only(function) -> str:
    """A function's source with its docstring removed."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    node = tree.body[0]
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)):
        node.body = node.body[1:]
    return ast.unparse(tree)


GEO_IDS = {
    "compliant_coffee": "a" * 64,
    "post_cutoff_clearing": "b" * 64,
    "legacy_clearing": "c" * 64,
    "marginal_clearing": "d" * 64,
}


# --------------------------------------------------------------------------
# The chain has to have the shape the argument needs
# --------------------------------------------------------------------------


def test_one_field_goes_into_two_lots() -> None:
    """The whole point. Without it the easy case looks like the whole problem.

    A chain where every field feeds exactly one lot can be traced by reading a
    list, and trace-forward looks like a lookup rather than a search.
    """
    tr = _module()
    pooled = []
    tr.pool_through_pancake = lambda members, name, token: (
        pooled.append(members) or (f"list-of-{len(pooled)}", "ok")
    )

    chain, _ = tr.build_chain(GEO_IDS, "token")

    shared = GEO_IDS[chain.shared_field]
    in_lots = [lot for lot in chain.lots.values() if shared in lot.fields]
    assert len(in_lots) == 2, "the shared field is not in two lots"


def test_every_field_reaches_the_container() -> None:
    """A field pooled into nothing would make the walk down silently incomplete."""
    tr = _module()
    tr.pool_through_pancake = lambda members, name, token: (f"list-{name[:6]}", "ok")

    chain, _ = tr.build_chain(GEO_IDS, "token")

    pooled = {geo for lot in chain.lots.values() for geo in lot.fields}
    assert pooled == set(GEO_IDS.values())


def test_the_container_declares_its_members_as_lots_not_as_fields() -> None:
    """The prefix that is not in the OpenAPI schema.

    Without it AR2 records a list_id as though it were a GeoID: the edge comes
    back kind=geoid, input_list_ids stays empty, and traceback stops at one
    level however large max_depth is. The chain looks built and is one hop deep.
    """
    tr = _module()
    seen = []
    tr.pool_through_pancake = lambda members, name, token: (
        seen.append(members) or (f"list-{len(seen)}", "ok")
    )

    tr.build_chain(GEO_IDS, "token")

    container_members = seen[-1]
    assert all(member.startswith(tr.CHILD_LIST) for member in container_members), (
        f"the container's members are not marked as child lots: {container_members}"
    )


def test_a_chain_of_too_few_fields_is_refused_rather_than_built_wrong() -> None:
    tr = _module()

    chain, why = tr.build_chain({"only": "a" * 64}, "token")

    assert chain is None
    assert "four" in why


def test_a_lot_that_could_not_be_registered_stops_the_chain() -> None:
    """Half a chain traced without complaint would read as a complete answer."""
    tr = _module()
    tr.pool_through_pancake = lambda members, name, token: ("", "AR2 refused the lot")

    chain, why = tr.build_chain(GEO_IDS, "token")

    assert chain is None
    # Named specifically. "could not be registered" also matches the container's
    # own guard, so the loose version passed while the mill-lot check was gone.
    assert "a mill lot could not be registered" in why


# --------------------------------------------------------------------------
# Down the graph
# --------------------------------------------------------------------------


def test_a_walk_that_stops_at_one_level_is_reported_not_shown_as_a_chain() -> None:
    """The failure the L: prefix prevents, caught if the prefix ever stops working."""
    tr = _module()
    chain, _ = _fake_chain(tr)

    notes = tr._what_the_walk_shows(
        {"hops": [{"depth": 0, "list_id": "x", "geoids": [], "input_list_ids": []}]}, chain
    )

    assert any("one level" in note for note in notes)
    assert any(tr.CHILD_LIST in note for note in notes)


def test_a_walk_that_misses_a_field_says_which_one() -> None:
    tr = _module()
    chain, _ = _fake_chain(tr)

    notes = tr._what_the_walk_shows({"hops": [
        {"depth": 0, "list_id": "c", "geoids": [], "input_list_ids": ["a", "b"]},
        {"depth": 1, "list_id": "a", "geoids": list(GEO_IDS.values())[:2]},
    ]}, chain)

    assert any("did not reach" in note for note in notes)


def test_a_complete_walk_is_not_nagged() -> None:
    tr = _module()
    chain, _ = _fake_chain(tr)

    notes = tr._what_the_walk_shows({"hops": [
        {"depth": 0, "list_id": "c", "geoids": [], "input_list_ids": ["a", "b"]},
        {"depth": 1, "list_id": "a", "geoids": list(GEO_IDS.values())},
    ]}, chain)

    assert notes == []


def test_the_notebook_tries_the_walk_down_unauthorised_first() -> None:
    """The refusal is the demonstration, and it only reads as one if it comes first."""
    built = _built()

    refused = built.index("try to walk down without a grant")
    granted = built.index("issue a grant over the container and walk down")

    assert refused < granted


def test_a_404_on_trace_is_explained_as_a_refusal() -> None:
    """Read as 'no such consignment' it looks like the chain was never built."""
    tr = _module()

    assert "404" in _code_only(tr.walk_down)
    body = inspect.getsource(tr.walk_down)
    assert "confirm it does" in body or "confirm" in body


# --------------------------------------------------------------------------
# Up the graph: the gates
# --------------------------------------------------------------------------


def test_the_notebook_presents_four_different_credentials_to_the_same_door() -> None:
    """One refusal proves nothing; the contrast between four is the demonstration."""
    built = _built()
    section = built[built.index("try to walk up, four ways"):]
    section = section[:section.index('""")')]

    for presented in ("nothing but a login", "a grant on the container",
                      "a grant on somebody else's field", "a grant on the seed field itself"):
        assert presented in section


def test_a_refusal_is_attributed_to_the_check_that_made_it() -> None:
    """'403' alone does not say whether accreditation or scope was the problem."""
    tr = _module()

    gate_a = tr.walk_up.__doc__
    assert "Gate A" in gate_a and "Gate B" in gate_a

    body = _code_only(tr.walk_up)
    assert "capabilit" in body, "the two 403s are not told apart"


def test_the_gate_composition_is_described_as_the_code_has_it() -> None:
    """The deck says 'two gates'. The code says (accredited OR grant) AND scope.

    Repeating the slide would have been easier and would have described a
    system that refuses a farmer access to their own field's lots.
    """
    built = " ".join(_built().split())

    assert "accredited, *or* holding a grant) *and* authorized for this particular" in built


def test_the_undemonstrated_tier_is_named_as_undemonstrated() -> None:
    """Tier 3 is not shown, and the notebook has to say so rather than imply it."""
    built = _built()

    assert "tier 3" in built.lower()
    assert "cannot be demonstrated" in built


# --------------------------------------------------------------------------
# AG-015: the door beside the gate
# --------------------------------------------------------------------------


def test_the_notebook_reports_the_ungated_door() -> None:
    """A demo that showed the gate and stopped would be advertising."""
    built = _built()

    assert "AG-015" in built
    assert "reverse" in built
    # The section itself, not just a mention. Deleting the heading and leaving
    # the reference further down passed the looser version of this.
    assert "## 4. A second door to the same answer" in built
    assert built.index("ask each door the same question") > built.index("try to walk up")


def test_both_doors_are_asked_the_same_question_with_the_same_account() -> None:
    """Different accounts, or different questions, and the comparison proves nothing."""
    tr = _module()
    body = _code_only(tr.what_a_bare_login_gets)

    assert "reverse" in body
    assert "traceforward" in body
    assert body.count("token") >= 2


def test_the_comparison_is_read_from_both_answers_not_asserted() -> None:
    built = _built()
    section = built[built.index("compare what the two doors return"):]
    section = section[:section.index('""")')]

    assert "FORWARD.get('list_ids')" in section
    assert "lots_containing" in section
    assert "<=" in section, "the subset claim is stated rather than computed"


def test_the_oracle_is_checked_against_the_chain_that_was_built() -> None:
    """An oracle scored against its own output would agree with itself."""
    built = _built()
    section = built[built.index("test whether the open door is an exact oracle"):]
    section = section[:section.index('""")')]

    assert "LOT_A.fields" in section, "the truth is not taken from the chain"


def test_the_oracle_has_a_control_that_must_answer_no() -> None:
    """Without it, an oracle that said yes to everything would look exact."""
    built = _built()

    assert "unregistered_geoid" in built
    tr = _module()
    assert len(tr.unregistered_geoid()) == 64


def test_an_oracle_that_disagrees_with_the_truth_is_called_out() -> None:
    """If it is noisy, the finding is smaller, and the notebook must say so."""
    tr = _module()
    shown = io.StringIO()

    with contextlib.redirect_stdout(shown):
        tr.show_oracle([("a", True), ("b", False)], {"a": False, "b": False})

    text = shown.getvalue()
    assert "DISAGREES" in text
    assert "noisier" in text


def test_an_exact_oracle_is_not_described_as_noisy() -> None:
    tr = _module()
    shown = io.StringIO()

    with contextlib.redirect_stdout(shown):
        tr.show_oracle([("a", True), ("b", False)], {"a": True, "b": False})

    assert "DISAGREES" not in shown.getvalue()


def test_the_finding_does_not_overstate_what_leaks() -> None:
    """Membership is protected. Saying otherwise would be the same error inverted."""
    built = " ".join(_built().split())

    assert "Membership itself is still protected" in built
    assert "cannot learn who *else* is in a consignment" in built


# --------------------------------------------------------------------------
# The proof, and taking the grant back
# --------------------------------------------------------------------------


def test_a_proof_that_names_another_member_is_a_leak() -> None:
    """The check has to be able to fail, or it is decoration."""
    tr = _module()
    other = "b" * 64

    assert tr.proof_reveals([{"sibling": other}], [other]) == [other]
    assert tr.proof_reveals([{"sibling": "f" * 64}], [other]) == []


def test_the_notebook_checks_the_proof_against_the_lots_other_members() -> None:
    built = _built()
    section = built[built.index("prove one field's membership"):]
    section = section[:section.index('""")')]

    assert "proof_reveals" in section
    assert "LOT_B.fields" in section


def test_revocation_is_tested_by_using_the_credential_again() -> None:
    """A revocation call returning 200 says nothing about whether the door shut."""
    built = _built()
    section = built[built.index("revoke the customs grant"):]
    section = section[:section.index('""")')]

    assert section.count("walk_down") == 2, "the walk is not retried after revoking"
    assert "before revocation" in section
    assert "after revocation" in section


def test_a_revoked_credential_that_still_works_is_called_a_defect() -> None:
    """The outcome this step exists to catch, not the one it expects."""
    built = _built()
    section = built[built.index("revoke the customs grant"):]
    section = section[:section.index('""")')]

    assert "That is a defect" in section


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_the_setup_is_shared_with_the_other_notebooks_rather_than_copied() -> None:
    """Eighty lines hand-copied diverge the first time one of the three is fixed."""
    built = _built()

    assert "build_openscience_notebook" in built
    assert "_find_support_module" not in built.replace(
        '"_find_support_module" in body', ""), "the setup cell is pasted in"


def test_the_setup_is_lifted_parsed_rather_than_as_source_text() -> None:
    """Reading the file gives escaped triple quotes, which will not parse."""
    built = _built()

    assert "openscience.CELLS" in built
    assert 're.findall' not in built, (
        "the setup cell is scraped from the source text, so its escaping is wrong"
    )


def test_the_notebook_points_at_its_two_companions() -> None:
    built = _built()

    assert "ar2_field_identity_demo.ipynb" in built
    assert "openscience_dpi_demo.ipynb" in built


def test_the_sections_are_numbered_in_the_order_they_are_read() -> None:
    built = _built()

    numbers = [int(n) for n in re.findall(r"^## (\d+)\. ", built, re.M)]

    assert numbers == list(range(len(numbers))), f"sections run {numbers}"


def test_a_refusal_is_not_reported_as_a_failure() -> None:
    """Several steps here are meant to be refused; FAILED would train the reader wrong."""
    built = _built()

    assert "A refusal is not a failure here" in built


def test_the_synthetic_part_is_named_as_synthetic() -> None:
    """Real coordinates and real GeoIDs. No coffee was milled."""
    built = " ".join(_built().split())

    assert "The chain is synthetic" in built
    assert "no coffee was milled and no container sailed" in built


def _fake_chain(tr):
    """A chain built without touching the network."""
    tr.pool_through_pancake = lambda members, name, token: (f"list-{name[:8]}", "ok")
    return tr.build_chain(GEO_IDS, "token")


# --------------------------------------------------------------------------
# AG-016: the authority path cannot be demonstrated, and why matters
# --------------------------------------------------------------------------


def test_the_reason_tier_three_is_missing_is_not_blamed_on_this_account() -> None:
    """'This account is not accredited' implies another account could be.

    None can. There is no issuance route in any running service, which is a
    finding about the deployment rather than a limitation of the demo.
    """
    built = " ".join(_built().split())

    assert "not because this account happens to lack accreditation" in built
    assert "no account can have it" in built
    assert "AG-016" in built


def test_the_mocked_tier_three_tests_are_named_as_mocked() -> None:
    """The gate opening is covered. What is behind it is not."""
    built = " ".join(_built().split())

    assert "_resolve_holders" in built
    assert "patched out" in built or "mocks out" in built


def test_what_tier_three_would_add_is_stated() -> None:
    """Otherwise 'tier 3 missing' reads as a version number rather than a capability."""
    built = " ".join(_built().split())

    assert "resolves the holders" in built or "holder resolution" in built
    assert "audit" in built
