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



import hmac, hashlib, base64, time, requests, logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime
from tap_adapter_base import TAPAdapter, SIRUPType, create_bite_from_sirup
logger = logging.getLogger(__name__)

class RavenSlingshotAdapter(TAPAdapter):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('base_url')
        self.sirup_types = [SIRUPType.OEM_DATA] 


        creds = config.get('credentials', {})
        self.api_key = creds.get('api_key')
        self.access_key = creds.get('access_key')
        raw_secret = creds.get('shared_secret')
        
        if not all([self.api_key, self.access_key, raw_secret]):
            raise ValueError("Raven Slingshot requires api_key, shared_secret, and access_key.")
            
        
        self.shared_secret = base64.b64decode(raw_secret)

    def _generate_headers(self, method: str, path: str):
        timestamp = str(int(time.time()))
        host = urlparse(self.base_url).netloc
        
        components = [method.upper(), host.lower(), path.lower(), timestamp, self.api_key, self.access_key]
        string_to_sign = "\r\n".join(components) + "\r\n"
        
        sig_bytes = hmac.new(
            self.shared_secret,
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        return {
            "X-SS-APIKey": self.api_key,
            "X-SS-Signature": base64.b64encode(sig_bytes).decode(),
            "X-SS-AccessKey": self.access_key,
            "X-SS-TimeStamp": timestamp,
            "Accept": "application/json"
        }

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        path = "/jobdata"
        url = f"{self.base_url}{path}"
        headers = self._generate_headers("GET", path)
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status() # Raises error for 4xx/5xx
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Raven Slingshot API Error: {e}")
            return None

    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
       
        is_almond = "almond" in vendor_data.get('crop_type', '').lower()
        
        required_nutrients = ['N', 'P', 'K']
        found = [n for n in required_nutrients if n in vendor_data]
        completeness = len(found) / len(required_nutrients)
        
        return {
            "sirup_type": sirup_type.value,
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": vendor_data,
            "metadata": {
                "unit": "lbs_kernel_weight" if is_almond else "bushels",
                "completeness_score": completeness,
                "is_partial_bite": completeness < 1.0
            }
        }

    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sirup["geoid"] = geoid
        return create_bite_from_sirup(sirup, "oem_data", ["raven", "slingshot", "nutrients"])
