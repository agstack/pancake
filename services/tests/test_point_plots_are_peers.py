"""A plot declared by a coordinate goes through consent exactly as a boundary does.

Regulation (EU) 2023/1115 Art. 2(28) lets a plot of at most four hectares be
declared by a single coordinate, and AR2 registers such plots as first-class:
a point's GeoID is a SHA-256 over a one-cell S2 cover, a polygon's over its
multi-cell cover, and the two are indistinguishable on the wire -- 64 hex
characters either way.

Pancake is geometry-free by design: it stores no boundary, computes no area, and
treats a GeoID as an opaque string. So the claim "the consent flow works
whichever kind of plot the farmer registered" should be true here for free. This
module is the check that it *is* true, and stays true. Without it the claim rests
on an audit someone did once, and the first area computation or geometry lookup
to arrive in this service would break smallholders declared by a coordinate --
who are the majority of the GGMS caseload -- while every existing test passed.

The GeoIDs below are real ones, minted by AR2 from a point and from a boundary
in the Honduran coffee belt (see test_ar2_point_geoids_are_opaque_here).
"""
import pytest

from pancake_services.grants import sdjwt
from pancake_services.grants.merkle import merkle_root, verify_inclusion

# Minted by AR2 at commit f6a6a2f: POINT (-88.312345 14.812345) with 0.3 ha
# declared, and the boundary of a neighbouring parcel.
POINT_GEOID = "4dbd1480e2f556d890d094c8be644a7755f68fb578f42b9862d763329cef87d2"
POLYGON_GEOID = "717cf048e47f7adbf0c69896b889f365033382d6f84481e1a1e89dbec7286096"
MIXED = [POINT_GEOID, POLYGON_GEOID]

LENDER = "hub-acct-buyer"


def _guarantee_body(subject: str, **over):
    body = {
        "subject": subject,
        "subject_kind": "geoid",
        "beneficiary_account": LENDER,
        "request_ref": "CR-2026-0042",
        "amount": 900.0,
        "currency": "HNL",
        "coverage_ratio": 0.8,
        "risk_class": "low",
        "rule_set_version": "eudr-perennial-crop/2026.09.16",
        "evidence": ["bite-screen-point-01"],
        "state": "PRE_APPROVED",
        "validity_days": 365,
    }
    body.update(over)
    return body


# --------------------------------------------------------------------------
# identity
# --------------------------------------------------------------------------


def test_ar2_point_geoids_are_opaque_here() -> None:
    """Both kinds are 64 hex characters, so nothing downstream can branch on shape."""
    for geoid in MIXED:
        assert len(geoid) == 64
        int(geoid, 16)


# --------------------------------------------------------------------------
# lists
# --------------------------------------------------------------------------


