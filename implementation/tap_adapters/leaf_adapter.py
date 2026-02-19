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

class LeafAdapter(TAPAdapter):
    """
    Universal Adapter via Leaf Agriculture.
    Unlocks JD, CNH, Trimble, and AGCO data through one endpoint.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = self.credentials.get("api_key")

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Leaf uses 'leafUserId' to identify the specific farmer
        leaf_user_id = params.get("leaf_user_id")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

        # Discovery: Fetching all fields managed by Leaf for this user
        response = requests.get(
            f"{self.base_url}/users/{leaf_user_id}/fields", 
            headers=headers
        )
        
        if response.status_code == 200:
            return {"fields": response.json()}
        return None

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        raw_fields = vendor_data.get("fields", [])
        
        # Standardizing different OEM field data into SIRUP format
        assets = [{
            "asset_id": f.get("id"),
            "category": "FIELD",
            "display_name": f.get("name"),
            "provider": f.get("providerValue"), # e.g., 'JohnDeere' or 'Trimble'
            "area_acres": f.get("area", {}).get("value")
        } for f in raw_fields]

        return {
            "sirup_type": "oem_data",
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {"assets": assets}
        }

    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sirup["geoid"] = geoid
        return create_bite_from_sirup(
            sirup=sirup,
            bite_type="oem_data",
            additional_tags=["leaf", "multi-vendor", "usa"]
        )
