"""
TAP Vendor Adapters
===================

Concrete adapter implementations for specific vendors:
1. Terrapipe - Satellite imagery (NDVI)
2. SoilGrids (ISRIC) - Soil profile and infiltration
3. Terrapipe GFS - Weather forecast

Each adapter implements the TAPAdapter interface.
"""

import requests
import urllib.request
import json
import time
import socket
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from tap_adapter_base import TAPAdapter, SIRUPType, create_bite_from_sirup


class TerrapipeNDVIAdapter(TAPAdapter):
    """
    Adapter for Terrapipe satellite imagery (NDVI)
    
    Provides: SATELLITE_IMAGERY SIRUP
    Authentication: API key (secretkey + client)
    """
    
    def _initialize(self):
        """Setup Terrapipe-specific configuration"""
        self.headers = {
            "secretkey": self.credentials.get('secretkey', ''),
            "client": self.credentials.get('client', '')
        }
    
    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch NDVI data from Terrapipe
        
        Params:
            - date: str (YYYY-MM-DD) - specific date for NDVI image
            - start_date: str (optional) - for getting available dates
            - end_date: str (optional) - for getting available dates
        """
        date = params.get('date')
        
        if not date:
            # If no date provided, get available dates
            start_date = params.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            end_date = params.get('end_date', datetime.now().strftime('%Y-%m-%d'))
            
            dates = self._get_available_dates(geoid, start_date, end_date)
            if dates:
                date = dates[0]  # Use most recent
            else:
                return None
        
        url = f"{self.base_url}/getNDVIImg"
        query_params = {
            "geoid": geoid,
            "date": date
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=query_params, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                data['_query_date'] = date  # Store query date
                return data
        except Exception as e:
            print(f"Error fetching NDVI from Terrapipe: {e}")
        
        return None
    
    def _get_available_dates(self, geoid: str, start_date: str, end_date: str) -> List[str]:
        """Get available NDVI dates for a GeoID"""
        url = f"{self.base_url}/getNDVIDatesForGeoid"
        params = {
            "geoid": geoid,
            "start_date": start_date,
            "end_date": end_date
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
            if response.status_code == 200:
                dates = response.json().get("dates", [])
                # Filter to requested window (API returns all dates)
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                filtered = [
                    d for d in dates
                    if start_dt <= datetime.strptime(d, '%Y-%m-%d') <= end_dt
                ]
                return sorted(filtered, reverse=True)  # Most recent first
        except Exception as e:
            print(f"Error fetching NDVI dates: {e}")
        
        return []
    
    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        """Transform Terrapipe NDVI data into SIRUP format"""
        
        if sirup_type != SIRUPType.SATELLITE_IMAGERY:
            return None
        
        # Extract NDVI features
        ndvi_img = vendor_data.get("ndvi_img", {})
        features = ndvi_img.get("features", [])
        
        if not features:
            return None
        
        # Calculate NDVI statistics
        ndvi_values = [
            f["properties"]["NDVI"]
            for f in features
            if "NDVI" in f.get("properties", {})
        ]
        
        if not ndvi_values:
            return None
        
        ndvi_array = np.array(ndvi_values)
        
        sirup = {
            "sirup_type": sirup_type.value,
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "geoid": vendor_data.get("_query_geoid", ""),
            "data": {
                "date": vendor_data.get("_query_date"),
                "boundary": vendor_data.get("boundary_geoDataFrameDict"),
                "ndvi_image": ndvi_img,
                "ndvi_stats": {
                    "mean": float(ndvi_array.mean()),
                    "median": float(np.median(ndvi_array)),
                    "min": float(ndvi_array.min()),
                    "max": float(ndvi_array.max()),
                    "std": float(ndvi_array.std()),
                    "count": len(ndvi_array),
                    "percentile_25": float(np.percentile(ndvi_array, 25)),
                    "percentile_75": float(np.percentile(ndvi_array, 75))
                }
            },
            "metadata": {
                "source": "satellite",
                "index_type": "NDVI",
                "resolution": "10m",
                "sensor": vendor_data.get("metadata", {}).get("sensor", "Sentinel-2"),
                "cloud_coverage": vendor_data.get("metadata", {}).get("cloud_coverage", "unknown")
            },
            "units": {
                "ndvi": "dimensionless [-1 to 1]"
            }
        }
        
        return sirup
    
    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert NDVI SIRUP into BITE"""
        
        bite = create_bite_from_sirup(
            sirup=sirup,
            bite_type="imagery_sirup",
            additional_tags=["satellite", "ndvi", "vegetation", "polygon"]
        )
        
        # Override geoid if provided
        if geoid:
            bite["Header"]["geoid"] = geoid
        
        return bite


