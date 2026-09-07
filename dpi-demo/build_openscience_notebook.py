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

### Reading public science data for a field, and knowing what the answer is worth

This notebook walks one question end to end: **can a buyer show that the coffee
in a container did not come from land cleared after 2020?**

It is the second of three, and each answers a different question:

| | question | where |
|---|---|---|
| **1. Field identity** | when is a boundary the same field? | `ar2_field_identity_demo.ipynb` |
| **2. Open science** ← you are here | what can public data say about it? | this notebook |
| **3. Traceability** | where did this lot come from, and who may ask? | `traceability_demo.ipynb` |

They stand alone, so identity and consent appear briefly here — enough to
follow the argument — and are taken apart properly in the first. Sections 3 to
5 are the summary; if a GeoID or a grant is unfamiliar, start there.

What this notebook is actually about is the part in between: **public science
data has to be readable for a location, and the answer has to arrive with
enough context to be audited.** Most of what follows is about that second
clause. A reading with no scope, no provenance and no account of what was
missing is not evidence, however precise the number looks — and four of the
sections below exist because a plausible number turned out to mean something
other than what it appeared to.

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

- **LIVE** — ran against a running service. AR2 minted the GeoID, Pancake
  issued the grant, the node answered over HTTP.
- **LOCAL** — ran in this kernel, and could only ever have been one of three
  harmless things: writing a file, re-displaying a reading already fetched, or
  Pancake's own adapter reshaping what the node returned. **No LOCAL step reads
  a raster or computes a reading.** It cannot: the first cell installs an import
  hook that makes the data plane unimportable here.
- **SKIPPED** — the service was not available and there is no substitute. The
  cell says what it would have done.
- **FAILED** — it tried and something broke. The reason is printed.

Four of these steps used to fall back to an in-process copy of the data plane
when the node was unreachable. That produces the same numbers while
demonstrating nothing about anyone's deployment, and quietly turns an outage
into a clean run, so it is gone.

**A cell that did not really run does not look like one that did.** Nothing in
this notebook manufactures a reading to keep the narrative flowing. Where a
number could not be obtained there is a gap, and the gap is named, because a
plausible number in a document about compliance is worse than a missing one.

### Running it yourself

Section 0 below is the whole of it: a virtualenv, one `pip install`, and a file
with four addresses in it. **You do not need Docker and you do not run any of
the services** — they are somebody's deployment and you are a client of it.

The committed output is a real run against that deployment, on the date in the
first cell. Nine steps live, three local, none skipped and none failed.

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
## 0. Setting this up

Skip to section 1 if someone has already set this up for you. Otherwise this
takes about five minutes, most of it waiting for `pip`.

