"""Contract: the connector against a real terrapipe-os node over real HTTP.

The unit tests in ``test_tap_terrapipe_os.py`` drive the adapters against
response bodies written by hand from reading the node's source. That proves the
adapters are self-consistent and proves nothing about the node. A hand-written
fixture agrees with whatever its author believed, and the belief is the thing
most likely to be wrong -- the response shapes here were guessed wrong twice
while this connector was being written (``coverage`` for ``coverage_fraction``,
an ``evidence`` list where the node groups evidence under ``primary``,
``second_opinion`` and ``commodity``), and only reading the node's serialiser
caught it.

So this module runs the real thing: the real registry from ``layers/layers.json``,
real parquet stores on disk written through the node's own path builder, the
real FastAPI app on a real socket, and the connector's real ``requests``
session pointed at it. The only fakes are the two services outside both repos
-- the AR2 node that resolves a GeoID to a cover, and the hub that signs
tokens -- and the hub fake signs with real RS256 against a real JWKS, because
the verifier under test does real cryptography.

It skips when terrapipe-os is not checked out beside this repo. A skip here is
a gap in cover, not a pass: the suite reports it as one.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
from datetime import date
from pathlib import Path

import pytest

from pancake_services.tap.adapter_base import SIRUPType

TERRAPIPE_OS = Path(__file__).resolve().parents[3] / "terrapipe-os"

pytest.importorskip("terrapipe_os", reason="terrapipe-os is not installed in this environment")
pytest.importorskip("uvicorn")
if not (TERRAPIPE_OS / "tests").is_dir():  # pragma: no cover - environment guard
    pytest.skip("terrapipe-os checkout not found beside pancake", allow_module_level=True)

sys.path.insert(0, str(TERRAPIPE_OS / "tests"))

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from hub import FakeHub  # noqa: E402
from store import fill, write_store  # noqa: E402
from test_ar2 import GEO_ID, GRANT, FakeAR2  # noqa: E402

from helpers import COFFEE_BELT, leaf_at  # noqa: E402
from terrapipe_os import s2  # noqa: E402
from terrapipe_os.ar2 import AR2Client, HubAuth  # noqa: E402
from terrapipe_os.handlers import Service  # noqa: E402
from terrapipe_os.hubauth import HubVerifier  # noqa: E402
from terrapipe_os.registry import Registry  # noqa: E402
from terrapipe_os.service import create_app  # noqa: E402

from pancake_services.tap.adapters.terrapipe_os import (  # noqa: E402
    DeforestationAdapter,
    NoDataHere,
    TerrapipeOSError,
    VegetationIndexAdapter,
    WeatherForecastAdapter,
)

CUT_OFF = 2020
CLEARED_YEAR = 2022
NDVI_DATE = "2026-08-21"
FORECAST_DAY = date(2026, 9, 2)
GRID_NEAR = (14.25, -88.0)
STEP_HOURS = 3


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.load(TERRAPIPE_OS / "layers" / "layers.json")


@pytest.fixture(scope="module")
def node(tmp_path_factory, registry):
    """A real terrapipe-os on a real port, with real stores under it.

    Module-scoped: starting a server per test would triple the runtime for no
    extra cover, since no test here mutates the stores.
    """
    root = tmp_path_factory.mktemp("share")
    share, network = root / "share", root / "network"
    share.mkdir()
    network.mkdir()

    import os

    os.environ["TERRAPIPE_SHARE"] = str(share)
    os.environ["TERRAPIPE_NETWORK"] = str(network)

    hub, ar2 = FakeHub(), FakeAR2()

    def route(request: httpx.Request) -> httpx.Response:
        return hub.handle(request) or ar2._handle(request)

    http = httpx.Client(transport=httpx.MockTransport(route))
    verifier = HubVerifier("http://hub/.well-known/jwks.json", http=http)
    ar2_client = AR2Client(
        "http://node", auth=HubAuth("http://hub", "svc", "secret", http=http), http=http
    )
    service = Service(registry=registry, ar2=ar2_client, auth_description=verifier.describe())
    app = create_app(service, verifier)

    _write_stores(registry)
    _write_gfs(network)

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    _wait_until_up(base_url, server)

    yield base_url, hub, network

    server.should_exit = True
    thread.join(timeout=10)


def _wait_until_up(base_url: str, server, timeout: float = 15.0) -> None:
    import requests

    deadline = time.time() + timeout
    while time.time() < deadline:
        if getattr(server, "started", False):
            try:
                if requests.get(f"{base_url}/health", timeout=2).status_code == 200:
                    return
            except requests.RequestException:
                pass
        time.sleep(0.05)
    raise RuntimeError("terrapipe-os did not come up")


def _write_stores(registry: Registry) -> None:
    """Real parquet, written through the node's own path builder.

    A quarter of the field cleared after the cut-off, all of it coffee, and one
    NDVI date. Written over the L16 cell the fake AR2's cover sits in, which is
    how the node's own service tests place data.
    """
    c16 = leaf_at(*COFFEE_BELT).parent(16).id()

    jrc = registry["jrc_tmf_deforestation_year"]
    cells = list(s2.children_at(c16, jrc.storage.data_level))
    quarter = len(cells) // 4
    write_store(jrc, {c: (CLEARED_YEAR if i < quarter else 0) for i, c in enumerate(cells)})

    coffee = registry["icf_honduras_cafe_2020"]
    write_store(coffee, fill(c16, coffee.storage.data_level, 1))

    ndvi = registry["ndvi_sentinel2"]
    write_store(
        ndvi,
        fill(c16, ndvi.storage.data_level, 0.71),
        time_value=NDVI_DATE,
        value_column=ndvi.storage.value_columns[0],
    )


def _write_gfs(network: Path) -> None:
    """A GFS day laid out as the TerraPipe cron writes it: kelvin, kg/m2, 3-hourly.

    Two grid points, so the node has a nearest one to choose, and a temperature
    that encodes which point it came from.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq
    import s2sphere

    token = (
        s2sphere.CellId.from_lat_lng(s2sphere.LatLng.from_degrees(*COFFEE_BELT))
        .parent(5)
        .to_token()
    )
    day = FORECAST_DAY
    directory = (
        network
        / "GFS"
        / "PARQUET_S2_2"
        / f"s2_token_L5={token}"
        / f"year={day.year}"
        / f"month={day.month}"
        / f"day={day.day}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "utc_timestamp": f"{day.isoformat()}T{hour:02d}:00:00Z",
            "fhr": hour,
            "latitude": lat,
            "longitude": lon,
            "t2m": 273.15 + 22.0 + hour / 10,
            "d2m": 285.0,
            "u10": 1.0,
            "v10": 0.5,
            "tp": 0.5,
            "r2": 70.0,
        }
        for lat, lon in (GRID_NEAR, (15.25, -88.0))
        for hour in range(0, 24, STEP_HOURS)
    ]
    pq.write_table(pa.Table.from_pylist(rows), directory / "part-0.parquet")


