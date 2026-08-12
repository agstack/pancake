"""Offline seed weather adapter.

Writes canned-but-realistic hourly weather BITEs so the DPI demo runs with no
vendor credentials and no network. Deterministic per (geoid, date) so repeated
runs dedupe cleanly in the BITE store.

This is a demo convenience, never a production data source: every BITE it emits
is tagged ``seed`` and marked ``resolution: hourly-synthesized-from-daily``.
"""
from __future__ import annotations

import hashlib
import math
from datetime import timedelta
from typing import Any, Dict, Optional

from pancake_services.tap.adapter_base import SIRUPType, TAPAdapter, create_bite_from_sirup
from pancake_services.tap.adapters.weather_common import (
    build_weather_sirup,
    default_date_window,
    synthesize_hourly,
)


def _seeded_unit(geoid: str, day_ordinal: int, salt: str) -> float:
    """Deterministic pseudo-random in [0,1) from geoid+day, no global RNG state."""
    h = hashlib.sha256(f"{geoid}:{day_ordinal}:{salt}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class SeedWeatherAdapter(TAPAdapter):
    """Deterministic offline weather generator (demo fallback)."""

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        forecast = params.get("mode", "historical") == "forecast"
        start, end = default_date_window(params, forecast=forecast)

        daily = []
        d = start
        while d <= end:
            o = d.toordinal()
            # Seasonal baseline + field-specific offset, mild day-to-day variation.
            seasonal = 18.0 + 8.0 * math.sin(2 * math.pi * (d.timetuple().tm_yday / 365.0))
            field_offset = (_seeded_unit(geoid, 0, "field") - 0.5) * 4.0
            swing = 6.0 + 4.0 * _seeded_unit(geoid, o, "swing")
            t_mean = seasonal + field_offset + (_seeded_unit(geoid, o, "day") - 0.5) * 3.0
            rain_roll = _seeded_unit(geoid, o, "rain")
            precip = round(max(0.0, (rain_roll - 0.6) * 30.0), 2)  # ~40% of days wet
            rh_mean = 60.0 + 30.0 * rain_roll  # wetter days are more humid
            daily.append({
                "date": d,
                "t_min": round(t_mean - swing / 2.0, 2),
                "t_max": round(t_mean + swing / 2.0, 2),
                "precip": precip,
                "rh_mean": round(min(98.0, rh_mean), 1),
                "wind": round(1.0 + 3.0 * _seeded_unit(geoid, o, "wind"), 2),
            })
            d += timedelta(days=1)

        return {"_geoid": geoid, "_forecast": forecast, "daily": daily}

    def transform_to_sirup(
        self, vendor_data: Dict[str, Any], sirup_type: SIRUPType
    ) -> Optional[Dict[str, Any]]:
        body = synthesize_hourly(vendor_data["daily"])
        return build_weather_sirup(
            geoid=vendor_data["_geoid"],
            vendor=self.vendor_name,
            sirup_type_value=sirup_type.value,
            body=body,
            source="seed (offline demo generator)",
            extra_metadata={"synthetic": True},
        )

    def sirup_to_bite(
        self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        bite_type = sirup["sirup_type"]  # weather_historical | weather_forecast
        bite = create_bite_from_sirup(sirup, bite_type, ["weather", "seed", "synthetic"])
        if geoid:
            bite["Header"]["geoid"] = geoid
        return bite