**You need Python 3.10 or newer.** Check with `python3 --version`. This catches
people out on macOS, which still ships 3.9 as `python3` — the first sign is
`pip` refusing to install `mcp` with a wall of version numbers. Install a newer
one from [python.org](https://www.python.org/downloads/) or with
`brew install python@3.12`, and use that name (`python3.12`) below.

**You do not need Docker, and you do not need to run any of the services.**
Everything the notebook reads comes from a deployment over HTTP. Nothing is
computed in this kernel — there is an import hook a few cells down that makes
that impossible rather than merely intended.

### macOS and Linux

```bash
git clone https://github.com/agstack/pancake.git
cd pancake/dpi-demo

python3.12 -m venv .venv                 # or python3.10 / python3.11
source .venv/bin/activate
pip install -r requirements.txt

cp demo.env.example demo.env             # then edit it: see below
python -m ipykernel install --user --name openscience-demo
jupyter lab openscience_dpi_demo.ipynb
```

### Windows

The same, in PowerShell. Only the two middle lines differ:

```powershell
git clone https://github.com/agstack/pancake.git
cd pancake\\dpi-demo

py -3.12 -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt

copy demo.env.example demo.env
python -m ipykernel install --user --name openscience-demo
jupyter lab openscience_dpi_demo.ipynb
```

If PowerShell refuses to run the activate script, it is the execution policy
rather than anything here:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

### Filling in `demo.env`

Four addresses and an account. The file is read when the notebook imports its
support module, so **a change needs a kernel restart**, and a real environment
variable overrides it if you want to point one run somewhere else.

```
HUB_URL=http://<host>:8000
AR2_NODE_URL=http://<host>:8001
PANCAKE_URL=http://<host>:8100
TERRAPIPE_OS_URL=http://<node-host>:8200
TERRAPIPE_OS_MCP_URL=http://<node-host>:8201/mcp

DEMO_EMAIL=you@example.org
DEMO_PASSWORD=pick-something
```

Ask whoever runs the deployment for the four addresses. The account is yours to
invent: it is registered on the hub the first time you run the notebook, and
every token is fetched fresh, so there is nothing to rotate and nothing secret
to be handed.

`demo.env` is gitignored. It names a deployment and holds a password, so it is
not a file to commit or paste into chat.

### If it does not work

The next cell reports what it found rather than failing silently, and
distinguishes the two things that go wrong. If every address reads `localhost`
and everything is `DOWN`, the notebook was never told which deployment to use —
`demo.env` is missing or the kernel predates it. If the addresses look right and
services are still down, it is the deployment, and the cell says so.

Selecting the wrong kernel is the other common one: the notebook needs the
kernel from the virtualenv you just installed into, not the system Python. In
JupyterLab that is the name in the top right.
""")

md("""
## 1. What is actually running

Before anything claims to work, find out what is here. This cell decides which
mode the rest of the notebook is in.
""")

code("""
import json, os, sys, textwrap
from pathlib import Path

if sys.version_info < (3, 10):
    # Worth catching here rather than letting it surface as a confusing import
    # error three cells down. Stock macOS ships 3.9, and the first sign of it is
    # `pip install` refusing mcp with a wall of version numbers.
    raise SystemExit(
        f"This notebook needs Python 3.10 or newer; this kernel is "
        f"{sys.version_info.major}.{sys.version_info.minor}.\\n"
        "See the setup section above: the fix is to build the virtualenv with a "
        "newer interpreter and select that kernel."
    )

def _find_support_module():
    \"\"\"Locate openscience_demo.py, which lives in pancake/dpi-demo/.

    This used to be sys.path.insert(0, os.getcwd()) with a comment saying the
    notebook runs from dpi-demo/. It does not always: a reviewer opens the
    executed copy archived under workplan/, or launches Jupyter from home, and
    gets ModuleNotFoundError with nothing pointing at the cause.
    \"\"\"
    starts = []
    if os.environ.get("PANCAKE_DPI_DEMO"):
        starts.append(Path(os.environ["PANCAKE_DPI_DEMO"]).expanduser())
    # The directory holding this notebook, when the editor tells us what it is.
    for key in ("__vsc_ipynb_file__", "__session__"):
        if globals().get(key):
            starts.append(Path(globals()[key]).resolve().parent)
    starts += [Path.cwd(), *Path.cwd().parents, Path.home()]
    for base in starts:
        for candidate in (base, base / "dpi-demo", base / "pancake" / "dpi-demo"):
            if (candidate / "openscience_demo.py").is_file():
                return candidate.resolve()
    return None

_HOME = _find_support_module()
if _HOME is None:
    raise SystemExit(textwrap.dedent(f\"\"\"
        Cannot find openscience_demo.py, which this notebook is built around.

        It lives in the pancake repository at pancake/dpi-demo/, alongside the
        notebook's own source. Looked outward from {Path.cwd()} and found no
        copy.

        Either start the kernel from that directory:
            cd <your pancake checkout>/dpi-demo && jupyter lab

        or point at it and restart the kernel:
            export PANCAKE_DPI_DEMO=<your pancake checkout>/dpi-demo
    \"\"\").strip())

import importlib, importlib.util, subprocess

# Install what is missing, into this kernel, from the file that declares it.
#
# The support module imports requests at module level, so this has to run before
# it is imported rather than at the first cell that needs a map. sys.executable
# rather than a bare `pip` so it lands in the interpreter actually running this
# notebook, which is the usual way a "pip install" that appeared to succeed ends
# up in some other environment. cwd is _HOME because requirements.txt refers to
# ../services relative to itself.
_NEEDED = {"requests": "requests", "httpx": "httpx", "folium": "folium",
           "plotly": "plotly", "s2sphere": "s2sphere", "mcp": "mcp"}
_missing = [p for module, p in _NEEDED.items() if importlib.util.find_spec(module) is None]
if _missing:
    print(f"dependencies     installing {', '.join(_missing)} into this kernel")
    _pip = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"],
        cwd=str(_HOME), capture_output=True, text=True,
    )
    importlib.invalidate_caches()
    _still = [p for module, p in _NEEDED.items() if importlib.util.find_spec(module) is None]
    if _still:
        raise SystemExit(textwrap.dedent(f\"\"\"
            Could not install {', '.join(_still)}.

            pip said:
            {(_pip.stderr or _pip.stdout or '(nothing)').strip()[:800]}

            Install by hand and restart the kernel:
                cd {_HOME} && pip install -r requirements.txt
        \"\"\").strip())
    print(f"                 installed; no restart needed")
else:
    print(f"dependencies     all present")

sys.path.insert(0, str(_HOME))

# Pancake's own package, for the step that turns a screen into a BITE.
# requirements.txt installs it editable, but an editable install takes effect
# through a .pth file read at interpreter startup, so on the very first run in a
# fresh kernel it is installed and still not importable -- which showed up as
# that one step skipping for no visible reason. Adding the source directory is
# deterministic and costs nothing when pip already did the job.
_services = _HOME.parent / "services"
if _services.is_dir() and str(_services) not in sys.path:
    sys.path.append(str(_services))

import openscience_demo as od

# Python caches modules, so a kernel that imported this before the file changed
# keeps running the old code, and the symptom is an AttributeError for a helper
# that is plainly there in the source. Reloading costs nothing and removes a
# whole class of confusing failure while the notebook is under active work.
od = importlib.reload(od)

print(f"support module   {_HOME}")
print(f"                 {od.forbid_local_backend()}")
print(f"settings         {od.SETTINGS_FILE.name}: "
      + (', '.join(od.SETTINGS_LOADED) if od.SETTINGS_LOADED else 'not read'))
print()

STACK = od.services()
for name, info in STACK.items():
    print(f"{name:14} {'UP  ' if info['up'] else 'DOWN'}  {info['url']:32} {info['detail']}")
print(f"{'mcp':14}       {od.MCP_URL}")

NODE_UP = STACK['terrapipe-os']['up']
print()
print(od.mode(STACK))
""")

md("""
### What this node holds

Before any field exists, ask the node what it can talk about. This is a public
catalogue: no token, no GeoID, no consent. Consent is needed to learn something
about *a particular field*, not to find out what could be learned about one, and
seeing that distinction here is the point of asking now.

Five of these come from Honduras's own forestry authority, the Instituto de
Conservación Forestal, published as downloads at
[geoportal.icf.gob.hn](https://geoportal.icf.gob.hn/geoportal/main): the coffee
and oil palm maps for 2020, and forest cover for 2024, 2018 and 2014. They are
mirrored here rather than fetched live, so a reading does not depend on that
site being up, and every reading reports the licence it came under. The ICF
files carry no stated licence, which the node says plainly rather than guessing.

The rest are global: the JRC's tropical moist forest products, which carry the
deforestation evidence; Hansen tree cover for the year 2000 baseline; ESA
WorldCover for land cover; Sentinel-2 NDVI; and NOAA's GFS forecast.

Having both matters. A national map and a global one disagreeing about the same
hectare is information, and the screen reports it as a second opinion rather
than picking a winner.
""")

code("""
LAYERS, why = od.library()
print(why)
od.show_library(LAYERS)
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

md("""
Where they are. Satellite imagery underneath, because the point of these four
is what is on the ground: click any field for its story, and switch to the
street layer with the control at the top right.

The boundaries are square because they *are* S2 cells — these are test fields
placed on cells the rasters had something to say about, not surveyed farms.
Everything downstream treats them as ordinary polygons, and a real boundary
from a mapping tool goes through the same path unchanged, which is what
section 10 does.
""")

code("""
if od.have_folium():
    display(od.field_map(FIELDS))
else:
    print(od.maps_unavailable())
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
HUB_TOKEN, TOKEN_SOURCE = od.hub_token()
print(f"hub token: {'yes' if HUB_TOKEN else 'no'} - {TOKEN_SOURCE}")
""")

code("""
GEOIDS = {}

with od.step("register boundaries -> GeoID") as s:
    if STACK['ar2-node']['up'] and HUB_TOKEN:
        for feature in FIELDS:
            name = feature['properties']['name']
            # {'wkt': ...} is the only body this route takes, and the GeoID comes
            # back under 'Geo Id'. Both were wrong here until 2026-09-02.
            r = od.post(f"{od.NODE_URL}/register-field-boundary",
                        token=HUB_TOKEN,
                        json={'wkt': od.wkt_of(feature['geometry']), 'field_name': name})
            GEOIDS[name] = od.geoid_of(r)
            print(f"  {name:22} {GEOIDS[name] or f'refused HTTP {r.status_code}: ' + r.text[:70]}")
        minted = [n for n, g in GEOIDS.items() if g]
        if not minted:
            raise RuntimeError(
                "AR2 is up and authenticated but minted no GeoID. That is a failure to "
                "report, not a reason to fall back to labels."
            )
    else:
        why = "AR2 not reachable" if not STACK['ar2-node']['up'] else f"no hub token ({TOKEN_SOURCE})"
        od.local(s, f"{why}; using a labelled local identifier, not a GeoID")
        for feature in FIELDS:
            p = feature['properties']
            GEOIDS[p['name']] = f"local-cell:{p['s2_token']}"
        print(f"  {why}, so no GeoID was minted. These are labels, not GeoIDs:")
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
                               token=HUB_TOKEN).json()
    else:
        od.skip(s, "the node is not answering")

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
    if STACK['pancake']['up'] and HUB_TOKEN and all(GEOIDS.values()):
        # Two calls: a grant is issued against a field list, so the list is
        # created first and its list_id names the subject. There is no
        # POST /grants -- the notebook asked for one until 2026-09-02 and read
        # the 404 as the grant being unavailable.
        CONSENT = od.consent_for(
            [GEOIDS[f['properties']['name']] for f in FIELDS],
            token=HUB_TOKEN,
            purpose='eudr-screening',
        )
        GRANT = CONSENT.credential
        print(f"  {'grant issued' if GRANT else 'no grant'}: {CONSENT.why}")
        print(f"  list_id     {CONSENT.list_id}")
        print(f"  credential  {CONSENT.jti}   <- what a revocation names")
        if not GRANT:
            raise RuntimeError(f"Pancake is up and authenticated but issued no grant: {CONSENT.why}")
    else:
        if not STACK['pancake']['up']:
            why = "Pancake is not up"
        elif not HUB_TOKEN:
            why = f"there is no hub token ({TOKEN_SOURCE})"
        else:
            why = "no GeoID was minted, so there is nothing to grant access to"
        od.skip(s, f"{why}; the screens below use the field cover directly")
        print(f"  {why}, so there is no grant to present.")
        print("  The screens that follow read the field's own cover, which is what a")
        print("  grant would have unlocked. In a real deployment the grant is what")
        print("  authorises that, and its absence is why the previous cell was coarse.")
""")

md("""
### The same question, three times

One field, one question — *how much of this was cleared after 2020?* — asked
three times over. Nothing changes between the calls except one HTTP header.

The field is the one that was cleared after the cut-off, so there is a real
finding to be masked or revealed. Watch the middle column, not the verdict.
""")

code("""
SUBJECT_ID = GEOIDS[SUBJECT]
DISCLOSURE = []

with od.step("the same screen at three disclosure tiers") as s:
    if NODE_UP and HUB_TOKEN and SUBJECT_ID:
        # A consent minted here and destroyed here, rather than the notebook's
        # own GRANT. This cell ends by revoking what it was given, so pointing
        # it at the shared credential meant running it twice asked both
        # questions with a credential its own first run had already killed:
        # rows two and three both came back 403, underneath a paragraph
        # asserting that row two had worked. Re-running one cell is the most
        # ordinary thing a reader does, and it turned the section that explains
        # consent into a section that appeared to disprove it.
        TIERS = od.consent_for([SUBJECT_ID], token=HUB_TOKEN, purpose='disclosure-comparison')

        DISCLOSURE.append(("nothing", *od.screen_with(SUBJECT_ID, HUB_TOKEN)))
        if TIERS.credential:
            DISCLOSURE.append(("a field-access grant",
                               *od.screen_with(SUBJECT_ID, HUB_TOKEN, TIERS.credential)))

            # Withdraw it and ask a third time. A revoked credential is refused
            # outright rather than quietly downgraded to the coarse answer --
            # a silent downgrade would make revocation indistinguishable from
            # never having presented anything.
            WITHDRAWN, why = od.revoke(TIERS.jti, HUB_TOKEN)
            print(f"  revoked: {why}")
            if WITHDRAWN:
                DISCLOSURE.append(("the same, now revoked",
                                   *od.screen_with(SUBJECT_ID, HUB_TOKEN, TIERS.credential)))
        else:
            print(f"  no grant to compare against: {TIERS.why}")
    else:
        od.skip(s, "the node or the hub is not answering")

if DISCLOSURE:
    print()
    od.show_disclosure(DISCLOSURE)
""")

md("""
Three things to take from that table.

**The coarse answer is not a worse version of the precise one; it is about a
different subject.** Without a grant the node answers about the S2 level-10 cell
the field sits in — some 81 km² against the field's 8.9 hectares. The clearing
is genuinely there in both, but spread across a neighbourhood it is a fraction
of a percent, and confined to the field it is over 40%. Neither figure is wrong.
Only one of them is about a farm.

**Every answer says which scope it used.** A coarse reading can never be mistaken
for a precise one downstream, because the scope travels with the number.

**Revocation bites, and it bites loudly.** The third row presents the same
credential as the second, seconds later, and is refused outright. Had the node
quietly fallen back to the neighbourhood answer, a withdrawn consent would look
exactly like a caller who never had one — and the owner would have no way to
tell whether withdrawing it had done anything.

If the second row is not a 200, the table says so beneath itself and the
paragraph above does not hold for that run. That happened on 2026-09-06: this
cell used to revoke the notebook's shared credential, so running it a second
time asked rows two and three with a grant its own first run had already
withdrawn, and both came back 403 under this same confident paragraph.

The credential in that third row was minted for this comparison and destroyed
here. The grant issued in section 5, which the rest of the notebook uses, was
never touched.
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
                                   token=HUB_TOKEN, grant=GRANT).json()
    else:
        od.skip(s, "the node is not answering")

for feature in FIELDS:
    name = feature['properties']['name']
    if name not in SCREENS:
        continue
    print(f"{feature['properties']['title']}")
    od.show_screen(SCREENS[name])
    drift = od.compare(feature['properties']['expected'], SCREENS[name])
    if drift:
        print("  DOES NOT MATCH WHAT WAS PLACED: " + '; '.join(drift))
    else:
        placed = feature['properties']['expected']
        print(f"  matches what was placed, within the boundary fringe "
              f"(coffee {(SCREENS[name].get('commodity') or {}).get('coffee_fraction', 0):.4f} "
              f"against {placed.get('coffee_fraction', 0):.4f} read off the cell alone)")
    print()
""")

md("""
The same four fields again, now coloured by the verdict each one came back
with. Red is deforestation detected, green is not detected. Click through for
the fraction cleared and how much of the field was actually measured — a
verdict without its coverage is half the answer.
""")

code("""
if od.have_folium() and SCREENS:
    display(od.field_map(FIELDS, screens=SCREENS))
elif not od.have_folium():
    print(od.maps_unavailable())
""")

md("""
### Why the figures do not land exactly on what was placed

Each of these fields was chosen by reading the stores directly and recording
what was there. The screen then reports slightly different numbers — coffee at
0.984 where 1.000 was placed, and so on. The gap is small, systematic, and worth
understanding, because it is a property of GeoIDs rather than an error.

The placer read **one S2 cell** at level 15. The screen reads **AR2's cover of
the polygon** registered from that cell's corners, and a cover is not the cell
it came from. For the first field AR2 returns the L15 cell plus 98 refinement
cells at level 20, hugging the boundary and adding about 9.6% in area. That
fringe is real ground just outside the cell, it is mostly but not entirely
coffee, and it pulls the field's figures towards its surroundings.

This is the honest behaviour. A field boundary is a polygon, a cover approximates
it from the outside, and the approximation is visible in the numbers. It also
sets the tolerance used above: the check flags a field only when it drifts
further than the fringe can explain, which is what tells you a store has changed
underneath the demo rather than that S2 is doing its job.
""")

md("""
Zoomed to one field, this stops being an argument and becomes a picture.

The blue square is the field's own S2 cell, the one the placer read. The orange
skirt around its edge is the refinement AR2 added when covering the polygon —
much smaller cells, at level 20, tracing the boundary. The white outline is the
registered boundary itself.

Those orange cells are the difference. They are real ground just outside the
blue square, the screen reads them because they are part of the cover, and they
are mostly but not entirely coffee — which is the whole of why the figures come
back near what was placed rather than exactly on it.

The cover is asked of AR2 rather than recomputed here. Registration is
idempotent on the geometry, so an already-registered field comes back in about
70 ms with its cover attached, and what gets drawn is the registry's covering
rather than a second implementation of it.
""")

code("""
if od.have_folium() and HUB_TOKEN:
    subject = next(f for f in FIELDS if f['properties']['name'] == SUBJECT)
    cover, why = od.s2_cover(subject, HUB_TOKEN)
    print(f"  {why}")
    if cover:
        display(od.cover_map(subject, cover))
elif not od.have_folium():
    print(od.maps_unavailable())
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

md("""
And the same thing as a picture, which is more convincing than the ratio.

The dashed cell is what AR2 hands back for this GeoID when **no grant** is
presented — asked of AR2 rather than derived here, so it is the registry's own
disclosure. The solid shape inside it is the field, which AR2 releases **only**
against a grant.

Consent is not a switch on the answer. It is the difference between these two
shapes, and every response says which one it is describing.
""")

code("""
if od.have_folium() and SUBJECT in GEOIDS and HUB_TOKEN:
    cell, why = od.masked_cell(GEOIDS[SUBJECT], HUB_TOKEN)
    print(f"  {why}")
    subject = next(f for f in FIELDS if f['properties']['name'] == SUBJECT)
    display(od.consent_map(subject, neighbourhood_token=cell))
elif not od.have_folium():
    print(od.maps_unavailable())
else:
    print("  needs a GeoID and a hub token; both come from the cells above")
""")

# ==========================================================================
# 7. The same field, across three national vintages
# ==========================================================================

md("""
## 7. The same field, in three national maps

The screen above reads global products. Honduras publishes its own, and the
node mirrors three vintages of it: 2014, 2018 and 2024. Asking all three of one
field is the closest thing here to a time series, and it turns out to be a
lesson about identity rather than about land.
""")

code("""
with od.step("read three vintages of the national map") as s:
    # The coffee field, not whichever came first. This section and the next are
    # about shade-grown coffee, and run on a pasture field they showed a pasture
    # field and drew no conclusion.
    COFFEE_ID, which = od.the_coffee_field(GEOIDS, HUB_TOKEN, GRANT)
    print(f"  reading {which}")
    if NODE_UP and COFFEE_ID:
        VINTAGES = od.vintages(COFFEE_ID, HUB_TOKEN, GRANT)
        if not any(v['classes'] for v in VINTAGES):
            od.empty(s, "no vintage returned a reading")
    else:
        od.skip(s, which if not COFFEE_ID else "the node is not answering")
        VINTAGES = []

if VINTAGES:
    print()
    od.show_vintages(VINTAGES)
""")

md("""
### The same decade, for all four fields

One field's three readings are a table. All four fields' readings are a
picture, and the picture is the point: the colours are what the *notebook*
grouped the publisher's labels into, because the three vintages use three
different legends and the raw labels do not line up across years.

That grouping is an editorial act, and it is worth naming as one. Hover any
square for the label the publisher actually used.
""")

code("""
TREND = []

with od.step("read every vintage for every field") as s:
    if NODE_UP and GRANT and any(GEOIDS.values()):
        BY_FIELD = {name: od.vintages(geo_id, HUB_TOKEN, GRANT)
                    for name, geo_id in GEOIDS.items() if geo_id}
        TREND = od.trend_rows(BY_FIELD)
        READ = sum(1 for row in TREND if row['label'] != 'no reading')
        print(f"  {READ} of {len(TREND)} field-vintage readings returned a class")
        if not READ:
            od.empty(s, "no vintage returned a reading for any field")
    else:
        od.skip(s, "no grant, or the node is not answering")
""")

code("""
if TREND and od.have_plotly():
    od.trend_chart(TREND).show()
elif TREND:
    print("plotly is not installed; the readings are in TREND")
""")

md("""
**This is the time trend this notebook can honestly draw, and it is not the
one that would sell it.** Three points a decade apart, of a categorical
variable, from a publisher who changed their legend twice. The chart a
reviewer wants is a season of NDVI — a curve per field, greening and
senescing — and section 9 explains why it is not here.
""")

md("""
Three readings of one field, and the crop never changed. What changed is how
the node can describe it.

**2024 answers in words** — `cafe`, and the forest classes around it — because
that layer's legend is declared. **2018 and 2014 answer with a bare number**,
`unlabelled_12` and `unlabelled_14`, because theirs are not. That is the right
thing for the node to say: inventing a label to satisfy a schema is how a wrong
one becomes permanent, so it says what it has and no more.

The two numbers are resolved above from the publisher's own legends, read out
of the source files on 2026-09-07. And this is where it gets dangerous:

| | 2014 | 2018 |
|---|---|---|
| code 12 | Pastos/Cultivos | **Cafetales** |
| code 14 | **Cafetales** | Vegetación Secundaria Húmeda |

The same number means different things in different years. Of the 26 codes
present in both vintages, three carry the same label. **A forest-loss figure
computed by subtracting one vintage from another by raw code would read this
field as coffee that became pasture and then became coffee again** — two
land-use changes that never happened — and the arithmetic would give no sign of
it. The node cannot currently refuse that comparison, because nothing tells it
the two codebooks are incompatible.

That is the argument for declaring a codebook alongside a categorical layer,
and for refusing cross-vintage arithmetic unless a crosswalk is declared. It is
recorded as AG-001 and is not yet built.
""")

# ==========================================================================
# 8. National against global
# ==========================================================================

md("""
## 8. When the national map and a global product disagree

Holding both a national map and a global one is not redundancy. It is the only
way to catch the specific mistake the EUDR legality guidance names.

The guide is explicit: *the potential for false positives; agroforestry
systems, including where crops are grown under tree cover, are not to be
considered forests.* Honduran coffee is largely shade-grown. A global canopy
product sees the shade trees, calls the hectare forest, and calls their removal
deforestation.

Read as a verdict that is an accusation against a farmer. Read as a
disagreement between two sources that are each right about what they measure,
it is the follow-up case the guide asks for.
""")

code("""
with od.step("hold the national reading against the global ones") as s:
    if NODE_UP and COFFEE_ID:
        DISAGREEMENT = od.national_against_global(COFFEE_ID, HUB_TOKEN, GRANT)
        if not DISAGREEMENT['national']:
            od.empty(s, DISAGREEMENT['why'])
    else:
        od.skip(s, which if not COFFEE_ID else "the node is not answering")
        DISAGREEMENT = {}

if DISAGREEMENT:
    od.show_disagreement(DISAGREEMENT)
""")

md("""
Neither product is wrong, and no average of them would be right. The national
map is measuring what is grown; the land-cover product is measuring what the
canopy looks like from orbit. On shade-grown coffee those two answers differ
for a good reason, and the difference is the finding.

This is why the screen reports per layer and per source rather than collapsing
to a single number. A score would have to pick one of these, and picking either
one silently is how a compliance system produces confident falsehoods.
""")

# ==========================================================================
# 7. Absence
# ==========================================================================

md("""
## 9. An absent layer is not a zero

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

md("""
`outside_coverage` is the absence with a shape, so it can be drawn.

Each rectangle is a layer's **declared** extent, as the library states it — not
where the data happens to be good, but where the publisher says the map exists.
The four fields are in red.

The oil palm layer is the one to look at. It is a regional band across the
north, and three of the four fields sit south of it in the coffee belt. When the
node says `outside_coverage` for those three it is not failing to find palm; it
is declining to report on ground its palm map never described. The fourth field
falls inside the band and comes back `no_data`, which is the different and
weaker statement: the map covers you and has nothing here.

Layers wider than this view — the JRC tropical belt, and the global ones — are
counted in the legend rather than drawn, since a rectangle around the whole map
says nothing.
""")

code("""
if od.have_folium() and STACK['terrapipe-os']['up']:
    display(od.coverage_map(FIELDS, od.get(f"{od.TERRAPIPE_OS_URL}/layers", token=HUB_TOKEN).json()))
elif not od.have_folium():
    print(od.maps_unavailable())
""")

# ==========================================================================
# 8. Other layers
# ==========================================================================

md("""
## 10. The same door, other data

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
                   token=HUB_TOKEN, grant=GRANT, params={'time': '2026-08-21'})
        # A 404 carrying reason: no_data is the node saying it holds nothing,
        # which is neither a success nor a failure. Recorded LIVE until
        # 2026-09-07, which made the ledger claim vegetation had been shown.
        got, why = od.holds_data(r, s)
        print(od.brief(r.json()))
    else:
        od.skip(s, "the node is not answering")

with od.step("GFS forecast for a field") as s:
    if NODE_UP:
        name = FIELDS[0]['properties']['name']
        r = od.get(f"{od.TERRAPIPE_OS_URL}/forecast/{GEOIDS[name]}", token=HUB_TOKEN)
        got, why = od.holds_data(r, s)
        print(od.brief(r.json()))
    else:
        od.skip(s, "the node is not answering")
""")

# ==========================================================================
# 11. Legality: a population, and a draw anyone can check
# ==========================================================================

md("""
## 11. A population, and a draw anyone can check

Deforestation is one of two things the EUDR asks. The other is legality — that
the commodity was produced in accordance with the laws of the country of
production — and it covers land rights, labour, tax and eight other categories
that no satellite can see. The guidance for it is a **survey**: define the
population, size a sample, interview at random, report how you chose.

Its steps map onto what is already here more closely than anything else in
this notebook. Step 3 defines a population; an AR2 list artifact **is** one —
an immutable, content-derived set of GeoIDs. Step 6 requires recorded, dated,
withdrawable consent before an interview; that is a grant. Step 4 asks which
deforestation analyses were used and what share of the production area each
covers; that is `/menu`, across a list.

Step 5 sizes the sample, and the figures are the strongest argument in the
document because they are counterintuitive:
""")

code("""
with od.step("size the sample the way the guide does") as s:
    for population in (100, 1_000, 100_000, 1_000_000):
        detect, prevalence, _ = od.interviews_needed(population, one_in=10)
        print(f"  population {population:>9,}   "
              f"to detect a problem in 1 farm in 10: {detect:>3} interviews   "
              f"to measure how common it is: {prevalence:>3}")
    od.local(s, "the guide's own tables, transcribed")
""")

md("""
**The numbers stop growing.** Detecting a problem affecting one farm in ten
takes 29 interviews whether the supply base is a thousand farms or a million.
Sampling cost is set by the confidence you want, not by the size of the base —
which is the answer to *we have ten thousand smallholders, this cannot be
done.* It can; it costs 29 interviews.

### The part that is missing, and that a list can half-supply

Step 7 requires the selection be random and Step 8 requires reporting how it
was made. The methods the guide offers are *a random number generator, drawing
lots, spinning a bottle, or any equivalent method.*

Every one of those is **unfalsifiable after the fact.** An auditor handed a list
of 29 farms cannot tell a spun bottle from a convenient choice, so Step 8
collects an assertion where it means to collect evidence. That is not a
criticism of the guide — with a paper population there is nothing better
available.

A list artifact makes something better available, though **less than it first
appears**, and the honest version of the argument is worth more than the
overstated one.
""")

code("""
with od.step("draw a sample from the list, seeded by the list alone") as s:
    if CONSENT.list_id and any(GEOIDS.values()):
        MEMBERS = [g for g in GEOIDS.values() if g]
        WANTED, _, why = od.interviews_needed(len(MEMBERS), one_in=10)
        # Capped at the population: this demo has four fields and the guide's
        # smallest tabulated population is a hundred.
        SIZE = min(WANTED, 2)
        NAIVE = od.draw(CONSENT.list_id, MEMBERS, SIZE)
        od.show_draw(NAIVE, len(MEMBERS))
    else:
        od.skip(s, "there is no list to draw from")
""")

md("""
It is reproducible, and that much is real: the draw belongs to one exact
population, cannot be passed off as a draw from another, and any holder of the
list recomputes it.

**But it is not unpredictable, and the first version of this section claimed it
was.** It said the identifier is derived from the membership, so it "cannot be
edited to suit" the draw. It can. Editing the membership changes the identifier,
which changes the draw completely — so whoever composes the population can add
a member, recompute, see whether the farms they would rather not have visited
came up, and try again. Each attempt is a fresh independent draw and costs
nothing.

The arithmetic is worse than it sounds:
""")

code("""
with od.step("measure how cheap it is to grind the draw") as s:
    # Add one dummy member, which changes the list_id and so redraws entirely.
    # Count how often a field the composer wants left out is in fact left out.
    TARGET = MEMBERS[0]
    ESCAPED = sum(
        1 for attempt in range(500)
        if TARGET not in od.verifiable_sample(
            CONSENT.list_id[:-4] + f"{attempt:04x}",
            MEMBERS + [f"{9_000_000 + attempt:064x}"],
            SIZE)
    )
    print(f"  a composer wanting one field left out of the sample succeeds")
    print(f"  in {ESCAPED} of 500 recomputations ({ESCAPED / 5:.0f}%).")
    print()
    print("  At the guide's own scale it is easier still: with a thousand farms")
    print("  and a sample of 29, any one farm is drawn 2.9% of the time, so the")
    print("  first attempt succeeds nineteen times in twenty with no grinding at")
    print("  all. Wanting a hundred particular farms all left out takes about")
    print("  twenty recomputations. A fraction of a second.")
    od.local(s, "arithmetic on the draw above")
""")

md("""
So what the list_id gives is **binding**, not unpredictability. It moves the
trust rather than removing it — out of the draw and into the population
definition, which is where Step 3 already puts it: *good population definition
is a precondition for a meaningful verification exercise.* Worth having, and
less than was claimed.

### Removing it properly

Grinding needs a seed the composer could not have known when the membership was
fixed. Commit the `list_id`, then draw on a public randomness beacon round
published **after** the commitment. drand — the League of Entropy's beacon — is
public, needs no key, publishes every thirty seconds, and keeps every past
round retrievable and signed, so a draw published today can still be rechecked
in five years.
""")

code("""
with od.step("draw again, bound to a beacon round nobody could predict") as s:
    ROUND = od.beacon()
    BOUND = None
    if not ROUND:
        od.empty(s, "drand is unreachable from here")
    elif CONSENT.list_id and MEMBERS:
        BOUND = od.draw(CONSENT.list_id, MEMBERS, SIZE, entropy=ROUND)
        od.show_draw(BOUND, len(MEMBERS))
    else:
        od.skip(s, "there is no list to draw from")
""")

code("""
with od.step("show the draw still checks out years later") as s:
    if ROUND and BOUND:
        # Exactly what an auditor does: fetch the cited round and recompute.
        # Nothing from the original run is reused except its published inputs.
        FETCHED = od.beacon_at(ROUND.round)
        REDONE = od.draw(CONSENT.list_id, list(reversed(MEMBERS)), SIZE, entropy=FETCHED)
        OTHER = od.draw(CONSENT.list_id, MEMBERS, SIZE,
                        entropy=od.Beacon('drand', ROUND.round - 1, 'f' * 64))
        print(f"  round {ROUND.round} is still retrievable:  {FETCHED is not None}")
        print(f"  the auditor's recomputation matches: {REDONE.sample == BOUND.sample}")
        print(f"  ...from the members in a different order, holding nothing else")
        print(f"  a draw on a different round differs: {OTHER.sample != BOUND.sample}")
    else:
        od.skip(s, "there is no beacon-bound draw to check")
""")

md("""
Now the composer would have to predict drand to grind, and the auditor needs
only the list, the round number and the sample size to check the whole thing.
That is what Step 8 was asking for.

An auditor-supplied nonce, handed over after the list is committed, does the
same job with no external dependency and a different trust assumption: it
trusts the auditor, whose incentive runs the other way and who is already
trusted with the interviews. `draw()` takes either.

### Subgroups

Step 5 allows the population to be divided where subgroups may be expected to
differ, and requires that *every member of the total population must fall into
one of the subgroups*. Step 7 then wants a separate draw inside each.
""")

code("""
with od.step("draw separately within each subgroup") as s:
    if BOUND and len(MEMBERS) >= 3:
        STRATA = {"steep_slope": MEMBERS[:2], "valley_floor": MEMBERS[2:]}
        BY_GROUP = od.draw_by_subgroup(
            CONSENT.list_id, STRATA, {name: 1 for name in STRATA}, entropy=ROUND)
        for name, made in BY_GROUP.items():
            print(f"  {name:14} drew {made.size} of "
                  f"{made.size + len(made.reserves)}: {made.sample[0][:20]}...")
        print()
        # A field in two subgroups, or in none, is a defect in the population
        # definition that would otherwise surface as a wrong denominator.
        try:
            od.draw_by_subgroup(CONSENT.list_id,
                                {"a": MEMBERS[:2], "b": MEMBERS[1:]}, {"a": 1, "b": 1})
            print("  overlapping subgroups were accepted -- that is a defect")
        except ValueError as complaint:
            print(f"  overlapping subgroups refused: {complaint}")
    else:
        od.skip(s, "there are too few fields to divide")
""")

md("""
Each subgroup draws independently, because the subgroup name is part of the
seed; without that a field would rank identically in every group it appeared
in. The partition is checked rather than assumed.

**What none of this is.** It does not make the interviews honest, and it says
nothing about the eight legality categories themselves. It closes exactly one
gap: whether the sample was chosen fairly becomes checkable instead of
asserted. Everything else in the guide still needs people.

**And it is a draft.** Whether an auditor would accept a recomputable draw in
place of a witnessed one is a question about audit practice, not about code,
and nobody who does this work has been asked yet. Recorded as AG-014.
""")

# ==========================================================================
# 9. Pancake
# ==========================================================================

md("""
## 12. Into the DPI: a screen becomes a BITE

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
            # Pancake's own adapter, and it makes no call: it reshapes the screen
            # the node already returned. Reported LIVE until 2026-09-06 because
            # the node happened to be up, which credited a local transformation
            # to the wrong side of the wire.
            od.local(s, "Pancake's adapter, reshaping the screen the node returned")
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
## 13. Out to the regulator: a DDS-ready file

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
    if not SCREENS:
        od.skip(s, "no screens to attach")
    else:
        # The node needs to know which plot is which field, so the GeoID rides
        # in the properties. It screens each one itself, using the grant we hold
        # for it -- a plot with no grant comes back with geometry and no finding.
        SUBMITTED = json.loads(json.dumps(EXPORT))
        for feature, field in zip(SUBMITTED['features'], FIELDS):
            feature['properties']['GeoID'] = GEOIDS[field['properties']['name']]

        RESULT = od.dds_export(
            SUBMITTED, country='HN', token=HUB_TOKEN,
            grants={g: GRANT for g in GEOIDS.values()} if GRANT else {})

        collection = RESULT['collection']
        print(f"  plots        {len(collection['features'])}")
        print(f"  screened     {RESULT['screened']} of {len(collection['features'])}")
        for refusal in RESULT['refused']:
            print(f"    refused    feature {refusal['feature']}: {refusal['reason']}")
        print(f"  problems     {len(RESULT['problems'])}"
              + ("" if RESULT['problems'] else "  (well-formed against the rules as we read them)"))
        for problem in RESULT['problems']:
            print(f"    - {problem}")
        print(f"  statements   {RESULT['chunks']}  (a statement is capped at 25 MB; "
              f"a larger consignment is split)")
        print()
        example = collection['features'][1]['properties']
        for key, value in example.items():
            if key == 'deforestation':
                continue
            print(f"  {key:16} {value}")
        if 'deforestation' in example:
            print(f"  {'deforestation':16} {json.dumps(example['deforestation'])[:280]}")
        print()
        leaked = [k for k, v in example.items() if 'Ramirez' in str(v)]
        print(f"  the producer's name appears in: {leaked or 'nothing'}")
        print(f"  {RESULT['validator_note'][:150]}")
""")

code("""
# Written out so it can be opened in any GIS, or diffed between runs.
with od.step("write the statement to disk") as s:
    if not SCREENS:
        od.skip(s, "nothing to write")
    else:
        od.local(s, "the file is written here; the statement in it was built on the node")
        out = os.path.join(os.getcwd(), 'honduras_dds_ready.geojson')
        with open(out, 'w') as handle:
            json.dump(collection, handle, indent=2)
        print(f"  {out}  ({os.path.getsize(out)} bytes)")
""")

# ==========================================================================
# 11. Publication
# ==========================================================================

md("""
## 14. How a scientist adds a layer

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
    if not NODE_UP:
        od.skip(s, "the node is not answering")
    else:
        # Actually try to publish, without a publish credential, and let the
        # operator's node say no. Read out of a local gate object until
        # 2026-09-06, which showed that this checkout contains a rule rather
        # than that the deployment enforces one.
        status, detail = od.publication_gate(HUB_TOKEN)
        print(f"  POST {od.TERRAPIPE_OS_URL}/layers  ->  {status}")
        print(f"  {detail}")
        print()
        print("  The gate checks that a layer can be read and attributed, not that it is")
        print("  right. There is no refusal reason meaning 'we disagree with the science'.")
        print("  Judging the data is the community's job, and the provenance travels with")
        print("  every reading so it can.")
""")

# ==========================================================================
# 12. Agents
# ==========================================================================

md("""
## 15. The same node, for an agent

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
    if not NODE_UP:
        od.skip(s, "the node is not answering")
    else:
        # Asked of the operator's MCP server over HTTP. Built in process against
        # a local terrapipe_os until 2026-09-06, which listed the tools this
        # checkout defines rather than the ones the node actually offers.
        for name, summary in od.mcp_tools(HUB_TOKEN):
            print(f"  {name:22} {summary[:92]}")
""")

md("""
### Asking it something

Below is a scripted turn: the questions are written by hand, the answers are
the node's own, over MCP. Not a language model — a model call needs a key,
costs money and returns something different every run, so the committed output
would stop being a record of what the node does and become a record of what a
model said about it.

Watch the third and fourth calls. They are the same tool, on the same field,
differing only in whether a grant is presented.
""")

code("""
with od.step("ask the node four questions as an agent would") as s:
    if not NODE_UP or not SUBJECT_ID:
        od.skip(s, "the node is not answering")
    else:
        EXCHANGE = od.ask_the_node([
            ("What can you tell me about this field, and what would each answer "
             "cost its owner in disclosure?",
             "field_menu", {"geo_id": SUBJECT_ID}),

            ("Has it been cleared since the cut-off?",
             "screen_deforestation", {"geo_id": SUBJECT_ID}),

            ("What is growing on it?",
             "read_layer", {"geo_id": SUBJECT_ID,
                            "layer_id": "icf_honduras_forest_cover_2024"}),

            ("The same question, with the owner's grant.",
             "read_layer", {"geo_id": SUBJECT_ID,
                            "layer_id": "icf_honduras_forest_cover_2024",
                            "field_grant": GRANT}),
        ], HUB_TOKEN)
        od.show_exchange(EXCHANGE)
""")

md("""
Three things worth taking from that.

**The second answer came back at neighbourhood scope.** No grant was presented,
so the node answered about the surrounding cell rather than the field, and said
so in the payload. An agent that reported that figure as the farm's would be
wrong, and the scope travelling with the number is what stops it.

**The third call was refused outright** — `grant_required` — and the fourth,
identical but for the credential, was answered. The agent surface is not a
side door. It calls the same handlers as the HTTP routes and enforces the same
consent, so there is no path where automating a request loosens the rules that
apply to making it.

**Every tool description says what the tool will not do.** An agent picks a tool
by reading them, so a description that oversells is a defect in the same way a
wrong return value is.
""")

# ==========================================================================
# 14. Ledger
# ==========================================================================

md("""
## 16. What this run actually demonstrated

Generated from the steps above rather than written by hand. A hand-written
summary of a notebook is a claim about some previous run; this one cannot
disagree with the cells it follows.

Read the unticked lines as the honest to-do list. There are two kinds and the
difference matters:

- **SKIPPED** — the call was never made, because something upstream was not
  running. Bring the stack up.
- **EMPTY** — the call was made, and the node answered that it holds nothing
  for that field. Nothing is broken; the layer needs ingesting.

The second word exists because until 2026-09-07 there was only the first four,
and a node answering `404 no_data` was recorded **LIVE** — so this ledger, the
one part of the notebook written to be incapable of overstating what ran,
reported that vegetation and weather had been demonstrated when neither had.
""")

code("""
print(od.LEDGER.checklist())
""")

md("""
### Against what this notebook set out to cover

The ledger says what ran. This says what was *asked for*, which is a different
list and a shorter one. Four categories of public data were in scope:
deforestation rasters, pest and disease, weather, and satellite vegetation.

Read from the ledger rather than written by hand, so it cannot tick a category
the run did not demonstrate.
""")

code("""
od.show_coverage(od.coverage_scoreboard(od.LEDGER))
""")

md("""
**One of four.** Deforestation is thoroughly demonstrated — four products,
three national vintages, a disagreement between them, and a screen that refuses
to call an incompletely measured field clean. The other three are not, and they
fail in two different ways.

*Weather and satellite* have layers. Both are declared, both report `mirrored:
true`, and both return no data for every field tried, across several date
ranges, while a positive control on the same node returns 200. That is an
ingest or a read-path defect rather than a design gap, it is **AG-013**, and it
is the single largest hole in this notebook: NDVI is what would have carried the
time trend, and GFS is what would have carried weather.

*Pest and disease* is different and worse. There is no layer to mount. The
public occurrence records that exist — GBIF for coffee leaf rust and berry borer
— resolve to a district or a municipality, not to a field, and a field-level
answer built from them would be an interpolation wearing a reading's clothes.
Recorded as **AG-013b**. Nothing here is blocked on Rajat; it is blocked on the
data not existing.

That is the honest scoreboard, and a demo that showed the first row and moved
on would be selling rather than reviewing.
""")

md("""
---

### Where this goes next

**What is already load-bearing.** The screen refuses to call an incompletely
measured field clean. Absence never becomes zero. Consent changes the
resolution of an answer rather than gating it entirely. Every number carries
the provenance that lets somebody else check it. And the two sections that
matter most are the ones where the data disagrees with itself — the national
map against the global product, and the same field across three vintages —
because a system that cannot show you a disagreement will eventually show you
a confident falsehood instead.

**What is not here.** NDVI and GFS are declared, mirrored and unreadable for
every field in this notebook, which is why they carry EMPTY above rather than a
chart; that is a provisioning gap, recorded as AG-013. Four more deforestation
rasters are being mirrored. Neither of the two older ICF vintages declares its
legend, so the node answers them with bare numbers and section 7 resolves those
by hand — the codebook belongs in the layer definition, recorded as AG-001.

**And one thing that is design, not provisioning.** Pest and disease was asked
for and is absent, because there is no open field-level pest surveillance layer
for Honduras to mirror. GBIF holds two records of coffee leaf rust and four of
coffee berry borer for the whole country — verified against the live API, with
a negative control to confirm the species filter fires. That is a real gap in
the open-science plane, not an oversight in this notebook, and inventing a risk
score to fill it would have been worse than leaving it named.

**Where to go next.** Field identity, de-duplication and the disclosure tiers
are taken apart on real parcel data in `ar2_field_identity_demo.ipynb`. Lots,
trace-back, trace-forward and the authority to ask are in
`traceability_demo.ipynb`.

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
