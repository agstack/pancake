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

class SoilDataAdapter(TAPAdapter):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        lat, lon = params.get("lat"), params.get("lon")
        
        sql_query = f"""
            SELECT TOP 1 mu.muname, ch.om_r 
            FROM mapunit mu 
            INNER JOIN component co ON mu.mukey = co.mukey 
            INNER JOIN chorizon ch ON co.cokey = ch.cokey 
            WHERE mu.mukey IN (
                SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('POINT({lon} {lat})')
            )
        """
        
        payload = {"query": sql_query, "format": "json"}
        response = requests.post(self.base_url, data=payload)
        return response.json() if response.status_code == 200 else None

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:

        table = vendor_data.get("Table")
        

        if not table or len(table) < 1:
            print(f"⚠️ No soil data found in SDA for this coordinate.")
            return None
        

        row = table[0]
        muname = row[0] if len(row) > 0 else "Unknown Map Unit"
        om_r = row[1] if len(row) > 1 and row[1] is not None else 0.0

        return {
            "sirup_type": sirup_type.value,
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "map_unit_name": muname,
                "organic_matter_r_factor": float(om_r),
            },
            "metadata": {
                "source": "USDA NRCS Soil Data Access (SDA)",
                "query_type": "Point-in-Polygon Intersection"
            }
        }


    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sirup["geoid"] = geoid
        return create_bite_from_sirup(sirup, "soil_data", ["usa", "nrcs", "soil_health"])
