"""Generate green_guarantee_demo.ipynb.

The fourth of four. Generated rather than hand-edited, as the other three are:
a committed .ipynb is a JSON diff with escaped newlines, and prose drifts out of
step with code inside one.

    python build_green_guarantee_notebook.py          # write the notebook
    python build_green_guarantee_notebook.py --run    # write it and execute it

What it walks is the Green Guarantee Micro-Credit System's workflow (SRS
"Confianza HCDS Connector", §2.2.1, steps 1-27) on the DPI's rails: a plot
becomes a GeoID, the farmer consents, the plot is screened, the screen comes
out as a three-valued risk class with the evidence that settled it named, the
guarantor issues the guarantee as a credential the lender can verify and the
guarantor can revoke, and every step is in the ledger.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "green_guarantee_demo.ipynb"

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


def shared_setup() -> str:
    """The setup cell from the open-science notebook, verbatim but for the modules."""
    sys.path.insert(0, str(HERE))
    import build_openscience_notebook as openscience  # noqa: PLC0415

    setup = [body for kind, body in openscience.CELLS
             if kind == "code" and "_find_support_module" in body]
    if not setup:
        raise SystemExit("could not lift the setup cell from the open-science builder")
    return setup[0].replace(
        "import openscience_demo as od",
        "import openscience_demo as od\nimport trace_demo as tr\nimport guarantee_demo as gg",
    ).replace(
        "od = importlib.reload(od)",
        "od = importlib.reload(od)\ntr = importlib.reload(tr)\ngg = importlib.reload(gg)",
    )


# ==========================================================================
# 0. What this is
# ==========================================================================

md("""
# A guarantee a lender can check, on a plot nobody had to hand over

### The Green Guarantee Micro-Credit System, walked on DPI rails

A smallholder in Honduras wants a micro-credit to renovate a coffee plot. The
lender wants to know two things before it lends: *is this plot what the farmer
says it is*, and *will this coffee be legal to sell into Europe after
30 December 2026*. A guarantor — Confianza — stands behind the loan if the
answers are good.

The Software Requirements Specification for that system (Permarobotics for
CIAT, September 2026) describes it as a data space: the plot travels from the
farmer's phone to a connector, to a risk service, to the guarantor, to the
lender. This notebook walks the same 27 steps on the AgStack DPI and asks, at
each one, what actually has to move.

The answer, most of the time, is: **a name and a signed statement about it**.
Not the polygon.

Every step below is recorded LIVE (the hosted services answered), LOCAL (the
code exists and ran here, but is not yet deployed — it says which commit), or
NOT-OURS (Layer 3: the App, the marketplace, farmer identity — by design). The
ledger at the end is generated from what ran, not typed.
""")

code(shared_setup())

md("""
## 1. Who is answering

Four hosted services and three checkouts on this machine. The hosted services
are what the other three notebooks use; the checkouts hold tonight's code for
the pieces the hosted services do not yet have, and the ledger names the commit
wherever one of them is used.
""")

code("""
STACK = od.services()
for name, info in STACK.items():
    print(f"  {'UP  ' if info['up'] else 'DOWN'}  {name:13} {info['url']}  ({info['detail']})")
print()
print(od.mode(STACK))
print()
print("local checkouts used for LOCAL steps:", gg.checkouts())
TOKEN, HOW = od.hub_token()
print("hub session:", HOW)
""")

# ==========================================================================
# 1. A plot becomes a name
# ==========================================================================

md("""
## 2. Step 5 — a plot becomes a GeoID (LIVE)

The SRS's step 5: the App uploads the plot, the Connector registers it, a
`plotId` comes back. Here `plotId` **is** the GeoID: a SHA-256 over the S2 cell
cover of the boundary, so the same land drawn twice yields the same name and
two different plots cannot share one. That single property answers the SRS's
`TBD-1` (duplicate detection) on the plot rather than on the farmer.

