"""Generate openscience_dpi_demo.ipynb.

The notebook is generated rather than hand-edited so that its prose and its
code stay in one reviewable text file. Editing a committed .ipynb by hand means
reviewing a JSON diff with escaped newlines, which is how explanatory text
drifts out of step with the code it explains.

    python build_openscience_notebook.py          # write the notebook
    python build_openscience_notebook.py --run    # write it and execute it

Executing commits real output. That is the point: the notebook is meant to be
read by people who will not run it, so what is committed has to be a record of
a real run, with every step marked LIVE, LOCAL, SKIPPED or FAILED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "openscience_dpi_demo.ipynb"

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


# ==========================================================================
# 0. What this is
# ==========================================================================

md("""
# Open science on a GeoID

### Deforestation, vegetation and weather for a field, from public data, with the consent that governs it

This notebook walks one question end to end: **can a buyer show that the coffee
in a container did not come from land cleared after 2020?**

Answering it touches every part of the DPI, which is why it makes a good tour.
A boundary has to become a durable identity. Somebody has to consent to that
identity being resolved to a location. Public science data has to be readable
for that location. The answer has to arrive with enough context to be audited,
and end up in the form a regulator accepts.

Four repositories are involved and each does one thing:

| | what it owns |
|---|---|
| **AR2** | the boundary becomes a **GeoID**, recomputable from the geometry by anyone |
| **Pancake** | consent: who may resolve that GeoID to a place, and the **BITE** store the answers land in |
| **terrapipe-os** | the open-science data plane: mirrored public rasters, read per GeoID |
| **agstack-pnd** | a consumer, running models off what arrives |

---

### How to read this

Every step prints a badge, and the last cell prints a ledger of all of them.

- **LIVE** — ran against the running stack. AR2 minted the GeoID, Pancake
  issued the grant, the node answered over HTTP.
- **LOCAL** — the stack is not up, but the mirrored rasters are mounted and
  terrapipe-os is importable, so the data plane ran in this process against
  the real national stores. The numbers are real; the identity and consent
  parts are stood in for, and each affected cell says so.
- **SKIPPED** — neither was available. The cell says what it would have done.
- **FAILED** — it tried and something broke. The reason is printed.

**A cell that did not really run does not look like one that did.** Nothing in
this notebook manufactures a reading to keep the narrative flowing. Where a
number could not be obtained there is a gap, and the gap is named, because a
plausible number in a document about compliance is worse than a missing one.

### Running it yourself

The committed output is from a LOCAL run: no stack, real rasters. To reproduce
that much you need the two national stores ingested, which is one command each
in `terrapipe-os`:

```bash
export TERRAPIPE_SHARE=/tmp/tpos-share
bin/ingest-raster jrc_tmf_deforestation_year <the JRC TMF GeoTIFF>
bin/ingest-raster icf_honduras_cafe_2020     <the ICF coffee GeoTIFF>
bin/place-demo-fields examples/honduras_demo_fields.geojson
```

For a LIVE run, `cd dpi-demo && make openscience` brings up AR2, the hub,
Pancake and the node together, and every step below that says SKIPPED or LOCAL
becomes LIVE.

### What is real and what is not

Real: the deforestation, forest cover and coffee rasters (JRC TMF and the
Honduran forestry authority ICF), the readings taken from them, every verdict,
and the layer definitions.

Not real: **the field boundaries**. They are S2 cells rather than surveyed
farms, and each one says so in its own `boundary` property. What is not
invented is *where* they are — they were chosen by scanning the ingested
national rasters for cells that genuinely tell each story. So the polygons are
stand-ins and the findings about the land under them are not.
""")

md("""
## 1. What is actually running

Before anything claims to work, find out what is here. This cell decides which
mode the rest of the notebook is in.
""")

code("""
import json, os, sys, textwrap
sys.path.insert(0, os.getcwd())   # the notebook runs from dpi-demo/, beside its support module
import openscience_demo as od

STACK = od.services()
for name, info in STACK.items():
    print(f"{name:14} {'UP  ' if info['up'] else 'DOWN'}  {info['url']:32} {info['detail']}")

