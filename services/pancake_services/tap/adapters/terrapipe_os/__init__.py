"""Connector from Pancake to a terrapipe-os open-science node.

Three adapters over one client, each turning a node answer into a SIRUP and
then a BITE:

- :class:`~.deforestation.DeforestationAdapter` -- the EUDR screen for a GeoID
  (``land_use_screen``).
- :class:`~.vegetation.VegetationIndexAdapter` -- an NDVI reading for a date
  (``vegetation_index``).
- :class:`~.weather.WeatherForecastAdapter` -- the GFS forecast at the grid
  point nearest the field (``weather_forecast``).

The node is not a vendor in the usual sense: it holds no Pancake secret, it
authenticates the caller against the same hub Pancake does, and it answers at
whichever disclosure tier the presented grant allows. What that buys is in
``client.py``; what each adapter does with the answer is in its own module.

One rule holds across all three. Every reading the node returns carries a
coverage fraction and a provenance block, and both travel into the BITE. A
number without its coverage is not interpretable -- a screen over a tenth of a
field reads exactly like a clean one -- so an adapter that dropped them would
turn a hedged answer into a confident one.
"""

from pancake_services.tap.adapters.terrapipe_os.client import (
    GrantRequired,
    HubTokenSource,
    NoDataHere,
    TerrapipeOSClient,
    TerrapipeOSError,
)
from pancake_services.tap.adapters.terrapipe_os.deforestation import DeforestationAdapter
from pancake_services.tap.adapters.terrapipe_os.vegetation import VegetationIndexAdapter
from pancake_services.tap.adapters.terrapipe_os.weather import WeatherForecastAdapter

__all__ = [
    "DeforestationAdapter",
    "GrantRequired",
    "HubTokenSource",
    "NoDataHere",
    "TerrapipeOSClient",
    "TerrapipeOSError",
    "VegetationIndexAdapter",
    "WeatherForecastAdapter",
]