Four Honduran fields with synthetic boundaries in real places: the rasters
underneath them genuinely tell each story. Their names say what to expect.
""")

code("""
FIELDS = od.demo_fields()
GEO = {}
with od.step("register four plots -> GeoIDs") as s:
    for f in FIELDS:
        name = f["properties"]["name"]
        GEO[name] = tr.register(f, TOKEN)
        print(f"  {name:22} {GEO[name]}")
    if not all(GEO.values()):
        raise RuntimeError("a registration returned no GeoID")
""")

md("""
## 3. Steps 4–5 for a plot that is a point (LOCAL — `ar2 f6a6a2f`)

Regulation (EU) 2023/1115 Art. 2(28) lets a plot of **at most four hectares**
be described by a single coordinate, and the SRS carries that (`TFC-F-09`,
`C-1`). The median plot in the cooperative survey we hold is 0.30 ha, so nearly
every Honduran coffee plot qualifies. The question the SRS leaves open is what
a *name* for a point is.

A field is named by its cover and two redraws of it are brought together by
IoU at registration. A point is now the same thing with a cover of one cell:
the **leaf cell** it lands in, so the fix keeps the precision it was surveyed
at, and two fixes of one tree are brought together by **distance** — within
10 m is the same plot, and the second submission is recorded as an alias of the
first. The area is a *declared* attribute, capped at the regulation's four
hectares.

Earlier today this was done by naming the point after its level-20 cell (~8 m)
on the reasoning that a fix cannot leave one. Measured over 20,000 fixes in the
coffee belt, that held a 1 m re-survey together 86.3% of the time and called two
plots 5 m apart one plot 40.0% of the time: a fix near a cell boundary crosses
it, and the grid cannot know it is near one. The cell below shows both answers
for the same tree. The hosted node has neither yet, so this runs from the
checkout and is marked LOCAL; the alias-writing half needs Postgres and is a
Phase 1 check.
""")

code("""
# A tree whose fix sits close to a level-20 boundary -- about one in seven does,
# and it is the case the withdrawn regime got wrong.
lat, lng = gg.a_tree_near_a_cell_edge(14.7500, -88.2500)
with od.step("point plot -> GeoID, resolved by distance", outcome=od.LOCAL) as s:
    here = gg.point_name(lat, lng)
    print(f"  the fix           {lat:.6f}, {lng:.6f}  (near a level-20 boundary)")
    print(f"  named by cell     {here.token}  (level {here.level}, one-cell cover)")
    print(f"  GeoID             {here.geo_id}")
    near = gg.jitter(lat, lng, metres=1.0)
    far = gg.jitter(lat, lng, metres=50.0)
    same, how = gg.resolves_to_one_plot(near, here)
    print(f"  4 fixes 1 m off   {same}/4 resolve onto this plot ({how})")
    print(f"                    the withdrawn L20 naming would have kept {gg.grid_would_have(near, here)}/4")
    print(f"  across the belt   {gg.belt_wide_rates()}")
    same_far, _ = gg.resolves_to_one_plot(far, here)
    print(f"  4 fixes 50 m off  {same_far}/4 resolve (a different plot, as it should be)")
    print(f"  distinct GeoIDs   {len({p.geo_id for p in near})} for the 4 near fixes: the name keeps the fix, "
          f"the resolver keeps the plot")
    for area in (0.3, 4.0, 4.5):
        ok, why = gg.declared_area(area)
        print(f"  declared {area:>3} ha  {'accepted' if ok else 'REFUSED'}: {why}")
    od.local(s, gg.point_regime_note())
""")

md("""
### 3b. The rest of the journey, for the same coordinate plot

A name is not enough. The SRS asks for a *verdict* on the plot and a filing the
EU registry will accept, and a plot declared by a coordinate has to reach both
by the same route a boundary does. Three steps below, and each was broken until
this evening:

- **What the registry says the plot is.** A screening node that does not know it
  is holding a coordinate has no way to know how much ground the coordinate
  stands for. `GeometryKind` and `AreaHa` are now on the wire at L0 as well as
  L1. The hosted node predates them, so the cell below asks it and reports what
  it actually said.
- **What the screen reads.** A point's cover is one S2 leaf cell, about a
  centimetre. Read as it stands, the screen returned the single 36 m JRC cell
  containing it, at `coverage_fraction` 1.0 and `scope: "field"` with no
  caveat — a clean bill of health for a plot whose surrounding ground may be
  cleared. It is now read over a disc of the **declared area** around the fix,
  labelled `declared_footprint`, with the declaration named in the caveat.
