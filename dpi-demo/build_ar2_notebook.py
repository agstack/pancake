"""Generate ar2_field_identity_demo.ipynb.

Generated rather than hand-edited, for the same reason as the open-science
notebook: prose and the code it explains stay in one reviewable text file
instead of a JSON diff full of escaped newlines.

    python build_ar2_notebook.py          # write the notebook
    python build_ar2_notebook.py --run    # write it and execute it
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "ar2_field_identity_demo.ipynb"

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


# ==========================================================================
# 0. Setup
# ==========================================================================

md("""
# A field's name

### What AR2 does, shown on parcels drawn by a national land register

Every platform that touches a farm gives its fields names. The co-op has a
number, the exporter has a code, the certifier has a reference, and none of them
is the same name. A field's identity stops at each company boundary, so
questions that cross one — *which products came from this field?* — get answered
by phone and email.

The internet had this problem before DNS. All names lived in one hand-maintained
file, and DNS replaced it with a namespace owned by nobody. AR2 applies that
design to fields, with one difference worth the whole notebook: **a domain is
assigned by a registry, but a GeoID is computed from the boundary itself.**
There is no allocator to capture, pay, or petition.

That claim is easy to state and easy to get subtly wrong, and the failure is
invisible until it matters. This notebook tests it on real parcels:

1. the same name is computed **here**, off the node, and by the node — and the
   two strings are compared
2. the same field, **redrawn four ways**, keeps one name
3. a **different** field that happens to share a bounding box gets its own name
4. knowing a name reveals **nothing** without permission

Steps 2 and 3 are the load-bearing ones, and they are where the previous
generation of this software fails.

---

**A note on where the parcels come from.** They are Dutch. The rest of this
project is about Honduras, and no Honduran parcel register of comparable
openness appears to exist. That seam is left visible rather than papered over
with shapes we drew ourselves — the argument here is about what a *name*
survives when a boundary is redrawn, and a boundary we invented could be quietly
invented to make the point. These were digitised by the Dutch agricultural
agency for subsidy administration, by people who have never heard of a GeoID.

That the geometry is Dutch and the story is Honduran is itself part of the
claim: identity is a function of geometry and is indifferent to which country
drew it.
""")

md("""
## 0. Setting this up

Same setup as the other two notebooks in this folder. If you have run either of
them, everything below is already in place and this section is a no-op.

**macOS / Linux**

```bash
cd dpi-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter lab ar2_field_identity_demo.ipynb
```

**Windows (PowerShell)**

```powershell
cd dpi-demo
py -3 -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
jupyter lab ar2_field_identity_demo.ipynb
```

Python 3.10 or newer. The cell below installs anything missing into the running
kernel, so if `pip install` above was skipped it still works.

**One thing this notebook wants that the others do not.** Section 3 recomputes
a GeoID without asking the node, which needs AR2's own derivation code. Point
`AR2_SOURCE` at a checkout of the `ar2` repository, or set `PYTHONPATH` before
launching Jupyter. Without it the notebook still runs — it just cannot make the
independence claim, and says so rather than quietly trusting the node.

See [`README-openscience.md`](README-openscience.md) for the full setup guide,
including `demo.env`.
""")

code("""
import importlib, os, subprocess, sys
from pathlib import Path

if sys.version_info < (3, 10):
    raise SystemExit(
        f"This notebook needs Python 3.10 or newer; this kernel is "
        f"{sys.version.split()[0]}. On macOS the system Python is 3.9 -- "
        "create a venv from a newer interpreter (see section 0)."
    )

HERE = Path.cwd()
for candidate in (HERE, *HERE.parents):
    if (candidate / "ar2_demo.py").exists():
        sys.path.insert(0, str(candidate))
        HERE = candidate
        break
    if (candidate / "dpi-demo" / "ar2_demo.py").exists():
        sys.path.insert(0, str(candidate / "dpi-demo"))
        HERE = candidate / "dpi-demo"
        break
