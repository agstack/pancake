"""
Asset Registry Client - GeoID Resolution Service
Integrates with https://github.com/agstack/asset-registry
"""
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from flask import current_app

logger = logging.getLogger(__name__)


class AssetRegistryClient:
    """
    Client for Asset Registry API
    Handles point and polygon registration to get GeoIDs
    """
    
    def __init__(self, base_url: str = None, timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout
    
    def _get_base_url(self):
        """Get base URL with lazy initialization"""
        if self.base_url:
            return self.base_url
        try:
            from flask import current_app
            return current_app.config.get('ASSET_REGISTRY_URL', 'http://localhost:4000')
        except RuntimeError:
            return 'http://localhost:4000'
    
    def register_point(self, lat: float, lon: float, token: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Register a point location and get GeoID
        
        Args:
            lat: Latitude
            lon: Longitude
            token: Optional auth token
            
        Returns:
            (geoid, error_message)
        """
        try:
            # Convert to WKT POINT format
            wkt = f"POINT({lon} {lat})"
            
            headers = {}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            payload = {
                'wkt': wkt
            }
            
            url = f"{self._get_base_url()}/register-point"
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                geoid = data.get('Geo Id')
                if geoid:
                    logger.info(f"Registered point ({lat}, {lon}) -> GeoID: {geoid}")
                    return geoid, None
                else:
                    return None, "No GeoID returned from Asset Registry"
            else:
                error_msg = response.json().get('message', 'Unknown error')
                logger.error(f"Asset Registry error: {error_msg}")
                return None, error_msg
                
        except requests.exceptions.Timeout:
            logger.error("Asset Registry timeout")
            return None, "Asset Registry timeout"
        except Exception as e:
            logger.error(f"Asset Registry exception: {e}")
            return None, str(e)
    
    def register_polygon(self, coordinates: list, token: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Register a polygon boundary and get GeoID
        
        Args:
            coordinates: List of [lon, lat] pairs forming polygon
            token: Optional auth token
            
        Returns:
            (geoid, error_message)
        """
        try:
            # Convert to WKT POLYGON format
            coords_str = ', '.join([f"{lon} {lat}" for lon, lat in coordinates])
            wkt = f"POLYGON(({coords_str}))"
            
            headers = {}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            
            payload = {
                'wkt': wkt,
                'threshold': 95
            }
            
            url = f"{self._get_base_url()}/register-field-boundary"
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                geoid = data.get('Geo Id')
                if geoid:
                    logger.info(f"Registered polygon -> GeoID: {geoid}")
                    return geoid, None
                else:
                    return None, "No GeoID returned from Asset Registry"
            else:
                error_msg = response.json().get('message', 'Unknown error')
                logger.error(f"Asset Registry error: {error_msg}")
                return None, error_msg
                
        except requests.exceptions.Timeout:
            logger.error("Asset Registry timeout")
            return None, "Asset Registry timeout"
        except Exception as e:
            logger.error(f"Asset Registry exception: {e}")
            return None, str(e)
    
    def register_geojson(self, geojson: Dict[str, Any], token: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Register GeoJSON feature and get GeoID
        Handles both Point and Polygon geometries
        
        Args:
            geojson: GeoJSON feature dict
            token: Optional auth token
            
        Returns:
            (geoid, error_message)
        """
        try:
            geometry = geojson.get('geometry', {})
            geometry_type = geometry.get('type')
            coordinates = geometry.get('coordinates')
            
            if not geometry_type or not coordinates:
                return None, "Invalid GeoJSON: missing geometry or coordinates"
            
            if geometry_type == 'Point':
                # coordinates is [lon, lat]
                lon, lat = coordinates
                return self.register_point(lat, lon, token)
            
            elif geometry_type == 'Polygon':
                # coordinates is [ [[lon, lat], ...] ]
                polygon_coords = coordinates[0]  # Outer ring
                return self.register_polygon(polygon_coords, token)
            
            else:
                return None, f"Unsupported geometry type: {geometry_type}"
                
        except Exception as e:
            logger.error(f"GeoJSON registration exception: {e}")
            return None, str(e)
    
    def resolve_capture_point(self, capture_point: Dict[str, Any], token: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve a capture_point {lat, lon} to GeoID
        
        Args:
            capture_point: Dict with 'lat' and 'lon' keys
            token: Optional auth token
            
        Returns:
            (geoid, error_message)
        """
        try:
            lat = capture_point.get('lat')
            lon = capture_point.get('lon')
            
            if lat is None or lon is None:
                return None, "capture_point must have 'lat' and 'lon'"
            
            return self.register_point(float(lat), float(lon), token)
            
        except ValueError as e:
            return None, f"Invalid lat/lon values: {e}"
        except Exception as e:
            return None, str(e)


# Singleton instance
asset_registry_client = AssetRegistryClient()

