"""TAP worker: wire vendor adapters to the BITE store and run the scheduler.

    python -m pancake_services.tap.worker --config dpi-demo/tap_vendors.yaml
    python -m pancake_services.tap.worker --config ... --once   # single pass, then exit

The frozen ingest interface is ``BiteStore.save`` (pancake_services.store.bites).
Vendors whose ``enabled_if_env`` variable is empty/unset are skipped -- this is how
the demo degrades from live TerraPipe to the offline seed adapter with no edits.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Dict, List

import yaml

from pancake_services.common.config import load_settings
from pancake_services.common.db import Base, make_engine, make_session_factory
from pancake_services.store.bites import BiteStore
from pancake_services.tap.adapter_base import TAPAdapterFactory
from pancake_services.tap.config import _interpolate
from pancake_services.tap.runtime import TAPRuntime, VendorSchedule, schedule_from_config

logger = logging.getLogger("pancake.tap.worker")


def _enabled(vendor_raw: Dict[str, Any]) -> bool:
    """A vendor is skipped if its ``enabled_if_env`` variable is empty/unset."""
    gate = vendor_raw.get("enabled_if_env")
    if not gate:
        return True
    return bool(os.environ.get(gate, "").strip())


def load_enabled_vendors(config_path: str) -> List[Dict[str, Any]]:
    """Load vendor configs, skipping gated-off vendors and interpolating the rest."""
    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}
    vendors: List[Dict[str, Any]] = []
    for vendor_raw in raw.get("vendors", []):
        if not _enabled(vendor_raw):
            logger.info("skipping vendor %s (gate %s is empty)",
                        vendor_raw.get("vendor_name"), vendor_raw.get("enabled_if_env"))
            continue
        vendors.append(_interpolate(vendor_raw))
    return vendors


def build_runtime(config_path: str) -> tuple[TAPRuntime, List[VendorSchedule]]:
    settings = load_settings()
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    store = BiteStore(make_session_factory(engine))

    factory = TAPAdapterFactory()
    schedules: List[VendorSchedule] = []
    for vendor in load_enabled_vendors(config_path):
        factory.register_adapter(vendor)
        schedule = schedule_from_config(vendor)
        if schedule:
            schedules.append(schedule)

    runtime = TAPRuntime(factory, store.save)
    return runtime, schedules


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pancake TAP ingestion worker")
    parser.add_argument("--config", required=True, help="Path to vendor config YAML")
    parser.add_argument("--once", action="store_true", help="Run one pass and exit")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    runtime, schedules = build_runtime(args.config)
    if not schedules:
        logger.warning("no enabled vendors with schedules; nothing to do")
        return 0

    logger.info("TAP worker starting: %d vendor schedule(s)", len(schedules))
    if args.once:
        for schedule in schedules:
            report = runtime.run_once(schedule)
            logger.info("vendor=%s ok=%d failed=%d",
                        schedule.vendor_name, report.succeeded, report.failed)
        return 0

    try:
        runtime.run_forever(schedules)
    except KeyboardInterrupt:
        runtime.stop()
        logger.info("TAP worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
