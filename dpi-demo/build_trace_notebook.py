"""Generate traceability_demo.ipynb.

The third of three. Generated rather than hand-edited for the same reason as
the others: editing a committed .ipynb means reviewing a JSON diff with escaped
newlines, which is how explanatory text drifts out of step with the code.

    python build_trace_notebook.py          # write the notebook
    python build_trace_notebook.py --run    # write it and execute it
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "traceability_demo.ipynb"

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


def shared_setup() -> str:
    """The setup cell from the open-science notebook, verbatim but for the module.

    Lifted rather than copied by hand. The three notebooks have to find their
    support module, guard the Python version and install dependencies in
    exactly the same way, and a hand-copy of eighty lines diverges the first
    time one of them is fixed.
    """
    # Imported rather than read as text. Reading the file gives the source
    # form, in which every triple quote inside the cell is backslash-escaped,
    # and pasting that into a notebook produces a SyntaxError on the first
    # docstring. Importing runs the module's md()/code() calls, which do
    # nothing but append to its CELLS, and yields the parsed strings.
    sys.path.insert(0, str(HERE))
    import build_openscience_notebook as openscience  # noqa: PLC0415

    setup = [body for kind, body in openscience.CELLS
             if kind == "code" and "_find_support_module" in body]
    if not setup:
        raise SystemExit("could not lift the setup cell from the open-science builder")
    return setup[0].replace(
        "import openscience_demo as od",
        "import openscience_demo as od\nimport trace_demo as tr",
    ).replace(
        "od = importlib.reload(od)",
        "od = importlib.reload(od)\ntr = importlib.reload(tr)",
    )


# ==========================================================================
# 0. What this is
# ==========================================================================

md("""
# A lot, and who may ask about it

### Traceability on a GeoID: down the graph, up the graph, and the difference in what each one costs

Fields do not ship. **Lots** do — a container, a delivery, a day's harvest
pooled from several farms — and every question that matters commercially is
asked of the lot rather than of the field.

This notebook builds one small supply chain and asks it two questions that look
symmetrical and are not:

- **Down the graph.** *This container is on the dock at Rotterdam. Which farms
  is it from?* The due-diligence direction. A customs officer or a buyer asks
  it, and they are holding the product.
- **Up the graph.** *This farm turned out to be a problem. Where did its output
  go?* The recall direction. It is the harder one, and it is gated differently,
  because it reaches into other companies' customer relationships rather than
  the caller's own.

It is the third of three, and each answers a different question:

| | question | where |
|---|---|---|
| **1. Field identity** | when is a boundary the same field? | `ar2_field_identity_demo.ipynb` |
| **2. Open science** | what can public data say about it? | `openscience_dpi_demo.ipynb` |
| **3. Traceability** ← you are here | where did this lot come from, and who may ask? | this notebook |

The three stand alone. GeoIDs and grants are used here and taken apart properly
in the first.

---

### How to read this

Every step prints a badge and the last cell prints a ledger of all of them.

- **LIVE** — ran against a running service.
- **LOCAL** — ran in this kernel, and could only be a harmless thing: writing a
  file, or re-displaying something already fetched.
- **EMPTY** — the call was made and the service holds nothing for it. Nothing
  broken, nothing demonstrated.
- **SKIPPED** — never ran, because something upstream was down.
- **FAILED** — a real defect. Read its reason.

**A refusal is not a failure here.** Several steps below are supposed to be
refused, and are marked LIVE because the refusal is the demonstration. Where
that is the case the text says so before the cell runs.
""")

md("""
## 0. Setting this up

Setup is identical to the other two notebooks and is written out in
[`README-openscience.md`](README-openscience.md). In short: a virtualenv on
Python 3.10 or newer, `pip install -r requirements.txt`, and a `demo.env`
naming the four deployment addresses. The next cell checks all of it and
reports what it found rather than failing silently.
""")

code(shared_setup())

code("""
HUB_TOKEN, TOKEN_SOURCE = tr.hub_token()
print(f"hub token: {'yes' if HUB_TOKEN else 'no'} - {TOKEN_SOURCE}")
""")

# ==========================================================================
# 1. The chain
# ==========================================================================

md("""
## 1. How food actually moves

