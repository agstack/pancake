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
import json
from datetime import datetime
from typing import Dict, Any, Optional
from tap_adapter_base import TAPAdapter, SIRUPType, create_bite_from_sirup

class USDAArmsAdapter(TAPAdapter):
    """
    Adapter for USDA ARMS API - Financial benchmarks for US agriculture.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = self.credentials.get("api_key")

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fips_map = {"IA": "19", "TX": "48", "CA": "06", "NE": "31"}
        state_code = fips_map.get(geoid.split('_')[1], "19")

        url = f"{self.base_url}/surveydata"
        query_params = {
            "api_key": self.api_key,
            "state": state_code,
            "year": params.get("year", 2023),
            "report": params.get("report", "Farm Business Income Statement"),
            "variable": params.get("variable", "Total cash expenses")
        }
        
        response = requests.get(url, params=query_params)
        return response.json() if response.status_code == 200 else {}


    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:

        records = vendor_data.get("data") or []
        
        for r in records:

            if r.get("category") == "All Farms" and r.get("categoryValue") == "TOTAL":

                return {
                    "sirup_type": "financial_benchmark",
                    "vendor": self.vendor_name,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "data": {

                        "total_farm_expense": float(str(r.get("estimate")).replace(',', ''))
                    }
                }
        return None

    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sirup["geoid"] = geoid
        return create_bite_from_sirup(sirup, "financial_benchmark", ["usa", "finance", "economics"])
