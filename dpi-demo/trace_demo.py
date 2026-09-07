"""Support for the traceability notebook: a lot, and who may ask about it.

The third of three. The first is about what makes a field's name, the second
about what public data can say for that name; this one is about the graph built
on top of it, and about the fact that walking the graph in one direction is a
different permission question from walking it in the other.

Shares its honesty machinery with the open-science notebook -- the ledger, the
badges, the maps -- so that a step here means exactly what the same step means
there. What is added is the chain and the two gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import requests

from openscience_demo import (  # noqa: F401 - re-exported for the notebook
    EMPTY,
    FAILED,
    LEDGER,
    LIVE,
    LOCAL,
    NODE_URL,
    PANCAKE_URL,
    SKIPPED,
    Consent,
    ACCENT,
    ACCENT_TINT,
    OUTLINE,
    brief,
    demo_fields,
    empty,
    have_folium,
    hub_token,
    local,
    post,
    revoke,
    skip,
    step,
)

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NOT_FOUND = 404
HTTP_FORBIDDEN = 403
HTTP_UNAUTHORIZED = 401

CHILD_LIST = "L:"
"""How a member is marked as a child lot rather than a field.

Without the prefix AR2 records a list_id as though it were a GeoID: the edge
comes back ``kind: geoid``, ``input_list_ids`` stays empty, and traceback stops
at the first level however large ``max_depth`` is. The chain looks like it was
built and is one hop deep. Found by reading
``ar2/app/tests/test_fsma204_traceability.py``, which is where the multi-level
shape is exercised; it is not in the OpenAPI schema, where ``members`` is
documented only as a list of strings.
"""


# ==========================================================================
# The chain
# ==========================================================================


@dataclass
class Lot:
    """One node of the chain: a pooling or transformation event."""

    list_id: str
    label: str
    event_type: str
    fields: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)


@dataclass
class Chain:
    """Four fields, two mill lots, one container -- and one field in both lots.

    The shape is from the permissions deck, slide 7: *four fields, two shred
    lots, cases, shelf. Field 3 feeds both lots -- normal practice, and the
    reason recalls are hard.* One field in two lots is what makes trace-forward
    a different question from reading a list, and a chain that lacked it would
    make the easy case look like the whole problem.
    """

    fields: dict[str, str]
    lots: dict[str, Lot]
    container: Lot
    shared_field: str
    consent: Consent | None = None

    @property
    def name_of(self) -> dict[str, str]:
        return {geo_id: name for name, geo_id in self.fields.items()}


def pool(members: list[str], event_type: str, token: str,
         location: str | None = None) -> tuple[str, str]:
    """Register a lot at AR2 directly. Returns (list_id, why)."""
    body: dict[str, Any] = {"members": members, "event_type": event_type}
    if location:
        body["location_geo_id"] = location
    try:
        response = requests.post(
            f"{NODE_URL}/list-artifact",
            headers={"Authorization": f"Bearer {token}"},
            json=body, timeout=60,
        )
    except requests.RequestException as exc:
        return "", f"AR2 could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return "", f"AR2 refused the lot: HTTP {response.status_code} {response.text[:120]}"
    list_id = (response.json() or {}).get("list_id", "")
    return list_id, f"registered as {list_id[:16]}..."


def pool_through_pancake(members: list[str], name: str, token: str) -> tuple[str, str]:
    """The same registration, made through Pancake so a grant can be issued on it.

    A grant is issued against a Pancake field list, and traceback needs a grant
    scoped to the list being walked. A lot registered straight at AR2 therefore
    cannot be traced by its own creator: there is nothing to issue the grant
    against. Pancake passes the members through unchanged, prefix and all, and
    because a list_id is derived from its members the two routes produce the
    same identifier -- so this is the same lot, not a copy of it.
    """
    try:
        response = post(f"{PANCAKE_URL}/fieldlists", token=token,
                        json={"name": name, "geoids": members})
    except requests.RequestException as exc:
        return "", f"Pancake could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return "", f"Pancake refused the list: HTTP {response.status_code} {response.text[:120]}"
    list_id = (response.json() or {}).get("list_id", "")
    return list_id, f"registered as {list_id[:16]}..."


def build_chain(geo_ids: dict[str, str], token: str) -> tuple[Chain | None, str]:
    """Four fields into two lots into a container, with one field in both."""
    names = list(geo_ids)
    if len(names) < 4 or not all(geo_ids.values()):  # noqa: PLR2004
        return None, "the chain needs four registered fields"

    shared = names[1]
    lot_a_members = [geo_ids[names[0]], geo_ids[shared]]
    lot_b_members = [geo_ids[shared], geo_ids[names[2]], geo_ids[names[3]]]

    lot_a, why_a = pool_through_pancake(lot_a_members, "mill lot A -- morning delivery", token)
    lot_b, why_b = pool_through_pancake(lot_b_members, "mill lot B -- afternoon delivery", token)
    if not lot_a or not lot_b:
        return None, f"a mill lot could not be registered: {why_a or why_b}"

    container, why_c = pool_through_pancake(
        [f"{CHILD_LIST}{lot_a}", f"{CHILD_LIST}{lot_b}"], "container HNCF-2026-09", token)
    if not container:
        return None, f"the container could not be registered: {why_c}"

    return Chain(
        fields=geo_ids,
        lots={
            "mill lot A": Lot(lot_a, "mill lot A", "harvest_pooling", lot_a_members),
            "mill lot B": Lot(lot_b, "mill lot B", "harvest_pooling", lot_b_members),
        },
        container=Lot(container, "container HNCF-2026-09", "export_container",
                      inputs=[lot_a, lot_b]),
        shared_field=shared,
    ), f"container {container[:16]}..., two lots, four fields"


def show_chain(chain: Chain) -> None:
    """The chain as it was built, and which field is in two places."""
    print(f"  container   {chain.container.list_id[:20]}...  {chain.container.label}")
    for label, lot in chain.lots.items():
        print(f"    {label:12} {lot.list_id[:20]}...  {len(lot.fields)} fields")
        for geo_id in lot.fields:
            name = chain.name_of.get(geo_id, geo_id[:12])
            mark = "   <- in both lots" if name == chain.shared_field else ""
            print(f"        {name:22} {geo_id[:16]}...{mark}")
    print()
    print(f"  {chain.shared_field} is in two lots. That is ordinary practice -- a")
    print("  morning and an afternoon delivery from the same farm -- and it is why a")
    print("  recall cannot be answered by reading one list.")


def grant_on(list_id: str, token: str, purpose: str) -> Consent:
    """A grant scoped to one lot, which is what traceback checks for."""
    issued = post(f"{PANCAKE_URL}/grants/issue", token=token, json={
        "list_id": list_id, "grantee_account": "self", "purpose": purpose,
        "validity_days": 30, "masking_level": "L1",
    })
    if not issued.ok:
        return Consent(None, list_id, None,
                       f"the grant was refused: HTTP {issued.status_code} {issued.text[:120]}")
    body = issued.json() or {}
    return Consent(body.get("credential"), list_id, _jti(body.get("credential")),
                   f"granted over {list_id[:12]}... for '{purpose}'")


def _jti(credential: str | None) -> str | None:
    """The credential's own id, which is what revocation names."""
    if not credential:
        return None
    import base64  # noqa: PLC0415

    try:
        payload = credential.split("~")[0].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        return claims.get("jti")
    except (IndexError, ValueError, TypeError):
        return None