The simplest imaginable chain — one field, one lot, one buyer — makes
traceability look easy, and every real difficulty disappears from it. So this
is one step more complicated, which is enough to bring the difficulty back:

```
    four fields  ->  two mill lots  ->  one export container
```

with **one field in both lots**. A farm delivers in the morning and again in
the afternoon; the two deliveries are milled into different lots; both lots go
in the same container. Entirely ordinary, and it is the reason a recall cannot
be answered by reading a list. When that farm turns out to be a problem, the
question is not *what was in this lot* but *which lots did this farm reach* —
and that is a search, not a lookup.

At the mill, identity dies today. The bag knows the mill and the date, not the
fields. Everything beyond that hop is a records request by phone and email.
""")

code("""
FIELDS = tr.demo_fields()
GEOIDS, CHAIN = {}, None

with tr.step("register four field boundaries") as s:
    if STACK['ar2-node']['up'] and HUB_TOKEN:
        for feature in FIELDS:
            name = feature['properties']['name']
            GEOIDS[name] = tr.register(feature, HUB_TOKEN)
        for name, geo_id in GEOIDS.items():
            print(f"  {name:24} {geo_id[:20] if geo_id else 'not registered'}...")
    else:
        tr.skip(s, "AR2 is not answering")
""")

code("""
with tr.step("pool them into two lots and a container") as s:
    if GEOIDS and all(GEOIDS.values()):
        CHAIN, why = tr.build_chain(GEOIDS, HUB_TOKEN)
        if not CHAIN:
            tr.empty(s, why)
        else:
            print(f"  {why}\\n")
            tr.show_chain(CHAIN)
    else:
        tr.skip(s, "there are no GeoIDs to pool")
""")

code("""
if CHAIN and tr.have_folium():
    display(tr.chain_map(CHAIN, FIELDS))
""")

md("""
### What a lot identifier is

A `list_id` is derived from its members, exactly as a GeoID is derived from a
boundary. Three consequences, and they are the reason this is worth doing at
all:

- The same members always produce the same identifier, so two parties who pool
  the same fields arrive at the same name without talking to each other.
- A list cannot be edited after the fact. Changing a member produces a
  different list rather than a changed one.
- Nobody allocates it, so nobody can charge rent on the namespace or go down
  and take it with them.

**A lot may contain lots.** That is how the container holds the two mill lots
rather than a flattened bag of fields, and it is what lets a walk down the
graph report the mill step instead of skipping it.
""")

code("""
with tr.step("show that the container's identifier is derived, not allocated") as s:
    if CHAIN:
        # Register the identical members a second time. A registry that
        # allocated identifiers would hand back a new one.
        again, why = tr.pool_through_pancake(
            [f"{tr.CHILD_LIST}{CHAIN.lots['mill lot A'].list_id}",
             f"{tr.CHILD_LIST}{CHAIN.lots['mill lot B'].list_id}"],
            "the same container, registered again", HUB_TOKEN)
        print(f"  first registration   {CHAIN.container.list_id}")
        print(f"  second registration  {again}")
        print(f"  same identifier: {again == CHAIN.container.list_id}")
        print()
        # And a lot with one member changed is a different lot, not an edit.
        altered, _ = tr.pool_through_pancake(
            [f"{tr.CHILD_LIST}{CHAIN.lots['mill lot A'].list_id}"],
            "a container with one lot removed", HUB_TOKEN)
        print(f"  with one lot removed {altered}")
        print(f"  different identifier: {altered != CHAIN.container.list_id}")
    else:
        tr.skip(s, "there is no chain to check")
""")

# ==========================================================================
# 2. Down the graph
# ==========================================================================

md("""
## 2. Down the graph: which farms is this container from?

The due-diligence direction. The caller is holding the product, and the
question is what went into it.

