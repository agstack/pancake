# Module 5: TAP/SIRUP I/O System
## Universal Vendor Integration Framework

**An AgStack Project of The Linux Foundation**

**Episode**: Module 5 of 10  
**Duration**: ~25 minutes  
**Prerequisites**: Episode 0, Module 2 (BITE), Module 4 (MEAL)  
**Technical Level**: Intermediate to Advanced

---

## Introduction

In Module 2, we explored BITE—the universal data format. But how does vendor data (satellite imagery, weather, soil sensors) become BITEs? That's where **TAP** (Third-party Agentic-Pipeline) and **SIRUP** (Spatio-temporal Intelligence for Reasoning and Unified Perception) come in.

**What you'll learn:**
- The vendor integration problem (100+ vendors, 1000s of redundant integrations)
- TAP architecture (adapter pattern, universal docking port)
- SIRUP format (normalized vendor data)
- Adapter implementation (how vendors "dock" their APIs)
- Multi-vendor demo (Terrapipe, SoilGrids, Weather APIs)
- Vendor benefits (reduced cost, faster time-to-market)
- Farmer benefits (vendor choice, data portability)

**Who this is for:**
- Vendor engineers building TAP adapters
- Backend developers integrating third-party APIs
- Farm operators evaluating vendor options
- Standards committee members designing interoperability

---

## Chapter 1: The Vendor Integration Problem

### Scenario: Adding Satellite Imagery to a Farm App

**Today's workflow** (without TAP):

**Step 1**: Choose vendor (Planet, Sentinel Hub, terrapipe.io)

**Step 2**: Read vendor docs (200 pages)
- Authentication: API keys? OAuth? JWT?
- Endpoints: REST? GraphQL? SOAP?
- Data format: GeoJSON? WKT? Custom JSON?
- Rate limits: 100 requests/day? 1000/hour?
- Error handling: HTTP 429? 503? Custom error codes?

**Step 3**: Write custom integration code
```python
# planet.py (500 lines)
class PlanetClient:
    def authenticate(self): ...
    def search_scenes(self, aoi, date_range): ...
    def download_image(self, scene_id): ...
    def parse_metadata(self, response): ...
    def handle_errors(self, exception): ...
    def retry_logic(self): ...
```

**Step 4**: Convert to internal format
```python
def planet_to_internal(planet_data):
    return {
        "ndvi": extract_ndvi(planet_data),
        "date": parse_date(planet_data["acquired"]),
        "cloud_cover": planet_data["properties"]["cloud_percent"],
        # ... 50 more fields
    }
```

**Step 5**: Maintain forever
- **API changes**: Vendor updates endpoint → code breaks
- **Rate limits**: Vendor changes limits → app throttled
- **New fields**: Vendor adds data → manual updates required

**Result**: 
- **Time**: 2-4 weeks per vendor
- **Cost**: $10K-$50K development
- **Maintenance**: Ongoing burden
- **Vendor lock-in**: Hard to switch (sunk cost)

### The Multiplication Problem

**1 app × 10 vendors = 10 custom integrations**  
**100 apps × 10 vendors = 1,000 redundant integrations**  
**1,000 farms × 10 vendors = 10,000 variations**

**Industry-wide waste**: $500M-$1B/year (estimated) on redundant integration work.

---

## Chapter 2: What is TAP?

**TAP** is a **pattern**, not a product. It defines:
1. **Input**: Vendor API (any format)
2. **Output**: BITEs (standardized)
3. **Process**: Adapters (plug-in modules)

### The TAP Pattern

```
Vendor API → TAP Adapter → BITE Generator → PANCAKE Storage
```

**Analogy**: Electrical plug/socket
- **Vendor API**: Power source (120V AC, 240V AC, DC, etc.)
- **TAP Adapter**: Plug shape (Type A, Type C, USB-C, etc.)
- **BITE**: Standard voltage (transformed to 5V DC for devices)
- **PANCAKE**: Device (charges regardless of original source)

### TAP Components

**1. TAP Core** (shared infrastructure)
- Authentication manager
- Rate limiting (respect vendor quotas)
- Error handling (retries, backoff)
- Logging (audit trail)
- Scheduling (cron-like)

**2. TAP Adapter** (vendor-specific, pluggable)
- API client (how to call vendor)
- Data mapper (vendor format → BITE Body)
- Metadata extractor (vendor-specific fields)

**3. BITE Generator** (universal)
- Create BITE Header (id, geoid, timestamp, type)
- Insert Body (from adapter)
- Compute Footer (hash)

**4. PANCAKE Connector** (universal)
- Store BITE
- Generate embedding
- Index

---

## Chapter 3: The Docking Metaphor

### Inspiration: Space Station Docking

**International Space Station (ISS)**: Multiple spacecraft dock (SpaceX, Russian Soyuz, Japanese HTV)

