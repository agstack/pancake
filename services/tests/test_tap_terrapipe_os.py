"""The terrapipe-os connector: client, three adapters, and what each refuses to store.

The node is faked at the HTTP boundary with a real ``requests`` session
adapter, so the client's own header, token and error handling is exercised
rather than mocked past. Response bodies are copied from the shapes
terrapipe-os actually serialises (``DeforestationScreen.to_dict``,
``handlers.Service.read``, ``GfsForecast.to_dict``).
"""
import json
import time

import jwt as pyjwt
import pytest
import requests

from pancake_services.store.bites import BiteStore
from pancake_services.tap.adapter_base import SIRUPType, TAPAdapterFactory
from pancake_services.tap.adapters.terrapipe_os import (
    DeforestationAdapter,
    GrantRequired,
    HubTokenSource,
    NoDataHere,
    TerrapipeOSClient,
    TerrapipeOSError,
    VegetationIndexAdapter,
    WeatherForecastAdapter,
)
from pancake_services.tap.runtime import TAPRuntime, TaskSpec, VendorSchedule

NODE = "http://terrapipe-os.test"
HUB = "http://hub.test"
GEOID = "9f7c2a1b3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5061728394a5b6c7d8e"


# --------------------------------------------------------------------------
# a fake node
# --------------------------------------------------------------------------


class FakeNode:
    """Answers the four routes the connector uses, and counts what was asked."""

    def __init__(self):
        self.calls = []
        self.routes = {}
        self.token_issues = 0

    def set(self, path, status=200, body=None, requires_grant=False):
        self.routes[path] = {"status": status, "body": body, "requires_grant": requires_grant}

    def session(self):
        node = self

        class Adapter(requests.adapters.BaseAdapter):
            def send(self, request, **kwargs):
                path = request.url.replace(NODE, "").replace(HUB, "").split("?")[0]
                query = request.url.split("?")[1] if "?" in request.url else ""
                node.calls.append(
                    {
                        "path": path,
                        "query": query,
                        "authorization": request.headers.get("Authorization"),
                        "grant": request.headers.get("X-Field-Grant"),
                    }
                )
                if path == "/users/token":
                    node.token_issues += 1
                    claims = {"sub": "pancake", "exp": int(time.time()) + 3600}
                    token = pyjwt.encode(claims, "k" * 32, algorithm="HS256")
                    return node._respond(200, {"access_token": token}, request)

                route = node.routes.get(path)
                if route is None:
                    return node._respond(
                        404, {"detail": f"no route {path}", "reason": "geoid_not_found"}, request
                    )
                if route["requires_grant"] and not request.headers.get("X-Field-Grant"):
                    return node._respond(
                        403,
                        {"detail": "a field-access grant is required", "reason": "grant_required"},
                        request,
                    )
                return node._respond(route["status"], route["body"], request)

            def close(self):
                pass

        def _respond(status, body, request):
            response = requests.Response()
            response.status_code = status
            response._content = json.dumps(body).encode()
            response.headers["Content-Type"] = "application/json"
            response.url = request.url
            response.request = request
            return response

        node._respond = lambda status, body, request: _respond(status, body, request)
        session = requests.Session()
        session.mount(NODE, Adapter())
        session.mount(HUB, Adapter())
        return session


def screen_body(verdict="deforestation_detected", scope="field", coverage=1.0):
    """The shape terrapipe_os.screen.DeforestationScreen.to_dict produces."""
    return {
        "geo_id": GEOID,
        "scope": scope,
        "cover_tier": "precise" if scope == "field" else "coarse",
        "cutoff_year": 2020,
        "verdict": verdict,
        "deforested_fraction": 0.4375 if verdict == "deforestation_detected" else 0.0,
        "deforested_by_year": {"2021": 0.171875, "2022": 0.265625},
        "coverage_fraction": coverage,
        "coverage_threshold": 0.99,
        "primary": {
            "layer_id": "jrc_tmf_deforestation_year",
            "absent": None,
            "note": None,
            "reading": {
                "value": {"no_deforestation_detected": 0.5625, "2022": 0.265625},
                "unit": None,
                "coverage_fraction": coverage,
                "method": "area_weighted_class_fractions",
                "detail": {},
            },
        },
        "second_opinion": {
            "agrees_with_primary": None,
            "evidence": [
                {
                    "layer_id": "icf_honduras_forest_cover_2018",
                    "absent": "not_mirrored",
                    "note": "store does not exist on the share; this layer has not been ingested here",
                }
            ],
        },
        "commodity": {
            "coffee_fraction": 0.8125,
            "evidence": [
                {
                    "layer_id": "icf_honduras_cafe_2020",
                    "absent": None,
                    "note": None,
                    "reading": {
                        "value": {"cafe": 0.8125, "no_cafe": 0.1875},
                        "unit": None,
                        "coverage_fraction": 1.0,
                        "method": "area_weighted_class_fractions",
                        "detail": {},
                    },
                }
            ],
        },
        "context": [{"layer_id": "esa_worldcover", "absent": "not_mirrored", "note": "not ingested"}],
        "caveats": [],
        "provenance": {
            "jrc_tmf_deforestation_year": {
                "source": "European Commission Joint Research Centre",
                "licence": "CC-BY-4.0",
            }
        },
    }


