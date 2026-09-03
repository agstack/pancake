"""The demo's own vendor file, loaded the way the worker loads it.

``dpi-demo/tap_vendors.yaml`` is configuration that nothing else executes, so a
typo in an adapter path or a sirup type sits there until the demo is run in
front of somebody. These tests load the real file, register the real adapter
classes from it, and check the gate behaves: no open-science node configured,
no open-science vendors.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pancake_services.tap.adapter_base import SIRUPType, TAPAdapterFactory
from pancake_services.tap.runtime import schedule_from_config
from pancake_services.tap.worker import load_enabled_vendors

CONFIG = Path(__file__).resolve().parents[2] / "dpi-demo" / "tap_vendors.yaml"

OPEN_SCIENCE = {
    "terrapipe-os-deforestation",
    "terrapipe-os-ndvi",
    "terrapipe-os-weather",
}


@pytest.fixture
def node_configured(monkeypatch):
    monkeypatch.setenv("TERRAPIPE_OS_URL", "http://terrapipe-os:8200")
    monkeypatch.setenv("TERRAPIPE_OS_CLIENT_ID", "pancake")
    monkeypatch.setenv("TERRAPIPE_OS_CLIENT_SECRET", "secret")
    monkeypatch.setenv("HUB_URL", "http://hub:8000")
    monkeypatch.delenv("TERRAPIPE_SECRET", raising=False)


def test_the_demo_config_is_present_and_parses(monkeypatch):
    for _v in ("TERRAPIPE_OS_URL", "TERRAPIPE_OS_CLIENT_ID", "TERRAPIPE_OS_CLIENT_SECRET"):
        monkeypatch.delenv(_v, raising=False)
    assert CONFIG.is_file(), CONFIG
    assert load_enabled_vendors(str(CONFIG)), "the seed vendor is always enabled"


def test_without_a_node_the_open_science_vendors_are_skipped(monkeypatch):
    monkeypatch.delenv("TERRAPIPE_OS_URL", raising=False)

    names = {v["vendor_name"] for v in load_enabled_vendors(str(CONFIG))}

    assert not (names & OPEN_SCIENCE), "an unconfigured node must not be scheduled"
    assert "seed" in names, "the demo must still have its offline path"


def test_with_a_node_all_three_adapters_register_and_schedule(node_configured):
    vendors = {v["vendor_name"]: v for v in load_enabled_vendors(str(CONFIG))}
    assert OPEN_SCIENCE <= set(vendors)

    factory = TAPAdapterFactory()
    for name in OPEN_SCIENCE:
        vendor = vendors[name]
        # Registering imports the class named in the file: this is the check
        # that catches a renamed or misspelled adapter path.
        adapter = factory.register_adapter(vendor)
        assert adapter is not None, name
        assert adapter.base_url == "http://terrapipe-os:8200"
        schedule = schedule_from_config(vendor)
        assert schedule and schedule.tasks, f"{name} has no tasks"
        for task in schedule.tasks:
            assert adapter.supports_sirup_type(task.sirup_type), (name, task.sirup_type)


def test_the_screen_vendor_asks_for_the_type_the_adapter_emits(node_configured):
    vendors = {v["vendor_name"]: v for v in load_enabled_vendors(str(CONFIG))}
    schedule = schedule_from_config(vendors["terrapipe-os-deforestation"])

    assert [t.sirup_type for t in schedule.tasks] == [SIRUPType.LAND_USE_SCREEN]
    # A verdict changes when an annual raster lands, not hourly.
    assert schedule.interval_seconds >= 86400


def test_credentials_are_interpolated_from_the_environment_not_hardcoded(node_configured):
    vendors = {v["vendor_name"]: v for v in load_enabled_vendors(str(CONFIG))}
    credentials = vendors["terrapipe-os-ndvi"]["credentials"]

    assert credentials["client_secret"] == "secret"
    assert credentials["hub_url"] == "http://hub:8000"

    # Structural, not textual: every credential value in the uninterpolated
    # file must be a ${VAR} reference. Grepping for the word "secret" would
    # match the key name `secretkey` and pass while a literal sat next to it.
    raw = yaml.safe_load(CONFIG.read_text())
    literals = [
        (vendor.get("vendor_name"), key, value)
        for vendor in raw["vendors"]
        for key, value in (vendor.get("credentials") or {}).items()
        if not (isinstance(value, str) and value.startswith("${") and value.endswith("}"))
    ]
    assert not literals, f"credentials must come from the environment: {literals}"


def test_no_grant_is_needed_to_start_and_one_is_picked_up_when_present(node_configured, monkeypatch):
    """The demo must start before any grant is issued, and sharpen once one is.

    Interpolation raises on an unset ``${VAR}``, so naming a grant in the file
    would make an absent grant fatal at startup instead of merely coarsening
    the answer. The grant is read per GeoID at request time instead.
    """
    monkeypatch.delenv("TERRAPIPE_OS_FIELD_GRANT", raising=False)
    assert "FIELD_GRANT" not in CONFIG.read_text()

    vendors = {v["vendor_name"]: v for v in load_enabled_vendors(str(CONFIG))}
    vendor = vendors["terrapipe-os-deforestation"]
    adapter = TAPAdapterFactory().register_adapter(vendor)
    geoid = "a" * 64

    assert adapter.grant_for(geoid, {}) is None, "no grant is a legitimate state"

    monkeypatch.setenv(vendor["metadata"]["grant_env_template"].format(geoid=geoid), "grant-jwt")
    assert adapter.grant_for(geoid, {}) == "grant-jwt"


def test_a_node_url_without_credentials_skips_the_vendor_rather_than_failing_the_load(monkeypatch):
    """The state Rajat's box was in on 2026-09-03, and what it used to cost.

    A terrapipe-os node was running and TERRAPIPE_OS_URL was set. The hub client
    credentials that go with it were not, because the node had been reached with
    a personal token instead. The vendor was gated on the URL alone, so it passed
    the gate, and interpolation then raised on ${TERRAPIPE_OS_CLIENT_ID} -- which
    is a hard error for the whole vendor file, taking the seed vendor and the
    offline demo path down with it.

    Half-configured must be skipped, not fatal.
    """
    monkeypatch.setenv("TERRAPIPE_OS_URL", "http://a-node:8200")
    monkeypatch.delenv("TERRAPIPE_OS_CLIENT_ID", raising=False)
    monkeypatch.delenv("TERRAPIPE_OS_CLIENT_SECRET", raising=False)

    names = {v["vendor_name"] for v in load_enabled_vendors(str(CONFIG))}

    assert not (names & OPEN_SCIENCE), "a node without credentials must not be scheduled"
    assert "seed" in names, "and it must not take the rest of the file down with it"


def test_the_demo_config_parses_whatever_is_in_the_ambient_environment(monkeypatch):
    """Deterministic in both directions, because it used to pass or fail by accident.

    Run on a laptop that happened to export TERRAPIPE_OS_URL, this file failed;
    run in CI, it passed. A test whose result depends on the shell it inherits
    is not reporting on the code.
    """
    for var in ("TERRAPIPE_OS_URL", "TERRAPIPE_OS_CLIENT_ID", "TERRAPIPE_OS_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    assert load_enabled_vendors(str(CONFIG)), "the seed vendor is always enabled"

    monkeypatch.setenv("TERRAPIPE_OS_URL", "http://a-node:8200")
    monkeypatch.setenv("TERRAPIPE_OS_CLIENT_ID", "id")
    monkeypatch.setenv("TERRAPIPE_OS_CLIENT_SECRET", "secret")
    fully = {v["vendor_name"] for v in load_enabled_vendors(str(CONFIG))}
    assert OPEN_SCIENCE <= fully