def adapter(cls, base_url, hub, *, grant=None, sirup_types):
    made = cls(
        {
            "vendor_name": "terrapipe-os",
            "base_url": base_url,
            "auth_method": "bearer_token",
            "sirup_types": sirup_types,
            "credentials": {
                "access_token": hub.token(),
                **({"field_grant": grant} if grant else {}),
            },
        }
    )
    return made


# --------------------------------------------------------------------------


def test_the_node_answers_the_connectors_own_client(node):
    base_url, hub, _ = node
    made = adapter(DeforestationAdapter, base_url, hub, sirup_types=["land_use_screen"])

    health = made.client.health()
    layer_ids = {layer["layer_id"] for layer in made.client.layers()}

    assert health["status"] == "ok"
    assert {"jrc_tmf_deforestation_year", "ndvi_sentinel2", "gfs_forecast"} <= layer_ids


def test_a_real_screen_becomes_a_bite_with_the_keys_the_adapter_expects(node):
    """The check the hand-written fixture cannot make: the node's own keys."""
    base_url, hub, _ = node
    made = adapter(
        DeforestationAdapter, base_url, hub, grant=GRANT, sirup_types=["land_use_screen"]
    )

    bite = made.fetch_and_transform(GEO_ID, SIRUPType.LAND_USE_SCREEN, {})

    assert bite is not None, "the node answered; something in the adapter dropped it"
    data = bite["Body"]["sirup_data"]
    # Every key the adapter copies must exist upstream. A typo here silently
    # becomes a null in a compliance record, which is the failure this catches.
    for key in (
        "verdict",
        "scope",
        "cover_tier",
        "cutoff_year",
        "deforested_fraction",
        "deforested_by_year",
        "coverage_fraction",
        "coverage_threshold",
        "primary",
        "second_opinion",
        "commodity",
        "context",
        "caveats",
    ):
        assert data[key] is not None, f"{key} came back empty from the real node"

    assert data["verdict"] == "deforestation_detected"
    assert data["cutoff_year"] == CUT_OFF
    assert 0.2 < data["deforested_fraction"] < 0.3, "a quarter of the field was cleared"
    assert str(CLEARED_YEAR) in {str(y) for y in data["deforested_by_year"]}
    assert data["scope"] == "field", "a grant was presented, so the answer is about the field"

    metadata = bite["Body"]["metadata"]
    assert "jrc_tmf_deforestation_year" in metadata["layers_consulted"]
    assert metadata["provenance"]["jrc_tmf_deforestation_year"]["licence"]
    # The layers not mirrored in this fixture must be named as absent, not zero.
    assert metadata["layers_absent"], "unmirrored layers should be reported, not silently omitted"