**How?** Standardized **docking port** (Common Berthing Mechanism)
- Any spacecraft can dock
- No ISS modifications needed
- New spacecraft just need compatible adapter

**TAP is the "docking port" for agricultural data vendors.**

### TAP Docking Process

**Step 1**: Vendor approaches TAP
```
Vendor SIRUP Data ----approaching----→ TAP
```

**Step 2**: Authentication handshake
```
TAP: "Provide credentials"
Vendor: "Here's API key: xyz123"
TAP: "Validated. Proceed."
```

**Step 3**: Data exchange
```
Vendor: "Here's NDVI for field-abc, date 2024-11-01"
TAP: "Received. Transforming..."
```

**Step 4**: BITE creation
```
TAP: "Created BITE-12345 (imagery_sirup)"
```

**Step 5**: Storage
```
TAP → PANCAKE: "Store BITE-12345"
PANCAKE: "Stored. Embedding generated."
```

**Step 6**: Disconnect (vendor can leave)
```
Vendor: "Done. See you tomorrow."
TAP: "Acknowledged. Thanks!"
```

### Why Docking Works

**For Vendors**:
- Build adapter once, works forever
- No app-specific integrations (1 TAP adapter, not 1000 custom integrations)
- Focus on core value (satellite imagery, weather, sensors), not integration

**For Apps/Farmers**:
- Add new vendor in minutes (not weeks)
- Switch vendors easily (swap adapter, BITEs stay consistent)
- All vendor data in same format (BITE)

---

## Chapter 4: SIRUP Format

### What is SIRUP?

**SIRUP** (Spatio-temporal Intelligence for Reasoning and Unified Perception) is the normalized data format that flows through TAP adapters.

**SIRUP is vendor-agnostic**:
- Terrapipe NDVI → SIRUP → BITE
- Planet RGB → SIRUP → BITE
- SoilGrids soil data → SIRUP → BITE
- DTN weather → SIRUP → BITE

**All become BITEs with consistent structure.**

### SIRUP Structure

```json
{
  "sirup_type": "satellite_imagery",
  "vendor": "terrapipe.io",
  "geoid": "field-abc",
  "timestamp": "2025-03-15T10:45:00Z",
  "data": {
    "satellite": "Sentinel-2",
    "ndvi_stats": {
      "mean": 0.65,
      "min": 0.42,
      "max": 0.81,
      "std": 0.08
    },
    "raster_url": "https://api.terrapipe.io/rasters/2025-03-15/field-abc.tif",
    "resolution_m": 10
  },
  "metadata": {
    "cloud_cover_percent": 5,
    "processing": {
      "atmospheric_correction": "Sen2Cor",
      "cloud_masking": "FMask"
    }
  }
}
```

### Supported SIRUP Types

| SIRUP Type | Description | Examples |
|------------|-------------|----------|
| `satellite_imagery` | Remote sensing data | NDVI, EVI, thermal |
| `weather_forecast` | Future weather | Temperature, precipitation |
| `weather_historical` | Past weather | Climate records |
| `soil_profile` | Soil properties by depth | Texture, pH, nutrients |
| `soil_infiltration` | Water infiltration | Ksat, drainage rates |
| `soil_moisture` | Current moisture | Volumetric water content |
| `crop_health` | Crop monitoring | Disease, stress detection |
| `pest_disease` | Pest/pathogen data | Pressure maps |
| `market_price` | Commodity prices | Spot prices, futures |
| `custom` | Proprietary data | Define your own |

**Vendors propose new types** → AgStack TAC approves → Becomes standard

---

## Chapter 5: Adapter Implementation

### Adapter Interface (Standardized)

Every TAP adapter must implement:

```python
class TAPAdapter:
    """Base class for all TAP adapters"""
    
    def authenticate(self, credentials: dict) -> bool:
        """Validate API credentials"""
        raise NotImplementedError
    
    def fetch_data(self, params: dict) -> dict:
        """Fetch data from vendor API
        
        Args:
            params: {
                "geoid": "abc123",
                "start_date": "2024-10-01",
                "end_date": "2024-10-31",
                "data_type": "ndvi"  # vendor-specific
            }
        
        Returns:
            Raw vendor response (any format)
        """
        raise NotImplementedError
    
    def transform_to_sirup(self, raw_data: dict, params: dict) -> dict:
        """Convert vendor data to SIRUP format
        
        Returns:
            {
                "sirup_type": "satellite_ndvi",
                "vendor": "vendor-name",
                "geoid": params["geoid"],
                "timestamp": "...",
                "data": {...},
                "metadata": {...}
            }
        """
        raise NotImplementedError
    
    def get_metadata(self) -> dict:
        """Adapter metadata (for TAP registry)
        
        Returns:
            {
                "vendor": "vendor-name",
                "version": "1.0.0",
                "data_types": ["ndvi", "rgb_imagery"],
                "rate_limit": "1000/hour",
                "cost": "$0.05/field/month"
            }
        """
        raise NotImplementedError
```