- **What gets filed.** The EU takes a Point geometry only with an `Area`
  property, and only up to four hectares. AR2's export emitted a Point with no
  `Area`, which the DDS schema rejects. It now emits the declared area, or
  refuses and says what to do.
""")

code("""
POINT_HA = 2.0   # a plot at the larger end of the survey, well inside the 4 ha ceiling

with od.step("a coordinate plot is a peer through screen and filing", outcome=od.LOCAL) as s:
    print("  what the registry says this plot is:")
    status, body = gg.l0_view(od.NODE_URL, GEO["compliant_coffee"], TOKEN)
    print(f"    hosted node (HTTP {status}): {gg.kind_on_the_wire(body)}")
    print("    after redeploy:  " + gg.kind_on_the_wire({"GeometryKind": "point", "AreaHa": POINT_HA}))

    print("  what the screen reads for it:")
    gg.show_footprint(gg.footprint_of(lat, lng, POINT_HA))

    print("  what gets filed for it:")
    filed = gg.point_filing(lat, lng, POINT_HA)
    print(f"    geometry {filed['geometry']} with Area {filed['area']} ha; "
          f"DDS rules broken: {filed['problems'] or 'none'}")
    refused = gg.point_filing(lat, lng, None)
    print(f"    with no declared area: refused -- {refused['refused'][:96]}...")

    if filed["problems"] or filed["geometry"] != "Point" or "refused" not in refused:
        raise RuntimeError("the point filing did not come out as a valid Point with an Area")
    od.local(s, "AR2 builds the filing from the checkout here; the two rules the EU applies to a "
                "Point are checked in this process, and in terrapipe-os by dds.validate")
""")

# ==========================================================================
# 2. What the lender sees, and consent
# ==========================================================================

md("""
## 4. What a lender sees with a login and no consent (LIVE)

The SRS moves the polygon and the farmer's personal data to Confianza and on to
every participating financial institution (`IF-04`, `IF-06`). The April design
with CIAT said the opposite: **lenders get Level 0**. Here is what Level 0 is —
asked of the node, not asserted.
""")

code("""
low = GEO["compliant_coffee"]
with od.step("lender's view of a plot without a grant (L0)") as s:
    status, body = gg.l0_view(od.NODE_URL, low, TOKEN)
    print(f"  HTTP {status}")
    lines = gg.describe_l0(body, FIELDS[0])
    for line in lines:
        print("  " + line)
    if status != 200 or not any("present in the answer: 0 of" in line for line in lines):
        raise RuntimeError(f"the node answered {status}, or a boundary vertex came back at L0")
""")

md("""
## 5. Step 6 — the farmer consents, to a purpose, for a time (LIVE)

A grant is an SD-JWT credential the farmer's account issues over a list holding
the plot, naming the grantee, the purpose and the expiry, with an ODRL policy
inside and a revocation bit in a public status list. It is what turns the L0
answer above into an L1 screen below — and it is what the farmer can withdraw
in §11.
""")

code("""
CONSENT = {}
with od.step("consent grants for the screen (Pancake)") as s:
    for name, geo_id in GEO.items():
        CONSENT[name] = od.consent_for([geo_id], TOKEN, purpose="green-guarantee screen", name=f"ggms {name}")
        c = CONSENT[name]
        print(f"  {name:22} {'granted' if c.credential else 'FAILED'}  jti={c.jti}  list={str(c.list_id)[:12]}…")
    if not all(c.credential for c in CONSENT.values()):
        raise RuntimeError("a grant was not issued")
""")

# ==========================================================================
# 3. The screen and the class
# ==========================================================================

md("""
## 6. Step 5b — the screen, with the grant (LIVE)