SHARE_OK, SHARE_WHY = od.share_mounted()
TPOS_OK, TPOS_WHY = od.terrapipe_os_importable()
print()
print(f"mirrored rasters   {'YES' if SHARE_OK else 'NO '}  {SHARE_WHY}")
print(f"terrapipe-os here  {'YES' if TPOS_OK else 'NO '}  {TPOS_WHY}")

NODE_UP = STACK['terrapipe-os']['up']
CAN_RUN_LOCALLY = SHARE_OK and TPOS_OK
print()
print("mode:", "LIVE (stack is up)" if NODE_UP else
      ("LOCAL (real rasters, in process)" if CAN_RUN_LOCALLY else "SKIPPED (nothing to read)"))
""")

# ==========================================================================
# 2. The fields
# ==========================================================================

md("""
## 2. Four fields, chosen by what the rasters say

Each field below was selected by scanning the ingested national rasters for a
cell that genuinely tells its story. `expected` is what the placer read at the
time it chose the field; the screens later in this notebook are computed fresh,
and are checked against it. A disagreement would mean the store changed under
us or the screen changed its mind, and either is better found here than in
front of an audience.
""")

code("""
FIELDS = od.demo_fields()
for feature in FIELDS:
    p = feature['properties']
    print(f"{p['name']}  --  {p['title']}")
    print(f"  {p['area_ha']} ha at {p['centroid'][1]:.4f}, {p['centroid'][0]:.4f}")
    print(f"  boundary: {p['boundary']}")
    print(textwrap.fill(p['narrative'], 92, initial_indent='  ', subsequent_indent='  '))
    print()
""")

# ==========================================================================
# 3. GeoID
# ==========================================================================

md("""
## 3. A boundary becomes a GeoID

The GeoID is derived from the geometry, so anyone holding the boundary can
recompute it and check they were given the identifier for the field they think
they have. That is what makes the rest of the chain auditable: the screen is
about a GeoID, and the GeoID is about a shape nobody can quietly swap.

Minting one is AR2's job and only AR2's. When the stack is not up this notebook
does **not** compute a substitute — a second implementation that agreed today
would drift tomorrow, and a fabricated identifier in a compliance walkthrough
is exactly the wrong thing to demonstrate. It uses a clearly-marked local label
instead, and the screens key off the field's S2 cover, which for these
particular fields is exact because they *are* S2 cells.
""")

code("""
GEOIDS = {}

with od.step("register boundaries -> GeoID") as s:
    if STACK['ar2-node']['up']:
        for feature in FIELDS:
            name = feature['properties']['name']
            r = od.post(f"{od.NODE_URL}/register-field-boundary",
                        json={'geometry': feature['geometry']})
            GEOIDS[name] = (r.json() or {}).get('geo_id') if r.ok else None
            print(f"  {name:22} {GEOIDS[name] or 'refused: ' + r.text[:80]}")
    else:
        od.local(s, "AR2 not reachable; using a labelled local identifier, not a GeoID")
        for feature in FIELDS:
            p = feature['properties']
            GEOIDS[p['name']] = f"local-cell:{p['s2_token']}"
        print("  AR2 is not up, so no GeoID was minted. These are labels, not GeoIDs:")
        for name, label in GEOIDS.items():
            print(f"  {name:22} {label}")
""")

# ==========================================================================
# 4. Without consent
# ==========================================================================

md("""
## 4. What can be learned *without* permission

This is the part people usually expect to be all-or-nothing, and it is not.

Ask the node about a field with no grant in hand and it still answers — about
the neighbourhood cell the field sits in, roughly 80 km², rather than the field.
That answer is genuinely useful for a regional risk view and it is useless for
identifying whose farm it is. Every response says which scope it used, so a
coarse answer can never be mistaken for a precise one.

This is the disclosure tiering doing its job: consent changes the *resolution*
of the answer rather than switching it on and off.
""")

code("""
COARSE_SCREEN = None
SUBJECT = FIELDS[1]['properties']['name']   # the field cleared after the cut-off

