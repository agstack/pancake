# Running the open-science DPI notebook

[`openscience_dpi_demo.ipynb`](openscience_dpi_demo.ipynb) walks one question end
to end — *can a buyer show that the coffee in a container did not come from land
cleared after 2020?* — and touches every part of the AgStack DPI on the way:
a boundary becomes a GeoID, consent is issued and presented, public science data
is read for that field, and a regulator-ready file comes out.

This page is everything you need to run it. Nothing else.

**You do not need Docker, and you do not run any of the services.** They are
somebody's deployment; you are a client of it. Nothing is computed in your
kernel — there is an import hook in the first cell that makes that impossible
rather than merely intended.

---

## Before you start

**Python 3.10 or newer.** Check:

```bash
python3 --version
```

If that says 3.9 or older you need a newer one. This catches people out on
macOS, which still ships 3.9 as `python3`; the first symptom is `pip` refusing
to install `mcp` with a screenful of version numbers.

```bash
# macOS, with Homebrew
brew install python@3.12
```

On Windows or Linux, take an installer from
[python.org/downloads](https://www.python.org/downloads/).

**The four addresses of a deployment**, from whoever runs it. See
[Filling in `demo.env`](#filling-in-demoenv) below.

---

## macOS and Linux

Paste this whole block:

```bash
git clone https://github.com/agstack/pancake.git
cd pancake/dpi-demo
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m ipykernel install --user --name openscience-demo
cp demo.env.example demo.env
```

Use `python3.10` or `python3.11` above if that is what you have.

Now edit `demo.env` — see below — and then:

```bash
source .venv/bin/activate
jupyter lab openscience_dpi_demo.ipynb
```

## Windows (PowerShell)

Paste this whole block:

```powershell
git clone https://github.com/agstack/pancake.git
cd pancake\dpi-demo
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
python -m ipykernel install --user --name openscience-demo
copy demo.env.example demo.env
```

If PowerShell refuses to run the activation script, that is its execution
policy rather than anything here. This affects the current window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then edit `demo.env` and:

```powershell
.venv\Scripts\Activate.ps1
jupyter lab openscience_dpi_demo.ipynb
```

---

## Filling in `demo.env`

Four addresses and an account. Paste this into `demo.env` and replace the
angle-bracketed parts:

```
HUB_URL=http://<host>:8000
AR2_NODE_URL=http://<host>:8001
PANCAKE_URL=http://<host>:8100
TERRAPIPE_OS_URL=http://<node-host>:8200
TERRAPIPE_OS_MCP_URL=http://<node-host>:8201/mcp

DEMO_EMAIL=you@example.org
DEMO_PASSWORD=pick-something
```

**The addresses** come from whoever runs the deployment. The first four are
AR2's hub and registry, Pancake, and the terrapipe-os node; the node is often on
a different host from the rest.

**The account is yours to invent.** It is registered on the hub the first time
you run the notebook, and every token is fetched fresh, so there is nothing to
rotate and nobody has to hand you a secret.

The file is read when the notebook imports its support module, so **a change
needs a kernel restart**. A real environment variable overrides it, which is how
you point one run somewhere else without editing anything:

```bash
TERRAPIPE_OS_URL=http://other-node:8200 jupyter lab
```

`demo.env` is gitignored. It names a deployment and holds a password, so it is
not a file to commit or paste into chat.

---

## Running it

Open the notebook and **Run All**. It takes about fifteen seconds.

The first cell installs anything missing from `requirements.txt` into the
running kernel, so if you skipped a step above it will mostly rescue itself.

Two things to check in its output:

```
dependencies     all present
support module   /path/to/pancake/dpi-demo
                 local terrapipe-os backend blocked: ...
settings         demo.env: HUB_URL, AR2_NODE_URL, PANCAKE_URL, ...

hub            UP    http://...:8000    HTTP 200
ar2-node       UP    http://...:8001    HTTP 200
pancake        UP    http://...:8100    HTTP 200
terrapipe-os   UP    http://...:8200    HTTP 200

mode: LIVE against the hosted node
```

`settings` should list the keys from your `demo.env`, and the four services
should read `UP`. The last cell prints a ledger of every step:

```
9 against live services, 3 against local data, 0 skipped, 0 failed.
```

**LIVE** means it ran against a running service. **LOCAL** means one of three
harmless things — writing a file, re-displaying a reading already fetched, or
Pancake's adapter reshaping what the node returned. No LOCAL step reads a raster
or computes a reading. **SKIPPED** means a service was unavailable and there is
no substitute; the cell says what it would have done. A cell that did not really
run never looks like one that did.

---

## When it does not work

**Every address says `localhost` and everything is `DOWN`.** The notebook was
never told which deployment to use: `demo.env` is missing, or the kernel was
started before you created it. Create it and restart the kernel. The notebook
distinguishes this from a real outage and says which one it thinks it is.

**`AttributeError: module 'openscience_demo' has no attribute ...`** A kernel
that imported the support module before the file changed. Restart the kernel
and run all. (The first cell now reloads the module, so this should not recur.)

**`ModuleNotFoundError: No module named 'openscience_demo'`** The notebook
searches outward from the kernel's working directory and reports where it
looked. Either start Jupyter from `dpi-demo/`, or point at it and restart:

```bash
export PANCAKE_DPI_DEMO=/path/to/pancake/dpi-demo
```

**`This notebook needs Python 3.10 or newer`** The kernel is an old Python.
Usually the wrong kernel is selected — it needs the one from the virtualenv you
installed into, not the system Python. In JupyterLab that is the name in the top
right; pick `openscience-demo`.

**No maps, and a note about folium.** The first cell installs it. If that
failed, do it by hand and restart the kernel:

```bash
cd pancake/dpi-demo && pip install -r requirements.txt
```

**Something says SKIPPED.** That is the notebook being honest rather than
broken. The cell says what was unavailable.

---

## What you are looking at

Five maps, all Leaflet via folium:

| Where | What |
|---|---|
| Section 2 | The four demo fields on satellite imagery |
| Section 6 | The same fields, coloured by the verdict each came back with |
| Section 6 | The S2 cover — the field's own cell, and the refinement AR2 added around its edge |
| Section 6 | The disclosure boundary: what AR2 releases without a grant, and what it releases with one |
| Section 7 | Each layer's declared extent, which is why some layers answer `outside_coverage` |

The field boundaries are **synthetic** — S2 cells rather than surveyed farms,
and each says so in its own `boundary` property. What is not invented is where
they are: each was chosen by scanning the ingested national rasters for a cell
that genuinely tells its story. The rasters, the readings, the verdicts and the
layer definitions are all real.

**Licences.** terrapipe-os is MPL-2.0; Pancake and AR2 are EUPL-1.2. The data
keeps its own — JRC TMF is CC-BY-4.0, GFS is a US Government work in the public
domain, the ICF layers are the Honduran forestry authority's — and every reading
reports the licence of the layer it came from.