One call per plot to the hosted terrapipe-os node, presenting the grant. The
verdict is the regulation's question with a date in it — *was any of this
cleared after 31 December 2020* — read from the JRC year-of-first-deforestation
product, with the national forestry authority's 2018 and 2024 maps as a second
opinion, the national coffee map as the commodity check, and Hansen and ESA
WorldCover as context. Every reading carries its coverage and every absence its
reason.
""")

code("""
SCREEN = {}
with od.step("screen four plots at field scope") as s:
    for name, geo_id in GEO.items():
        status, screen = od.screen_with(geo_id, TOKEN, CONSENT[name].credential)
        SCREEN[name] = screen
        print(f"  {name:22} HTTP {status}  {screen.get('verdict','?'):26} scope={screen.get('scope')}  "
              f"cleared after 2020: {screen.get('deforested_fraction')}")
    if any(sc.get("scope") != "field" for sc in SCREEN.values()):
        raise RuntimeError("a screen came back below field scope with a grant presented")
""")

md("""
## 7. Steps 10–11 — the three-valued class, and *which evidence settled it* (LOCAL — `terrapipe-os 18a7f72`)

Whisp, the FAO tool the SRS names as the risk service, answers **low**,
**high** or **more information needed**. A lender's system built for that
vocabulary should be able to read ours, so the screen now speaks it — and does
the one thing Whisp cannot: it says *which layer* settled the class.

The order is the regulation's. Clearing after the cut-off is `high` at any
coverage. Then the `low` paths, each from a named national or public layer:
coffee on the plot in the **2020 national coffee map**; `cafetales` in the
**2018 national forest map** (established before the cut-off); clearing **at or
before the cut-off** in the JRC product; or **no tree cover to lose** in ESA
WorldCover. What none of those settles is `more_info_needed`, with the paths
tried listed so the field agent knows which piece of evidence would close it.

The hosted node does not have this yet: the readings above are LIVE and the
classification runs here over them. After the redeploy the node returns `risk`
itself and this step turns LIVE without a change to the notebook.
""")

code("""
RISK = {}
with od.step("risk class from the evidence", outcome=od.LOCAL) as s:
    rows = []
    for name, screen in SCREEN.items():
        RISK[name] = gg.classify(screen)
        rows.append((name, screen, RISK[name]))
    gg.show_classes(rows)
    where = {r["computed"] for r in RISK.values()}
    if where == {"by the node"}:
        s["outcome"] = od.LIVE
        s["detail"] = "the node returned the class itself"
    else:
        od.local(s, f"classifier terrapipe-os {gg.checkouts()['terrapipe-os']} over the node's evidence; "
                    f"rule set {next(iter(RISK.values()))['rule_set_version']}")
""")

md("""
Read the last column. `compliant_coffee` is clean **and** the national coffee
map puts coffee on it in 2020: `low`, settled by a Honduran source, not by the
absence of a signal. `legacy_clearing` was cleared in the 1990s: `low`, because
the regulation asks about clearing *after* 2020 and the JRC product says when
this happened. `post_cutoff_clearing` is `high`, and the year is in the reason.

The SRS's `CC-F-09` asks that the decision rule be versioned. It is: every
class above was reached under `rule_set_version` shown in the ledger, and a
lender's file that records the class without it is a memory, not evidence.
""")

# ==========================================================================
# 4. The guarantee
# ==========================================================================

md("""
## 8. Step 12 — the guarantee is *pre-approved*, as a credential (LOCAL — `pancake 77e974f`)

In the SRS the guarantee is a row in Confianza's database that the lender
queries. Here it is the same kind of object as the consent above: an SD-JWT
credential with its own type, signed by the guarantor, naming the lender, the
request, the amount, the coverage ratio, the **risk class it was decided on**,
the **rule set that class was reached under**, and the evidence records. The
lender verifies it without asking anyone; the guarantor revokes it publicly.

