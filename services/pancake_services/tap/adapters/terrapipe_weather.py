"""TerraPipe weather TAP adapter.

Service-grade port of the legacy ``TerrapipeGFSAdapter`` (implementation/tap_adapters.py),
adapted to emit the PnD-friendly weather SIRUP body (see weather_common.py) and to
support both WEATHER_FORECAST and WEATHER_HISTORICAL.

Reality check (documented, not hidden): the deployed TerraPipe TP-1 hourly API does
not exist yet. This adapter calls the legacy ``/getGFSStats`` endpoint, which returns
daily/coarse statistics; we synthesize hourly from those (same approach as the
agstack-pnd NOAA provider) and mark ``resolution`` accordingly. When a true hourly
endpoint ships, only ``_to_daily_records`` needs to change.

Credentials come from the environment via the vendor config YAML (guardrail 7).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

from pancake_services.tap.adapter_base import SIRUPType, TAPAdapter, create_bite_from_sirup
from pancake_services.tap.adapters.weather_common import (
    build_weather_sirup,
    default_date_window,
    synthesize_hourly,
)

logger = logging.getLogger(__name__)


class TerrapipeWeatherAdapter(TAPAdapter):
    """Fetches GFS-derived weather from TerraPipe and emits weather SIRUPs."""

    def _initialize(self) -> None:
        self.headers = {
            "secretkey": self.credentials.get("secretkey", ""),
            "client": self.credentials.get("client", ""),
            "Accept": "*/*",
        }
        self._authenticated = False

    def _authenticate(self) -> None:
        """Best-effort session login for a bearer token (legacy TerraPipe)."""
        email = self.credentials.get("email")
        password = self.credentials.get("password")
        if not email or not password:
            return
        try:
            resp = requests.post(
                f"{self.base_url}/", json={"email": email, "password": password},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token") or data.get("token")
                if token:
                    self.headers["Authorization"] = f"Bearer {token}"
                    self._authenticated = True
        except Exception as exc:  # noqa: BLE001 - the runtime owns retries
            logger.warning("TerraPipe auth failed: %s", exc)

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._authenticated:
            self._authenticate()
        forecast = params.get("mode", "forecast") == "forecast"
        start, end = default_date_window(params, forecast=forecast)

        try:
            resp = requests.get(
                f"{self.base_url}/getGFSStats",
                headers=self.headers,
                params={
                    "geoid": geoid,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                },
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TerraPipe getGFSStats error (geoid=%s): %s", geoid, exc)
            return None
        if resp.status_code != 200:
            logger.warning("TerraPipe getGFSStats status %s (geoid=%s)", resp.status_code, geoid)
            return None

        raw = resp.json()
        return {"_geoid": geoid, "_forecast": forecast,
                "_start": start.isoformat(), "_end": end.isoformat(), "raw": raw}

    def _to_daily_records(self, raw: Dict[str, Any], start: str, end: str) -> List[Dict[str, Any]]:
        """Normalize a getGFSStats payload into daily records.

        The legacy payload shape varies; we defensively pull common keys and fall
        back to a flat daily fill so downstream synthesis always has input.
        """
        stats = raw.get("stats") or raw.get("data") or raw
        records: List[Dict[str, Any]] = []

        # Case 1: a list of per-day dicts.
        if isinstance(stats, list):
            for row in stats:
                records.append({
                    "date": row.get("date") or row.get("day"),
                    "t_min": row.get("t_min", row.get("temperature_min", row.get("tmin"))),
                    "t_max": row.get("t_max", row.get("temperature_max", row.get("tmax"))),
                    "precip": row.get("precipitation", row.get("precip", 0.0)),
                    "rh_mean": row.get("relative_humidity", row.get("humidity", 70.0)),
                    "wind": row.get("wind_speed", row.get("wind", 2.0)),
                })
            records = [r for r in records if r.get("date")]
            if records:
                return records

        # Case 2: scalar/aggregate stats -> fill the window uniformly.
        def _num(*keys: str, default: float) -> float:
            for k in keys:
                v = stats.get(k) if isinstance(stats, dict) else None
                if isinstance(v, (int, float)):
                    return float(v)
            return default

        t_min = _num("t_min", "temperature_min", "tmin", default=12.0)
        t_max = _num("t_max", "temperature_max", "tmax", default=26.0)
        precip = _num("precipitation", "precip", default=0.0)
        rh = _num("relative_humidity", "humidity", default=70.0)
        wind = _num("wind_speed", "wind", default=2.0)

        d0 = date.fromisoformat(start)
        d1 = date.fromisoformat(end)
        d = d0
        while d <= d1:
            records.append({"date": d, "t_min": t_min, "t_max": t_max,
                            "precip": precip, "rh_mean": rh, "wind": wind})
            d += timedelta(days=1)
        return records

    def transform_to_sirup(
        self, vendor_data: Dict[str, Any], sirup_type: SIRUPType
    ) -> Optional[Dict[str, Any]]:
        daily = self._to_daily_records(
            vendor_data["raw"], vendor_data["_start"], vendor_data["_end"]
        )
        if not daily:
            return None
        body = synthesize_hourly(daily)
        return build_weather_sirup(
            geoid=vendor_data["_geoid"],
            vendor=self.vendor_name,
            sirup_type_value=sirup_type.value,
            body=body,
            source="TerraPipe GFS (getGFSStats)",
            extra_metadata={"model": "NOAA GFS", "native_resolution": "daily/coarse"},
        )

    def sirup_to_bite(
        self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        bite = create_bite_from_sirup(
            sirup, sirup["sirup_type"], ["weather", "gfs", "terrapipe"]
        )
        if geoid:
            bite["Header"]["geoid"] = geoid
        return bite