def test_a_list_may_mix_coordinates_and_boundaries(client, owner_headers) -> None:
    """What a cooperative actually has: some plots surveyed, some a GPS fix."""
    response = client.post(
        "/fieldlists", json={"name": "Cooperativa mixta", "geoids": MIXED}, headers=owner_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["list_id"] == merkle_root(MIXED)
    assert body["geoids"] == sorted(MIXED)


def test_the_listid_does_not_depend_on_which_kind_arrives_first(client, owner_headers) -> None:
    first = client.post(
        "/fieldlists", json={"name": "point first", "geoids": [POINT_GEOID, POLYGON_GEOID]},
        headers=owner_headers,
    )
    again = client.post(
        "/fieldlists", json={"name": "boundary first", "geoids": [POLYGON_GEOID, POINT_GEOID]},
        headers=owner_headers,
    )
    assert first.json()["list_id"] == again.json()["list_id"]


def test_a_coordinate_plot_can_prove_its_membership(client, owner_headers) -> None:
    """The proof a buyer checks. A point must be provable in a mixed list, or the
    farmer is in the lot and cannot show it."""
    created = client.post(
        "/fieldlists", json={"name": "Cooperativa mixta", "geoids": MIXED}, headers=owner_headers
    ).json()

    for geoid in MIXED:
        response = client.get(
            f"/fieldlists/{created['list_id']}/proof/{geoid}", headers=owner_headers
        )
        assert response.status_code == 200, f"{geoid} could not be proved in its own list"
        proof = response.json()
        assert verify_inclusion(proof["geoid"], proof["proof"], proof["list_id"])


def test_a_list_of_coordinates_alone_is_a_list(client, owner_headers) -> None:
    """A cooperative where nothing has been surveyed yet is still a cooperative."""
    response = client.post(
        "/fieldlists", json={"name": "all points", "geoids": [POINT_GEOID]}, headers=owner_headers
    )
    assert response.status_code == 201, response.text
    assert response.json()["list_id"] == merkle_root([POINT_GEOID])


# --------------------------------------------------------------------------
# the grant
# --------------------------------------------------------------------------


@pytest.fixture()
def mixed_grant(client, owner_headers):
    created = client.post(
        "/fieldlists", json={"name": "Cooperativa mixta", "geoids": MIXED}, headers=owner_headers
    ).json()
    response = client.post(
        "/grants/issue",
        json={
            "list_id": created["list_id"],
            "grantee_account": LENDER,
            "purpose": "eudr-due-diligence",
            "validity_days": 30,
        },
        headers=owner_headers,
    )
    assert response.status_code == 201, response.text
    return created, response.json()


def test_a_grant_over_a_mixed_list_discloses_both_kinds(mixed_grant, dev_issuer) -> None:
    created, grant = mixed_grant
    result = sdjwt.verify(grant["credential"], dev_issuer.public_key_pem)

    assert result.claims["sub"] == created["list_id"]
    assert sorted(result.disclosed_geoids) == sorted(MIXED), (
        "a coordinate plot was dropped from the disclosures, so consent would not cover it"
    )


def test_a_grant_verifies_and_carries_the_coordinate_plot(client, mixed_grant) -> None:
    _, grant = mixed_grant
    response = client.post("/grants/verify", json={"credential": grant["credential"]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert POINT_GEOID in body["disclosed_geoids"]


def test_revoking_a_mixed_grant_revokes_it_for_both(client, owner_headers, mixed_grant) -> None:
    _, grant = mixed_grant
    revoked = client.post(
        "/grants/revoke", json={"jti": grant["jti"]}, headers=owner_headers
    )
    assert revoked.status_code == 200, revoked.text

    after = client.post("/grants/verify", json={"credential": grant["credential"]}).json()
    assert after["valid"] is False


# --------------------------------------------------------------------------
# the guarantee, which is what the lender reads
# --------------------------------------------------------------------------


def test_a_guarantee_can_be_issued_over_a_coordinate_plot(client, owner_headers) -> None:
    response = client.post(
        "/guarantees/issue", json=_guarantee_body(POINT_GEOID), headers=owner_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["subject"] == POINT_GEOID
    assert body["state"] == "PRE_APPROVED"


def test_a_guarantee_over_a_coordinate_verifies_like_any_other(client, owner_headers) -> None:
    issued = client.post(
        "/guarantees/issue", json=_guarantee_body(POINT_GEOID), headers=owner_headers
    ).json()

    verified = client.post("/guarantees/verify", json={"credential": issued["credential"]})
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["valid"] is True
    assert body["claims"]["sub"] == POINT_GEOID
    assert body["claims"]["risk"]["risk_class"] == "low"


def test_the_lenders_credential_says_which_rule_set_judged_the_plot(client, owner_headers) -> None:
    """A verdict over a disc inferred from a declared area is not a verdict over
    a survey. The rule-set version is how the file says which it was."""
    issued = client.post(
        "/guarantees/issue", json=_guarantee_body(POINT_GEOID), headers=owner_headers
    ).json()
    verified = client.post(
        "/guarantees/verify", json={"credential": issued["credential"]}
    ).json()
    assert verified["claims"]["risk"]["rule_set_version"] == "eudr-perennial-crop/2026.09.16"


def test_a_guarantee_over_a_mixed_list_covers_the_coordinate_plots_in_it(
    client, owner_headers
) -> None:
    created = client.post(
        "/fieldlists", json={"name": "Cooperativa mixta", "geoids": MIXED}, headers=owner_headers
    ).json()
    response = client.post(
        "/guarantees/issue",
        json=_guarantee_body(created["list_id"], subject_kind="fieldlist"),
        headers=owner_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["subject"] == created["list_id"]


# --------------------------------------------------------------------------
# the audit trail
# --------------------------------------------------------------------------


def test_the_meal_records_a_coordinate_plot_under_its_own_geoid(
    client, owner_headers, mixed_grant
) -> None:
    """Provenance has to be findable by the identifier the farmer holds."""
    response = client.get(f"/audit/{POINT_GEOID}", headers=owner_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["geoid"] == POINT_GEOID
    assert body["events"], "no MEAL events for a coordinate plot that was just granted"


# --------------------------------------------------------------------------
# the negative: nothing here may start needing a shape
# --------------------------------------------------------------------------


def test_no_endpoint_asks_for_geometry_area_or_a_boundary() -> None:
    """The reason points work: this service never asks what shape a plot is.

    A guard rather than an observation. The day an endpoint takes an area or a
    boundary, consent stops being geometry-free and plots declared by a
    coordinate start failing validation -- which is a regression this service
    would otherwise report as a feature.
    """
    import inspect  # noqa: PLC0415
    import pkgutil  # noqa: PLC0415
    from importlib import import_module  # noqa: PLC0415

    from pancake_services.grants import schemas  # noqa: PLC0415

    forbidden = ("area_ha", "hectares", "acreage", "wkt", "geometry", "boundary", "polygon")
    offenders = []
    for name, model in vars(schemas).items():
        fields = getattr(model, "model_fields", None)
        if not fields:
            continue
        for field_name in fields:
            if any(word in field_name.lower() for word in forbidden):
                offenders.append(f"{name}.{field_name}")
    assert offenders == [], f"request/response schemas now carry geometry: {offenders}"

    # And the same for the routers' own signatures, which is where a parameter
    # would arrive without passing through a schema.
    import pancake_services.grants.routers as routers  # noqa: PLC0415

    signature_offenders = []
    for module_info in pkgutil.iter_modules(routers.__path__):
        module = import_module(f"{routers.__name__}.{module_info.name}")
        for func_name, func in vars(module).items():
            if not inspect.isfunction(func):
                continue
            for parameter in inspect.signature(func).parameters:
                if any(word in parameter.lower() for word in forbidden):
                    signature_offenders.append(f"{module_info.name}.{func_name}({parameter})")
    assert signature_offenders == [], (
        f"endpoints now take geometry parameters: {signature_offenders}"
    )
