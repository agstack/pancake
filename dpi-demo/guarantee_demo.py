"""Support for green_guarantee_demo.ipynb: the pieces the other three do not have.

Three things are new here and each is labelled for what it is:

* **The point regime** comes from the AR2 checkout on this machine (``ar2
  3aa3514``), because the hosted node still names a point by its leaf cell. It
  is a pure function of a coordinate; nothing is registered.
* **The risk class** is computed by ``terrapipe_os.screen._classify`` from the
  checkout here (``terrapipe-os 18a7f72``) over the *hosted node's* evidence.
  The readings are LIVE; only the last step -- reading three named layers off
  the evidence and saying low / high / more information needed -- runs in this
  process, because the node has not been redeployed with it yet. That step is
  marked LOCAL and says so.
* **The Green Guarantee** is issued by Pancake's own application running in
  this process (``pancake 77e974f``) with a throwaway issuer key, an in-memory
  database, and the *hosted hub's* JWKS for authentication -- so the caller is
  the same real hub account the LIVE steps use. Marked LOCAL.

Everything else -- registration, consent, the screen, the DDS export, revocation
of consent -- goes to the hosted services through ``openscience_demo`` and is
LIVE or it is nothing.
"""
from __future__ import annotations

import base64
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# checkouts on this machine
# --------------------------------------------------------------------------

AGSTACK_ROOT = Path(os.environ.get("AGSTACK_ROOT", HERE.parents[1])).expanduser()
AR2_DIR = Path(os.environ.get("AR2_DIR", AGSTACK_ROOT / "ar2")).expanduser()
TERRAPIPE_OS_DIR = Path(os.environ.get("TERRAPIPE_OS_DIR", AGSTACK_ROOT / "terrapipe-os")).expanduser()


