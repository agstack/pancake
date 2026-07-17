"""Shared helpers for weather TAP adapters.

Weather SIRUP body contract (what consumers like agstack-pnd read from a BITE):

    Body.sirup_data = {
        "period":     {"start": ISO8601-date, "end": ISO8601-date},
        "resolution": "hourly" | "hourly-synthesized-from-daily",
        "timestamps": [ISO8601 datetime, ...],        # one per hour
        "series":     {                                # aligned with timestamps
            "air_temperature":  [float, ...],
            "relative_humidity":[float, ...],
            "precipitation":    [float, ...],          # mm in that hour
            "wind_speed":       [float, ...],
            "dew_point":        [float, ...],
        },
        "daily": [ {"date":..., "t_min":..., "t_max":..., "precip":..., "rh_mean":...}, ... ],
    }

Pancake carries no numpy dependency, so synthesis is plain-Python. The synthesis
mirrors the agstack-pnd NOAA provider (sinusoidal diurnal temperature) so that
"weather from a BITE" behaves like "weather from NOAA" for the models.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

STANDARD_FIELDS = [
    "air_temperature",
    "relative_humidity",
    "precipitation",
    "wind_speed",
    "dew_point",
]

UNITS = {
    "air_temperature": "degC",
    "relative_humidity": "percent",
    "precipitation": "mm",
    "wind_speed": "m/s",
    "dew_point": "degC",
}


def _dew_point(temp_c: float, rh_pct: float) -> float:
    """Magnus-formula dew point; RH clamped to a sane range."""
    rh = max(1.0, min(100.0, rh_pct))
    a, b = 17.27, 237.7
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh / 100.0)
    return (b * gamma) / (a - gamma)


def synthesize_hourly(daily: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Expand daily records into an hourly weather SIRUP body.

    Each daily record needs: ``date`` (date or ISO string), ``t_min``, ``t_max``,
    ``precip`` (mm/day), ``rh_mean`` (%), ``wind`` (m/s). Missing values get
    conservative defaults so a model always has something to run on.
    """
    timestamps: List[str] = []
    series: Dict[str, List[float]] = {f: [] for f in STANDARD_FIELDS}
    daily_out: List[Dict[str, Any]] = []

    for rec in daily:
        d = rec["date"]
        if isinstance(d, str):
            d = date.fromisoformat(d[:10])
        t_min = float(rec.get("t_min", 10.0))
        t_max = float(rec.get("t_max", 25.0))
        precip = float(rec.get("precip", 0.0))
        rh_mean = float(rec.get("rh_mean", 70.0))
        wind = float(rec.get("wind", 2.0))
        daily_out.append(
            {"date": d.isoformat(), "t_min": t_min, "t_max": t_max,
             "precip": precip, "rh_mean": rh_mean, "wind": wind}
        )

        avg = (t_min + t_max) / 2.0
        amp = (t_max - t_min) / 2.0
        for h in range(24):
            ts = datetime(d.year, d.month, d.day, h, tzinfo=timezone.utc)
            # Diurnal temperature: min ~06:00, max ~15:00.
            temp = avg + amp * math.sin(math.pi * (h - 6) / 12.0)
            # RH is anti-correlated with temperature within the day.
            rh = max(15.0, min(100.0, rh_mean + (avg - temp) * 2.5))
            # Spread daily precip across the wettest part of the afternoon.
            hourly_precip = (precip / 6.0) if 12 <= h < 18 else 0.0
            timestamps.append(ts.isoformat())
            series["air_temperature"].append(round(temp, 2))
            series["relative_humidity"].append(round(rh, 1))
            series["precipitation"].append(round(hourly_precip, 3))
            series["wind_speed"].append(round(wind, 2))
            series["dew_point"].append(round(_dew_point(temp, rh), 2))

    period = {
        "start": daily_out[0]["date"] if daily_out else None,
        "end": daily_out[-1]["date"] if daily_out else None,
    }
    return {
        "period": period,
        "resolution": "hourly-synthesized-from-daily",
        "timestamps": timestamps,
        "series": series,
        "daily": daily_out,
    }


def build_weather_sirup(
    geoid: str,
    vendor: str,
    sirup_type_value: str,
    body: Dict[str, Any],
    source: str,
    extra_metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Wrap a weather body into the SIRUP envelope the runtime expects."""
    metadata = {
        "source": source,
        "resolution": body.get("resolution"),
        "field_count": len(body.get("series", {})),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return {
        "sirup_type": sirup_type_value,
        "vendor": vendor,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "geoid": geoid,
        "data": body,
        "metadata": metadata,
        "units": UNITS,
    }


def default_date_window(params: Dict[str, Any], forecast: bool) -> tuple[date, date]:
    """Resolve a (start, end) window from params with sensible defaults."""
    today = datetime.now(timezone.utc).date()
    if params.get("start_date") and params.get("end_date"):
        return (
            date.fromisoformat(str(params["start_date"])[:10]),
            date.fromisoformat(str(params["end_date"])[:10]),
        )
    days = int(params.get("days", 7))
    if forecast:
        return today, today + timedelta(days=days)
    return today - timedelta(days=days), today
