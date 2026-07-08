"""Canonical TAP adapter interface (service-grade port of implementation/tap_adapter_base.py).

Every vendor adapter implements three steps:
  1. get_vendor_data(geoid, params)      -> raw vendor API response
  2. transform_to_sirup(raw, sirup_type) -> normalized SIRUP payload
  3. sirup_to_bite(sirup, geoid, params) -> BITE envelope for storage

Adapters stay dumb and predictable: no retries inside adapters (the runtime
owns retry policy) and vendor credentials come from environment variables
only (guardrail 7).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ulid import ULID

logger = logging.getLogger(__name__)


class SIRUPType(Enum):
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
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    CUSTOM = "custom"


class TAPAdapter(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.vendor_name = config.get("vendor_name", "Unknown")
        self.base_url = config.get("base_url", "")
        self.auth_method = AuthMethod(config.get("auth_method", "api_key"))
        self.credentials = config.get("credentials", {})
        self.sirup_types = [SIRUPType(t) for t in config.get("sirup_types", [])]
        self.rate_limit = config.get("rate_limit", {"max_requests": 100, "time_window": 60})
        self.timeout = config.get("timeout", 60)
        self.metadata = config.get("metadata", {})
        self._initialize()

    def _initialize(self):
        """Optional vendor-specific initialization."""

    @abstractmethod
    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def transform_to_sirup(
        self, vendor_data: Dict[str, Any], sirup_type: SIRUPType
    ) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def sirup_to_bite(
        self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]: ...

    def fetch_and_transform(
        self, geoid: str, sirup_type: SIRUPType, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Complete pipeline: vendor API -> SIRUP -> BITE. None means 'skip, log, retry later'."""
        vendor_data = self.get_vendor_data(geoid, params)
        if not vendor_data:
            return None
        sirup = self.transform_to_sirup(vendor_data, sirup_type)
        if not sirup:
            return None
        return self.sirup_to_bite(sirup, geoid, params)

    def supports_sirup_type(self, sirup_type: SIRUPType) -> bool:
        return sirup_type in self.sirup_types

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "vendor_name": self.vendor_name,
            "sirup_types": [t.value for t in self.sirup_types],
            "auth_method": self.auth_method.value,
            "rate_limit": self.rate_limit,
            "metadata": self.metadata,
        }


class TAPAdapterFactory:
    def __init__(self):
        self.adapters: Dict[str, TAPAdapter] = {}
        self.vendor_configs: Dict[str, Dict[str, Any]] = {}

    def register_adapter(self, config: Dict[str, Any]) -> TAPAdapter:
        vendor_name = config.get("vendor_name")
        adapter_class_path = config.get("adapter_class")
        if not vendor_name or not adapter_class_path:
            raise ValueError("vendor_name and adapter_class are required")
        module_path, class_name = adapter_class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        adapter = adapter_class(config)
        self.adapters[vendor_name] = adapter
        self.vendor_configs[vendor_name] = config
        logger.info("registered TAP adapter %s (%s)", vendor_name,
                    [t.value for t in adapter.sirup_types])
        return adapter

    def get_adapter(self, vendor_name: str) -> Optional[TAPAdapter]:
        return self.adapters.get(vendor_name)

    def get_adapters_for_sirup_type(self, sirup_type: SIRUPType) -> List[TAPAdapter]:
        return [a for a in self.adapters.values() if a.supports_sirup_type(sirup_type)]

    def list_vendors(self) -> List[str]:
        return list(self.adapters.keys())


def create_bite_from_sirup(
    sirup: Dict[str, Any], bite_type: str, additional_tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Standard SIRUP -> BITE envelope (Header/Body/Footer with content hash)."""
    bite_id = str(ULID())
    timestamp = sirup.get("timestamp", datetime.now(timezone.utc).isoformat())
    header = {
        "id": bite_id,
        "geoid": sirup.get("geoid", ""),
        "timestamp": timestamp,
        "type": bite_type,
        "source": {
            "pipeline": "TAP",
            "vendor": sirup.get("vendor", "unknown"),
            "sirup_type": sirup.get("sirup_type", ""),
            "auto_generated": True,
        },
    }
    body = {
        "sirup_data": sirup.get("data", {}),
        "metadata": sirup.get("metadata", {}),
        "units": sirup.get("units", {}),
    }
    digest = hashlib.sha256(
        (json.dumps(header, sort_keys=True) + json.dumps(body, sort_keys=True)).encode()
    ).hexdigest()
    tags = ["automated", "tap", sirup.get("sirup_type", "")]
    if additional_tags:
        tags.extend(additional_tags)
    return {
        "Header": header,
        "Body": body,
        "Footer": {"hash": digest, "schema_version": "1.0", "tags": tags},
    }
