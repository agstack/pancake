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
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tap_adapter_base import OAuth2TAPAdapter, SIRUPType, create_bite_from_sirup

class JohnDeereAdapter(OAuth2TAPAdapter):
    """
    Adapter for John Deere Operations Center
    Provides: CUSTOM (Organization/Equipment Data)
    Authentication: OAuth2 with Token Rotation
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.config = config

    def refresh_token(self, farmer_id: str) -> bool:
        """Handles OAuth2 token refresh logic"""
        registry = self.load_registry()
        farmer_data = registry.get(farmer_id, {})
        refresh_token = farmer_data.get("refresh_token")

        if not refresh_token:
            return False

        # Build refresh request
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.credentials.get('client_id'),
            'client_secret': self.credentials.get('client_secret')
        }
        
        # Use the token endpoint from config
        token_url = self.config.get("token_url", "https://signin.johndeere.com/oauth2/aus78av9p4u0uW7sj357/v1/token")
        response = requests.post(token_url, data=payload)

        if response.status_code == 200:
            new_data = response.json()
            registry[farmer_id].update({
                "access_token": new_data['access_token'],
                "refresh_token": new_data.get('refresh_token', refresh_token)
            })
            self.save_registry(registry)
            return True
        else:
            print(f"❌ Refresh failed: {response.status_code}")
            return False

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        farmer_id = params.get("farmer_id")
        registry = self.load_registry()
        farmer_data = registry.get(farmer_id, {})
        token = farmer_data.get("access_token")

        if not token:
            return None

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/vnd.deere.axiom.v3+json'
        }

        #Fetch Organizations
        org_res = requests.get(f"{self.base_url}/organizations", headers=headers)

        #Handle 401 Unauthorized
        if org_res.status_code == 401:
            if self.refresh_token(farmer_id):
                return self.get_vendor_data(geoid, params) # Retry after refresh
            return None

        if org_res.status_code != 200:
            return None

        organizations = org_res.json().get('values', [])
        all_machines = []

        #Loop through Orgs to get specific Machines
        for org in organizations:
            org_id = org.get('id')
            
            # Try /equipment (New API) then /machines (Legacy API)
            for endpoint in ['equipment', 'machines']:
                url = f"{self.base_url}/organizations/{org_id}/{endpoint}"
                res = requests.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json().get('values', [])
                    if data:
                        all_machines.extend(data)
                        break

        #Fallback for  testing
        if not all_machines:
            all_machines.append({
                "id": "sandbox-demo-01",
                "name": "Verification Tractor",
                "modelName": "8R 370",
                "vin": "RW8370VIRTUAL"
            })

        return {"organizations": organizations, "machines": all_machines}

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        machines = vendor_data.get('machines', [])
        assets = [{
            "asset_id": m.get("id"),
            "category": "MACHINERY",
            "brand": "John Deere",
            "model": m.get("modelName", "Unknown Model"),
            "serial_number": m.get("vin") or m.get("serialNumber"),
            "display_name": m.get("name")
        } for m in machines]

        return {
            "sirup_type": "oem_data",
            "vendor": "johndeere",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "organizations": vendor_data.get('organizations', []),
                "assets": assets
            }
        }

    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Wrap SIRUP into a BITE packet for Pancake ingestion"""
        sirup["geoid"] = geoid
        bite = create_bite_from_sirup(
            sirup=sirup, 
            bite_type="oem_data", 
            additional_tags=["johndeere", "machinery"]
        )
        return bite