# ==========================================================================
# Down the graph: this container is on the dock, whose farms is it from
# ==========================================================================


def walk_down(list_id: str, token: str, grant: str | None,
              max_depth: int = 5) -> tuple[dict[str, Any], str]:
    """Trace back from a lot to the fields under it, through any child lots."""
    headers = {"Authorization": f"Bearer {token}"}
    if grant:
        headers["X-Grant-Token"] = grant
    try:
        response = requests.get(f"{NODE_URL}/list-artifact/{list_id}/traceback",
                                params={"max_depth": max_depth}, headers=headers, timeout=60)
    except requests.RequestException as exc:
        return {}, f"AR2 could not be reached: {exc.__class__.__name__}"
    if response.status_code == HTTP_NOT_FOUND:
        return {}, ("AR2 answered 404. The list exists; the answer is 404 rather than 403 "
                    "so that a stranger cannot confirm it does")
    if not response.ok:
        return {}, f"AR2 answered HTTP {response.status_code}: {response.text[:120]}"
    body = response.json() or {}
    return body, f"{len(body.get('hops', []))} hop(s) down from {list_id[:12]}..."


def show_walk_down(walked: dict[str, Any], chain: Chain) -> None:
    """The graph as the node returned it, deepest hop last."""
    hops = sorted(walked.get("hops", []), key=lambda hop: hop["depth"])
    for hop in hops:
        indent = "  " + "    " * hop["depth"]
        print(f"{indent}depth {hop['depth']}  {hop['list_id'][:16]}...  {hop.get('event_type')}")
        for geo_id in hop.get("geoids") or []:
            name = chain.name_of.get(geo_id, "a field not in this demo")
            mark = "   <- also in the other lot" if name == chain.shared_field else ""
            print(f"{indent}    {name:24} {geo_id[:16]}...{mark}")
        for child in hop.get("input_list_ids") or []:
            print(f"{indent}    made from lot {child[:16]}...")

    reached = {geo for hop in hops for geo in (hop.get("geoids") or [])}
    print()
    print(f"  one grant, {len(hops)} hops, {len(reached)} distinct fields reached.")
    for note in _what_the_walk_shows(walked, chain):
        print(f"  NOTE: {note}")


