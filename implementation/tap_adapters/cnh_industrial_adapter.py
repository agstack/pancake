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
from tap_adapter_base import OAuth2TAPAdapter, SIRUPType, create_bite_from_sirup

class CNHIndustrialAdapter(OAuth2TAPAdapter):
    """
    Adapter for CNH Industrial (New Holland/Case IH) FieldOps API.
    Handles ISO 15143-3 telemetry and California specialty crop normalization.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.auth_url = config.get("auth_url", "https://stg.identity.cnhind.com/oauth/token")
        self.subscription_key = self.credentials.get('subscription_key')
 
    def refresh_token(self, farmer_id: str) -> bool:
        """Implements CNH-specific refresh logic"""
        registry = self.load_registry()
        farmer_data = registry.get(farmer_id, {})
        refresh_token = farmer_data.get("refresh_token")

        if not refresh_token:
            return False

        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.credentials.get('client_id'),
            'client_secret': self.credentials.get('client_secret')
        }
        
        response = requests.post(self.auth_url, data=payload)

        if response.status_code == 200:
            new_data = response.json()
            registry[farmer_id].update({
                "access_token": new_data['access_token'],
                "refresh_token": new_data.get('refresh_token', refresh_token)
            })
            self.save_registry(registry)
            return True
        return False

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetches telemetry using the required CNH subscription key header."""
        farmer_id = params.get("farmer_id")
        registry = self.load_registry()
        token = registry.get(farmer_id, {}).get("access_token")

        if not token:
            return None

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
            'Ocp-Apim-Subscription-Key': self.subscription_key
        }

        # Targeted endpoint for Fuel Intensity calculations
        endpoint = f"{self.base_url}/equipment/telemetry"
        res = requests.get(endpoint, headers=headers)

        if res.status_code == 401:
            if self.refresh_token(farmer_id):
                return self.get_vendor_data(geoid, params)
        
        return res.json() if res.status_code == 200 else None

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        """
        Normalizes CNH data. 
        Converts Liters to Gallons and calculates Fuel Intensity for Almonds.
        """
        try:
            # Extracting from ISO 15143-3 response structure
            equipment = vendor_data['equipment'][0]
            fuel_liters = equipment['telemetry']['FuelUsedLast24Hours']['value']
            
            # Normalization logic for EB-2 NIW 'Specialty Crop' impact
            fuel_gallons = fuel_liters * 0.264172 # Liter to Gallon
            area_worked = vendor_data.get('field_context', {}).get('area_worked', 1.0)
            intensity = fuel_gallons / area_worked
            
            return {
                "sirup_type": sirup_type.value,
                "vendor": self.vendor_name,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {
                    "fuel_intensity": round(intensity, 4),
                    "total_fuel": round(fuel_gallons, 2),
                    "equipment_id": equipment.get('equipmentId')
                },
                "units": {
                    "fuel": "gallons",
                    "intensity": "gallons_per_acre"
                },
                "metadata": {
                    "crop": vendor_data.get('field_context', {}).get('crop_type', 'Almonds'),
                    "is_partial_bite": False
                }
            }
        except (KeyError, IndexError):
            return None

    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Wraps the SIRUP into the standardized BITE envelope"""
        sirup['geoid'] = geoid
        return create_bite_from_sirup(sirup, bite_type="oem_telemetry_sync")