with od.step("screen without a grant (neighbourhood scope)") as s:
    if NODE_UP:
        COARSE_SCREEN = od.get(f"{od.TERRAPIPE_OS_URL}/screen/{GEOIDS[SUBJECT]}",
                               token=os.environ.get('HUB_TOKEN')).json()
    elif CAN_RUN_LOCALLY:
        od.local(s, "computed in process from the mirrored rasters")
        import s2sphere
        from terrapipe_os.ar2 import COARSE_LEVEL, Cover
        from terrapipe_os.screen import screen_deforestation
        REGISTRY = od.local_registry()
        token = FIELDS[1]['properties']['s2_token']
        coarse = s2sphere.CellId.from_token(token).parent(COARSE_LEVEL).to_token()
        print(f"  the field's own cell                {token}   (~9 ha)")
        print(f"  what a caller without a grant gets  {coarse}   (L{COARSE_LEVEL})")
        print()
        COARSE_SCREEN = screen_deforestation(
            Cover(geo_id=GEOIDS[SUBJECT], tier='coarse', tokens=(coarse,), masking_level='L0'),
            REGISTRY).to_dict()
    else:
        od.skip(s, "no node and no mirrored rasters")

if COARSE_SCREEN:
    od.show_screen(COARSE_SCREEN)
""")

# ==========================================================================
# 5. Consent
# ==========================================================================

md("""
## 5. Consent, as a thing you can hold

To get an answer about the *field*, a caller presents a field-access grant.
Pancake issues those: a selective-disclosure credential, signed, revocable,
and held by the field's owner rather than by whoever wants the data. That is
the difference between "the registry decided you may" and "the owner said you
may, and here is the proof".

The node never holds a grant of its own. It passes the caller's grant to AR2
untouched, which is what makes the guarantee simple to state: **the node can
never read a field its caller could not.**
""")

code("""
GRANT = os.environ.get('FIELD_GRANT')

with od.step("Pancake issues a field-access grant") as s:
    if STACK['pancake']['up'] and STACK['ar2-node']['up']:
        target = GEOIDS[FIELDS[1]['properties']['name']]
        r = od.post(f"{od.PANCAKE_URL}/grants",
                    json={'geoids': [target], 'purpose': 'eudr-screening'},
                    token=os.environ.get('HUB_TOKEN'))
        GRANT = (r.json() or {}).get('credential') if r.ok else None
        print("  grant issued" if GRANT else f"  refused: {r.status_code} {r.text[:120]}")
    else:
        od.skip(s, "Pancake is not up; the screens below use the field cover directly")
        print("  Without Pancake there is no grant to present.")
        print("  The screens that follow read the field's own cover, which is what a")
        print("  grant would have unlocked. In a real deployment the grant is what")
        print("  authorises that, and its absence is why the previous cell was coarse.")
""")

# ==========================================================================
# 6. The screens
# ==========================================================================

md("""
## 6. The four verdicts

Now the actual question, for each field. Read each result as three things
rather than one:

- **the verdict** — deforestation detected, not detected, or inconclusive;
- **the coverage** — what share of the field was actually measured. A clean
  verdict over 12% of a field is not a clean field, and the screen refuses to
  round that up: incomplete cover returns *inconclusive*, not *clean*;
- **the evidence** — which layers were read, and which were not there.

Note the third field especially. Cleared decades ago, and legal: the cut-off is
2020, so a 1994 clearing is not a breach. The screen returns no deforestation
detected *and still reports the historical clearing year by year*, because
hiding it would make the verdict impossible to check.
""")

code("""
SCREENS = {}

with od.step("screen each field") as s:
    if NODE_UP:
        for feature in FIELDS:
            name = feature['properties']['name']
            SCREENS[name] = od.get(f"{od.TERRAPIPE_OS_URL}/screen/{GEOIDS[name]}",
                                   token=os.environ.get('HUB_TOKEN'), grant=GRANT).json()
    elif CAN_RUN_LOCALLY:
        od.local(s, "computed in process from the mirrored rasters")
        from terrapipe_os.screen import screen_deforestation
        REGISTRY = od.local_registry()
        for feature in FIELDS:
            name = feature['properties']['name']
            cover = od.local_cover(feature, GEOIDS[name])
            SCREENS[name] = screen_deforestation(cover, REGISTRY).to_dict()
    else:
        od.skip(s, "no node and no mirrored rasters")