def ndvi_body(value=0.72, coverage=1.0):
    """The shape handlers.Service.read produces: no echo of the date asked for."""
    return {
        "geo_id": GEOID,
        "cover": {"tier": "precise", "masking_level": "L1", "tokens": 3},
        "layer_id": "ndvi_sentinel2",
        "value": value,
        "unit": "dimensionless",
        "coverage_fraction": coverage,
        "complete": coverage == 1.0,
        "cells_read": 1024,
        "field_leaf_cells": 4096,
        "covered_leaf_cells": int(4096 * coverage),
        "method": "area_weighted_mean",
        "detail": {},
        "provenance": {"source": "Copernicus Sentinel-2, processed by TerraPipe"},
    }


def forecast_body(steps=3, step_hours=3):
    """The shape terrapipe_os.gfs.GfsForecast.to_dict produces: kelvin, kg/m2."""
    return {
        "geo_id": GEOID,
        "layer_id": "gfs_forecast",
        "cell_token": "8f65",
        "grid_point": {"latitude": 14.25, "longitude": -88.0},
        "distance_km": 12.4,
        "start": "2026-09-02",
        "end": "2026-09-03",
        "steps": [
            {
                "valid_time": f"2026-09-02T{i * step_hours:02d}:00:00+00:00",
                "forecast_hour": i * step_hours,
                "t2m": 295.15 + i,
                "r2": 78.0,
                "tp": 1.5,
                "u10": 2.0,
            }
            for i in range(steps)
        ],
        "variables": {
            "t2m": {"description": "air temperature at 2 m", "unit": "K"},
            "r2": {"description": "relative humidity at 2 m", "unit": "%"},
            "tp": {"description": "total precipitation over the step", "unit": "kg/m²"},
            "u10": {"description": "eastward wind at 10 m", "unit": "m/s"},
        },
        "provenance": {"source": "NOAA NCEP", "licence": "Public domain (US Government work)"},
        "files_read": 2,
        "grid_points_in_partition": 9,
        "notes": [],
    }


@pytest.fixture
def node():
    return FakeNode()


def make_adapter(cls, node, *, grant=None, sirup_types, vendor="terrapipe-os"):
    adapter = cls(
        {
            "vendor_name": vendor,
            "base_url": NODE,
            "auth_method": "bearer_token",
            "sirup_types": sirup_types,
            "credentials": {"access_token": "test-token", **({"field_grant": grant} if grant else {})},
        }
    )
    adapter.client._session = node.session()
    return adapter


# --------------------------------------------------------------------------
# the client
# --------------------------------------------------------------------------


def test_the_hub_token_is_fetched_once_and_reused(node):
    source = HubTokenSource(HUB, "pancake", "secret", session=node.session())
    client = TerrapipeOSClient(NODE, source, session=node.session())
    node.set(f"/menu/{GEOID}", body={"geo_id": GEOID, "layers": []})

    client.menu(GEOID)
    client.menu(GEOID)

    assert node.token_issues == 1, "the token should be reused until it nears expiry"
    menu_calls = [c for c in node.calls if c["path"].startswith("/menu")]
    assert len(menu_calls) == 2
    assert {c["authorization"] for c in menu_calls} == {f"Bearer {source.token()}"}


def test_a_401_refreshes_the_token_once_then_gives_up(node):
    source = HubTokenSource(HUB, "pancake", "secret", session=node.session())
    client = TerrapipeOSClient(NODE, source, session=node.session())
    node.set(f"/menu/{GEOID}", status=401, body={"detail": "expired", "reason": "unauthenticated"})

    with pytest.raises(TerrapipeOSError) as caught:
        client.menu(GEOID)

    assert caught.value.status_code == 401
    assert node.token_issues == 2, "one initial mint, one refresh after the 401"
    assert len([c for c in node.calls if c["path"].startswith("/menu")]) == 2


