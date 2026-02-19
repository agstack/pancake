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
class USDANASSAdapter(TAPAdapter):
    """
    Adapter for USDA NASS Quick Stats API.
    Provides: MARKET_PRICE and regional Yield data.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = self.credentials.get("api_key")


    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        query_params = {
            "key": self.api_key,
            "state_fips_code": params.get('fips'),
            "commodity_desc": params.get('commodity'),
            "year": params.get("year", 2024),

            "statisticcat_desc": params.get("statisticcat_desc", ["YIELD", "AREA HARVESTED", "OPERATIONS WITH AREA HARVESTED"])
        }
        response = requests.get(self.base_url, params=query_params,  verify=False)
        return response.json() if response.status_code == 200 else None

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        records = vendor_data.get('data', [])
        if not records: return None

        def clean_val(val):
            return float(str(val).replace(',', '')) if val else 0.0


        yield_val = next((r['Value'] for r in records if r['statisticcat_desc'] == 'YIELD'), 0)
        acres_val = next((r['Value'] for r in records if r['statisticcat_desc'] == 'AREA HARVESTED'), 0)

        farms_count = next((r['Value'] for r in records if 'OPERATIONS' in r['statisticcat_desc']), 0)

        c_yield = clean_val(yield_val)
        c_acres = clean_val(acres_val)
        c_farms = clean_val(farms_count)

        avg_acres = c_acres / c_farms if c_farms > 0 else 445.0 

        return {
            "sirup_type": "market_price",
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": { 
                "yield_per_acre": c_yield,
                "avg_acres_per_farm": avg_acres
            }
        }
    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Wrap USDA SIRUP into a BITE packet for Pancake ingestion"""
        sirup["geoid"] = geoid
        
        bite = create_bite_from_sirup(
            sirup=sirup,
            bite_type="market_price",
            additional_tags=["usda", "statistics", params.get("commodity", "CORN").lower()]
        )
        return bite