def _git_head(repo: Path) -> str:
    try:
        head = (repo / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            return (repo / ".git" / head[5:]).read_text().strip()[:7]
        return head[:7]
    except OSError:
        return "unknown"


def checkouts() -> dict[str, str]:
    """Which commit each LOCAL piece is running, so the ledger can say."""
    return {
        "ar2": _git_head(AR2_DIR),
        "terrapipe-os": _git_head(TERRAPIPE_OS_DIR),
        "pancake": _git_head(HERE.parent),
    }


# --------------------------------------------------------------------------
# the point regime (ar2 3aa3514)
# --------------------------------------------------------------------------

METRE_DEG = 1 / 111_320


def _geoid_v2():
    if str(AR2_DIR) not in sys.path:
        sys.path.insert(0, str(AR2_DIR))
    from app import geoid_v2  # noqa: PLC0415

    return geoid_v2


@dataclass
class PointName:
    lat: float
    lng: float
    token: str
    level: int
    geo_id: str


def point_name(lat: float, lng: float) -> PointName:
    g = _geoid_v2()
    tokens, geo_id = g.point_geo_id_with_tokens(lat, lng)
    return PointName(lat, lng, tokens[0], g.token_level(tokens[0]), geo_id)


def a_tree(lat: float, lng: float) -> tuple[float, float]:
    """The centre of the level-20 cell around a coordinate: a tree to fix a GPS on.

    The jitter demonstration puts the fixes around a point well inside a cell,
    so what it shows is the regime and not whether the chosen coordinate
    happened to sit a metre from a cell edge.
    """
    import s2geometry as s2g  # noqa: PLC0415

    g = _geoid_v2()
    cell = s2g.S2CellId(s2g.S2LatLng.FromDegrees(lat, lng)).parent(g.POINT_LEVEL)
    ll = cell.ToLatLng()
    return ll.lat().degrees(), ll.lng().degrees()


def jitter(lat: float, lng: float, metres: float) -> list[PointName]:
    """The same tree, fixed four times with a GPS that is off by ``metres``."""
    out = []
    for dlat, dlng in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        out.append(point_name(lat + dlat * metres * METRE_DEG,
                              lng + dlng * metres * METRE_DEG / math.cos(math.radians(lat))))
    return out


def declared_area(area_ha: float | None) -> tuple[bool, str]:
    g = _geoid_v2()
    try:
        return True, f"{g.point_area_declared(area_ha):g} ha accepted"
    except g.GeometryUnusable as exc:
        return False, str(exc)


def point_regime_note() -> str:
    g = _geoid_v2()
    return (f"points are named by their level-{g.POINT_LEVEL} cell; a point may stand for at most "
            f"{g.POINT_MAX_AREA_HA:g} ha (ar2 {_git_head(AR2_DIR)})")


# --------------------------------------------------------------------------
# the risk class (terrapipe-os 18a7f72), over the hosted node's evidence
# --------------------------------------------------------------------------


def _evidence(e: dict[str, Any] | None):
    """Rebuild what ``_classify`` reads from a serialised Evidence: layer_id, reading.value, absent."""
    if e is None:
        return SimpleNamespace(layer_id="?", reading=None, absent="not_in_library", note=None)
    reading = e.get("reading")
    return SimpleNamespace(
        layer_id=e.get("layer_id"),
        reading=SimpleNamespace(value=reading["value"]) if reading else None,
        absent=e.get("absent"),
        note=e.get("note"),
    )


_CLASSIFIER: dict[str, Any] | None = None


def classifier() -> dict[str, Any]:
    """The classification rules from the checkout's ``screen.py``, loaded by source.

    Not imported. The notebook's setup makes ``terrapipe_os`` unimportable on
    purpose -- every *reading* must come from the hosted node -- and this keeps
    to that: the two pure functions and the constants they use are lifted out of
    the file with ``ast`` and executed on their own. Nothing here can open a
    store. What it can do is say what tonight's rule makes of the node's
    evidence, and name the commit it came from.
    """
    global _CLASSIFIER  # noqa: PLW0603
    if _CLASSIFIER is not None:
        return _CLASSIFIER
    import ast  # noqa: PLC0415
    from typing import Literal  # noqa: PLC0415

    source = (TERRAPIPE_OS_DIR / "src" / "terrapipe_os" / "screen.py").read_text()
    tree = ast.parse(source)
    wanted_funcs = {"_class_share", "_classify"}
    keep: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted_funcs:
            keep.append(node)
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
            names = [t.id for t in node.targets]  # type: ignore[union-attr]
            if all(n.isupper() or n in ("Verdict", "RiskClass") for n in names):
                keep.append(node)
    module = ast.Module(body=keep, type_ignores=[])
    ns: dict[str, Any] = {"Any": Any, "Literal": Literal, "__name__": "terrapipe_os_screen_rules"}
    exec(compile(module, str(TERRAPIPE_OS_DIR / "src/terrapipe_os/screen.py"), "exec"), ns)  # noqa: S102
    missing = wanted_funcs - set(ns)
    if missing:
        raise RuntimeError(f"screen.py at {checkouts()['terrapipe-os']} has no {missing}")
    _CLASSIFIER = ns
    return ns


def classify(screen: dict[str, Any]) -> dict[str, Any]:
    """Tonight's three-valued class from a LIVE screen.

    If the node already answered with ``risk`` (after it is redeployed), that is
    returned untouched and the caller marks the step LIVE. Otherwise the rules
    from the local checkout run over the node's evidence.
    """
    if screen.get("risk"):
        return {**screen["risk"], "rule_set_version": (screen.get("rule_set") or {}).get("version"),
                "computed": "by the node"}

    sc = classifier()
    by_id = {}
    for e in [screen.get("primary"), *screen.get("second_opinion", {}).get("evidence", []),
              *screen.get("commodity", {}).get("evidence", []), *screen.get("context", [])]:
        if e:
            by_id[e["layer_id"]] = e
    earlier = sc["SECOND_OPINION_LAYERS"][0]
    cafe = sc["COMMODITY_LAYERS"][0]
    inconclusive = next((c for c in screen.get("caveats", []) if "No primary evidence" in c
                         or "needed to call it clear" in c), None)
    risk = sc["_classify"](
        verdict=screen["verdict"],
        cutoff_year=screen["cutoff_year"],
        deforested_fraction=screen.get("deforested_fraction"),
        deforested_by_year={int(k): v for k, v in (screen.get("deforested_by_year") or {}).items()},
        primary=_evidence(by_id.get(sc["PRIMARY_LAYER"]) or screen.get("primary")),
        cafe=_evidence(by_id.get(cafe)),
        earlier_epoch=_evidence(by_id.get(earlier)),
        land_cover=_evidence(by_id.get("esa_worldcover")),
        inconclusive_because=inconclusive,
    )
    return {**risk, "rule_set_version": sc["RULE_SET_VERSION"], "computed": "in this kernel"}


def show_classes(rows: list[tuple[str, dict[str, Any], dict[str, Any]]]) -> None:
    """One line per field: what the node found, what class that is, and which layer settled it."""
    width = max(len(name) for name, _, _ in rows)
    print(f"{'field'.ljust(width)}  {'verdict (LIVE)':28} {'class':17} settled by")
    for name, screen, risk in rows:
        by = ", ".join(risk.get("resolved_by") or []) or "-- nothing; " + " > ".join(risk.get("paths_tried", []))
        print(f"{name.ljust(width)}  {screen.get('verdict', '?'):28} {risk['risk_class']:17} {by}")
    print()
    for name, _, risk in rows:
        print(f"{name}: {risk['because']}")


# --------------------------------------------------------------------------
# Pancake in this process (pancake 77e974f), authenticated by the hosted hub
# --------------------------------------------------------------------------


class LocalPancake:
    """Pancake's grants application, in-process, with the hosted hub as its identity provider.

    A throwaway Ed25519 issuer key and an in-memory SQLite. The point is not
    the deployment -- it is that the guarantee endpoints exist, sign, verify,
    supersede, revoke and write the MEAL, on tonight's code, for the same hub
    account the LIVE steps used. Marked LOCAL wherever it appears.
    """

    def __init__(self, hub_url: str, ar2_node_url: str):
        from fastapi.testclient import TestClient  # noqa: PLC0415

        from pancake_services.common.config import Settings  # noqa: PLC0415
        from pancake_services.grants.app import create_app  # noqa: PLC0415
        from pancake_services.grants.issuer import IssuerIdentity, generate_keypair_pem  # noqa: PLC0415

        priv, pub = generate_keypair_pem()
        self.issuer = IssuerIdentity(issuer_id="did:web:pancake.local-demo", kid="local-demo-1",
                                     private_key_pem=priv, public_key_pem=pub)
        settings = Settings(
            database_url="sqlite:///:memory:",
            hub_jwks_url=f"{hub_url.rstrip('/')}/.well-known/jwks.json",
            hub_url="",  # no hub revocation registry for the local instance
            ar2_node_url=ar2_node_url,
            status_list_uri="http://pancake.local-demo/grants/status-list",
        )
        self.app = create_app(settings=settings, issuer=self.issuer)
        self.client = TestClient(self.app)
        self.where = "pancake in this kernel, hub JWKS from " + hub_url

    def post(self, path: str, token: str, **json_body) -> tuple[int, dict[str, Any]]:
        r = self.client.post(path, json=json_body, headers={"Authorization": f"Bearer {token}"})
        return r.status_code, (r.json() if r.content else {})

    def get(self, path: str, token: str) -> tuple[int, Any]:
        r = self.client.get(path, headers={"Authorization": f"Bearer {token}"})
        return r.status_code, (r.json() if r.content else {})

    def verify(self, credential: str) -> dict[str, Any]:
        return self.client.post("/guarantees/verify", json={"credential": credential}).json()

    def verify_as_grant(self, credential: str) -> dict[str, Any]:
        return self.client.post("/grants/verify", json={"credential": credential}).json()


def claims_of(credential: str) -> dict[str, Any]:
    """The signed payload, decoded without verification -- for display only."""
    token = credential.split("~")[0]
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def show_guarantee(credential: str) -> None:
    c = claims_of(credential)
    g, r = c["guarantee"], c["risk"]
    print(f"  vct         {c['vct']}")
    print(f"  sub         {c['sub'][:16]}… ({c['subject_kind']})")
    print(f"  beneficiary {c['beneficiary']}")
    print(f"  guarantee   {g['state']}  {g['amount']:,.0f} {g['currency']} at {g['coverage_ratio']:.0%} cover, "
          f"request {g['request_ref']}" + (f", supersedes {g['supersedes'][:10]}…" if g.get('supersedes') else ""))
    print(f"  risk        {r['risk_class']} under {r['rule_set_version']}; evidence {r['evidence']}")
    print(f"  odrl        {c['odrl']['permission'][0]['action']} for "
          f"{c['odrl']['permission'][0]['constraint'][1]['rightOperand']}; "
          f"prohibited: {c['odrl']['prohibition'][0]['action']}")
    print(f"  status      list idx {c['status']['status_list']['idx']}; expires "
          f"{__import__('datetime').datetime.utcfromtimestamp(c['exp']).date()}")
    print(f"  jti         {c['jti']}")


# --------------------------------------------------------------------------
# what a lender sees
# --------------------------------------------------------------------------


def l0_view(node_url: str, geo_id: str, token: str) -> tuple[int, dict[str, Any]]:
    """The node's answer about a field to a caller with a login and no grant."""
    try:
        r = requests.get(f"{node_url}/fetch-field/{geo_id}", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    except requests.RequestException as exc:
        return 0, {"reason": exc.__class__.__name__}
    return r.status_code, (r.json() if r.content else {})


def describe_l0(body: dict[str, Any], field: dict[str, Any]) -> list[str]:
    """Name what is and is not in an L0 answer, from the answer rather than from memory.

    The answer carries a polygon -- the S2 cell the registry masks the field to,
    tens of square kilometres -- and a reader who sees "Polygon" in it may take
    that for the boundary. So the check is the one that matters: does any vertex
    of the field the notebook registered appear in what came back.
    """
    import openscience_demo as od  # noqa: PLC0415

    text = json.dumps(body)
    level = body.get("MaskingLevel") or body.get("masking_level") or "not stated"
    cell = (body.get("Geo Data") or {}).get("cell_token")
    out = [f"masking level in the answer: {level}"]
    if cell:
        out.append(f"geometry in the answer: S2 cell {cell} (level {od.MASKED_LEVEL}), "
                   f"about {od._cell_area_km2(cell):,.0f} km² -- the registry's mask, not the boundary")
    ring = field["geometry"]["coordinates"][0]
    leaked = [pt for pt in ring if f"{pt[0]:.6f}".rstrip("0") in text and f"{pt[1]:.6f}".rstrip("0") in text]
    out.append(f"vertices of the registered boundary present in the answer: {len(leaked)} of {len(ring)}")
    out.append("keys: " + ", ".join(sorted(body.keys())))
    return out