def test_discovery_needs_no_token(node):
    client = TerrapipeOSClient(NODE, session=node.session())
    node.set("/layers", body=[{"layer_id": "jrc_tmf_deforestation_year"}])

    assert client.layers()[0]["layer_id"] == "jrc_tmf_deforestation_year"
    assert node.calls[-1]["authorization"] is None


def test_the_grant_travels_in_its_own_header(node):
    client = TerrapipeOSClient(NODE, static_token="t", session=node.session())
    node.set(f"/screen/{GEOID}", body=screen_body(), requires_grant=True)

    client.screen(GEOID, grant="grant-jwt")

    assert node.calls[-1]["grant"] == "grant-jwt"


def test_refusals_are_typed_by_the_nodes_own_reason(node):
    client = TerrapipeOSClient(NODE, static_token="t", session=node.session())
    node.set(f"/screen/{GEOID}", requires_grant=True, body=screen_body())
    node.set(f"/data/{GEOID}/ndvi_sentinel2", status=404, body={"detail": "none", "reason": "no_data"})
    node.set("/layers", status=503, body={"detail": "share down", "reason": "store_unavailable"})

    with pytest.raises(GrantRequired):
        client.screen(GEOID)
    with pytest.raises(NoDataHere):
        client.read_layer(GEOID, "ndvi_sentinel2")
    with pytest.raises(TerrapipeOSError) as other:
        client.layers()
    assert other.value.reason == "store_unavailable"
    assert not isinstance(other.value, (GrantRequired, NoDataHere))


def test_an_unreachable_node_is_an_error_not_an_empty_answer():
    client = TerrapipeOSClient("http://127.0.0.1:9", static_token="t", timeout=1)
    with pytest.raises(TerrapipeOSError, match="unreachable"):
        client.menu(GEOID)


# --------------------------------------------------------------------------
# deforestation
# --------------------------------------------------------------------------


def test_the_screen_is_carried_into_a_bite_with_its_coverage_and_evidence(node):
    adapter = make_adapter(
        DeforestationAdapter, node, grant="g", sirup_types=["land_use_screen"]
    )
    node.set(f"/screen/{GEOID}", body=screen_body(), requires_grant=True)

    bite = adapter.fetch_and_transform(GEOID, SIRUPType.LAND_USE_SCREEN, {})

    data = bite["Body"]["sirup_data"]
    assert data["verdict"] == "deforestation_detected"
    assert data["deforested_fraction"] == 0.4375
    assert data["coverage_fraction"] == 1.0, "a verdict without its coverage is not interpretable"
    assert data["deforested_by_year"] == {"2021": 0.171875, "2022": 0.265625}
    assert data["scope"] == "field"

    metadata = bite["Body"]["metadata"]
    assert metadata["grant_presented"] is True and metadata["field_scoped"] is True
    assert "jrc_tmf_deforestation_year" in metadata["layers_consulted"]
    # Absence is named per layer, never rendered as a zero.
    assert metadata["layers_absent"]["icf_honduras_forest_cover_2018"] == "not_mirrored"
    assert metadata["layers_absent"]["esa_worldcover"] == "not_mirrored"
    assert metadata["provenance"]["jrc_tmf_deforestation_year"]["licence"] == "CC-BY-4.0"
    assert bite["Header"]["type"] == "land_use_screen"
    assert "eudr" in bite["Footer"]["tags"]


def test_without_a_grant_the_screen_is_stored_as_a_neighbourhood_answer(node):
    adapter = make_adapter(DeforestationAdapter, node, sirup_types=["land_use_screen"])
    node.set(f"/screen/{GEOID}", body=screen_body(scope="neighbourhood"))

    bite = adapter.fetch_and_transform(GEOID, SIRUPType.LAND_USE_SCREEN, {})

    assert bite["Body"]["sirup_data"]["scope"] == "neighbourhood"
    assert bite["Body"]["metadata"]["field_scoped"] is False
    assert bite["Body"]["metadata"]["grant_presented"] is False
    assert node.calls[-1]["grant"] is None


def test_a_grant_required_refusal_is_recorded_not_retried(node):
    adapter = make_adapter(DeforestationAdapter, node, sirup_types=["land_use_screen"])
    node.set(f"/screen/{GEOID}", body=screen_body(), requires_grant=True)

    assert adapter.fetch_and_transform(GEOID, SIRUPType.LAND_USE_SCREEN, {}) is None
    assert len(node.calls) == 1, "retrying a refusal we cannot satisfy just costs round trips"


