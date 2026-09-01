"""NDVI adapter: a vegetation index reading for a field on a date.

NDVI is an index, not a measurement of any physical quantity, and one date is
heavily affected by cloud and haze. Two consequences are built in here rather
than left to the consumer:

- The SIRUP is unitless and typed ``vegetation_index`` rather than
  ``satellite_imagery``. There is no image in it; there is one area-weighted
  number per date over the field.
- A run asks for several dates and stores what came back. A date with no
  acquisition is absent from the series and listed in ``dates_absent`` with
  the node's reason, so a gap is visible as a gap. Interpolating across it
  here would manufacture a reading on a day the satellite did not see the
  field.

The node partitions NDVI by day, so each date is a separate read. A missing
date is ordinary and cheap; the adapter does not retry it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pancake_services.tap.adapter_base import SIRUPType
from pancake_services.tap.adapters.terrapipe_os.base import (
    VENDOR_DEFAULT,
    TerrapipeOSAdapter,
    envelope,
)
from pancake_services.tap.adapters.terrapipe_os.client import NoDataHere, TerrapipeOSError

DEFAULT_LAYER = "ndvi_sentinel2"
DEFAULT_DAYS = 30


class VegetationIndexAdapter(TerrapipeOSAdapter):
    """Emits a ``vegetation_index`` SIRUP from ``GET /data/{geoid}/{layer}``."""

    def _dates(self, params: Dict[str, Any]) -> List[str]:
        if params.get("dates"):
            return [str(d)[:10] for d in params["dates"]]
        if params.get("date"):
            return [str(params["date"])[:10]]
        today = datetime.now(timezone.utc).date()
        if params.get("start_date") and params.get("end_date"):
            start = date.fromisoformat(str(params["start_date"])[:10])
            end = date.fromisoformat(str(params["end_date"])[:10])
        else:
            end = today
            start = today - timedelta(days=int(params.get("days", DEFAULT_DAYS)))
        return [(start + timedelta(days=n)).isoformat() for n in range((end - start).days + 1)]

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        layer_id = params.get("layer_id", DEFAULT_LAYER)
        grant = self.grant_for(geoid, params)
        readings: List[Dict[str, Any]] = []
        absent: Dict[str, str] = {}

        for day in self._dates(params):
            try:
                reading = self.client.read_layer(geoid, layer_id, grant=grant, time_value=day)
                # The date is carried alongside rather than read back out of the
                # response: the node reports the reading, not the question.
                readings.append({"date": day, "reading": reading})
            except NoDataHere:
                absent[day] = "no_acquisition"
            except TerrapipeOSError as exc:
                if exc.reason in ("grant_required", "grant_refused"):
                    # No point asking for the remaining dates: the refusal is
                    # about the field, not about the day.
                    return None
                if exc.reason in ("geoid_not_found", "layer_not_found", "store_unavailable"):
                    return None
                raise

        if not readings:
            # Every date came back empty. That is a real finding about coverage
            # but it is not a vegetation reading, and a BITE of nothing would
            # sit in the store looking like one.
            return None
        return {
            "_geoid": geoid,
            "_layer_id": layer_id,
            "_grant_presented": bool(grant),
            "readings": readings,
            "absent": absent,
        }

    def transform_to_sirup(
        self, vendor_data: Dict[str, Any], sirup_type: SIRUPType
    ) -> Optional[Dict[str, Any]]:
        readings = vendor_data["readings"]
        points = [
            {
                "date": item["date"],
                "value": item["reading"].get("value"),
                "coverage_fraction": item["reading"].get("coverage_fraction"),
                "complete": item["reading"].get("complete"),
                "cells_read": item["reading"].get("cells_read"),
                "method": item["reading"].get("method"),
            }
            for item in readings
        ]
        covered = [
            p["coverage_fraction"] for p in points if isinstance(p["coverage_fraction"], (int, float))
        ]
        first = readings[0]["reading"]
        data = {
            "layer_id": vendor_data["_layer_id"],
            "index": "ndvi",
            "series": points,
            "dates_absent": vendor_data["absent"],
        }
        metadata = {
            "source": "terrapipe-os",
            "node": self.client.base_url,
            "grant_presented": vendor_data["_grant_presented"],
            "cover": first.get("cover"),
            "dates_returned": len(points),
            "dates_absent": len(vendor_data["absent"]),
            "min_coverage_fraction": min(covered) if covered else None,
            "provenance": first.get("provenance") or {},
            "interpretation": (
                "An index, not a physical measurement. Single dates are affected by cloud and haze; "
                "read the series. Gaps are dates with no acquisition and are not interpolated."
            ),
        }
        return envelope(
            geoid=vendor_data["_geoid"],
            vendor=self.vendor_name or VENDOR_DEFAULT,
            sirup_type_value=sirup_type.value,
            data=data,
            metadata=metadata,
            units={"value": "dimensionless", "coverage_fraction": "fraction_of_field"},
        )

    def bite_tags(self) -> list:
        return ["terrapipe-os", "open-science", "ndvi", "vegetation"]