else:
    raise SystemExit(
        "Could not find ar2_demo.py. Run this notebook from the dpi-demo "
        "directory, or set AR2_DEMO_DIR to point at it."
    )

missing = [m for m in ("requests", "folium", "s2sphere", "shapely")
           if importlib.util.find_spec(m) is None]
if missing:
    print(f"installing: {', '.join(missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                           "-r", str(HERE / "requirements.txt")])

# AR2's own derivation, for the independence check in section 3. Optional:
# without it section 3 reports that it could not check rather than pretending.
AR2_SOURCE = os.environ.get("AR2_SOURCE") or str(Path.home() / "ar2")
if (Path(AR2_SOURCE) / "app" / "geoid_v2.py").exists():
    sys.path.insert(0, AR2_SOURCE)

import ar2_demo as ar
import honduras_fields as hf
importlib.reload(ar)   # a stale kernel is the commonest confusion here
importlib.reload(hf)

print(f"support module: {ar.__file__}")
print(f"survey        : {hf.directory() or 'not present -- section 5 will say so'}")
print(f"AR2 source    : {AR2_SOURCE if 'app.geoid_v2' in sys.modules or (Path(AR2_SOURCE) / 'app' / 'geoid_v2.py').exists() else 'not found -- section 3 will say so'}")
""")

# ==========================================================================
# 1. What is running
# ==========================================================================

md("""
## 1. What is actually running

Two services matter here. The **hub** knows who you are and routes requests to
the country's node; it stores no boundaries. The **node** holds boundaries and
verifies every permission slip itself. A third, **Pancake**, issues those slips
and is needed only in section 6.

That separation is the security argument, and it is worth stating before
anything runs: the hub knows who you are but has no data, the node has data but
cannot invent permissions, and Pancake mints permissions but holds no
boundaries. No single compromise exposes a field.

Every step below is marked **LIVE**, **LOCAL**, **SKIPPED** or **FAILED**, and
the last section counts them. A notebook that quietly falls back to a canned
answer when a service is down is worse than one that stops, so this one is built
not to be able to.
""")

code("""
STACK = ar.mode.__self__ if hasattr(ar.mode, "__self__") else None
HUB_TOKEN, why = ar.hub_token()
print(f"hub token: {why}")

import requests
for name, url in (("hub", ar.HUB_URL), ("AR2 node", ar.NODE_URL), ("Pancake", ar.PANCAKE_URL)):
    try:
        alive = requests.get(f"{url}/docs", timeout=15).status_code == 200
    except requests.RequestException:
        alive = False
    print(f"  {name:10} {url:34} {'up' if alive else 'NOT REACHABLE'}")
""")

# ==========================================================================
# 2. The parcels
# ==========================================================================

md("""
## 2. Parcels somebody else drew

These come live from the Dutch crop parcel register (Basisregistratie
Gewaspercelen), served openly by PDOK. They are fetched rather than vendored so
that the licence can be checked against the source at the moment of reading,
and so nobody has to trust a file in this repository to be what it claims.

The service's own capabilities document gives `Fees: none` and an access
constraint of **CC0 1.0** — a public domain dedication, under which no
attribution is owed. It is credited anyway.

The area is Flevoland: reclaimed seabed, laid out for mechanised farming, so the
parcels are large and unambiguous. The register returns ditches and field
margins alongside actual fields; only arable parcels are kept.
""")

code("""
with ar.step("fetch real parcels from the Dutch register") as s:
    FIELDS, why = ar.parcels(limit=4)
    print(f"  {why}")
    for f in FIELDS:
        print(f"    {ar.describe(f)}")
    if not FIELDS:
        ar.skip(s, why)

SUBJECT = FIELDS[0] if FIELDS else None
RING = ar._ring(SUBJECT) if SUBJECT else None
""")

code("""
ar.parcel_map(FIELDS) if FIELDS else print("no parcels to draw")
""")

# ==========================================================================
# 3. The name
# ==========================================================================

md("""
## 3. A boundary becomes a name

Four steps, and none of them consults a registry:

1. **canonicalise** the polygon — a fixed vertex order and winding, so that two
   descriptions of the same shape become the same shape
2. **cover** it with S2 cells — a hierarchical grid over the globe, at a fixed
   resolution. The cover is of the *polygon*, not of its bounding box. That
   distinction is the whole of section 4.
3. **sort** the cell tokens, so the order they were produced in cannot matter
4. **SHA-256** the sorted list — that is the GeoID

Below, the name is computed twice: once on this machine from the boundary alone,
and once by asking the node. If the strings match, the claim holds — the name is
a function of the geometry, and the node is a convenience rather than an
authority. If they do not match, that is a defect and the notebook says so.

This is the difference from DNS that matters. There is no allocator here to
capture, to pay, or to petition, because there is nothing to allocate.
""")

code("""
with ar.step("compute the name here, and ask the node for it") as s:
    if not RING:
        ar.skip(s, "no parcel to name")
    else:
        LOCAL_ID, note = ar.computed_here(RING)
        NAMED = ar.name_of(RING, HUB_TOKEN)

        print(f"  computed here : {LOCAL_ID}")
        print(f"                  ({note})")
        print(f"  the node says : {NAMED.geo_id}")
        print(f"                  ({NAMED.message})")
        print()
        if LOCAL_ID is None:
            print("  NOT CHECKED: AR2's derivation is not importable here, so this run")
            print("  cannot show the name being recomputed independently. Set AR2_SOURCE.")
        elif LOCAL_ID == NAMED.geo_id:
            print("  They agree, character for character. The node was not needed to")
            print("  learn the name -- only to record that this field is known.")
        else:
            print("  THEY DIFFER. That is a defect: the name is supposed to be a")
            print("  function of the geometry, and two implementations disagree.")
""")

md("""
### What the name is hashed over

The S2 cover, drawn on the parcel. The name is a hash of exactly these cell
tokens, sorted. Zoom in and the cells are visible individually; the boundary is
the heavier line.

A cover is not a rasterisation of the field — it is the set of grid cells needed
to describe the shape at a fixed resolution, and a shape with more detail needs
more cells. That is why moving one vertex changes the cover a little and moving
a whole field changes it completely, which is what makes the next section work.
""")

code("""
with ar.step("show the S2 cover the name is derived from") as s:
    if not RING:
        ar.skip(s, "no parcel")
    else:
        TOKENS, note = ar.cover_of(RING)
        print(f"  {note}")
        if TOKENS:
            print(f"  first three   : {TOKENS[:3]}")
        else:
            ar.skip(s, note)

ar.cover_map(RING, TOKENS) if RING and TOKENS else None
""")

# ==========================================================================
# 4. The centrepiece
# ==========================================================================

md("""
## 4. The same field, drawn four more times

A boundary is never captured twice the same way. A different phone, a different
day, a surveyor who cut a corner, a receiver with a worse fix — each produces a
slightly different polygon of the same ground. A naming scheme that mints a new
name for each of those has not named the field; it has named the measurement.

Four redrawings, on the parcel from section 3:

| | what it stands for |
|---|---|
| one vertex pushed out ~20 m | a GPS fix a few metres out |
| one vertex pulled in, bounding box unchanged | a corner cut on resurvey |
| every vertex drifted 3 m | a different receiver, same walk |
| a different L-shaped field, same bounding box | **not this field at all** |

The last is the control. It is a genuinely different piece of ground that
happens to sit inside the same bounding box, and it must get its own name.

"True overlap" below is intersection-over-union computed with shapely — real
areas, not either scheme's own cover arithmetic. Neither naming scheme is
marking its own homework.
""")

code("""
REDRAWINGS, RESULTS = [], []
with ar.step("redraw the same field four ways and ask each time") as s:
    if not RING or not NAMED.geo_id:
        ar.skip(s, "no named parcel to redraw")
    else:
        REDRAWINGS = ar.redrawings(RING)
        RESULTS = [(r, ar.name_of(r.ring, HUB_TOKEN)) for r in REDRAWINGS]

if RESULTS:
    print()
    ar.show_redrawings(NAMED, RESULTS)
""")

code("""
ar.redrawing_map(RING, REDRAWINGS) if REDRAWINGS else None
""")

md("""
### What the previous generation does with the same four

The AR 1.x lineage — and the FAO fork of it — covers the boundary's **bounding
box** rather than the polygon. Identity therefore never sees the field's shape.
Measured on those repositories at their latest commits (26 Aug 2026), on a ~4 ha
field:

| the same field, redrawn | true overlap | what AR 1.x does |
|---|---|---|
| one vertex pushed out ~20 m | 97.6% | **a second, unlinked name** |
| same move, near a cell edge | 96.4% | a new name; the overlap check never runs |
| one vertex pulled in, bbox unchanged | 66.5% | **rejected as a duplicate** |
| a different L-shaped field, same bbox | 36.0% | **cannot register at all** |

Both failure directions in one table. Near-identical redrawings split into
separate identities; a genuinely different field is refused as a duplicate of
one it merely shares a rectangle with.

The newest Open Foris GeoID service (2026) removes derivation entirely — its
GeoIDs are UUIDs, allocated rather than computed — so the same field registered
twice yields two names unless something non-public intervenes.

**Why this is not a tidiness argument.** A split identity is invisible until the
day it matters, and then it hides product. If a farm's output is recorded under
two names because the boundary was walked twice, a recall that finds one name
does not reach the other half of the harvest. Identity resolution is not
housekeeping — it is the reason a trace can be trusted at all.
""")

# ==========================================================================
# 5. The same thing, in a real survey
# ==========================================================================

md("""
## 5. The same argument, without anything invented

Everything above this line was made up by us. The Dutch parcels are real, but
the four redrawings are ours — we moved the vertices, so of course they behave
as we said they would. A reviewer is entitled to discount the whole section on
that basis.

This section uses a **cooperative's own plot survey from Honduras**: sixteen
KML files, walked with phones by the people who farm the plots. Nobody produced
them for this notebook and nobody cleaned them up.

**They are not in this repository and will not be.** Each file is named for a
farmer and their national identity number, and the boundary itself is exactly
the personal data section 6 is about protecting. The loader reads them
from a directory outside the tree, returns geometry and a plot code, and
refuses a plot label that looks like an identity number — one of them is. If
the survey is not on this machine the section says so and the notebook carries
on.
""")

code("""
SURVEY = hf.load()
if SURVEY:
    hf.show(SURVEY)
else:
    print(f"  {hf.describe(SURVEY)}")
""")

md("""
### What arrived

Three things in that table are worth more than the four redrawings above,
because none of them were arranged.

**Two rows are one piece of ground.** Two files, two farmers, two national
identity numbers — and byte-identical vertex lists. This is the duplicate case
occurring by itself in a sixteen-file survey. Under AR 1.x's bounding-box rule
one of those two farmers is refused as a duplicate; under Open Foris's 2026
UUIDs they get two unrelated names for one plot.

**Two traces cross themselves.** Walked badly, closed wrong, and a naming
scheme has to do something defensible with them rather than reject them.

**They are very small.** A tenth of a hectare is a thirty-metre square, about
one Hansen pixel. The synthetic fields elsewhere in these notebooks are eight
hectares, which is a far easier case than the one that actually exists.
""")

code("""
NAMES = {}
with ar.step("name every distinct boundary in the survey") as s:
    if not SURVEY:
        ar.skip(s, "the survey is not on this machine")
    else:
        for plot in SURVEY:
            NAMES[plot.label] = ar.name_of([list(p) for p in plot.ring], HUB_TOKEN)

if NAMES:
    print()
    print(f"  {'plot':24} {'ha':>5}  {'geo id':24} note")
    for plot in SURVEY:
        got = NAMES[plot.label]
        note = "trace crosses itself" if plot.self_intersecting else ""
        if plot.duplicate_of:
            note = f"same ground as {plot.duplicate_of}"
        print(f"  {plot.label:24} {plot.hectares:5.2f}  "
              f"{(got.geo_id or 'refused: ' + got.message)[:24]:24} {note}")
""")

md("""
### The two farmers

The claim is not that the table above looks tidy. It is that the two rows
sharing a boundary got the **same name**, and that the name was not consulted
to decide it — it fell out of the geometry both times.
""")

code("""
with ar.step("compare the names given to the boundary that appears twice") as s:
    pairs = hf.duplicates(SURVEY) if SURVEY else []
    if not pairs:
        ar.skip(s, "no duplicated boundary in this survey")
    else:
        second, first_label = pairs[0]
        first, again = NAMES.get(first_label), NAMES.get(second.label)
        print(f"  first registration   {first_label:24} {str(first.geo_id)[:32]}")
        print(f"  second registration  {second.label:24} {str(again.geo_id)[:32]}")
        print()
        if first.geo_id and first.geo_id == again.geo_id:
            print("  One name. Two farmer records, two national identity numbers, one")
            print("  piece of ground -- and the hub resolved it without being told they")
            print("  were the same plot, because the name is computed from the boundary.")
            print()
            print(f"  The node's own words the second time: {again.message[:72]!r}")
            print(f"  Read as a new registration: {again.is_new}. Read as a resolution to")
            print(f"  a field already known: {again.resolved}.")
            print()
            print("  Note what it did *not* do: it did not refuse the second farmer. Both")
            print("  claims stand against one field, which is the situation on the ground")
            print("  and is a question for the cooperative, not for the naming scheme.")
        elif first.geo_id and again.geo_id:
            print("  Two names for one boundary. That is a defect in the derivation and")
            print("  this step exists to catch it.")
        else:
            print("  One of the two was refused, which is the AR 1.x behaviour this")
            print("  scheme is supposed to have fixed.")
""")

md("""
### The traces that cross themselves
""")

code("""
with ar.step("check the malformed traces were named rather than rejected") as s:
    broken = [p for p in SURVEY if p.self_intersecting] if SURVEY else []
    if not broken:
        ar.skip(s, "no self-intersecting traces in this survey")
    else:
        for plot in broken:
            got = NAMES[plot.label]
            verdict = "named" if got.geo_id else f"refused ({got.status})"
            print(f"  {plot.label:24} {len(plot.ring):3} vertices, crosses itself  -> {verdict}")
        print()
        if all(NAMES[p.label].geo_id for p in broken):
            print("  Both named. The derivation repairs the ring before it covers it, so")
            print("  a trace walked badly still gets a stable name instead of an error")
            print("  message the farmer cannot act on.")
            print()
            print("  This is worth stating carefully: repairing a self-intersection is a")
            print("  *choice about the geometry*, and two repairs of the same bad ring")
            print("  must agree or the name is not stable. That the same file names the")
            print("  same way twice is shown above; that any two implementations of the")
            print("  repair agree is not demonstrated here.")
        else:
            print("  At least one was refused. A survey that cannot name its own worst")
            print("  traces pushes the cleanup onto whoever collected them.")
""")

md("""
### The map the cooperative would recognise

Drawn only if the survey is present, and only ever on this machine.
""")

code("""
ar.parcel_map([p.feature for p in hf.distinct(SURVEY)]) if SURVEY else None
""")

# ==========================================================================
# 6. Disclosure
# ==========================================================================

md("""
## 6. Knowing the name grants nothing

A GeoID is safe to print on a shipping container. What it resolves to is decided
per caller, per query.

Ask the node about the name with no permission slip and it answers **L0**: the
roughly 10 km grid cell the field sits in, the country, and a rounded area.
Nothing else. This is not redaction applied to a full answer — it is how the
response is constructed, so there is no un-redacted version sitting behind it to
leak.

Present a valid slip and the same query returns **L1**: the exact boundary.

The owner reads back the same way. The first slip is self-issued at
registration, so there is one verification path for everyone and no privileged
back door.
""")

code("""
DISCLOSED = []
with ar.step("look the name up with no permission slip") as s:
    if not NAMED.geo_id:
        ar.skip(s, "nothing named to look up")
    else:
        DISCLOSED.append(("nothing", *ar.what_the_name_reveals(NAMED.geo_id, HUB_TOKEN)))

if DISCLOSED:
    ar.show_what_is_revealed(DISCLOSED)
""")

md("""
### The same name, with a slip

Pancake issues the slip. It is an SD-JWT verifiable credential carrying its own
terms — which fields, what purpose, until when — signed, and revocable by
flipping one bit on a public list.

The node verifies it locally: signature, expiry, revocation. It does not call
Pancake to do so, which is why consent keeps being enforced when Pancake is
down.
""")

code("""
with ar.step("issue a slip and look the same name up again") as s:
    if not NAMED.geo_id:
        ar.skip(s, "nothing named to look up")
    else:
        import openscience_demo as od
        CONSENT = od.consent_for([NAMED.geo_id], token=HUB_TOKEN, purpose='field-identity-demo')
        print(f"  {CONSENT.why}")
        if CONSENT.credential:
            DISCLOSED.append(("a field-access slip",
                              *ar.what_the_name_reveals(NAMED.geo_id, HUB_TOKEN, CONSENT.credential)))
        else:
            ar.skip(s, CONSENT.why)

if len(DISCLOSED) > 1:
    print()
    ar.show_what_is_revealed(DISCLOSED)
    coarse, precise = DISCLOSED[0][2], DISCLOSED[1][2]
    print()
    print(f"  The coarse answer is a {ar.vertices_disclosed(coarse)}-point grid cell.")
    print(f"  The precise one is the {ar.vertices_disclosed(precise)}-point boundary the farmer walked.")
""")

md("""
### The two answers, on one map

The dashed cell is what anyone may learn from the name alone. The solid shape
inside it is what the slip unlocks. The cell is roughly 10 km across and the
field is a few hundred metres, which is the difference between knowing a farm
exists somewhere in a district and knowing which farm it is.
""")

code("""
ar.disclosure_map(DISCLOSED[0][2], DISCLOSED[1][2]) if len(DISCLOSED) > 1 else None
""")

md("""
### And taken back

A slip is a thing you hold, so it is a thing that can be withdrawn. Revocation
publishes the credential's own identifier to a public status list the node
checks on every read. It does not need the holder's cooperation, it does not
need the credential to be found and deleted, and it does not need the field to
be re-registered or renamed.

The same credential is presented again below. Nothing about it has changed: it
has not expired and it is byte-for-byte what worked a moment ago.
""")

code("""
with ar.step("revoke the slip and present the very same one again") as s:
    if len(DISCLOSED) > 1 and CONSENT.credential and CONSENT.jti:
        done, why = ar.revoke(CONSENT.jti, HUB_TOKEN)
        print(f"  revoked  {why}\\n")
        AFTER = ar.what_the_name_reveals(NAMED.geo_id, HUB_TOKEN, CONSENT.credential)
        ar.show_what_is_revealed([*DISCLOSED, ("the same slip, revoked", *AFTER)])
        print()
        if ar.vertices_disclosed(AFTER[1]) == ar.vertices_disclosed(DISCLOSED[1][2]):
            print("  The revoked slip still returned the exact boundary. That is a")
            print("  defect, not a demonstration, and it is what this step exists to")
            print("  catch.")
        else:
            print("  Back to the grid cell. Note the status code: a revoked slip does")
            print("  not error, it degrades. The caller is not told they were cut off,")
            print("  which is the same answer a stranger gets and leaks nothing about")
            print("  who used to have access.")
    else:
        ar.skip(s, "there is no slip to revoke")
""")

# ==========================================================================
# 6. Federation
# ==========================================================================

md("""
## 7. One hub, many countries

The hub resolves the country from the coordinates and routes to that country's
node, so data stays in-country. Below, a Dutch parcel and a Honduran field are
registered through the *same* hub endpoint, and the hub decides where each
goes.

**What this deployment can and cannot show.** The routing path is real and is
exercised below. But there is one node behind this hub, so both countries land
on it. Routing is demonstrated; sovereignty is not. A second node would be
needed to show data staying in-country, and this notebook will not claim
otherwise.
""")

code("""
with ar.step("register in two countries through the same hub") as s:
    if not FIELDS:
        ar.skip(s, "no parcels")
    else:
        HONDURAN = ar.demo_fields()[0]['geometry']['coordinates'][0]
        for label, ring in (("a Dutch parcel", ar._ring(FIELDS[1])),
                            ("a Honduran field", HONDURAN)):
            through_hub = ar.name_of(ring, HUB_TOKEN, at=ar.HUB_URL)
            direct      = ar.name_of(ring, HUB_TOKEN, at=ar.NODE_URL)
            agree = through_hub.geo_id == direct.geo_id
            print(f"  {label:20} via hub {str(through_hub.geo_id)[:16]}...  "
                  f"direct {str(direct.geo_id)[:16]}...  same: {agree}")
        print()
        print("  One node stands behind this hub, so both routed to the same place.")
        print("  The routing ran; in-country residency is not shown by this run.")
""")

# ==========================================================================
# 7. Ledger
# ==========================================================================

md("""
## 8. What this run actually demonstrated

Generated from the steps above rather than written by hand, and it cannot
disagree with the cells it follows. Read the skipped lines as the honest to-do
list.
""")

code("""
print(ar.LEDGER.checklist())
""")

md("""
---

### Where to go next

- **[`openscience_dpi_demo.ipynb`](openscience_dpi_demo.ipynb)** — what can be
  *learned* about a field once it has a name and a permission slip: deforestation
  screening against national and global rasters, vegetation, weather.
- **the traceability notebook** — who else holds product from this field, in both
  directions, and who is allowed to ask.

### Sources

- Parcels: Basisregistratie Gewaspercelen, RVO / PDOK, CC0 1.0.
  [service.pdok.nl](https://service.pdok.nl/rvo/brpgewaspercelen/wfs/v1_0)
- AR 1.x and FAO fork measurements: *Permissions as Infrastructure*, Appendix E,
  26 Aug 2026, reproducing `evidence/fao_dedup_test_20260826.py`.
- S2 geometry: [s2geometry.io](https://s2geometry.io)
""")


def build() -> dict:
    return {
        "cells": [
            {
                "cell_type": kind,
                "metadata": {},
                "source": text.splitlines(keepends=True),
                **({"outputs": [], "execution_count": None} if kind == "code" else {}),
            }
            for kind, text in CELLS
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="execute the notebook after writing it")
    args = parser.parse_args()

    NOTEBOOK.write_text(json.dumps(build(), indent=1) + "\n")
    print(f"wrote {NOTEBOOK} ({len(CELLS)} cells)")

    if args.run:
        import nbformat
        from nbclient import NotebookClient

        nb = nbformat.read(NOTEBOOK, as_version=4)
        NotebookClient(
            nb, timeout=1200, kernel_name="python3", allow_errors=True,
            resources={"metadata": {"path": str(HERE)}},
        ).execute()
        nbformat.write(nb, NOTEBOOK)
        print("executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