def test_an_unrecognised_verdict_is_refused_rather_than_stored(node):
    adapter = make_adapter(DeforestationAdapter, node, grant="g", sirup_types=["land_use_screen"])
    node.set(f"/screen/{GEOID}", body=screen_body(verdict="probably_fine"))

    assert adapter.fetch_and_transform(GEOID, SIRUPType.LAND_USE_SCREEN, {}) is None


def test_a_per_task_grant_overrides_the_adapter_wide_one(node):
    adapter = make_adapter(DeforestationAdapter, node, grant="wide", sirup_types=["land_use_screen"])
    node.set(f"/screen/{GEOID}", body=screen_body())

    adapter.get_vendor_data(GEOID, {"field_grant": "per-task"})

    assert node.calls[-1]["grant"] == "per-task"


def test_a_screen_lands_in_the_bite_store_and_dedupes(app, node):
    store = BiteStore(app.state.session_factory)
    node.set(f"/screen/{GEOID}", body=screen_body())
    factory = TAPAdapterFactory()
    factory.register_adapter(
        {
            "vendor_name": "terrapipe-os",
            "adapter_class": f"{DeforestationAdapter.__module__}.DeforestationAdapter",
            "base_url": NODE,
            "sirup_types": ["land_use_screen"],
            "credentials": {"access_token": "t"},
        }
    )
    factory.get_adapter("terrapipe-os").client._session = node.session()
    runtime = TAPRuntime(factory, store.save, sleep=lambda s: None)

    report = runtime.run_once(
        VendorSchedule(
            vendor_name="terrapipe-os",
            interval_seconds=3600,
            tasks=[TaskSpec(geoid=GEOID, sirup_type=SIRUPType.LAND_USE_SCREEN)],
        )
    )

    assert report.succeeded == 1
    stored = store.query(geoid=GEOID, bite_type="land_use_screen")
    assert len(stored) == 1
    assert stored[0].envelope["Body"]["sirup_data"]["verdict"] == "deforestation_detected"


# --------------------------------------------------------------------------
# vegetation index
# --------------------------------------------------------------------------


def test_ndvi_dates_are_carried_alongside_the_readings(node):
    adapter = make_adapter(VegetationIndexAdapter, node, sirup_types=["vegetation_index"])
    node.set(f"/data/{GEOID}/ndvi_sentinel2", body=ndvi_body())

    bite = adapter.fetch_and_transform(
        GEOID, SIRUPType.VEGETATION_INDEX, {"dates": ["2026-08-01", "2026-08-11"]}
    )

    series = bite["Body"]["sirup_data"]["series"]
    assert [p["date"] for p in series] == ["2026-08-01", "2026-08-11"]
    assert all(p["value"] == 0.72 for p in series)
    assert bite["Body"]["units"]["value"] == "dimensionless"
    assert bite["Header"]["type"] == "vegetation_index"
    # The node is asked for one date at a time, since it partitions by day.
    assert [c["query"] for c in node.calls] == ["time=2026-08-01", "time=2026-08-11"]