def test_the_commodity_check_reaches_the_bite(node):
    base_url, hub, _ = node
    made = adapter(
        DeforestationAdapter, base_url, hub, grant=GRANT, sirup_types=["land_use_screen"]
    )

    bite = made.fetch_and_transform(GEO_ID, SIRUPType.LAND_USE_SCREEN, {})

    commodity = bite["Body"]["sirup_data"]["commodity"]
    assert commodity["coffee_fraction"] == pytest.approx(1.0), commodity
    # No oil-palm fraction, and a named reason for its absence rather than a
    # zero that would read as "no oil palm here". The reason changed on
    # 2026-09-02 from not_mirrored to outside_coverage, and the second is the
    # better answer: that product maps a belt across the north, this field is
    # in the coffee belt, and no mirror will ever cover it because the
    # publisher never surveyed it. "Not mirrored" invites someone to go and
    # fetch the missing tile.
    assert "oil_palm_fraction" not in commodity
    palma = [e for e in commodity["evidence"] if "palma" in e["layer_id"]]
    assert palma, "the oil-palm check must appear even when it cannot answer"
    assert palma[0]["absent"] == "outside_coverage"
    assert "declared coverage" in palma[0]["note"]


def test_without_a_grant_the_real_node_answers_about_the_neighbourhood(node):
    base_url, hub, _ = node
    made = adapter(DeforestationAdapter, base_url, hub, sirup_types=["land_use_screen"])

    bite = made.fetch_and_transform(GEO_ID, SIRUPType.LAND_USE_SCREEN, {})

    assert bite is not None, "a coarse answer is still an answer"
    assert bite["Body"]["sirup_data"]["scope"] != "field"
    assert bite["Body"]["metadata"]["field_scoped"] is False


def test_a_real_ndvi_read_carries_the_date_the_adapter_asked_for(node):
    base_url, hub, _ = node
    made = adapter(
        VegetationIndexAdapter, base_url, hub, grant=GRANT, sirup_types=["vegetation_index"]
    )

    bite = made.fetch_and_transform(
        GEO_ID, SIRUPType.VEGETATION_INDEX, {"dates": [NDVI_DATE, "2026-08-22"]}
    )

    data = bite["Body"]["sirup_data"]
    assert [p["date"] for p in data["series"]] == [NDVI_DATE]
    assert data["series"][0]["value"] == pytest.approx(0.71, abs=1e-6)
    # The second date has no partition on disk. It must be a named gap.
    assert data["dates_absent"] == {"2026-08-22": "no_acquisition"}


def test_a_real_forecast_arrives_in_celsius_at_the_models_own_step(node):
    """The conversion that would be invisible if only the fixture tested it.

    The store holds kelvin, because that is what GFS publishes. A consumer
    reading ``air_temperature`` from a weather BITE expects celsius. This is
    the test that fails if the adapter ever renames without converting.
    """
    base_url, hub, _ = node
    made = adapter(
        WeatherForecastAdapter, base_url, hub, grant=GRANT, sirup_types=["weather_forecast"]
    )

    bite = made.fetch_and_transform(
        GEO_ID,
        SIRUPType.WEATHER_FORECAST,
        {"start_date": FORECAST_DAY.isoformat(), "end_date": FORECAST_DAY.isoformat()},
    )

    assert bite is not None
    body = bite["Body"]["sirup_data"]
    assert body["resolution"] == f"{STEP_HOURS}-hourly (GFS forecast steps, not interpolated)"
    assert len(body["timestamps"]) == 24 // STEP_HOURS
    for name, values in body["series"].items():
        assert len(values) == len(body["timestamps"]), name

    temperatures = body["series"]["air_temperature"]
    assert all(20.0 < t < 25.0 for t in temperatures), temperatures
    assert bite["Body"]["units"]["air_temperature"] == "degC"
    # The nearest of the two grid points, with the distance that qualifies it.
    assert body["grid_point"] == {"latitude": GRID_NEAR[0], "longitude": GRID_NEAR[1]}
    assert body["distance_km"] > 0
    assert bite["Body"]["metadata"]["grid_points_in_partition"] == 2


def test_an_unmounted_store_is_an_operational_failure_not_an_empty_forecast(node, monkeypatch, tmp_path):
    """The share disappears mid-flight, as an NFS mount does.

    The node says ``store_unavailable`` with a 503, and the adapter lets that
    through rather than swallowing it. A share that is not mounted is a thing
    an operator has to fix; turning it into a quiet skip would leave the demo
    reporting no weather for as long as nobody looked. It is deliberately not
    treated like ``no_data``, which the node uses for "mounted, nothing here".
    """
    base_url, hub, _ = node
    monkeypatch.setenv("TERRAPIPE_NETWORK", str(tmp_path / "nothing-mounted-here"))
    made = adapter(
        WeatherForecastAdapter, base_url, hub, grant=GRANT, sirup_types=["weather_forecast"]
    )

    with pytest.raises(TerrapipeOSError) as caught:
        made.fetch_and_transform(GEO_ID, SIRUPType.WEATHER_FORECAST, {"days": 2})

    assert caught.value.reason == "store_unavailable"
    assert not isinstance(caught.value, NoDataHere)


def test_an_unknown_geoid_is_refused_without_inventing_a_reading(node):
    base_url, hub, _ = node
    made = adapter(DeforestationAdapter, base_url, hub, sirup_types=["land_use_screen"])

    assert made.fetch_and_transform("0" * 64, SIRUPType.LAND_USE_SCREEN, {}) is None
