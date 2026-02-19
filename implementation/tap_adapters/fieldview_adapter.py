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
from tap_adapter_base import OAuth2TAPAdapter, SIRUPType, create_bite_from_sirup
class FieldViewAdapter(OAuth2TAPAdapter):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = self.credentials.get("api_key")

    def refresh_token(self, farmer_id: str) -> bool:
        """
        Refreshes the OAuth2 token for the given farmer.
        Climate requires Basic Auth for refresh.
        """
        # TODO: Implement the token refresh logic for Climate FieldView.
        # This will involve making a POST request to the token endpoint
        # with the refresh token and client credentials, and then
        # updating the farmer's record in the registry with the new tokens.
        registry = self.load_registry()
        refresh_token = registry.get(farmer_id, {}).get("refresh_token")
        if not refresh_token:
            return False

        # Logic to call https://api.climate.com/api/oauth/token
        # and update registry...
        print("NOTE: Climate FieldView token refresh logic is not yet implemented.")
        return False

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        farmer_id = params.get("farmer_id")
        token = self.load_registry().get(farmer_id, {}).get("access_token")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.api_key
        }
        
        # Discovery: Get fields as 'assets'
        res = requests.get(f"{self.base_url}/fields", headers=headers)
        
        if res.status_code == 401 and self.refresh_token(farmer_id):
            return self.get_vendor_data(geoid, params)
            
        return {"fields": res.json().get("results", [])} if res.status_code == 200 else None

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        fields = vendor_data.get("fields", [])
        assets = [{
            "asset_id": f.get("id"),
            "category": "FIELD",
            "brand": "Climate FieldView",
            "display_name": f.get("name")
        } for f in fields]

        return {
            "sirup_type": "oem_data",
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {"assets": assets}
        }

    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Wrap FieldView SIRUP into a BITE packet"""
        sirup["geoid"] = geoid
        
        # Use the helper from tap_adapter_base.py
        bite = create_bite_from_sirup(
            sirup=sirup,
            bite_type="oem_data",
            additional_tags=["climate", "fieldview", "usa", "boundaries"]
        )
        return bite