Pancake's own application runs in this kernel for these steps, on tonight's
code, with a throwaway issuer key and the **hosted hub** as its identity
provider — the account issuing below is the same real account that registered
the plots above. It is marked LOCAL because it is not the hosted Pancake.
""")

code("""
PK = gg.LocalPancake(od.HUB_URL, od.NODE_URL)
LENDER = "hub-acct-banco-demo"
GUARANTEE = {}
with od.step("guarantee PRE_APPROVED as a credential", outcome=od.LOCAL) as s:
    status, g = PK.post("/guarantees/issue", TOKEN,
        subject=low, subject_kind="geoid", beneficiary_account=LENDER,
        request_ref="CR-2026-0001", amount=1500.0, currency="HNL", coverage_ratio=0.8,
        risk_class=RISK["compliant_coffee"]["risk_class"],
        rule_set_version=RISK["compliant_coffee"]["rule_set_version"],
        evidence=[f"screen:{low[:12]}"], state="PRE_APPROVED", validity_days=365)
    print(f"  HTTP {status}")
    if status != 201:
        raise RuntimeError(g)
    GUARANTEE["pre"] = g
    gg.show_guarantee(g["credential"])
    od.local(s, PK.where)
""")

md("""
## 9. The lender checks it — and a consent verifier refuses it (LOCAL)

Two verifications. The guarantee verifier accepts the credential: signature,
expiry, type, revocation bit. The **grant** verifier — the one the node uses
for field access — refuses it, because the type is wrong. A guarantee cannot be
waved at a node to read a polygon, and a consent grant cannot be shown to a
lender as a promise. Same machinery, two vocabularies, no overlap.
""")

code("""
with od.step("lender verifies the guarantee; grant verifier refuses it", outcome=od.LOCAL) as s:
    ok = PK.verify(GUARANTEE["pre"]["credential"])
    as_grant = PK.verify_as_grant(GUARANTEE["pre"]["credential"])
    print(f"  as a guarantee  valid={ok['valid']}  class={ok.get('claims',{}).get('risk',{}).get('risk_class')}")
    print(f"  as a grant      valid={as_grant['valid']}  ({as_grant.get('reason')})")
    if not ok["valid"] or as_grant["valid"]:
        raise RuntimeError("the two verifiers did not disagree the way they must")
    od.local(s, PK.where)
""")

md("""
## 10. Step 27 — *issued*, superseding the pre-approval (LOCAL)

The lender has accepted; the loan is disbursed (steps 13–25: the marketplace,
the App, the bank — not ours). The guarantor issues the guarantee proper: a new
credential that names the one it supersedes, and the old one is revoked in the
same transaction. At any moment exactly one active guarantee stands for a
request, and the old one fails verification the instant the new one exists.
""")

code("""
with od.step("guarantee ISSUED supersedes PRE_APPROVED", outcome=od.LOCAL) as s:
    status, g = PK.post("/guarantees/issue", TOKEN,
        subject=low, subject_kind="geoid", beneficiary_account=LENDER,
        request_ref="CR-2026-0001", amount=1500.0, currency="HNL", coverage_ratio=0.8,
        risk_class=RISK["compliant_coffee"]["risk_class"],
        rule_set_version=RISK["compliant_coffee"]["rule_set_version"],
        evidence=[f"screen:{low[:12]}"], state="ISSUED", supersedes_jti=GUARANTEE["pre"]["jti"])
    if status != 201:
        raise RuntimeError(g)
    GUARANTEE["issued"] = g
    gg.show_guarantee(g["credential"])
    print()
    print(f"  new one verifies:  {PK.verify(g['credential'])['valid']}")
    old = PK.verify(GUARANTEE["pre"]["credential"])
    print(f"  old one verifies:  {old['valid']}  ({old.get('reason')})")
    _, mine = PK.get("/guarantees/issued", TOKEN)
    active = [x["jti"] for x in mine if x["status"] == "active"]
    print(f"  active guarantees for this issuer: {len(active)}")
    if old["valid"] or len(active) != 1:
        raise RuntimeError("more than one guarantee stands for the request")
    od.local(s, PK.where)
""")

md("""
## 11. Step 26 — cancelled, with a reason, publicly (LOCAL)

The loan is repaid, or the farmer defaults, or the plot turns out not to be
what it was said to be. The guarantor revokes. The bit flips in the public
status list, the reason is recorded, and the lender's next verification fails.
Nobody has to be told; anybody can check.
""")

code("""
with od.step("guarantee revoked with a reason", outcome=od.LOCAL) as s:
    status, r = PK.post("/guarantees/revoke", TOKEN, jti=GUARANTEE["issued"]["jti"], reason="loan repaid in full")
    print(f"  HTTP {status}  status={r.get('status')}  reason={r.get('revoked_reason')}")
    after = PK.verify(GUARANTEE["issued"]["credential"])
    print(f"  lender verifies now: {after['valid']}  ({after.get('reason')})")
    if after["valid"]:
        raise RuntimeError("a revoked guarantee still verifies")
    od.local(s, PK.where)