**It needs a grant scoped to the thing being traced.** Not an account, not a
login — a credential naming this consignment. Run without one first, because
the refusal is worth seeing.
""")

code("""
with tr.step("try to walk down without a grant") as s:
    # Expected to be refused. The refusal is the demonstration, so this is a
    # LIVE step rather than a failure.
    if CHAIN:
        _, why = tr.walk_down(CHAIN.container.list_id, HUB_TOKEN, None)
        print(f"  {why}")
    else:
        tr.skip(s, "there is no container to trace")
""")

md("""
**404, not 403.** Deliberately: a 403 would confirm to a stranger that this
consignment exists, which is itself worth knowing to a competitor. The trace
graph is not a public index. It is a private one that the holder of the right
credential can walk, and to everybody else it is indistinguishable from empty.
""")

code("""
CUSTOMS = None

with tr.step("issue a grant over the container and walk down") as s:
    if CHAIN:
        CUSTOMS = tr.grant_on(CHAIN.container.list_id, HUB_TOKEN,
                              "customs due diligence, Rotterdam")
        print(f"  {CUSTOMS.why}\\n")
        WALKED, why = tr.walk_down(CHAIN.container.list_id, HUB_TOKEN, CUSTOMS.credential)
        print(f"  {why}\\n")
        if WALKED:
            tr.show_walk_down(WALKED, CHAIN)
        else:
            tr.empty(s, why)
    else:
        tr.skip(s, "there is no container to trace")
""")

md("""
One credential, and the whole consignment resolves: the container, the two mill
lots beneath it, and the four farms beneath those — including the farm that
appears twice, once in each lot.

Nothing here required the farms, the mill, the exporter and the buyer to share
a database, or to agree on a file format. They had to register the same
boundaries and get the same GeoIDs. That is the entire integration.

Note what the walk did **not** return: any geometry. The trace names fields; it
does not locate them. Resolving a GeoID to a place is a separate permission,
and a customs officer checking the composition of a consignment does not need
it.
""")

# ==========================================================================
# 3. Up the graph
# ==========================================================================

md("""
## 3. Up the graph: where did this farm's output go?

The recall direction, and a different question in kind. Walking down reads one
list and then its children. Walking up has to find every lot a field ever
entered, anywhere, including in companies the caller has never dealt with.

That is why it is gated separately. Reading the check in
`ar2/app/routers/traceforward.py`, the rule is:

> **(accredited, *or* holding a grant) *and* authorized for this particular
> seed field.**

An accredited investigator may trace forward from any field. Everybody else may
trace forward only from a field they hold a grant on — in practice, their own.
Four cases, run live:
""")

code("""
GATES, FORWARD = [], {}

with tr.step("try to walk up, four ways") as s:
    # Three of these four are supposed to be refused.
    if CHAIN and CUSTOMS:
        SEED = GEOIDS[CHAIN.shared_field]
        OWN = tr.grant_on(tr.own_list(SEED, HUB_TOKEN), HUB_TOKEN, "my own field")
        OTHER = tr.grant_on(tr.own_list(GEOIDS['legacy_clearing'], HUB_TOKEN),
                            HUB_TOKEN, "a neighbour's field")
        for label, credential in (
            ("nothing but a login", None),
            ("a grant on the container", CUSTOMS.credential),
            ("a grant on somebody else's field", OTHER.credential),
            ("a grant on the seed field itself", OWN.credential),
        ):
            body, gate = tr.walk_up(SEED, HUB_TOKEN, grant=credential)
            GATES.append((label, gate))
            if gate.passed:
                FORWARD = body
        tr.show_gates([g for _, g in GATES], [label for label, _ in GATES])
    else:
        tr.skip(s, "there is no chain to trace forward through")
