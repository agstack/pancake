#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




import requests
from typing import Dict, Any, Optional
from datetime import datetime
from tap_adapter_base import TAPAdapter, SIRUPType, create_bite_from_sirup

class NOAAWeatherAdapter(TAPAdapter):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.headers = {'User-Agent': 'PancakeLocalAgent/1.0 (contact@yourdomain.com)'}

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        lat, lon = params.get("lat"), params.get("lon")
        
        # 1. Get the grid points for the coordinates
        points_url = f"{self.base_url}/points/{lat},{lon}"
        res = requests.get(points_url, headers=self.headers).json()
        
        # 2. Get the hourly forecast URL from the points metadata
        forecast_url = res.get('properties', {}).get('forecastHourly')
        if not forecast_url: return None
        
        return requests.get(forecast_url, headers=self.headers).json()

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        periods = vendor_data.get('properties', {}).get('periods', [])
        weather_data = [{
            "time": p.get("startTime"),
            "temp": p.get("temperature"),
            "unit": p.get("temperatureUnit"),
            "description": p.get("shortForecast")
        } for p in periods[:24]] 
        return {
            "sirup_type": "weather_data",
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {"forecast": weather_data}
        }

    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sirup["geoid"] = geoid
        return create_bite_from_sirup(sirup, "weather_data", ["usa", "forecast", "noaa"])