### Example: Terrapipe NDVI Adapter

```python
from tap_adapter_base import TAPAdapter, SIRUPType
import requests

class TerrapipeNDVIAdapter(TAPAdapter):
    def __init__(self, config):
        self.base_url = "https://appserver.terrapipe.io"
        self.api_key = config['credentials']['api_key']
        self.client = config['credentials']['client']
        self.headers = {
            "secretkey": self.api_key,
            "client": self.client
        }
    
    def authenticate(self, credentials: dict) -> bool:
        """Test authentication"""
        response = requests.get(f"{self.base_url}/health", headers=self.headers)
        return response.status_code == 200
    
    def fetch_data(self, params: dict) -> dict:
        """Fetch NDVI data from Terrapipe"""
        url = f"{self.base_url}/getNDVIImg"
        response = requests.get(url, headers=self.headers, params={
            "geoid": params["geoid"],
            "date": params["date"]
        })
        return response.json()
    
    def transform_to_sirup(self, raw_data: dict, params: dict) -> dict:
        """Convert Terrapipe response to SIRUP"""
        ndvi_features = raw_data.get("ndvi_img", {}).get("features", [])
        ndvi_values = [f["properties"]["NDVI"] for f in ndvi_features]
        
        return {
            "sirup_type": SIRUPType.SATELLITE_IMAGERY.value,
            "vendor": "terrapipe.io",
            "geoid": params["geoid"],
            "timestamp": params["date"] + "T10:45:00Z",
            "data": {
                "satellite": "Sentinel-2",
                "ndvi_stats": {
                    "mean": float(np.mean(ndvi_values)),
                    "min": float(np.min(ndvi_values)),
                    "max": float(np.max(ndvi_values)),
                    "std": float(np.std(ndvi_values)),
                    "count": len(ndvi_values)
                },
                "raster_url": raw_data.get("raster_url"),
                "resolution_m": 10
            },
            "metadata": {
                "cloud_cover_percent": raw_data.get("cloud_cover", 0),
                "processing": {
                    "atmospheric_correction": "Sen2Cor"
                }
            }
        }
    
    def get_metadata(self) -> dict:
        return {
            "vendor": "terrapipe.io",
            "version": "1.0.0",
            "data_types": ["ndvi", "rgb"],
            "rate_limit": "unlimited",
            "cost": "$0.10/field/month"
        }
```

### Adapter Factory

The TAP Adapter Factory automatically discovers and loads vendor adapters from a simple YAML config:

```yaml
vendors:
  - vendor_name: terrapipe_ndvi
    adapter_class: tap_adapters.TerrapipeNDVIAdapter
    base_url: https://appserver.terrapipe.io
    auth_method: api_key
    credentials:
      api_key: ${TERRAPIPE_API_KEY}
      client: Dev
    sirup_types:
      - satellite_imagery
```

**Add a vendor** = Add a config block. No code changes needed.

---

## Chapter 6: Multi-Vendor Demo

### Three Vendors, One Interface

```python
from tap_adapter_base import TAPAdapterFactory, SIRUPType

# Load all vendors from config
factory = TAPAdapterFactory('tap_vendors.yaml')

# Fetch from different vendors, same interface
ndvi_bite = factory.get_adapter('terrapipe_ndvi').fetch_and_transform(
    geoid=my_field,
    sirup_type=SIRUPType.SATELLITE_IMAGERY,
    params={'date': '2025-01-15'}
)

soil_bite = factory.get_adapter('soilgrids').fetch_and_transform(
    geoid=my_field,
    sirup_type=SIRUPType.SOIL_PROFILE,
    params={'lat': 36.8, 'lon': -120.4, 'analysis_type': 'profile'}
)

weather_bite = factory.get_adapter('terrapipe_weather').fetch_and_transform(
    geoid=my_field,
    sirup_type=SIRUPType.WEATHER_FORECAST,
    params={'start_date': '2025-01-15', 'end_date': '2025-01-22'}
)

# All BITEs are standardized, ready for PANCAKE
pancake.store([ndvi_bite, soil_bite, weather_bite])
```

**Result**: 3 different vendors, 1 interface, 0 vendor-specific code.

### Reference Implementations

TAP ships with three reference adapters:

**1. Terrapipe NDVI Adapter** (`TerrapipeNDVIAdapter`)
- SIRUP Type: `satellite_imagery`
- Data: Sentinel-2 NDVI at 10m resolution
- Auth: API key (secretkey + client)
- Coverage: Global

