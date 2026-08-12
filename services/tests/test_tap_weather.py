"""Weather TAP adapters: seed generation, TerraPipe transform, worker gating, store round-trip."""
from pancake_services.store.bites import BiteStore
from pancake_services.tap.adapter_base import SIRUPType, TAPAdapterFactory
from pancake_services.tap.adapters.seed_weather import SeedWeatherAdapter
from pancake_services.tap.adapters.terrapipe_weather import TerrapipeWeatherAdapter
from pancake_services.tap.runtime import TAPRuntime, TaskSpec, VendorSchedule


def _seed_factory():
    factory = TAPAdapterFactory()
    factory.register_adapter({
        "vendor_name": "seed",
        "adapter_class": f"{SeedWeatherAdapter.__module__}.SeedWeatherAdapter",
        "sirup_types": ["weather_historical", "weather_forecast"],
    })
    return factory


def _seed_schedule(geoid="geo-seed-1"):
    return VendorSchedule(
        vendor_name="seed",
        interval_seconds=3600,
        tasks=[TaskSpec(geoid=geoid, sirup_type=SIRUPType.WEATHER_HISTORICAL,
                        params={"mode": "historical", "days": 3})],
    )


def test_seed_adapter_produces_aligned_hourly_series():
    adapter = SeedWeatherAdapter({
        "vendor_name": "seed",
        "sirup_types": ["weather_historical"],
    })
    raw = adapter.get_vendor_data("geo-x", {"mode": "historical", "days": 2})
    sirup = adapter.transform_to_sirup(raw, SIRUPType.WEATHER_HISTORICAL)
    body = sirup["data"]

    n = len(body["timestamps"])
    assert n == len(body["daily"]) * 24  # hourly expansion
    for field, values in body["series"].items():
        assert len(values) == n, field
    assert body["resolution"] == "hourly-synthesized-from-daily"
    # Temperature must actually vary across the day (diurnal cycle present).
    temps = body["series"]["air_temperature"]
    assert max(temps[:24]) > min(temps[:24])


def test_seed_is_deterministic_for_same_geoid_and_dates():
    a = SeedWeatherAdapter({"vendor_name": "seed", "sirup_types": ["weather_historical"]})
    r1 = a.get_vendor_data("geo-det", {"start_date": "2026-07-01", "end_date": "2026-07-03"})
    r2 = a.get_vendor_data("geo-det", {"start_date": "2026-07-01", "end_date": "2026-07-03"})
    assert r1["daily"] == r2["daily"]


def test_seed_run_once_lands_weather_bite_in_store(app):
    store = BiteStore(app.state.session_factory)
    runtime = TAPRuntime(_seed_factory(), store.save, sleep=lambda s: None)
    report = runtime.run_once(_seed_schedule("geo-seed-1"))

    assert report.succeeded == 1
    stored = store.query(geoid="geo-seed-1", bite_type="weather_historical")
    assert len(stored) == 1
    envelope = stored[0].envelope
    assert envelope["Body"]["sirup_data"]["series"]["air_temperature"]
    assert "seed" in envelope["Footer"]["tags"]


def test_terrapipe_transform_normalizes_daily_list():
    adapter = TerrapipeWeatherAdapter({
        "vendor_name": "terrapipe",
        "base_url": "https://example.invalid",
        "sirup_types": ["weather_forecast"],
        "credentials": {},
    })
    vendor_data = {
        "_geoid": "geo-tp",
        "_forecast": True,
        "_start": "2026-07-01",
        "_end": "2026-07-02",
        "raw": {"stats": [
            {"date": "2026-07-01", "t_min": 12, "t_max": 24, "precipitation": 3, "humidity": 80},
            {"date": "2026-07-02", "t_min": 13, "t_max": 26, "precipitation": 0, "humidity": 65},
        ]},
    }
    sirup = adapter.transform_to_sirup(vendor_data, SIRUPType.WEATHER_FORECAST)
    body = sirup["data"]
    assert len(body["daily"]) == 2
    assert len(body["timestamps"]) == 48
    assert sirup["metadata"]["source"].startswith("TerraPipe")


def test_terrapipe_transform_fills_window_from_scalar_stats():
    adapter = TerrapipeWeatherAdapter({
        "vendor_name": "terrapipe", "base_url": "x", "sirup_types": ["weather_historical"],
        "credentials": {},
    })
    vendor_data = {
        "_geoid": "geo-tp2", "_forecast": False,
        "_start": "2026-07-01", "_end": "2026-07-03",
        "raw": {"temperature_min": 10, "temperature_max": 20, "precip": 1.0},
    }
    sirup = adapter.transform_to_sirup(vendor_data, SIRUPType.WEATHER_HISTORICAL)
    assert len(sirup["data"]["daily"]) == 3  # window filled uniformly


def test_worker_skips_vendor_when_gate_env_empty(tmp_path, monkeypatch):
    from pancake_services.tap.worker import load_enabled_vendors

    monkeypatch.delenv("TERRAPIPE_SECRET", raising=False)
    config = tmp_path / "vendors.yaml"
    config.write_text(
        """
vendors:
  - vendor_name: terrapipe
    adapter_class: pancake_services.tap.adapters.terrapipe_weather.TerrapipeWeatherAdapter
    enabled_if_env: TERRAPIPE_SECRET
    base_url: http://x
    sirup_types: [weather_forecast]
    credentials: {}
  - vendor_name: seed
    adapter_class: pancake_services.tap.adapters.seed_weather.SeedWeatherAdapter
    sirup_types: [weather_forecast]
"""
    )
    enabled = load_enabled_vendors(str(config))
    names = [v["vendor_name"] for v in enabled]
    assert names == ["seed"]  # terrapipe gated off, seed always on

    monkeypatch.setenv("TERRAPIPE_SECRET", "abc")
    enabled = load_enabled_vendors(str(config))
    assert {v["vendor_name"] for v in enabled} == {"terrapipe", "seed"}