def _what_the_walk_shows(walked: dict[str, Any], chain: Chain) -> list[str]:
    """Whether the run bears out what the section says about it."""
    notes = []
    hops = walked.get("hops", [])
    depths = {hop["depth"] for hop in hops}
    if len(depths) < 2:  # noqa: PLR2004
        notes.append(
            "the walk stopped at one level, so the container's members were recorded as "
            f"fields rather than as lots. Check the '{CHILD_LIST}' prefix: without it the "
            "chain looks built and is one hop deep."
        )
    reached = {geo for hop in hops for geo in (hop.get("geoids") or [])}
    missing = set(chain.fields.values()) - reached
    if missing and len(depths) >= 2:  # noqa: PLR2004
        names = ", ".join(sorted(chain.name_of.get(geo, geo[:10]) for geo in missing))
        notes.append(f"the walk did not reach {names}, which the chain says it should")
    return notes


# ==========================================================================
# Up the graph: this farm is a problem, where did its output go
# ==========================================================================


@dataclass
class Gate:
    """One check on the way up the graph, and what it answered."""

    name: str
    status: int
    detail: str

    @property
    def passed(self) -> bool:
        return self.status == HTTP_OK


def walk_up(seed_geo_id: str, token: str, grant: str | None = None,
            authority: str | None = None) -> tuple[dict[str, Any], Gate]:
    """Trace forward from a field to the lots it entered.

    Two gates, per the permissions deck slide 9. Gate A: the hub must have put
    ``trace-forward`` in the caller's token, which is for accredited accounts
    only. Gate B: own the seed field, or present a scoped, expiring, revocable
    authority credential. Both are checked at the node, and the reason for the
    accreditation is that this direction reaches into other companies' customer
    relationships rather than the caller's own.
    """
    headers = {"Authorization": f"Bearer {token}"}
    if grant:
        headers["X-Grant-Token"] = grant
    if authority:
        headers["X-Authority-Token"] = authority
    try:
        response = requests.post(f"{NODE_URL}/traceforward", headers=headers,
                                 json={"seed_geoid": seed_geo_id}, timeout=60)
    except requests.RequestException as exc:
        return {}, Gate("reachability", 0, f"AR2 could not be reached: {exc.__class__.__name__}")
    body = response.json() if response.content else {}
    detail = body.get("detail", "") if isinstance(body, dict) else ""
    if response.status_code == HTTP_UNAUTHORIZED:
        return {}, Gate("hub authentication", response.status_code, detail)
    if response.status_code == HTTP_FORBIDDEN:
        gate = "Gate A: accreditation" if "capabilit" in detail.lower() else "Gate B: authority"
        return {}, Gate(gate, response.status_code, detail)
    if not response.ok:
        return {}, Gate("trace-forward", response.status_code, detail or response.text[:120])
    return body, Gate("trace-forward", response.status_code, "both gates passed")


