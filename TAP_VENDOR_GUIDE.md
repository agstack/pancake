# TAP Vendor Integration Guide

**Version 1.0 | For AgStack Community Members**

## Overview

TAP (Third-party Agentic-Pipeline) is a universal data integration framework that enables agricultural data vendors to seamlessly integrate with the PANCAKE ecosystem. This guide shows you how to offer your data services through TAP.

---

## Table of Contents

1. [Why Integrate with TAP?](#why-integrate)
2. [Core Concepts](#core-concepts)
3. [Integration Steps](#integration-steps)
4. [Adapter Development](#adapter-development)
5. [Testing & Validation](#testing)
6. [Deployment](#deployment)
7. [Examples](#examples)
8. [Support](#support)

---

## Why Integrate with TAP? {#why-integrate}

### For Vendors
- **Reach the AgStack ecosystem**: Instant access to farmers, researchers, and agribusinesses
- **Standardized integration**: One adapter works everywhere PANCAKE is deployed
- **BITE format**: Your data becomes instantly queryable via natural language AI
- **Reduced integration costs**: Write once, deploy everywhere
- **Community support**: Open-source collaboration and bug fixes

### For Users
- **Vendor-agnostic**: Switch providers without changing code
- **Unified interface**: Same query format for all data sources
- **Data portability**: All vendor data in standard BITE format
- **Cost optimization**: Easy A/B testing of vendor services

---

## Core Concepts {#core-concepts}

### 1. TAP Architecture

```
┌─────────────┐
│ Your Vendor │
│     API     │
└──────┬──────┘
       │
       │ (1) Fetch raw data
       ↓
┌─────────────┐
│ TAP Adapter │ ← You implement this
└──────┬──────┘
       │
       │ (2) Transform to SIRUP
       ↓
┌─────────────┐
│    SIRUP    │ (Normalized data)
└──────┬──────┘
       │
       │ (3) Convert to BITE
       ↓
┌─────────────┐
│    BITE     │ (Standard format)
└──────┬──────┘
       │
       │ (4) Store in PANCAKE
       ↓
┌─────────────┐
│  PANCAKE DB │
└─────────────┘
```

### 2. Key Definitions

**TAP (Third-party Agentic-Pipeline)**
- The integration framework/manifold
- Handles vendor discovery, auth, rate limiting
- Routes requests to appropriate adapters

**SIRUP (Spatio-temporal Intelligence for Reasoning and Unified Perception)**
- Enriched, normalized data payload
- Vendor-specific structure, but documented
- Includes spatial, temporal, and semantic context
- Think: "maple syrup" that flows through the TAP

**BITE (Bidirectional Interchange Transport Envelope)**
- Universal data format (JSON)
- Three sections: Header, Body, Footer
- Think: "IP packet for agricultural data"
- Enables interoperability across all systems

**Adapter**
- Your code that connects vendor API → TAP
- Implements 3 methods: fetch, transform, convert
- ~100-300 lines of Python

### 3. SIRUP Types

Standard SIRUP types vendors can provide:

| Type | Description | Examples |
|------|-------------|----------|
| `satellite_imagery` | Remote sensing data | NDVI, EVI, LAI, thermal |
| `weather_forecast` | Future weather predictions | Temperature, precipitation, wind |
| `weather_historical` | Past weather observations | Climate records, trends |
| `soil_profile` | Soil properties by depth | Texture, pH, nutrients |
| `soil_infiltration` | Water infiltration rates | Ksat, drainage |
| `soil_moisture` | Current/historical moisture | Volumetric water content |
| `crop_health` | Crop condition monitoring | Disease detection, stress |
| `pest_disease` | Pest/pathogen data | Pressure maps, forecasts |
| `market_price` | Agricultural commodities | Spot prices, futures |
| `custom` | Your proprietary data | Define your own structure |

---

## Integration Steps {#integration-steps}

### Step 1: Understand Requirements

**What you need:**
- RESTful API (or we can help wrap other protocols)
- Authentication method (API key, OAuth2, etc.)
- Data that serves a SIRUP type (or propose a new one)
- Python 3.8+ environment for testing

**What you'll create:**
- 1 Python file (`your_vendor_adapter.py`)
- 1 config block in `tap_vendors.yaml`
- 1 test script (optional but recommended)

### Step 2: Choose Your SIRUP Type

Identify which SIRUP type(s) your data fits:

```python
from tap_adapter_base import SIRUPType

# Example: Weather data
my_sirup_types = [
    SIRUPType.WEATHER_FORECAST,
    SIRUPType.WEATHER_HISTORICAL
]
```

If none fit, propose a new one to the AgStack TAC.

### Step 3: Set Up Development Environment

```bash
# Clone PANCAKE repo
git clone https://github.com/agstack/pancake.git
cd pancake

# Install dependencies
pip install -r requirements_poc.txt
pip install pyyaml requests

# Set up your API credentials
export YOUR_VENDOR_API_KEY="your_key_here"
```

### Step 4: Implement Adapter

See [Adapter Development](#adapter-development) below.

### Step 5: Register in Config

Add your vendor to `tap_vendors.yaml`:

```yaml
vendors:
  - vendor_name: your_vendor
    adapter_class: tap_adapters.YourVendorAdapter
    base_url: https://api.yourvendor.com
    auth_method: api_key
    credentials:
      api_key: ${YOUR_VENDOR_API_KEY}
    sirup_types:
      - weather_forecast
    rate_limit:
      max_requests: 100
      time_window: 60
    timeout: 30
    metadata:
      description: "Your service description"
      resolution: "1km"
      coverage: "North America"
```

### Step 6: Test

```python
from tap_adapter_base import TAPAdapterFactory, SIRUPType

# Load your adapter
factory = TAPAdapterFactory('tap_vendors.yaml')
adapter = factory.get_adapter('your_vendor')

# Test fetch
bite = adapter.fetch_and_transform(
    geoid="test-geoid-123",
    sirup_type=SIRUPType.WEATHER_FORECAST,
    params={"start_date": "2025-01-01", "end_date": "2025-01-07"}
)

print(bite)
```

### Step 7: Submit to Community

1. Fork the PANCAKE repo
2. Add your adapter file to `tap_adapters.py` (or separate module)
3. Add config block to `tap_vendors.yaml`
4. Add tests to `tests/test_tap_adapters.py`
5. Submit Pull Request to AgStack
6. AgStack TAC reviews and approves

---

## Adapter Development {#adapter-development}

### Template Structure

```python
from tap_adapter_base import TAPAdapter, SIRUPType, create_bite_from_sirup
import requests
from typing import Dict, Any, Optional

class YourVendorAdapter(TAPAdapter):
    """
    Adapter for YourVendor Data Service
    
    Provides: WEATHER_FORECAST SIRUP
    Authentication: API Key
    """
    
    def _initialize(self):
        """Setup vendor-specific configuration"""
        self.api_key = self.credentials.get('api_key', '')
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch raw data from your vendor API
        
        Params:
            - start_date: str (YYYY-MM-DD)
            - end_date: str (YYYY-MM-DD)
            - ... your custom params
        
        Returns:
            Raw API response as dict, or None if failed
        """
        url = f"{self.base_url}/forecast"
        query_params = {
            "geoid": geoid,
            "start": params.get('start_date'),
            "end": params.get('end_date')
        }
        
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                params=query_params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API error: {response.status_code}")
                return None
        
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None
    
    def transform_to_sirup(self, vendor_data: Dict[str, Any], sirup_type: SIRUPType) -> Optional[Dict[str, Any]]:
        """
        Transform your raw data into SIRUP format
        
        SIRUP Structure:
        {
            "sirup_type": str,
            "vendor": str,
            "timestamp": str (ISO 8601),
            "geoid": str,
            "data": dict (your normalized data),
            "metadata": dict (resolution, confidence, etc.),
            "units": dict (for all numeric values)
        }
        """
        if sirup_type != SIRUPType.WEATHER_FORECAST:
            return None
        
        # Extract and normalize your data
        forecast = vendor_data.get('forecast', [])
        
        sirup = {
            "sirup_type": sirup_type.value,
            "vendor": self.vendor_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "geoid": vendor_data.get('location_id', ''),
            "data": {
                "forecast_days": forecast,
                "summary": {
                    "avg_temp": sum(d['temp'] for d in forecast) / len(forecast),
                    "total_precip": sum(d['precip'] for d in forecast)
                }
            },
            "metadata": {
                "source": "YourVendor Weather Model",
                "resolution": "1km",
                "model_version": vendor_data.get('version', 'v1.0')
            },
            "units": {
                "temperature": "°C",
                "precipitation": "mm"
            }
        }
        
        return sirup
    
    def sirup_to_bite(self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert SIRUP into standardized BITE format
        
        Use the helper function for standard BITEs
        """
        bite = create_bite_from_sirup(
            sirup=sirup,
            bite_type="weather_forecast",
            additional_tags=["weather", "forecast", "your_vendor"]
        )
        
        # Override geoid if needed
        if geoid:
            bite["Header"]["geoid"] = geoid
        
        return bite
```

### Key Implementation Notes

1. **Error Handling**: Always return `None` on failure, don't raise exceptions
2. **Timeouts**: Respect `self.timeout` from config
3. **Rate Limiting**: TAP factory handles this, but be respectful
4. **Logging**: Use `print()` for errors (we'll add proper logging later)
5. **Data Types**: Convert numpy/pandas types to native Python (`float()`, `int()`, `list()`)
6. **Timestamps**: Always ISO 8601 format with 'Z' suffix (UTC)
7. **Units**: Always document units in SIRUP metadata

### Common Patterns

#### Pattern 1: API with Pagination

```python
def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    all_data = []
    page = 1
    
    while True:
        response = requests.get(
            f"{self.base_url}/data",
            params={"geoid": geoid, "page": page},
            headers=self.headers
        )
        
        if response.status_code != 200:
            break
        
        data = response.json()
        all_data.extend(data.get('results', []))
        
        if not data.get('has_next'):
            break
        
        page += 1
    
    return {"results": all_data}
```

#### Pattern 2: Retry Logic

```python
def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
        except requests.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"Timeout after {max_retries} attempts")
    
    return None
```

#### Pattern 3: Multi-Point Sampling

```python
def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Get field boundary
    boundary = self._get_field_boundary(geoid)
    
    # Sample multiple points
    sample_points = self._generate_sample_points(boundary, n=5)
    
    results = []
    for point in sample_points:
        data = self._fetch_point_data(point['lat'], point['lon'])
        if data:
            results.append(data)
    
    return {"samples": results, "boundary": boundary}
```

---

## Testing & Validation {#testing}

### Unit Tests

```python
import pytest
from tap_adapters import YourVendorAdapter

def test_adapter_initialization():
    config = {
        'vendor_name': 'your_vendor',
        'base_url': 'https://api.yourvendor.com',
        'auth_method': 'api_key',
        'credentials': {'api_key': 'test_key'},
        'sirup_types': ['weather_forecast']
    }
    
    adapter = YourVendorAdapter(config)
    assert adapter.vendor_name == 'your_vendor'
    assert adapter.api_key == 'test_key'

def test_fetch_and_transform():
    adapter = YourVendorAdapter(test_config)
    
    bite = adapter.fetch_and_transform(
        geoid="test-geoid",
        sirup_type=SIRUPType.WEATHER_FORECAST,
        params={"start_date": "2025-01-01", "end_date": "2025-01-07"}
    )
    
    assert bite is not None
    assert "Header" in bite
    assert "Body" in bite
    assert "Footer" in bite
    assert bite["Header"]["geoid"] == "test-geoid"
```

### Integration Tests

```python
def test_end_to_end():
    # Real API call (use test credentials)
    factory = TAPAdapterFactory('tap_vendors.yaml')
    adapter = factory.get_adapter('your_vendor')
    
    bite = adapter.fetch_and_transform(
        geoid="real-test-geoid",
        sirup_type=SIRUPType.WEATHER_FORECAST,
        params={"start_date": "2025-01-01", "end_date": "2025-01-07"}
    )
    
    # Validate BITE structure
    assert BITE.validate(bite) == True
    
    # Check data quality
    assert bite["Body"]["sirup_data"]["data"] is not None
```

---

## Deployment {#deployment}

### For AgStack Community (Open Source)

1. Submit PR to PANCAKE repo
2. AgStack TAC reviews
3. Merged into `main` branch
4. Available to all community members
5. Listed in vendor registry

### For Commercial Vendors

1. Implement adapter (same process)
2. Host privately or request commercial support
3. Deploy on your infrastructure
4. Offer as managed service to customers

### Environment Variables

Always use environment variables for credentials:

```bash
# .env file
VENDOR_API_KEY=your_secret_key
VENDOR_SECRET=your_secret

# Load in code
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('VENDOR_API_KEY')
```

Never commit secrets to git!

---

## Examples {#examples}

### Example 1: Simple Weather API

See `tap_adapters.py:TerrapipeGFSAdapter` for a complete weather forecast implementation.

### Example 2: Soil Data Provider

See `tap_adapters.py:SoilGridsAdapter` for multi-SIRUP-type support (profile + infiltration).

### Example 3: Satellite Imagery

See `tap_adapters.py:TerrapipeNDVIAdapter` for handling raster imagery data.

---

## Support {#support}

### Documentation
- [BITE.md](BITE.md) - BITE format specification
- [TAP.md](TAP.md) - TAP architecture deep dive
- [SIRUP.md](SIRUP.md) - SIRUP data format
- [PANCAKE.md](PANCAKE.md) - Storage system overview

### Community
- **AgStack Slack**: #pancake channel
- **GitHub Issues**: [github.com/agstack/pancake/issues](https://github.com/agstack/pancake/issues)
- **Email**: pancake-support@agstack.org

### Commercial Support
- Contact AgStack for enterprise integration support
- Custom adapter development services available
- SLA-backed deployments

---

## Checklist

Before submitting your adapter:

- [ ] Adapter implements all 3 required methods
- [ ] Config added to `tap_vendors.yaml`
- [ ] Unit tests written and passing
- [ ] Integration test with real API successful
- [ ] BITE validation passes
- [ ] Documentation updated (if new SIRUP type)
- [ ] No secrets in code (use env vars)
- [ ] Error handling for all API calls
- [ ] Proper logging/print statements
- [ ] Code follows Python PEP 8 style

---

## License

Apache 2.0 - Same as PANCAKE

Community members: Free to use  
Commercial vendors: Contact AgStack for licensing

---

**Welcome to the TAP ecosystem! 🚰🌾**

Questions? Open an issue or reach out on Slack. We're here to help!