""")

code("""
with tr.step("read what the successful walk up returned") as s:
    if FORWARD:
        print(f"  seed      {FORWARD.get('seed_geoid', '')[:24]}...")
        print(f"  tier      {FORWARD.get('tier')}  (1 = by grant on the seed; 3 = by authority)")
        print(f"  lots      {FORWARD.get('match_count')} consignments contain this field")
        for match in (FORWARD.get('matches') or [])[:8]:
            known = tr.which_lot(match.get('list_id'), CHAIN)
            print(f"      {match.get('list_id', '')[:20]}...  "
                  f"resolution={match.get('resolution')}  {known}")
    else:
        tr.empty(s, "no walk up succeeded, so there is nothing to read")
""")

md("""
That is a recall. The farm is named, and every consignment it reached is
listed — each of which can be walked back down in turn, by whoever holds a
grant on it, to find the other farms that would have to be held with it.

**The tier matters.** Tier 1 is what a farmer gets for their own field: the
list identifiers, and nothing about who holds them. Tier 3, reached with an
accredited authority credential, additionally resolves the holders — which is
the part that reaches into other companies' trading relationships, and the part
that is written to an audit log every time it is used.

This run is tier 1, and **tier 3 cannot be demonstrated at all** — not because
this account happens to lack accreditation, but because no account can have it.
There is no route in any running service that issues an authority credential.
Pancake's issuer exposes `authority_pubkey()`, documented as its trust anchor
for *verifying* them, and mints only field grants; neither service's API has a
matching path.

AR2's own tests reach tier 3 by signing a credential inside the test file with
a test key. All three of those tests do it with `_resolve_holders` and the MEAL
audit chain patched out — which are the two behaviours that make tier 3
different from tier 1. So what is covered is that the gate opens, not that
anything behind it works.

Recorded as **AG-016**. It matters more than a missing demo: identity
disclosure to accredited authorities, always audited, is the goal the deck puts
on its own scorecard, and it is the reason trace-forward is a separate call
from trace-back. That promise currently has no issuance path and no unmocked
test.
""")

# ==========================================================================
# 4. The door beside the gate
# ==========================================================================

md("""
## 4. A second door to the same answer

The gate above is carefully built. It is also not the only way in, and a
demonstration that showed the gate and stopped would be advertising rather than
review.

`GET /list-artifact/reverse/{geoid}` returns the lists a field belongs to. It
needs a login. It does not need a grant on the seed, an authority credential,
or accreditation.
""")

code("""
with tr.step("ask each door the same question with a plain account") as s:
    if CHAIN:
        for question, door, status in tr.what_a_bare_login_gets(
                GEOIDS[CHAIN.shared_field], HUB_TOKEN):
            verdict = 'answered' if status == 200 else 'refused '
            print(f"  {verdict}  HTTP {status}   {door:30} {question}")
    else:
        tr.skip(s, "there is no chain to probe")
""")

code("""
with tr.step("compare what the two doors return") as s:
    if FORWARD and CHAIN:
        GATED = set(FORWARD.get('list_ids') or [])
        UNGATED, status, why = tr.lots_containing(GEOIDS[CHAIN.shared_field], HUB_TOKEN)
        print(f"  through the gate, with a grant on the seed:  {len(GATED)} lots")
        print(f"  through the open door, with only a login:    {len(UNGATED)} lots")
        print(f"  the open door's answer is a subset:          {set(UNGATED) <= GATED}")
        print(f"  it withholds:                                {len(GATED - set(UNGATED))} lots")
    else:
        tr.skip(s, "no gated answer to compare against")
""")

md("""
Membership itself is still protected — reading a lot, or walking it down,
answers 404 without a grant, so the caller cannot learn who *else* is in a
consignment. What leaks is the **edge set**: how many lots a field feeds, and
which identifiers they are.