""")

md("""
## 12. The MEAL — every step, hash-chained, for the plot (LOCAL)

The SRS asks for an audit trail (`CC-F-11`, `D-2`). Here it is the same
MEAL (Multi-User Engagement Asynchronous Ledger, Pancake's append-only
audit ledger, `docs/MEAL.md`) the consent grants write to, keyed by the plot's
GeoID: pre-approval, issue, the supersession's revocation, the final
revocation, each a signed packet chained to the one before. The chain
verifies or it does not.
""")

code("""
with od.step("MEAL for the plot verifies", outcome=od.LOCAL) as s:
    status, report = PK.get(f"/audit/{low}/report", TOKEN)
    print(f"  HTTP {status}  all chains valid: {report.get('all_chains_valid')}")
    for kind, n in sorted((report.get("events_by_type") or {}).items()):
        print(f"    {kind:26} {n}")
    if not report.get("all_chains_valid"):
        raise RuntimeError("the chain did not verify")
    od.local(s, PK.where)
""")

# ==========================================================================
# 5. The refusal, and the export
# ==========================================================================

md("""
## 13. Step 11 — a refusal the machine can read (LOCAL)

`post_cutoff_clearing` came out `high`. The SRS asks (`CC-F-10`, step 11) that
a rejection carry a machine-readable reason. The class, the sentence, the
layer, the year and the rule-set version are all in the screen; a guarantee is
simply not issued — and if a guarantor's policy issued one anyway, the credential
would say `high` on its face, for the lender to see.
""")

code("""
with od.step("the high case: refusal reasons are machine-readable", outcome=od.LOCAL) as s:
    r = RISK["post_cutoff_clearing"]
    print(json.dumps({k: r[k] for k in ("risk_class", "because", "resolved_by", "paths_tried", "rule_set_version")}, indent=2))
    if r["risk_class"] != "high":
        raise RuntimeError(f"expected high, got {r['risk_class']}")
    od.local(s, "class from the LIVE screen of a field the JRC records as cleared in 2021-22")
""")

md("""
## 14. Step 28, which the SRS does not have — the DDS-ready export (LIVE)

The reason any of this matters: on 30 December 2026 the buyer in Europe files a
Due Diligence Statement. The node turns screened plots into the GeoJSON the
EU's system wants — geometry, GeoID and the screen *alongside* it, never
smuggled into a named field. The plots with a grant come back screened; a plot
without one comes back with geometry and no finding, rather than a verdict
nobody consented to.
""")

code("""
with od.step("DDS-ready export of the screened plots") as s:
    # The export wants each feature to name its GeoID -- the boundary that was
    # registered is the boundary that is screened -- and the grant per GeoID.
    plots = [{**f, "properties": {**f["properties"], "GeoID": GEO[f["properties"]["name"]]}} for f in FIELDS]
    grants = {GEO[n]: CONSENT[n].credential for n in GEO}
    out = od.dds_export({"type": "FeatureCollection", "features": plots}, country="HN", token=TOKEN, grants=grants)
    feats = (out.get("collection") or {}).get("features") or []
    print(f"  features: {len(feats)}  screened: {out.get('screened')}  refused: {len(out.get('refused') or [])}  "
          f"problems: {len(out.get('problems') or [])}  chunks: {out.get('chunks')}")
    for f in feats:
        p = f.get("properties") or {}
        d = p.get("deforestation") or {}
        print(f"    {str(p.get('ProductionPlace') or '')[:22]:22} verdict={d.get('verdict')}  "
              f"coverage={d.get('coverage_fraction')}  risk_class={d.get('risk_class', '(after redeploy)')}")
    if out.get("screened") != len(FIELDS):
        raise RuntimeError(f"{out.get('screened')} of {len(FIELDS)} plots screened: {out.get('refused')}")