def show_gates(gates: list[Gate], labels: list[str] | None = None) -> None:
    """Which door opened, which did not, and what was presented at each."""
    labels = labels or [""] * len(gates)
    print(f"  {'presenting':36} {'':5} {'which check answered':26} why")
    for label, gate in zip(labels, gates):
        mark = "OPEN " if gate.passed else "shut "
        print(f"  {label:36} {mark} {gate.name:26} {gate.detail[:52]}")


def lots_containing(geo_id: str, token: str) -> tuple[list[str], int, str]:
    """The other door to the same question, and what it costs to open.

    ``GET /list-artifact/reverse/{geoid}`` returns the lists a field belongs to.
    It needs a login and nothing else: no grant, no authority credential, no
    accreditation. See ``the_door_beside_the_gate``.
    """
    try:
        response = requests.get(f"{NODE_URL}/list-artifact/reverse/{geo_id}",
                                headers={"Authorization": f"Bearer {token}"}, timeout=60)
    except requests.RequestException as exc:
        return [], 0, f"AR2 could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return [], response.status_code, f"AR2 answered HTTP {response.status_code}"
    lists = (response.json() or {}).get("list_ids", [])
    return lists, response.status_code, f"{len(lists)} list(s), with a login and nothing else"


def what_a_bare_login_gets(geo_id: str, token: str) -> list[tuple[str, str, int]]:
    """What each door answers for the same field, with the same plain account."""
    probes = []

    lists, status, _ = lots_containing(geo_id, token)
    probes.append(("which lots is this field in?", "GET /list-artifact/reverse", status))

    if lists:
        read = requests.get(f"{NODE_URL}/list-artifact/{lists[0]}",
                            headers={"Authorization": f"Bearer {token}"}, timeout=60)
        probes.append(("who else is in one of them?", "GET /list-artifact/{id}", read.status_code))
        walked = requests.get(f"{NODE_URL}/list-artifact/{lists[0]}/traceback",
                              headers={"Authorization": f"Bearer {token}"}, timeout=60)
        probes.append(("walk that lot down", "GET .../traceback", walked.status_code))

    forward = requests.post(f"{NODE_URL}/traceforward",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"seed_geoid": geo_id}, timeout=60)
    probes.append(("which lots is this field in?", "POST /traceforward", forward.status_code))
    return probes


def membership_oracle(candidates: dict[str, str], lot_id: str,
                      token: str) -> list[tuple[str, bool]]:
    """For each candidate field, does the ungated door say it is in this lot.

    The consequence that makes AG-015 worth more than a count. A GeoID is
    derived from a boundary and computable by anyone -- that is P1 and not
    negotiable -- so a caller who has a lot identifier from anywhere, a
    shipping document or a QR code, can test any boundary they can obtain
    against it. That is 'which farms feed this lot', which is the question
    slide 9 reserves for accredited callers.
    """
    verdicts = []
    for name, geo_id in candidates.items():
        lists, _, _ = lots_containing(geo_id, token)
        verdicts.append((name, lot_id in lists))
    return verdicts


def show_oracle(verdicts: list[tuple[str, bool]], truth: dict[str, bool]) -> None:
    """The oracle beside the truth, so that agreement is visible rather than claimed."""
    print(f"  {'field':24} {'oracle says':12} {'actually in the lot':20}")
    wrong = 0
    for name, verdict in verdicts:
        expected = truth.get(name, False)
        agree = verdict == expected
        wrong += not agree
        print(f"  {name:24} {str(verdict):12} {str(expected):20} {'' if agree else '<- DISAGREES'}")
    print()
    if wrong:
        print(f"  The oracle was wrong {wrong} time(s), so it is not exact. Still a leak, "
              "but a noisier one than AG-015 describes.")
    else:
        print("  Exact, including the field that is in no lot at all. A caller who can")
        print("  guess or obtain a boundary can test it against any lot id they hold.")


# ==========================================================================
# Proving one thing without revealing the rest
# ==========================================================================