class SoilGridsAdapter(TAPAdapter):
    """
    Adapter for ISRIC SoilGrids global soil dataset
    
    Provides: SOIL_PROFILE, SOIL_INFILTRATION SIRUP
    Authentication: None (public API)
    """
    
    def _initialize(self):
        """SoilGrids is a public API, no auth needed"""
        self.base_url = "https://rest.isric.org/soilgrids/v2.0"
        self.max_retries = 3
    
    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch soil data from SoilGrids
        
        Params:
            - lat: float (required for SoilGrids)
            - lon: float (required for SoilGrids)
            - analysis_type: str ("profile" or "infiltration")
            - field_coords: list (required for infiltration analysis)
        """
        lat = params.get('lat')
        lon = params.get('lon')
        analysis_type = params.get('analysis_type', 'profile')
        
        if not lat or not lon:
            print("⚠️ SoilGrids requires lat/lon coordinates")
            return None
        
        if analysis_type == 'profile':
            return self._get_soil_profile(lat, lon)
        elif analysis_type == 'infiltration':
            field_coords = params.get('field_coords')
            if not field_coords:
                print("⚠️ Infiltration analysis requires field_coords")
                return None
            return self._get_soil_infiltration(lat, lon, field_coords)
        else:
            print(f"⚠️ Unknown analysis_type: {analysis_type}")
            return None
    
    def _get_soil_profile(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Get full soil profile (10 properties × 6 depths)"""
        properties = ['bdod', 'cec', 'cfvo', 'clay', 'sand', 'silt', 
                     'nitrogen', 'ocd', 'phh2o', 'soc']
        depths = ['0-5cm', '5-15cm', '15-30cm', '30-60cm', '60-100cm', '100-200cm']
        
        # Build URL
        main_url = f'{self.base_url}/properties/query?lon={lon}&lat={lat}'
        prop_url = ''.join([f'&property={p}' for p in properties])
        depth_url = ''.join([f'&depth={d}' for d in depths])
        value_url = '&value=mean&value=Q0.05&value=Q0.5&value=Q0.95'
        url = main_url + prop_url + depth_url + value_url
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    data = json.load(response)
                    data['_analysis_type'] = 'profile'
                    data['_lat'] = lat
                    data['_lon'] = lon
                    return data
            except socket.timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    print(f"❌ SoilGrids timeout after {self.max_retries} attempts")
                    return None
            except Exception as e:
                print(f"Error fetching soil profile: {e}")
                return None
        
        return None
    
    def _get_soil_infiltration(self, lat: float, lon: float, field_coords: List) -> Optional[Dict[str, Any]]:
        """Get soil properties for infiltration calculation"""
        properties = ['sand', 'clay', 'silt', 'bdod', 'soc']
        depth = '0-5cm'  # Surface layer for infiltration
        
        main_url = f'{self.base_url}/properties/query?lon={lon}&lat={lat}'
        prop_url = ''.join([f'&property={p}' for p in properties])
        depth_url = f'&depth={depth}'
        value_url = '&value=mean'
        url = main_url + prop_url + depth_url + value_url
        
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                data = json.load(response)
                
                # Extract and normalize properties
                soil_props = {}
                for layer in data.get('properties', {}).get('layers', []):
                    prop_name = layer.get('name')
                    depths = layer.get('depths', [])
                    if depths:
                        value = depths[0].get('values', {}).get('mean')
                        
                        if prop_name == 'sand':
                            soil_props['sand'] = value / 10.0
                        elif prop_name == 'clay':
                            soil_props['clay'] = value / 10.0
                        elif prop_name == 'silt':
                            soil_props['silt'] = value / 10.0
                        elif prop_name == 'bdod':
                            soil_props['bulk_density'] = value / 100.0
                        elif prop_name == 'soc':
                            soil_props['organic_carbon'] = value / 10.0
                
                # Calculate infiltration rate (Ksat) using research formula
                # Based on: https://essd.copernicus.org/preprints/essd-2020-149
                ksat = self._calculate_ksat(soil_props)
                
                return {
                    '_analysis_type': 'infiltration',
                    '_lat': lat,
                    '_lon': lon,
                    'soil_properties': soil_props,
                    'infiltration_rate': ksat,
                    'field_coords': field_coords
                }
        
        except Exception as e:
            print(f"Error fetching infiltration data: {e}")
            return None
    
    def _calculate_ksat(self, soil_props: Dict[str, float]) -> Dict[str, float]:
        """Calculate infiltration rate using research-based formula"""
        sand = soil_props.get('sand', 50.0)
        clay = soil_props.get('clay', 25.0)
        bd = soil_props.get('bulk_density', 1.3)
        
        # Research coefficients
        b0, b1, b2 = 2.17, 0.9387, -0.8026
        b3, b4 = 0.0037, -0.017
        b6 = 0.0025
        
        log_ksat = (b0 + b1 * bd + b2 * (bd ** 2) + 
                   b3 * clay + b4 * bd * clay + b6 * sand)
        
        ksat_cm_day = np.exp(log_ksat)
        ksat_inches_day = ksat_cm_day * 0.393701
        
        return {
            'cm_per_day': float(ksat_cm_day),
            'inches_per_day': float(ksat_inches_day),
            'mm_per_hour': float(ksat_cm_day * 10 / 24)
        }
    
    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        """Transform SoilGrids data into SIRUP format"""
        
        analysis_type = vendor_data.get('_analysis_type')
        
        if analysis_type == 'profile' and sirup_type == SIRUPType.SOIL_PROFILE:
            return self._transform_profile_sirup(vendor_data)
        elif analysis_type == 'infiltration' and sirup_type == SIRUPType.SOIL_INFILTRATION:
            return self._transform_infiltration_sirup(vendor_data)
        else:
            return None
    
    def _transform_profile_sirup(self, vendor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform soil profile data to SIRUP"""
        
        # Parse profile data
        profile_data = []
        property_info = {
            'bdod': {'name': 'Bulk Density', 'factor': 100.0, 'unit': 'g/cm³'},
            'cec': {'name': 'CEC', 'factor': 10.0, 'unit': 'cmol(c)/kg'},
            'cfvo': {'name': 'Coarse Fragments', 'factor': 10.0, 'unit': 'vol%'},
            'clay': {'name': 'Clay', 'factor': 10.0, 'unit': '%'},
            'sand': {'name': 'Sand', 'factor': 10.0, 'unit': '%'},
            'silt': {'name': 'Silt', 'factor': 10.0, 'unit': '%'},
            'nitrogen': {'name': 'Nitrogen', 'factor': 100.0, 'unit': 'g/kg'},
            'ocd': {'name': 'Org. C Density', 'factor': 10.0, 'unit': 'kg/dm³'},
            'phh2o': {'name': 'pH', 'factor': 10.0, 'unit': 'pH'},
            'soc': {'name': 'Org. Carbon', 'factor': 10.0, 'unit': 'g/kg'}
        }
        
        depth_midpoints = {
            '0-5cm': 2.5, '5-15cm': 10.0, '15-30cm': 22.5,
            '30-60cm': 45.0, '60-100cm': 80.0, '100-200cm': 150.0
        }
        
        for layer in vendor_data.get('properties', {}).get('layers', []):
            prop_code = layer.get('name')
            if prop_code not in property_info:
                continue
            
            info = property_info[prop_code]
            for depth_data in layer.get('depths', []):
                depth_label = depth_data.get('label')
                values = depth_data.get('values', {})
                
                profile_data.append({
                    'property': info['name'],
                    'property_code': prop_code,
                    'unit': info['unit'],
                    'depth_label': depth_label,
                    'depth_cm': depth_midpoints.get(depth_label, 0),
                    'mean': values.get('mean', 0) / info['factor'],
                    'q05': values.get('Q0.05', 0) / info['factor'],
                    'q50': values.get('Q0.5', 0) / info['factor'],
                    'q95': values.get('Q0.95', 0) / info['factor']
                })
        
        sirup = {
            "sirup_type": SIRUPType.SOIL_PROFILE.value,
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "geoid": "",  # Will be set by caller
            "data": {
                "location": {
                    "lat": vendor_data.get('_lat'),
                    "lon": vendor_data.get('_lon')
                },
                "profile": profile_data,
                "num_properties": len(property_info),
                "num_depths": len(depth_midpoints)
            },
            "metadata": {
                "source": "ISRIC SoilGrids 250m",
                "resolution": "250m",
                "depths": list(depth_midpoints.keys()),
                "properties": list(property_info.keys())
            },
            "units": {prop: property_info[prop]['unit'] for prop in property_info}
        }
        
        return sirup
    
    def _transform_infiltration_sirup(self, vendor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform infiltration data to SIRUP"""
        
        sirup = {
            "sirup_type": SIRUPType.SOIL_INFILTRATION.value,
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "geoid": "",
            "data": {
                "location": {
                    "lat": vendor_data.get('_lat'),
                    "lon": vendor_data.get('_lon')
                },
                "soil_properties": vendor_data.get('soil_properties', {}),
                "infiltration_rate": vendor_data.get('infiltration_rate', {}),
                "field_boundary": vendor_data.get('field_coords', [])
            },
            "metadata": {
                "source": "ISRIC SoilGrids 250m",
                "method": "Research-based Ksat formula (Montzka et al. 2017)",
                "depth": "0-5cm surface layer",
                "reference": "https://essd.copernicus.org/preprints/essd-2020-149"
            },
            "units": {
                "infiltration_rate": "inches/day, cm/day, mm/hour",
                "sand": "%",
                "clay": "%",
                "silt": "%",
                "bulk_density": "g/cm³"
            }
        }
        
        return sirup
    
    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert soil SIRUP into BITE"""
        
        sirup_type = sirup.get('sirup_type')
        
        if sirup_type == SIRUPType.SOIL_PROFILE.value:
            bite_type = "soil_profile"
            tags = ["soil", "profile", "point", "isric"]
        elif sirup_type == SIRUPType.SOIL_INFILTRATION.value:
            bite_type = "soil_infiltration"
            tags = ["soil", "infiltration", "ksat", "polygon"]
        else:
            bite_type = "soil_data"
            tags = ["soil"]
        
        bite = create_bite_from_sirup(
            sirup=sirup,
            bite_type=bite_type,
            additional_tags=tags
        )
        
        if geoid:
            bite["Header"]["geoid"] = geoid
        
        return bite


class TerrapipeGFSAdapter(TAPAdapter):
    """
    Adapter for Terrapipe GFS Weather Forecast
    
    Provides: WEATHER_FORECAST SIRUP
    Authentication: OAuth2 Bearer token + API key
    """
    
    def _initialize(self):
        """Setup Terrapipe GFS configuration"""
        self.headers = {
            "secretkey": self.credentials.get('secretkey', ''),
            "client": self.credentials.get('client', ''),
            "Accept": "*/*"
        }
        
        # Authenticate and get bearer token
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate and obtain bearer token"""
        auth_url = f"{self.base_url}/"  # Login endpoint
        auth_data = {
            "email": self.credentials.get('email', ''),
            "password": self.credentials.get('password', '')
        }
        
        try:
            response = requests.post(auth_url, json=auth_data, timeout=self.timeout)
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token') or token_data.get('token')
                if access_token:
                    self.headers['Authorization'] = f'Bearer {access_token}'
                    print(f"✓ Authenticated with {self.vendor_name}")
                else:
                    print(f"⚠️ No access token in response from {self.vendor_name}")
            else:
                print(f"⚠️ Authentication failed: {response.status_code}")
        except Exception as e:
            print(f"Error authenticating with {self.vendor_name}: {e}")
    
    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch GFS weather forecast from Terrapipe
        
        Params:
            - start_date: str (YYYY-MM-DD)
            - end_date: str (YYYY-MM-DD)
        """
        start_date = params.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        end_date = params.get('end_date', (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        
        url = f"{self.base_url}/getGFSStats"
        query_params = {
            "geoid": geoid,
            "start_date": start_date,
            "end_date": end_date
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=query_params, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                data['_query_geoid'] = geoid
                data['_start_date'] = start_date
                data['_end_date'] = end_date
                return data
            else:
                print(f"GFS API returned status {response.status_code}")
        except Exception as e:
            print(f"Error fetching GFS data: {e}")
        
        return None
    
    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        """Transform GFS weather data into SIRUP format"""
        
        if sirup_type != SIRUPType.WEATHER_FORECAST:
            return None
        
        # Extract weather statistics
        # (Exact structure depends on GFS API response)
        stats = vendor_data.get('stats', vendor_data.get('data', {}))
        
        sirup = {
            "sirup_type": sirup_type.value,
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "geoid": vendor_data.get('_query_geoid', ''),
            "data": {
                "forecast_period": {
                    "start": vendor_data.get('_start_date'),
                    "end": vendor_data.get('_end_date')
                },
                "weather_data": stats,
                "summary": self._extract_weather_summary(stats)
            },
            "metadata": {
                "source": "GFS (Global Forecast System)",
                "model": "NOAA GFS",
                "resolution": "0.25 degrees",
                "forecast_type": "numerical weather prediction"
            },
            "units": {
                "temperature": "°C",
                "precipitation": "mm",
                "wind_speed": "m/s",
                "humidity": "%",
                "pressure": "hPa"
            }
        }
        
        return sirup
    
    def _extract_weather_summary(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key weather metrics for summary"""
        summary = {}
        
        # Common weather parameters (adapt based on actual API response)
        if isinstance(stats, dict):
            for key in ['temperature', 'precipitation', 'humidity', 'wind_speed']:
                if key in stats:
                    val = stats[key]
                    if isinstance(val, (list, np.ndarray)):
                        summary[f'{key}_mean'] = float(np.mean(val))
                        summary[f'{key}_min'] = float(np.min(val))
                        summary[f'{key}_max'] = float(np.max(val))
                    elif isinstance(val, (int, float)):
                        summary[key] = float(val)
        
        return summary
    
    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert weather SIRUP into BITE"""
        
        bite = create_bite_from_sirup(
            sirup=sirup,
            bite_type="weather_forecast",
            additional_tags=["weather", "forecast", "gfs", "polygon"]
        )
        
        if geoid:
            bite["Header"]["geoid"] = geoid
        
        return bite