""")

# ==========================================================================
# 6. Withdrawing consent
# ==========================================================================

md("""
## 15. The farmer withdraws consent (LIVE)

The last thing a data space built on file transfer cannot do. The farmer
revokes the grant. Presenting the revoked credential is now **refused** — the
node checks the public status list, not its memory of having seen the grant —
and the same screen without a grant answers at **neighbourhood** scope, the
L10 cell around the plot, about 80 km², because the node no longer has consent
to look at the field. Nothing was deleted from anyone's database, because
nothing was ever copied into one.
""")

code("""
with od.step("consent revoked: revoked grant refused; no grant -> neighbourhood") as s:
    ok, why = od.revoke(CONSENT["compliant_coffee"].jti, TOKEN)
    print(f"  revoke: {why}")
    status, refused = od.screen_with(low, TOKEN, CONSENT["compliant_coffee"].credential)
    print(f"  screen presenting the revoked grant:  HTTP {status}  {str(refused.get('detail') or refused.get('reason') or '')[:80]}")
    status2, bare = od.screen_with(low, TOKEN)
    print(f"  screen with no grant:                 HTTP {status2}  scope={bare.get('scope')}  cover={bare.get('cover_tier')}")
    if not ok or status == 200 or bare.get("scope") != "neighbourhood":
        raise RuntimeError("the revoked grant still bought a screen, or the bare screen did not degrade")
""")

# ==========================================================================
# 7. What this run demonstrated
# ==========================================================================

md("""
## 16. The 27 steps, and what this run actually demonstrated

| SRS steps | Content | Here |
|---|---|---|
| 1–3b | Farmer applies; identification, carnet, photo | NOT-OURS (farmer identity is Layer 3; the *plot* de-duplicates by construction, §2) |
| 4 | App captures the plot | NOT-OURS (the App); the shape it must produce is defined: polygon, or point + declared area ≤ 4 ha (§3) |
| 5 | Upload → register → `plotId` | §2 LIVE (polygon), §3 LOCAL (point: name pure, resolver needs the node's DB) |
| 5b | Risk result | §6 LIVE verdict + evidence; §7 class (LOCAL until the node is redeployed) |
| 6–8 | Publish and discover through the data space | not yet: a DCAT/DSP façade over the node is the next phase; consent grants are the exchange today (§5) |
| 9 | Validate the evidence | §9 LIVE-shaped: re-verification of a signed record |
| 10 | EUDR compliant? | §7 — the evidence and the rule set it was produced under are ours; the *decision* is Confianza's |
| 11 | Rejection reason, machine-readable | §13 |
| 12 | Pre-approved guarantee | §8 |
| 13–19b, 21–25 | Marketplace, App, disbursement | NOT-OURS |
| 20 | Acceptance through the data space | next phase, with 6–8 |
| 26 | Cancel | §11 |
| 27 | Issue | §10 |
| — | DDS-ready export; consent withdrawn and refused | §14, §15 LIVE |

The ledger below is generated from what ran.
""")

code("""
print(od.LEDGER.checklist())
print()
print("LOCAL steps ran on:", gg.checkouts())
""")


# ==========================================================================
# writer
# ==========================================================================


def build() -> dict:
    cells = []
    for kind, body in CELLS:
        cell = {"cell_type": kind, "metadata": {}, "source": body.splitlines(keepends=True)}
        if kind == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="execute after writing")
    args = parser.parse_args()
    NOTEBOOK.write_text(json.dumps(build(), indent=1) + "\n")
    print(f"wrote {NOTEBOOK} ({len(CELLS)} cells)")
    if args.run:
        import nbformat  # noqa: PLC0415
        from nbclient import NotebookClient  # noqa: PLC0415

        notebook = nbformat.read(NOTEBOOK, as_version=4)
        client = NotebookClient(notebook, timeout=900, kernel_name="python3", allow_errors=True,
                                resources={"metadata": {"path": str(HERE)}})
        client.execute()
        nbformat.write(notebook, NOTEBOOK)
        print(f"executed and wrote outputs to {NOTEBOOK}")


if __name__ == "__main__":
    main()
