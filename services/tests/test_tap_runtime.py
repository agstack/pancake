"""TAP runtime: scheduling, retry/backoff policy, frozen ingest interface, config interpolation."""
import pytest

from pancake_services.tap.adapter_base import (
    SIRUPType,
    TAPAdapter,
    TAPAdapterFactory,
    create_bite_from_sirup,
)
from pancake_services.tap.config import MissingEnvironmentVariable, load_vendor_configs
from pancake_services.tap.runtime import TaskSpec, TAPRuntime, VendorSchedule, schedule_from_config


class DummyAdapter(TAPAdapter):
    """Deterministic vendor: succeeds, or fails N times first (per config)."""

    def _initialize(self):
        self.fail_first = self.metadata.get("fail_first", 0)
        self.raise_error = self.metadata.get("raise_error", False)
        self.calls = 0

    def get_vendor_data(self, geoid, params):
        self.calls += 1
        if self.calls <= self.fail_first:
            if self.raise_error:
                raise RuntimeError("vendor exploded")
            return None
        return {"value": 21.5, "geoid": geoid}

    def transform_to_sirup(self, vendor_data, sirup_type):
        return {
            "sirup_type": sirup_type.value,
            "vendor": self.vendor_name,
            "timestamp": "2026-07-07T12:00:00+00:00",
            "geoid": vendor_data["geoid"],
            "data": {"temperature_mean": vendor_data["value"]},
            "metadata": {"source": "dummy"},
            "units": {"temperature": "°C"},
        }

    def sirup_to_bite(self, sirup, geoid, params):
        return create_bite_from_sirup(sirup, "weather_forecast", ["test"])


def make_factory(fail_first=0, raise_error=False):
    factory = TAPAdapterFactory()
    factory.register_adapter({
        "vendor_name": "dummy",
        "adapter_class": f"{DummyAdapter.__module__}.DummyAdapter",
        "sirup_types": ["weather_forecast"],
        "metadata": {"fail_first": fail_first, "raise_error": raise_error},
    })
    return factory


def make_schedule():
    return VendorSchedule(
        vendor_name="dummy",
        interval_seconds=60,
        tasks=[TaskSpec(geoid="geo-1", sirup_type=SIRUPType.WEATHER_FORECAST)],
    )


def test_successful_run_delivers_bite_to_sink():
    received = []
    runtime = TAPRuntime(make_factory(), received.append, sleep=lambda s: None)
    report = runtime.run_once(make_schedule())
    assert report.succeeded == 1 and report.failed == 0
    assert len(received) == 1
    bite = received[0]
    assert bite["Header"]["geoid"] == "geo-1"
    assert bite["Body"]["sirup_data"]["temperature_mean"] == 21.5
    assert bite["Footer"]["hash"]


def test_retry_then_success():
    received = []
    sleeps = []
    runtime = TAPRuntime(
        make_factory(fail_first=2), received.append,
        max_retries=3, backoff_base_seconds=1.0, sleep=sleeps.append,
    )
    report = runtime.run_once(make_schedule())
    assert report.succeeded == 1
    assert report.results[0].attempts == 3
    assert sleeps == [1.0, 2.0]  # exponential backoff
    assert len(received) == 1


def test_exhausted_retries_reported_not_raised():
    received = []
    runtime = TAPRuntime(
        make_factory(fail_first=10, raise_error=True), received.append,
        max_retries=3, sleep=lambda s: None,
    )
    report = runtime.run_once(make_schedule())
    assert report.failed == 1
    assert report.results[0].attempts == 3
    assert "vendor exploded" in report.results[0].error
    assert received == []


def test_unregistered_vendor_reported():
    runtime = TAPRuntime(TAPAdapterFactory(), lambda b: None, sleep=lambda s: None)
    report = runtime.run_once(make_schedule())
    assert report.failed == 1
    assert report.results[0].error == "adapter not registered"


def test_schedule_from_config():
    config = {
        "vendor_name": "dummy",
        "schedule": {
            "interval_seconds": 900,
            "tasks": [
                {"geoid": "g1", "sirup_type": "weather_forecast", "params": {"days": 7}},
                {"geoid": "g2", "sirup_type": "satellite_imagery"},
            ],
        },
    }
    schedule = schedule_from_config(config)
    assert schedule.interval_seconds == 900
    assert len(schedule.tasks) == 2
    assert schedule.tasks[0].params == {"days": 7}
    assert schedule_from_config({"vendor_name": "x"}) is None


def test_config_env_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("TP_SECRET", "s3cret")
    monkeypatch.setenv("TP_CLIENT", "client-1")
    config = tmp_path / "vendors.yaml"
    config.write_text(
        """
vendors:
  - vendor_name: terrapipe
    adapter_class: x.Y
    base_url: https://appserver.terrapipe.io
    credentials:
      secretkey: ${TP_SECRET}
      client: ${TP_CLIENT}
"""
    )
    vendors = load_vendor_configs(str(config))
    assert vendors[0]["credentials"] == {"secretkey": "s3cret", "client": "client-1"}


def test_config_missing_env_is_hard_error(tmp_path, monkeypatch):
    monkeypatch.delenv("NOPE_MISSING", raising=False)
    config = tmp_path / "vendors.yaml"
    config.write_text(
        """
vendors:
  - vendor_name: v
    adapter_class: x.Y
    credentials:
      key: ${NOPE_MISSING}
"""
    )
    with pytest.raises(MissingEnvironmentVariable):
        load_vendor_configs(str(config))
