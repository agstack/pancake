"""Weather adapter: the GFS forecast at the grid point nearest the field.

This is the second TerraPipe weather adapter in the tree and it is not a
replacement for the first. ``terrapipe_weather.TerrapipeWeatherAdapter`` calls
the legacy ``/getGFSStats`` endpoint, which resolves v1 identifiers only and
averages every grid point in a 250 km cell; this one calls a terrapipe-os node,
which resolves AR2 GeoIDs and reports the single nearest grid point with its
distance. Both exist because the legacy backend is still what some deployments
have.

The awkward decision, made explicitly
-------------------------------------

Pancake's weather SIRUP contract is hourly, and the existing adapters satisfy
it by synthesising hourly values from daily statistics -- a sinusoidal diurnal
curve, marked ``hourly-synthesized-from-daily``. GFS does not publish hourly;
it publishes forecast steps, typically three-hourly, and the node returns them
as published precisely so that nobody has to wonder whether a number was
modelled or interpolated.

So this adapter emits the series at the model's own step and marks
``resolution`` with that step. It does **not** synthesise hourly. A consumer
that needs hourly can interpolate and will know it did; a consumer that
interpolates a value this adapter invented could not tell. The body keeps the
contract's shape -- ``timestamps`` plus aligned ``series`` -- so a reader that
walks the arrays works either way, and ``resolution`` is the field that says
what it is walking.

The forecast is also honest about where it applies. A quarter-degree grid point
stands for a box roughly thirty kilometres across, so ``metadata`` carries the
point's coordinates and its distance from the field. This is the weather over
the district, and the BITE says so.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pancake_services.tap.adapter_base import SIRUPType
from pancake_services.tap.adapters.terrapipe_os.base import (
    VENDOR_DEFAULT,
    TerrapipeOSAdapter,
    envelope,
)

# GFS columns renamed into the SIRUP weather vocabulary, with the unit
# conversion each rename requires. Only exact conversions appear here: kelvin
# to celsius is a subtraction, and a kilogram of water per square metre is a
# millimetre of depth by definition. Renaming without converting would be the
# worst of the options -- a consumer reading ``air_temperature`` per the
# weather contract expects degrees celsius and would silently get 295.
#
# Anything not named here keeps the node's own column name and the node's own
# unit. An unmapped variable is still data; dropping it to keep the vocabulary
# tidy would lose it, and renaming it without knowing its unit would corrupt it.
CONVERSIONS = {
    "t2m": ("air_temperature", "degC", lambda v: round(v - 273.15, 2)),
    "d2m": ("dew_point", "degC", lambda v: round(v - 273.15, 2)),
    "r2": ("relative_humidity", "percent", lambda v: round(v, 1)),
    "tp": ("precipitation", "mm", lambda v: round(v, 3)),
}

DEFAULT_DAYS = 7


class WeatherForecastAdapter(TerrapipeOSAdapter):
    """Emits a ``weather_forecast`` SIRUP from ``GET /forecast/{geoid}``."""

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        today = datetime.now(timezone.utc).date()
        if params.get("start_date") and params.get("end_date"):
            start, end = str(params["start_date"])[:10], str(params["end_date"])[:10]
        else:
            days = int(params.get("days", DEFAULT_DAYS))
            start, end = today.isoformat(), (today + timedelta(days=days)).isoformat()

        forecast = self.call(
            "forecast", geoid, lambda: self.client.forecast(geoid, start=start, end=end)
        )
        if forecast is None:
            return None
        return {"_geoid": geoid, "_start": start, "_end": end, "forecast": forecast}

    def transform_to_sirup(
        self, vendor_data: Dict[str, Any], sirup_type: SIRUPType
    ) -> Optional[Dict[str, Any]]:
        forecast = vendor_data["forecast"]
        steps = forecast.get("steps") or []
        if not steps:
            # The node answered but the store held no step in the window. That
            # is a coverage fact, not a forecast, and it must not be stored as one.
            return None

        timestamps: List[str] = []
        series: Dict[str, List[Any]] = {}
        units: Dict[str, str] = {}
        node_units = {k: v.get("unit") for k, v in (forecast.get("variables") or {}).items()}
        converted: Dict[str, str] = {}

        for index, step in enumerate(steps):
            timestamps.append(step.get("valid_time"))
            for key, value in step.items():
                if key in ("valid_time", "forecast_hour"):
                    continue
                if key in CONVERSIONS and isinstance(value, (int, float)):
                    name, unit, convert = CONVERSIONS[key]
                    value = convert(value)
                    converted[key] = f"{key} ({node_units.get(key)}) -> {name} ({unit})"
                else:
                    name, unit = key, node_units.get(key)
                units[name] = unit
                column = series.setdefault(name, [None] * index)
                column.append(value)
            # Keep every column aligned with timestamps even when a step is
            # missing a variable: a shorter array read positionally would
            # attribute one step's value to another.
            for column in series.values():
                while len(column) < len(timestamps):
                    column.append(None)

        body = {
            "period": {"start": vendor_data["_start"], "end": vendor_data["_end"]},
            "resolution": _resolution_of(steps),
            "timestamps": timestamps,
            "series": series,
            "grid_point": forecast.get("grid_point"),
            "distance_km": forecast.get("distance_km"),
        }
        metadata = {
            "source": "terrapipe-os GFS reader (nearest grid point, not interpolated)",
            "node": self.client.base_url,
            "model": "NOAA GFS 0.25 degree",
            "resolution": body["resolution"],
            "field_count": len(series),
            "cell_token": forecast.get("cell_token"),
            "grid_point": forecast.get("grid_point"),
            "distance_km": forecast.get("distance_km"),
            "grid_points_in_partition": forecast.get("grid_points_in_partition"),
            "files_read": forecast.get("files_read"),
            "notes": forecast.get("notes") or [],
            "provenance": forecast.get("provenance") or {},
            "variable_descriptions": {
                k: v.get("description") for k, v in (forecast.get("variables") or {}).items()
            },
            "unit_conversions": sorted(converted.values()),
            "interpretation": (
                "One grid point about 30 km across, nearest the field, reported as published. "
                "Steps are the model's own; no hourly interpolation has been applied. "
                "Renamed variables were unit-converted exactly; the rest keep the model's own "
                "column names and units."
            ),
        }
        return envelope(
            geoid=vendor_data["_geoid"],
            vendor=self.vendor_name or VENDOR_DEFAULT,
            sirup_type_value=sirup_type.value,
            data=body,
            metadata=metadata,
            units=units,
        )

    def bite_tags(self) -> list:
        return ["terrapipe-os", "open-science", "weather", "gfs"]


def _resolution_of(steps: List[Dict[str, Any]]) -> str:
    """The model's own step, named from the data rather than assumed."""
    hours = [s.get("forecast_hour") for s in steps if isinstance(s.get("forecast_hour"), (int, float))]
    if len(hours) < 2:
        return "single-step"
    gaps = {round(b - a) for a, b in zip(hours, hours[1:]) if b > a}
    if len(gaps) == 1:
        return f"{gaps.pop()}-hourly (GFS forecast steps, not interpolated)"
    return "irregular (GFS forecast steps, not interpolated)"
