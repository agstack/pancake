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
           "s2sphere": "s2sphere", "mcp": "mcp"}
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
                   token=HUB_TOKEN, grant=GRANT, params={'time': '2026-08-21'})
        print(od.brief(r.json()))
    else:
        od.skip(s, "the NDVI store is on the TerraPipe network share, not mounted here")
        print("  The layer is defined and the read path is tested; what is missing is the mirror.")

with od.step("GFS forecast for a field") as s:
    if NODE_UP:
        name = FIELDS[0]['properties']['name']
        r = od.get(f"{od.TERRAPIPE_OS_URL}/forecast/{GEOIDS[name]}", token=HUB_TOKEN)
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
    if not NODE_UP:
        od.skip(s, "the node is not answering")
    else:
        # Asked of the operator's MCP server over HTTP. Built in process against
        # a local terrapipe_os until 2026-09-06, which listed the tools this
        # checkout defines rather than the ones the node actually offers.
        for name, summary in od.mcp_tools(HUB_TOKEN):
            print(f"  {name:22} {summary[:92]}")
""")

# ==========================================================================
# 13. Trace: a different question entirely
# ==========================================================================

md("""
## 13. A lot, and tracing it both ways

*Everything above answered one question about one field. This section asks a
different kind of question altogether, and it is here at the end because it
stands on its own: the same registry and the same credentials, used for supply
chain traceability rather than for screening. Read it as a second use case, not
as the conclusion of the first.*

Fields do not ship. Lots do — a container, a delivery, a day's harvest pooled
from several farms — and the questions that matter are asked of the lot.

A **field list** is that pooling made checkable. It is an ordered set of GeoIDs
with a `list_id` derived from its members, so the same three fields always
produce the same list, and a list cannot be edited after the fact without
becoming a different list. Pancake creates one every time it issues a grant;
you have already seen its `list_id` above.

Two questions run in opposite directions through it.

**Trace back** — *this container is on the dock; which farms is it from?* That is
the due-diligence direction, and it is what a customs officer or a buyer asks.

**Trace forward** — *this farm turned out to be a problem; where did its output
go?* That is the recall direction, and it is the harder one, because it has to
find every lot a field ever entered rather than reading one list.

Both are ordinary lookups here rather than a document exchange, which is the
whole argument for a shared identifier: the two parties do not have to agree on
a format, only on which field they are talking about.
""")

code("""
LOT, LOT_CONSENT = None, None
MEMBERS = ['compliant_coffee', 'legacy_clearing', 'post_cutoff_clearing']

with od.step("pool three fields into a lot") as s:
    if STACK['pancake']['up'] and HUB_TOKEN and all(GEOIDS.get(m) for m in MEMBERS):
        LOT_CONSENT = od.consent_for(
            [GEOIDS[m] for m in MEMBERS], token=HUB_TOKEN,
            purpose='trace demonstration', name='container HNCF-2026-09',
        )
        LOT = LOT_CONSENT.list_id
        print(f"  list_id  {LOT}")
        print(f"  members  {len(MEMBERS)} fields, one of which was cleared after the cut-off")
    else:
        od.skip(s, "Pancake is not answering, or no GeoIDs were minted")
""")

md("""
### Trace back: from the container to the farms
""")

code("""
with od.step("trace back from the lot to its fields") as s:
    if LOT and LOT_CONSENT and LOT_CONSENT.credential:
        BACK, why = od.trace_back(LOT, HUB_TOKEN, LOT_CONSENT.credential)
        print(f"  {why}")
        NAME_OF = {v: k for k, v in GEOIDS.items() if v}
        for hop in BACK.get('hops', []):
            print(f"\\n  depth {hop['depth']}  {len(hop.get('geoids') or [])} members")
            for geoid in hop.get('geoids') or []:
                print(f"      {geoid[:16]}...  {NAME_OF.get(geoid, 'a field not in this demo')}")
    else:
        od.skip(s, "there is no lot to trace back from")
""")

md("""
That request carried the grant scoped to *this* list. Without it AR2 answers
**404**, not 403 — deliberately, because a 403 would confirm to a stranger that
the list exists. Trace is not a public index; it is a private one that the
holder of a credential can walk.
""")

md("""
### Trace forward: from the farm to the containers
""")

code("""
with od.step("trace forward from a field to the lots it entered") as s:
    if GEOIDS.get('post_cutoff_clearing') and HUB_TOKEN:
        SUSPECT = GEOIDS['post_cutoff_clearing']
        LOTS, why = od.lists_containing(SUSPECT, HUB_TOKEN)
        print(f"  the field screened at {DISCLOSURE[1][2].get('deforested_fraction', 0):.1%} cleared "
              f"after the cut-off" if len(DISCLOSURE) > 1 else "  the field cleared after the cut-off")
        print(f"  {why}\\n")
        for list_id in LOTS:
            mark = '  <- the container above' if list_id == LOT else ''
            print(f"      {list_id[:16]}...{mark}")
    else:
        od.skip(s, "no GeoID was minted for the suspect field")
""")

md("""
That is a recall in three lines. The field is the one that failed its screen;
every lot listed is a consignment that would have to be held, and each of those
`list_id`s can be traced back in turn to find the other farms in it.

Nothing here required the farms, the exporter and the buyer to share a database
— only to have registered the same boundaries and got the same GeoIDs, which is
what makes the identifier worth having.

### Proving membership without revealing the list

A buyer may need to show a regulator that a particular field was in a particular
lot, without disclosing the other farms in it. The list is a Merkle tree, so
that is an inclusion proof: a handful of sibling hashes that recompute the
`list_id` and say nothing about anyone else.
""")

code("""
with od.step("prove one field is in the lot, without revealing the others") as s:
    if LOT and GEOIDS.get('compliant_coffee'):
        PROOF, why = od.inclusion_proof(LOT, GEOIDS['compliant_coffee'], HUB_TOKEN)
        print(f"  {why}\\n")
        for sibling in PROOF:
            print(f"      {sibling['position']:6} {sibling['sibling'][:32]}...")
        print(f"\\n  These recompute {LOT[:16]}... and disclose no other member.")
    else:
        od.skip(s, "there is no lot to prove membership in")
""")

# ==========================================================================
# 14. Ledger
# ==========================================================================

md("""
## 14. What this run actually demonstrated

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