def prove_membership(list_id: str, geo_id: str, token: str) -> tuple[list[dict[str, Any]], str]:
    """A Merkle inclusion proof: this field is in this lot, and nothing else."""
    try:
        response = requests.get(f"{PANCAKE_URL}/fieldlists/{list_id}/proof/{geo_id}",
                                headers={"Authorization": f"Bearer {token}"}, timeout=60)
    except requests.RequestException as exc:
        return [], f"Pancake could not be reached: {exc.__class__.__name__}"
    if not response.ok:
        return [], f"Pancake answered HTTP {response.status_code}: {response.text[:120]}"
    body = response.json() or {}
    proof = body.get("proof") or body.get("path") or []
    return proof, f"{len(proof)} sibling hash(es) recompute the list_id"


def proof_reveals(proof: list[dict[str, Any]], others: list[str]) -> list[str]:
    """Any other member's GeoID appearing in the proof would defeat its purpose."""
    blob = json.dumps(proof)
    return [geo_id for geo_id in others if geo_id in blob]


# ==========================================================================
# Drawing it
# ==========================================================================


def chain_map(chain: Chain, features: list[dict[str, Any]]):
    """The four fields, coloured by which lot they went into."""
    if not have_folium():
        return None
    import folium  # noqa: PLC0415

    from openscience_demo import (  # noqa: PLC0415
        _basemap, _bounds, _hand_over_to_the_boundaries, _legend, _pin,
    )

    rings = [feature["geometry"]["coordinates"][0] for feature in features]
    canvas = _basemap(rings)

    both = folium.FeatureGroup(name="in both lots", show=True)
    one = folium.FeatureGroup(name="in one lot", show=True)

    for feature in features:
        name = feature["properties"]["name"]
        shared = name == chain.shared_field
        colour = OUTLINE if shared else ACCENT
        group = both if shared else one
        ring = feature["geometry"]["coordinates"][0]
        folium.Polygon(
            locations=[[point[1], point[0]] for point in ring],
            color=colour, weight=3, fill=True, fill_opacity=0.25, fill_color=colour,
            tooltip=f"{name}{' -- in both lots' if shared else ''}",
        ).add_to(group)
        _pin(group, feature, colour,
             f"{name}{' -- in both lots' if shared else ''}")

    both.add_to(canvas)
    one.add_to(canvas)
    folium.LayerControl(collapsed=False).add_to(canvas)
    _legend(canvas, [
        ("in one mill lot", ACCENT, "solid"),
        ("in both mill lots", OUTLINE, "solid"),
    ], title="Which lot each field fed")
    canvas.fit_bounds(_bounds(rings))
    _hand_over_to_the_boundaries(canvas)
    return canvas


# ==========================================================================
# Small helpers the notebook leans on
# ==========================================================================


def register(feature: dict[str, Any], token: str) -> str:
    """A boundary becomes a GeoID. Taken apart properly in the identity notebook."""
    from openscience_demo import geoid_of, wkt_of  # noqa: PLC0415

    response = post(f"{NODE_URL}/register-field-boundary", token=token,
                    json={"wkt": wkt_of(feature["geometry"]),
                          "field_name": feature["properties"]["name"]})
    return geoid_of(response)


def own_list(geo_id: str, token: str) -> str:
    """A one-field list, so a grant can be issued naming that field as its subject.

    A grant is issued over a list, never over a bare GeoID, so demonstrating
    'a grant on the seed field' needs a list containing only the seed.
    """
    list_id, _ = pool_through_pancake([geo_id], f"just {geo_id[:12]}", token)
    return list_id


def which_lot(list_id: str | None, chain: Chain | None) -> str:
    """Name a list if this notebook made it, so the output is not all hashes."""
    if not list_id or not chain:
        return ""
    if list_id == chain.container.list_id:
        return f"<- {chain.container.label}"
    for label, lot in chain.lots.items():
        if list_id == lot.list_id:
            return f"<- {label}"
    return "a lot from an earlier run"


def unregistered_geoid() -> str:
    """A well-formed GeoID for a boundary nobody has registered.

    The control for the oracle. Without it, an oracle that answered 'no' to
    everything and 'yes' to everything registered would look identical to one
    that was actually reading the index.
    """
    import hashlib  # noqa: PLC0415

    return hashlib.sha256(b"a boundary nobody has ever registered").hexdigest()