That sounds thin until you notice it is an **oracle**. Given a lot identifier
obtained from anywhere — a shipping document, a QR code on a sack, a published
due diligence statement — a caller can test any field they can name against it.
And naming a field costs nothing, because a GeoID is computed from a boundary
by anyone who has the boundary. That is the first design principle and it is
not negotiable; it is what makes the identifier worth having. It also means the
oracle can be aimed at any farm whose outline can be traced from a public
parcel map.
""")

code("""
with tr.step("test whether the open door is an exact oracle") as s:
    if CHAIN:
        LOT_A = CHAIN.lots['mill lot A']
        # The truth, from the chain as it was built two sections ago.
        TRUTH = {name: geo_id in LOT_A.fields for name, geo_id in GEOIDS.items()}
        # A control. A field in no lot at all must answer no, or the oracle is
        # answering without looking and the agreement above means nothing.
        WITH_CONTROL = dict(GEOIDS, **{'a field in no lot': tr.unregistered_geoid()})
        tr.show_oracle(tr.membership_oracle(WITH_CONTROL, LOT_A.list_id, HUB_TOKEN), TRUTH)
    else:
        tr.skip(s, "there is no lot to test against")
""")

md("""
Recorded as **AG-015**, open. The fix is not complicated — scope `reverse` with
the same check `traceforward` already applies to its seed — and it is worth
saying plainly what the finding is and is not.

It is **not** that the gate on `traceforward` is wrong. That check was read in
the source and exercised four ways above, and it does what it says. The finding
is that it governs one door to the answer and not the other, so the protection
it provides is smaller than the design says it is.

This is the argument for demonstrating a permission model by trying to get
round it rather than by exercising it.
""")

# ==========================================================================
# 5. Proving one thing without revealing the rest
# ==========================================================================

md("""
## 5. Proving one farm was in the lot, without naming the others

A buyer may need to show a regulator that a particular field was in a
particular consignment. Handing over the lot discloses every other farm in it —
which is the buyer's supplier list, and not the regulator's business.

The list is a Merkle tree, so this is an inclusion proof: a handful of sibling
hashes that recompute the `list_id` and say nothing about anybody else.
""")

code("""
with tr.step("prove one field's membership without disclosing the list") as s:
    if CHAIN:
        LOT_B = CHAIN.lots['mill lot B']
        SUBJECT = LOT_B.fields[0]
        PROOF, why = tr.prove_membership(LOT_B.list_id, SUBJECT, HUB_TOKEN)
        print(f"  {why}\\n")
        for sibling in PROOF:
            print(f"      {sibling.get('position', '?'):6} {str(sibling.get('sibling'))[:40]}...")
        OTHERS = [g for g in LOT_B.fields if g != SUBJECT]
        LEAKED = tr.proof_reveals(PROOF, OTHERS)
        print()
        print(f"  the other {len(OTHERS)} members of the lot appear in the proof: "
              f"{LEAKED if LEAKED else 'none of them'}")
        if LEAKED:
            print("  which defeats the purpose -- that is a defect, not a demonstration")
    else:
        tr.skip(s, "there is no lot to prove membership in")
""")

# ==========================================================================
# 6. Withdrawing it
# ==========================================================================

md("""
## 6. The co-op changes its mind

A grant is a thing you hold, and therefore a thing that can be taken back. The
permissions deck puts it this way: a Honduran co-op shares boundaries with a
European buyer for due diligence, and then changes its mind.

Revocation publishes the credential's identifier to a status list the node
checks. It does not require the buyer's cooperation, and it does not require
finding every copy of the credential.
""")

code("""
with tr.step("revoke the customs grant and try the walk again") as s:
    if CUSTOMS and CUSTOMS.jti and CHAIN:
        before, _ = tr.walk_down(CHAIN.container.list_id, HUB_TOKEN, CUSTOMS.credential)
        print(f"  before revocation   {len(before.get('hops', []))} hops returned")
        done, why = tr.revoke(CUSTOMS.jti, HUB_TOKEN)
        print(f"  revoked             {why}")
        after, why_after = tr.walk_down(CHAIN.container.list_id, HUB_TOKEN, CUSTOMS.credential)
        print(f"  after revocation    {len(after.get('hops', []))} hops -- {why_after}")
        print()
        if after.get('hops'):
            print("  The revoked credential still walked the graph. That is a defect,")
            print("  not a demonstration, and it is what this step exists to catch.")
        else:
            print("  The same credential, unchanged and unexpired, no longer opens the door.")
    else:
        tr.skip(s, "there is no grant to revoke")