for feature in FIELDS:
    name = feature['properties']['name']
    if name not in SCREENS:
        continue
    print(f"{feature['properties']['title']}")
    od.show_screen(SCREENS[name])
    drift = od.compare(feature['properties']['expected'], SCREENS[name])
    print(f"  agrees with the placer: {'yes' if not drift else 'NO -- ' + '; '.join(drift)}")
    print()
""")

md("""
### What consent bought

The same field, asked about twice. Without a grant the answer was about the
neighbourhood, and the clearing inside this one field was diluted across some
80 km² of mostly untouched land until it nearly disappeared. With a grant the
finding is unmistakable.

Both answers are true. Neither is a substitute for the other, and the reason
they differ is disclosure rather than data quality — which is why every
response carries its scope.
""")

code("""
if COARSE_SCREEN and SUBJECT in SCREENS:
    field, hood = SCREENS[SUBJECT], COARSE_SCREEN
    print(f"  {'':14} {'cleared after 2020':>20} {'verdict':>26}")
    print(f"  {'field':14} {field['deforested_fraction']:>19.4f} {field['verdict']:>26}")
    print(f"  {'neighbourhood':14} {hood['deforested_fraction']:>19.4f} {hood['verdict']:>26}")
    ratio = field['deforested_fraction'] / hood['deforested_fraction']
    print(f"\\n  The finding is {ratio:.0f}x more concentrated in the field than in the cell around it.")
""")

# ==========================================================================
# 7. Absence
# ==========================================================================

md("""
## 7. An absent layer is not a zero

This is the single most important line in the design, and the easiest to get
wrong.

Six of the layers in the library are not mirrored on this machine. A system
that treated "no data" as "no deforestation" would return a *cleaner* verdict
the *less* it had looked — and it would look exactly like a system that had
checked everything. So absence has its own vocabulary: each layer reports why
it could not contribute, and none of them contributes a zero.

The same distinction runs through the whole node. `not_mirrored` (we do not
have this layer here) is a different answer from `no_data` (we have it, and it
says nothing about this field), and both differ from a reading of zero.
""")

code("""
with od.step("show what was absent, and why") as s:
    if not SCREENS:
        od.skip(s, "no screens were produced")
    else:
        od.local(s, "read off the screen computed above")
        rows = [(e['layer_id'], e.get('absent') or 'read', (e.get('note') or ''))
                for e in od.evidence_rows(SCREENS[SUBJECT])]
        for layer_id, state, note in sorted(rows, key=lambda r: (r[1] != 'read', r[0])):
            print(f"  {layer_id:34} {state}")
            if note:
                print(textwrap.fill(note, 92, initial_indent=' ' * 6, subsequent_indent=' ' * 6))
        print()
        print(f"  {sum(1 for r in rows if r[1] == 'read')} read, "
              f"{sum(1 for r in rows if r[1] != 'read')} absent.")
        print("  Not one of the absent layers contributed a value to the verdict.")
""")

# ==========================================================================
# 8. Other layers
# ==========================================================================

md("""
## 8. The same door, other data

Deforestation is one question. The node answers any layer in its library the
same way: a GeoID goes in, a value for that field comes out, area-weighted
across the cells the field covers, with the coverage and the provenance
attached.

Two that matter for the demo are NDVI (crop vigour through a season, one value
per acquisition date) and the GFS forecast (weather at the model grid point
nearest the field). Both read from the existing TerraPipe share. Where that
share is not mounted here, these steps skip — which is the honest outcome, and
is what the badge will say.
""")

code("""
with od.step("NDVI for a field") as s:
    if NODE_UP:
        name = FIELDS[0]['properties']['name']
        r = od.get(f"{od.TERRAPIPE_OS_URL}/data/{GEOIDS[name]}/ndvi_sentinel2",
                   token=os.environ.get('HUB_TOKEN'), grant=GRANT, params={'time': '2026-08-21'})
        print(od.brief(r.json()))
    else:
        od.skip(s, "the NDVI store is on the TerraPipe network share, not mounted here")
        print("  The layer is defined and the read path is tested; what is missing is the mirror.")

