"""
TAP Adapter Base Classes and Factory
=====================================

Universal adapter interface for integrating third-party data vendors into TAP
(Third-party Agentic-Pipeline). This enables plug-and-play vendor integration
for the PANCAKE ecosystem.

Key Concepts:
- TAPAdapter: Base class all vendors implement
- AdapterFactory: Auto-loads adapters from config
- Vendor data → SIRUP → BITE transformation pipeline
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import importlib
import yaml


class SIRUPType(Enum):
    """Standard SIRUP data types"""
    SATELLITE_IMAGERY = "satellite_imagery"
    WEATHER_FORECAST = "weather_forecast"
    WEATHER_HISTORICAL = "weather_historical"
    SOIL_PROFILE = "soil_profile"
    SOIL_INFILTRATION = "soil_infiltration"
    SOIL_MOISTURE = "soil_moisture"
    CROP_HEALTH = "crop_health"
    PEST_DISEASE = "pest_disease"
    MARKET_PRICE = "market_price"
    CUSTOM = "custom"


class AuthMethod(Enum):
    """Supported authentication methods"""
    NONE = "none"  # No authentication required
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    CUSTOM = "custom"


class TAPAdapter(ABC):
    """
    Base class for all TAP vendor adapters
    
    Every vendor must implement this interface to integrate with TAP.
    The adapter is responsible for:
    1. Fetching raw data from vendor API
    2. Transforming vendor data into SIRUP format
    3. Converting SIRUP into standardized BITE
    
    Example:
        class MyVendorAdapter(TAPAdapter):
            def get_vendor_data(self, geoid, params):
                # Fetch from vendor API
                return vendor_response
            
            def transform_to_sirup(self, vendor_data):
                # Normalize vendor data
                return sirup_dict
            
            def sirup_to_bite(self, sirup, geoid, params):
                # Create BITE
                return bite_dict
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with vendor-specific configuration
        
        Args:
            config: Vendor configuration dict containing:
                - vendor_name: str
                - base_url: str
                - auth_method: str (api_key, oauth2, etc.)
                - credentials: dict (keys, tokens, etc.)
                - sirup_types: list of SIRUPType this vendor provides
                - rate_limit: dict (max_requests, time_window)
                - timeout: int (request timeout in seconds)
        """
        self.vendor_name = config.get('vendor_name', 'Unknown')
        self.base_url = config.get('base_url', '')
        self.auth_method = AuthMethod(config.get('auth_method', 'api_key'))
        self.credentials = config.get('credentials', {})
        self.sirup_types = [SIRUPType(t) for t in config.get('sirup_types', [])]
        self.rate_limit = config.get('rate_limit', {'max_requests': 100, 'time_window': 60})
        self.timeout = config.get('timeout', 60)
        self.metadata = config.get('metadata', {})
        
        # Initialize vendor-specific state
        self._initialize()
    
    def _initialize(self):
        """Optional: Vendor-specific initialization (auth, validation, etc.)"""
        pass
    
    @abstractmethod
    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch raw data from vendor API
        
        Args:
            geoid: AgStack GeoID for the location
            params: Query parameters (date, date_range, depth, etc.)
        
        Returns:
            Raw vendor API response as dict, or None if failed
        """
        pass
    
    @abstractmethod
    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        """
        Transform raw vendor data into SIRUP format
        
        SIRUP (Spatio-temporal Intelligence for Reasoning and Unified Perception)
        is the normalized, enriched data payload that flows through TAP.
        
        Args:
            vendor_data: Raw response from get_vendor_data
            sirup_type: Type of SIRUP being generated
        
        Returns:
            SIRUP dict with standardized structure:
            {
                "sirup_type": str,
                "vendor": str,
                "timestamp": str (ISO 8601),
                "geoid": str,
                "data": dict (vendor-specific, but documented),
                "metadata": dict (resolution, confidence, source, etc.),
                "units": dict (for all numeric values)
            }
        """
        pass
    
    @abstractmethod
    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert SIRUP into standardized BITE format
        
        Args:
            sirup: SIRUP data from transform_to_sirup
            geoid: AgStack GeoID
            params: Original query parameters
        
        Returns:
            BITE dict with Header, Body, Footer structure
        """
        pass
    
    def fetch_and_transform(self, geoid: str, sirup_type: SIRUPType, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Complete pipeline: vendor API → SIRUP → BITE
        
        This is the main entry point for TAP to request data.
        
        Args:
            geoid: AgStack GeoID
            sirup_type: Type of SIRUP to fetch
            params: Query parameters
        
        Returns:
            BITE dict, or None if any step failed
        """
        # Step 1: Fetch from vendor
        vendor_data = self.get_vendor_data(geoid, params)
        if not vendor_data:
            return None
        
        # Step 2: Transform to SIRUP
        sirup = self.transform_to_sirup(vendor_data, sirup_type)
        if not sirup:
            return None
        
        # Step 3: Convert to BITE
        bite = self.sirup_to_bite(sirup, geoid, params)
        return bite
    
    def supports_sirup_type(self, sirup_type: SIRUPType) -> bool:
        """Check if this adapter supports a specific SIRUP type"""
        return sirup_type in self.sirup_types
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return adapter capabilities and metadata"""
        return {
            "vendor_name": self.vendor_name,
            "sirup_types": [t.value for t in self.sirup_types],
            "auth_method": self.auth_method.value,
            "rate_limit": self.rate_limit,
            "metadata": self.metadata
        }


class TAPAdapterFactory:
    """
    Factory for loading and managing TAP adapters
    
    Automatically discovers and instantiates vendor adapters from config files.
    Enables plug-and-play vendor integration.
    
    Example usage:
        factory = TAPAdapterFactory('tap_vendors.yaml')
        adapter = factory.get_adapter('terrapipe')
        bite = adapter.fetch_and_transform(geoid, SIRUPType.SATELLITE_IMAGERY, {...})
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize factory with vendor configurations
        
        Args:
            config_path: Path to YAML config file with vendor definitions
        """
        self.adapters = {}
        self.config_path = config_path
        
        if config_path:
            self.load_from_config(config_path)
    
    def load_from_config(self, config_path: str):
        """
        Load vendor adapters from YAML config
        
        Expected config structure:
        vendors:
          - vendor_name: terrapipe
            adapter_class: tap_adapters.TerrapipeAdapter
            base_url: https://appserver.terrapipe.io
            auth_method: api_key
            credentials:
              secretkey: ${TERRAPIPE_SECRET}
              client: ${TERRAPIPE_CLIENT}
            sirup_types:
              - satellite_imagery
            rate_limit:
              max_requests: 100
              time_window: 60
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        for vendor_config in config.get('vendors', []):
            self.register_adapter(vendor_config)
    
    def register_adapter(self, config: Dict[str, Any]):
        """
        Register a new adapter from configuration
        
        Args:
            config: Vendor configuration dict
        """
        vendor_name = config.get('vendor_name')
        adapter_class_path = config.get('adapter_class')
        
        if not vendor_name or not adapter_class_path:
            raise ValueError("vendor_name and adapter_class are required")
        
        # Dynamically import the adapter class
        module_path, class_name = adapter_class_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        
        # Instantiate the adapter
        adapter = adapter_class(config)
        self.adapters[vendor_name] = adapter
        
        print(f"✓ Registered TAP adapter: {vendor_name}")
        print(f"  SIRUP types: {[t.value for t in adapter.sirup_types]}")
    
    def get_adapter(self, vendor_name: str) -> Optional[TAPAdapter]:
        """Get adapter by vendor name"""
        return self.adapters.get(vendor_name)
    
    def get_adapters_for_sirup_type(self, sirup_type: SIRUPType) -> List[TAPAdapter]:
        """Get all adapters that support a specific SIRUP type"""
        return [
            adapter for adapter in self.adapters.values()
            if adapter.supports_sirup_type(sirup_type)
        ]
    
    def list_vendors(self) -> List[str]:
        """List all registered vendor names"""
        return list(self.adapters.keys())
    
    def get_all_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Get capabilities for all registered adapters"""
        return {
            name: adapter.get_capabilities()
            for name, adapter in self.adapters.items()
        }


# Helper function for common BITE creation
def create_bite_from_sirup(sirup: Dict[str, Any], bite_type: str, additional_tags: List[str] = None) -> Dict[str, Any]:
    """
    Helper function to create a BITE from SIRUP data
    
    Args:
        sirup: SIRUP data dict
        bite_type: BITE type string
        additional_tags: Optional additional tags
    
    Returns:
        BITE dict with Header, Body, Footer
    """
    import hashlib
    import json
    from datetime import datetime
    
    try:
        from ulid import ULID
    except ImportError:
        # Fallback if ULID not available
        import uuid
        ULID = lambda: str(uuid.uuid4())
    
    bite_id = str(ULID())
    timestamp = sirup.get('timestamp', datetime.utcnow().isoformat() + 'Z')
    geoid = sirup.get('geoid', '')
    
    header = {
        "id": bite_id,
        "geoid": geoid,
        "timestamp": timestamp,
        "type": bite_type,
        "source": {
            "pipeline": "TAP",
            "vendor": sirup.get('vendor', 'unknown'),
            "sirup_type": sirup.get('sirup_type', ''),
            "auto_generated": True
        }
    }
    
    body = {
        "sirup_data": sirup.get('data', {}),
        "metadata": sirup.get('metadata', {}),
        "units": sirup.get('units', {})
    }
    
    # Compute hash
    header_str = json.dumps(header, sort_keys=True)
    body_str = json.dumps(body, sort_keys=True)
    hash_val = hashlib.sha256((header_str + body_str).encode()).hexdigest()
    
    tags = ["automated", "tap", sirup.get('sirup_type', '')]
    if additional_tags:
        tags.extend(additional_tags)
    
    footer = {
        "hash": hash_val,
        "schema_version": "1.0",
        "tags": tags
    }
    
    return {
        "Header": header,
        "Body": body,
        "Footer": footer
    }