def test_a_date_with_no_acquisition_is_a_gap_not_an_interpolation(node):
    adapter = make_adapter(VegetationIndexAdapter, node, sirup_types=["vegetation_index"])
    calls = {"n": 0}
    real_read = adapter.client.read_layer

    def sometimes_empty(geoid, layer_id, *, grant=None, time_value=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise NoDataHere("no acquisition", 404, "no_data")
        return real_read(geoid, layer_id, grant=grant, time_value=time_value)

    adapter.client.read_layer = sometimes_empty
    node.set(f"/data/{GEOID}/ndvi_sentinel2", body=ndvi_body())

    bite = adapter.fetch_and_transform(
        GEOID, SIRUPType.VEGETATION_INDEX, {"dates": ["2026-08-01", "2026-08-02", "2026-08-03"]}
    )

    data = bite["Body"]["sirup_data"]
    assert [p["date"] for p in data["series"]] == ["2026-08-01", "2026-08-03"]
    assert data["dates_absent"] == {"2026-08-02": "no_acquisition"}
    assert bite["Body"]["metadata"]["dates_absent"] == 1


def test_no_ndvi_at_all_writes_nothing(node):
    adapter = make_adapter(VegetationIndexAdapter, node, sirup_types=["vegetation_index"])
    node.set(f"/data/{GEOID}/ndvi_sentinel2", status=404, body={"detail": "x", "reason": "no_data"})

    assert (
        adapter.fetch_and_transform(GEOID, SIRUPType.VEGETATION_INDEX, {"dates": ["2026-08-01"]})
        is None
    )


def test_partial_coverage_travels_with_every_ndvi_point(node):
    adapter = make_adapter(VegetationIndexAdapter, node, sirup_types=["vegetation_index"])
    node.set(f"/data/{GEOID}/ndvi_sentinel2", body=ndvi_body(coverage=0.12))

    bite = adapter.fetch_and_transform(
        GEOID, SIRUPType.VEGETATION_INDEX, {"dates": ["2026-08-01"]}
    )

    point = bite["Body"]["sirup_data"]["series"][0]
    assert point["coverage_fraction"] == 0.12 and point["complete"] is False
    assert bite["Body"]["metadata"]["min_coverage_fraction"] == 0.12


# --------------------------------------------------------------------------
# weather
# --------------------------------------------------------------------------


def test_the_forecast_keeps_the_models_own_steps_and_converts_units_exactly(node):
    adapter = make_adapter(WeatherForecastAdapter, node, sirup_types=["weather_forecast"])
    node.set(f"/forecast/{GEOID}", body=forecast_body(steps=3, step_hours=3))

    bite = adapter.fetch_and_transform(GEOID, SIRUPType.WEATHER_FORECAST, {"days": 2})

    body = bite["Body"]["sirup_data"]
    assert body["resolution"] == "3-hourly (GFS forecast steps, not interpolated)"
    assert len(body["timestamps"]) == 3
    for name, values in body["series"].items():
        assert len(values) == len(body["timestamps"]), name

    # Kelvin to celsius, exactly, and renamed only because it was converted.
    assert body["series"]["air_temperature"] == [22.0, 23.0, 24.0]
    assert bite["Body"]["units"]["air_temperature"] == "degC"
    assert body["series"]["precipitation"] == [1.5, 1.5, 1.5]
    assert bite["Body"]["units"]["precipitation"] == "mm"
    # An unmapped variable keeps the model's own name and unit rather than being dropped.
    assert body["series"]["u10"] == [2.0, 2.0, 2.0]
    assert bite["Body"]["units"]["u10"] == "m/s"
    assert any("t2m (K) -> air_temperature (degC)" in c for c in bite["Body"]["metadata"]["unit_conversions"])


def test_the_forecast_says_which_grid_point_it_is_for(node):
    adapter = make_adapter(WeatherForecastAdapter, node, sirup_types=["weather_forecast"])
    node.set(f"/forecast/{GEOID}", body=forecast_body())

    bite = adapter.fetch_and_transform(GEOID, SIRUPType.WEATHER_FORECAST, {})

    metadata = bite["Body"]["metadata"]
    assert metadata["grid_point"] == {"latitude": 14.25, "longitude": -88.0}
    assert metadata["distance_km"] == 12.4
    assert "30 km" in metadata["interpretation"]
    assert "no hourly interpolation" in metadata["interpretation"]


def test_an_empty_forecast_window_writes_nothing(node):
    adapter = make_adapter(WeatherForecastAdapter, node, sirup_types=["weather_forecast"])
    empty = forecast_body()
    empty["steps"] = []
    node.set(f"/forecast/{GEOID}", body=empty)

    assert adapter.fetch_and_transform(GEOID, SIRUPType.WEATHER_FORECAST, {}) is None


def test_an_irregular_step_sequence_is_labelled_as_such(node):
    adapter = make_adapter(WeatherForecastAdapter, node, sirup_types=["weather_forecast"])
    body = forecast_body(steps=3, step_hours=3)
    body["steps"][2]["forecast_hour"] = 12  # a gap in the model's own output
    node.set(f"/forecast/{GEOID}", body=body)

    bite = adapter.fetch_and_transform(GEOID, SIRUPType.WEATHER_FORECAST, {})

    assert bite["Body"]["sirup_data"]["resolution"].startswith("irregular")


# --------------------------------------------------------------------------
# the two new SIRUP types
# --------------------------------------------------------------------------


def test_the_new_sirup_types_round_trip_through_the_enum():
    assert SIRUPType("land_use_screen") is SIRUPType.LAND_USE_SCREEN
    assert SIRUPType("vegetation_index") is SIRUPType.VEGETATION_INDEX


def test_adapters_declare_the_types_they_serve(node):
    screen = make_adapter(DeforestationAdapter, node, sirup_types=["land_use_screen"])
    assert screen.supports_sirup_type(SIRUPType.LAND_USE_SCREEN)
    assert not screen.supports_sirup_type(SIRUPType.WEATHER_FORECAST)
    assert screen.get_capabilities()["sirup_types"] == ["land_use_screen"]