with od.step("GFS forecast for a field") as s:
    if NODE_UP:
        name = FIELDS[0]['properties']['name']
        r = od.get(f"{od.TERRAPIPE_OS_URL}/forecast/{GEOIDS[name]}", token=os.environ.get('HUB_TOKEN'))
        print(od.brief(r.json()))
    else:
        od.skip(s, "the GFS store is on the TerraPipe network share, not mounted here")
        print("  Steps are returned as the model published them; nothing is interpolated to hourly.")
""")

# ==========================================================================
# 9. Pancake
# ==========================================================================

md("""
## 9. Into the DPI: a screen becomes a BITE

A reading is only useful to the rest of the system once it is in the shared
envelope. Pancake's TAP connector calls the node, wraps what comes back in a
**SIRUP**, and stores it as a **BITE** — the unit every other DPI consumer
reads, addressed by GeoID.

This is where the WHISP call used to sit in the EUDR path. What replaces it
needs no Earth Engine account, no FAO credentials, and no third-party call on
the day a shipment needs clearing.

The transform below runs on the real screen computed above, so the BITE is a
real BITE even when the stack is down. What needs the stack is *storing* it.
""")

code("""
with od.step("turn a screen into a BITE") as s:
    if not SCREENS:
        od.skip(s, "no screen to wrap")
    else:
        try:
            from pancake_services.tap.adapter_base import SIRUPType
            from pancake_services.tap.adapters.terrapipe_os import DeforestationAdapter
        except ImportError as exc:
            od.skip(s, f"pancake_services not importable: {exc}")
        else:
            if not NODE_UP:
                od.local(s, "transformed in process from the screen computed above")
            name = FIELDS[1]['properties']['name']
            adapter = DeforestationAdapter({
                'vendor_name': 'terrapipe-os', 'base_url': od.TERRAPIPE_OS_URL,
                'auth_method': 'bearer_token', 'sirup_types': ['land_use_screen'],
                'credentials': {'access_token': 'notebook'},
            })
            sirup = adapter.transform_to_sirup(
                {'_geoid': GEOIDS[name], '_grant_presented': bool(GRANT), 'screen': SCREENS[name]},
                SIRUPType.LAND_USE_SCREEN)
            bite = adapter.sirup_to_bite(sirup, GEOIDS[name], {})
            print(f"  BITE type   {bite['Header']['type']}")
            print(f"  GeoID       {bite['Header']['geoid']}")
            print(f"  tags        {', '.join(bite['Footer']['tags'])}")
            print(f"  verdict     {bite['Body']['sirup_data']['verdict']}")
            print(f"  coverage    {bite['Body']['sirup_data']['coverage_fraction']}")
            print(f"  scope       {bite['Body']['metadata']['scope']}  "
                  f"(field-scoped: {bite['Body']['metadata']['field_scoped']})")
            print(f"  sources     {', '.join(bite['Body']['metadata']['provenance'])}")
            absent = bite['Body']['metadata']['layers_absent']
            print(f"  absent      {len(absent)} layers, each named: {', '.join(sorted(absent))[:90]}")
""")

# ==========================================================================
# 10. DDS
# ==========================================================================

md("""
## 10. Out to the regulator: a DDS-ready file