**2. SoilGrids Adapter** (`SoilGridsAdapter`)
- SIRUP Types: `soil_profile`, `soil_infiltration`
- Data: Global soil properties at 250m
- Auth: Public API (no auth required)
- Coverage: Global
- Source: ISRIC SoilGrids

**3. Terrapipe Weather Adapter** (`TerrapipeGFSAdapter`)
- SIRUP Type: `weather_forecast`
- Data: NOAA GFS weather forecasts
- Auth: OAuth2 bearer token + API key
- Coverage: Global, 0-16 day forecasts

---

## Chapter 7: Vendor Benefits

### 1. Reduced Integration Cost

**Before TAP**: 
- Custom integration for every customer
- 100 customers = 100 integrations
- Cost: $1K-$10K per integration

**With TAP**:
- One adapter (works for all TAP users)
- Cost: $5K-$10K one-time

**Savings**: $90K-$990K (for 100 customers)

### 2. Faster Time-to-Market

**Before TAP**: 
- Negotiate with each app developer
- Custom SDK for each platform
- Months per integration

**With TAP**:
- Publish adapter to TAP registry
- Instantly available to all TAP users
- Days to integrate

### 3. Customer Acquisition

**Before TAP**:
- Sales team pitches each farm/app
- One-by-one adoption

**With TAP**:
- Listed in TAP marketplace
- Farmers discover organically
- Network effects (more TAP users = more potential customers)

### 4. Focus on Core Value

**Before TAP**:
- 30% time on integration code
- 70% time on core product (satellite processing, weather models, etc.)

**With TAP**:
- 5% time on TAP adapter
- 95% time on core product

**Result**: Better product, faster innovation.

### 5. Vendor Independence

**Concern**: "What if TAP becomes a gatekeeper?"

**Answer**: TAP is open-source, vendor-neutral
- No approval process (publish adapter freely)
- No fees (open-source license)
- No lock-in (adapters work with any TAP-compatible system)

**Governance**: Community-driven (like Linux, Kubernetes)

---

## Chapter 8: Farmer Benefits

### 1. Vendor Choice

**Before TAP**:
- App supports 3 satellite vendors (hard-coded)
- Want to switch? App doesn't support new vendor.
- Locked in.

**With TAP**:
- App supports TAP (= 100+ vendors)
- Switch vendors in minutes:
```bash
tap-cli unsubscribe terrapipe-field-abc
tap-cli subscribe planet-field-abc
```
- BITEs stay consistent (same format)

### 2. Price Competition

**Before TAP**:
- Vendor knows you're locked in
- Prices increase, no alternatives

**With TAP**:
- Compare vendors side-by-side (TAP marketplace)
- Switch easily (no re-integration)
- Vendors compete on price/quality (not integration)

### 3. Data Portability

**Before TAP**:
- Vendor data in proprietary format
- Can't combine with other vendors

**With TAP**:
- All vendor data as BITEs
- Combine terrapipe NDVI + Planet RGB + DTN weather
- Unified analysis

### 4. Future-Proof

**Before TAP**:
- App shuts down → data lost
- Vendor changes API → integration breaks

**With TAP**:
- BITEs stored locally (PANCAKE)
- App-agnostic (move to new app, keep data)
- Adapter breaks? Use different vendor (BITEs compatible)

---

## Chapter 9: Vendor Onboarding

**For vendors wanting to integrate with TAP**:

1. **Read the guide**: See [TAP_VENDOR_GUIDE.md](TAP_VENDOR_GUIDE.md)
2. **Implement adapter**: ~100-300 lines, inherit from `TAPAdapter`
3. **Add config**: Single YAML block
4. **Test**: Use provided test framework
5. **Submit**: Pull request to AgStack PANCAKE repo
6. **Deploy**: Instantly available to all PANCAKE users

**Time to integrate**: 1-2 days (vs weeks/months for custom integration)

**Community support**: AgStack TAC reviews and assists

---

## Conclusion

**TAP solves the agricultural vendor integration crisis** by providing a **universal docking mechanism**:
- **Vendors**: Build one adapter, reach all TAP users
- **Farmers**: Add vendors in minutes, no custom integration
- **Ecosystem**: Network effects, data portability, innovation

**Why TAP matters**:
- **Today**: 100+ vendors, 1000s of redundant integrations, $1B wasted
- **Future**: 1 TAP standard, 100+ adapters, unified BITE ecosystem

**TAP is the "USB-C" of agricultural data—one port, infinite possibilities.**

**Next module**: Multi-Pronged RAG Query Engine - Semantic + Spatial + Temporal search.

---

**An AgStack Project | Powered by The Linux Foundation**

**Learn more**: https://agstack.org/pancake  
**GitHub**: https://github.com/agstack/pancake  
**License**: Apache 2.0 (Code) | CC BY 4.0 (Documentation)