""")

# ==========================================================================
# 7. Why the two directions are gated differently
# ==========================================================================

md("""
## 7. Why up is harder than down

The asymmetry is the point of this notebook, and it is easiest to see in a case
that is not about coffee.

The permissions deck cites an outbreak: **10,930 ill across 17 states**, and a
recall that named a company and a region — never a field. The product was
leafy greens, shredded at a processor where four fields became two lots, cases,
and then a shelf. Exactly the shape built above.

Walking **down** from a case of product is contained: the investigator holds
the product, and the answer concerns their own consignment. A grant on that
consignment is a proportionate thing to ask for.

Walking **up** from an implicated field is not contained. The answer is the set
of everybody who bought from that farm, which is commercially valuable
independently of any outbreak, and most of it belongs to companies who are not
party to the investigation. So it is gated on accreditation rather than
possession, the accredited use resolves holders where the unaccredited one does
not, and every use of an authority credential is written to an audit log.

That distinction is the whole reason to separate the two calls instead of
offering one `trace` that goes both ways. And it is why section 4 matters: a
carefully reasoned gate is worth what its weakest door is worth.
""")

# ==========================================================================
# 8. Ledger
# ==========================================================================

md("""
## 8. What this run actually demonstrated

Generated from the steps above rather than written by hand. A hand-written
summary is a claim about some previous run; this one cannot disagree with the
cells it follows.

Several steps above are refusals, and they are marked LIVE because a refusal
that arrives is a working gate. A step marked **EMPTY** is different: the call
was made and the service had nothing to say.
""")

code("""
print(tr.LEDGER.checklist())
""")

md("""
---

### What is load-bearing here

A lot is named the way a field is, so pooling is checkable rather than
asserted. A container can hold lots rather than a flattened bag of fields, so
the walk down reports the mill step instead of skipping it. Trace refuses
without a credential, and refuses in a way that does not confirm the
consignment exists. An inclusion proof lets one membership be shown without
disclosing a supplier list. A grant can be withdrawn without the holder's
cooperation.

### What is not

**AG-015**, above: `reverse` answers most of the trace-forward question with
only a login. Open, and the fix is to apply the check that already exists.

**AG-016**: tier 3 is not demonstrated and cannot be. Accredited
trace-forward, holder resolution and the authority audit log are implemented in
AR2 and reachable by nothing, because no service issues the credential that
opens them, and every test that reaches tier 3 mocks out the two behaviours
that distinguish it. What is shown is tier 1.

**The chain is synthetic.** The four boundaries are real coordinates in
Honduras and the GeoIDs are really minted, but no coffee was milled and no
container sailed. The graph is the demonstration; the commerce is a story.

### Licences

AR2 and Pancake are EUPL-1.2, terrapipe-os is MPL-2.0.
""")


# ==========================================================================


def build() -> dict:
    cells = []
    for kind, source in CELLS:
        lines = source.splitlines(keepends=True)
        if kind == "markdown":
            cells.append({"cell_type": "markdown", "metadata": {}, "source": lines})
        else:
            cells.append({
                "cell_type": "code", "metadata": {}, "source": lines,
                "execution_count": None, "outputs": [],
            })
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true",
                        help="execute the notebook and commit its output")
    args = parser.parse_args()

    NOTEBOOK.write_text(json.dumps(build(), indent=1) + "\n")
    print(f"wrote {NOTEBOOK} ({len(CELLS)} cells)")

    if args.run:
        import nbformat
        from nbclient import NotebookClient

        notebook = nbformat.read(NOTEBOOK, as_version=4)
        client = NotebookClient(notebook, timeout=900, kernel_name="python3", resources={
            "metadata": {"path": str(HERE)}
        })
        client.execute()
        nbformat.write(notebook, NOTEBOOK)
        print(f"executed and wrote outputs to {NOTEBOOK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