The last step closes the loop. A boundary drawn in a browser mapping tool —
[GeoRoots](https://georoots.eu) is the one this is written against, though
nothing here assumes it — goes in; it becomes a GeoID; the GeoID is screened;
and what comes back out is a GeoJSON in the shape an EUDR **Due Diligence
Statement** wants.

Start with what such a tool actually exports: geometry, a label, whoever
collected it, and no GeoID at all.
""")

code("""
EXPORT = {
    'type': 'FeatureCollection',
    'features': [
        {'type': 'Feature', 'geometry': feature['geometry'],
         'properties': {
             'plot_name': feature['properties']['title'],
             'farmer': 'Ana Ramirez',
             'collected_by': 'cooperative survey, Marcala',
             'collected_on': '2026-02-14',
         }}
        for feature in FIELDS
    ],
}
print(f"  {len(EXPORT['features'])} plots, no GeoID, properties named however the tool names them:")
print(textwrap.indent(json.dumps(EXPORT['features'][0]['properties'], indent=2), '  '))
""")

md("""
Reading that into plots is deliberately tolerant about where it came from and
strict about what it infers. The label is taken from the first recognised
spelling of a plot name; the country is supplied by the caller, because a
mapping tool does not know which jurisdiction the filing is for; and if no
property looks like a label, it asks rather than guesses — a guessed string in
a regulatory filing is worse than a refusal.

The GeoID is passed in rather than computed, because minting one is AR2's job.
That is the identifier's whole value: one authority derives it.

Three things worth watching in the output:

- The finding sits in its own `deforestation` property, deliberately outside
  the fields the EU names. The operator signs the statement; the screen is
  ours, not theirs, and it should be readable as a separate claim.
- `farmer` was in the export and **does not appear in the output**, under that
  name or any other. Recognising a producer's name lifts it somewhere it can be
  included on purpose, and removes it from the passthrough — an exclusion a
  later copy step can undo is not an exclusion.
- The `GeoID` travels, so whoever receives the file can recompute it from the
  geometry and confirm the boundary they were sent is the boundary screened.

**The validator here is our reading of EU guidance, not the EU's validator.**
An empty problem list means well-formed as we understand the rules — WGS 84 at
six decimals, the EU's case-sensitive property names, closed and simple rings,
a polygon wherever the plot exceeds 4 ha. It is not acceptance, and the
response says so.
""")

code("""
with od.step("export a DDS-ready GeoJSON") as s:
    if not SCREENS or not TPOS_OK:
        od.skip(s, "no screens, or terrapipe-os not importable")
    else:
        if not NODE_UP:
            od.local(s, "exported in process from the screens computed above")
        from terrapipe_os import dds

        plots = dds.plots_from_geojson(
            EXPORT, producer_country='HN',
            geo_ids={i: GEOIDS[f['properties']['name']] for i, f in enumerate(FIELDS)})
        for plot, feature in zip(plots, FIELDS):
            plot.screen = SCREENS.get(feature['properties']['name'])

        collection = dds.to_collection(plots)
        problems = dds.validate(collection)
        print(f"  plots        {len(collection['features'])}")
        print(f"  problems     {len(problems)}" + ("" if problems else "  (well-formed against the rules as we read them)"))
        for problem in problems:
            print(f"    - {problem}")
        print(f"  statements   {len(dds.chunk(collection))}  (a statement is capped at 25 MB; "
              f"a larger consignment is split)")
        print()
        example = collection['features'][1]['properties']
        for key, value in example.items():
            if key == 'deforestation':
                continue
            print(f"  {key:16} {value}")
        print(f"  {'deforestation':16} {json.dumps(example['deforestation'])[:280]}")
        print()
        leaked = [k for k, v in example.items() if 'Ramirez' in str(v)]
        print(f"  the producer's name appears in: {leaked or 'nothing'}")
""")

code("""
# Written out so it can be opened in any GIS, or diffed between runs.
with od.step("write the statement to disk") as s:
    if not SCREENS or not TPOS_OK:
        od.skip(s, "nothing to write")
    else:
        od.local(s, "written from the export above")
        out = os.path.join(os.getcwd(), 'honduras_dds_ready.geojson')
        with open(out, 'w') as handle:
            json.dump(collection, handle, indent=2)
        print(f"  {out}  ({os.path.getsize(out)} bytes)")
""")

# ==========================================================================
# 11. Publishing
# ==========================================================================

md("""
## 11. How a scientist adds a layer

The library is not a fixed list. A researcher with a dataset can publish it,
and the workflow is deliberately narrow: publication needs a credential issued
by the node's operator, the definition must carry provenance and a licence,
and if it declares a store then that store has to exist and pass `check-layer`
before it is accepted. Append-only — an existing `layer_id` is refused.

What the gate does **not** do is review the science. It refuses only what could
not be read honestly: a layer with no licence, or one whose store is not there.
Judging the data is the community's job, and the provenance travels with every
reading so the community can.
""")

code("""
with od.step("show the publication gate") as s:
    if not TPOS_OK:
        od.skip(s, "terrapipe-os not importable")
    else:
        od.local(s, "the refusal reasons, read out of the gate itself")
        import inspect, re
        from terrapipe_os.publish import gate
        # Read from the source rather than restated here, so this list cannot
        # quietly fall out of step with what the gate actually does.
        reasons = sorted(set(re.findall(r'PublicationRefused\\(\\s*"([a-z_]+)"', inspect.getsource(gate))))
        print("  A publication is refused for exactly these reasons, and no others:")
        for reason in reasons:
            print(f"    - {reason}")
        print()
        print("  None of them is 'we disagree with the science'. The gate checks that a layer")
        print("  can be read and attributed, not that it is right. Judging the data is the")
        print("  community's job, and the provenance travels with every reading so it can.")
""")

# ==========================================================================
# 12. Agents
# ==========================================================================

md("""
## 12. The same node, for an agent

Everything above is also available over MCP, so an agent can use it without a
human writing glue. The tools are not a second implementation — each one calls
the same handler the HTTP route calls, which is what keeps the two surfaces
from drifting apart.

The descriptions matter more than usual here. An agent picks a tool by reading
them, so each one has to say what the tool will *not* do: that a screen without
a grant is about the neighbourhood, that an incomplete reading is inconclusive
rather than clean, that the export will not guess which field a boundary is.
""")

code("""
with od.step("list the agent-facing tools") as s:
    if not TPOS_OK:
        od.skip(s, "terrapipe-os not importable")
    else:
        od.local(s, "the server built in process and asked what it offers")
        from mcp.client import Client
        from terrapipe_os.ar2 import AR2Client
        from terrapipe_os.handlers import Service
        from terrapipe_os.mcp_server import build_mcp

        service = Service(registry=od.local_registry(),
                          ar2=AR2Client('http://unreachable'), auth_description={})
        server = build_mcp(service, None, stdio_operator_is_principal=True)

        async def _tools():
            async with Client(server) as client:
                return (await client.list_tools()).tools

        for tool in sorted(od.run_async(_tools), key=lambda t: t.name):
            print(f"  {tool.name:22} {(tool.description or '').split('.')[0][:92]}")
""")

# ==========================================================================
# 13. Ledger
# ==========================================================================

md("""
## 13. What this run actually demonstrated

Generated from the steps above rather than written by hand. A hand-written
summary of a notebook is a claim about some previous run; this one cannot
disagree with the cells it follows.

Read the skipped lines as the honest to-do list. Each is something this run did
not show, and most of them close by bringing the stack up:

```
cd dpi-demo && make openscience
```
""")

code("""
print(od.LEDGER.checklist())
""")

md("""
---

### Where this goes next

The gaps this run leaves are provisioning, not design. NDVI and GFS read from
the existing TerraPipe share and need it mounted; four more deforestation
rasters are being mirrored; the stack sections need Docker.

What is already load-bearing: the screen refuses to call an incompletely
measured field clean, absence never becomes zero, consent changes the
resolution of an answer rather than gating it entirely, and every number
carries the provenance that lets somebody else check it.

**Licences.** terrapipe-os is MPL-2.0, Pancake is EUPL-1.2, AR2 is EUPL-1.2.
The data keeps its own: JRC TMF is CC-BY-4.0, GFS is a US Government work in
the public domain, the ICF layers are the Honduran forestry authority's, and
every reading reports the licence of the layer it came from.
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
    parser.add_argument("--run", action="store_true", help="execute the notebook and commit its output")
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
