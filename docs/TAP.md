# TAP: Third-party Agentic-Pipeline

**Version**: 1.0  
**Status**: Proof of Concept  
**Purpose**: Universal manifold for vendor data integration into the BITE ecosystem

---

## Table of Contents

1. [Overview](#overview)
2. [The Vendor Integration Problem](#the-vendor-integration-problem)
3. [What is TAP?](#what-is-tap)
4. [The Docking Metaphor](#the-docking-metaphor)
5. [TAP Architecture](#tap-architecture)
6. [How Vendors "Dock" Their SIRUP](#how-vendors-dock-their-sirup)
7. [Design Rationale](#design-rationale)
8. [TAP CLI Framework](#tap-cli-framework)
9. [Example: terrapipe.io Integration](#example-terrapipeio-integration)
10. [Vendor Benefits](#vendor-benefits)
11. [Farmer Benefits](#farmer-benefits)
12. [Future: TAP Marketplace](#future-tap-marketplace)

---

## Overview

**TAP** (Third-party Agentic-Pipeline) is a standardized integration pattern that enables agricultural data vendors to connect their services to the BITE/PANCAKE ecosystem without custom integration work.

### The Core Idea

**Problem**: 100+ ag-tech vendors, each with unique APIs, formats, authentication schemes  
**Solution**: Standardized "docking port" that any vendor can plug into  
**Result**: Vendor data automatically becomes BITEs, ready for AI/ML consumption

### Why "Agentic"?

TAP is designed for autonomous operation:
- **Scheduled**: Runs automatically (daily, hourly, on-demand)
- **Self-healing**: Retries on failure, handles rate limits
- **Intelligent**: Adapts to API changes, validates data quality
- **Observable**: Logs, metrics, alerts (vendor-agnostic monitoring)

**Traditional integrations**: Manual, brittle, vendor-specific  
**TAP**: Automated, robust, universal

---

## The Vendor Integration Problem

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

## What is TAP?

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

## The Docking Metaphor

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

## TAP Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         TAP SYSTEM                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Adapter    │  │   Adapter    │  │   Adapter    │    │
│  │  Planet.com  │  │ Terrapipe.io │  │  Sentinel    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            │                                │
│                    ┌───────▼────────┐                      │
│                    │   TAP  CORE    │                      │
│                    │                 │                      │
│                    │ • Auth Manager  │                      │
│                    │ • Rate Limiter  │                      │
│                    │ • Scheduler     │                      │
│                    │ • Error Handler │                      │
│                    └───────┬─────────┘                     │
│                            │                                │
│                    ┌───────▼────────┐                      │
│                    │ BITE Generator │                      │
│                    └───────┬─────────┘                     │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
                      ┌─────────────┐
                      │   PANCAKE   │
                      │   Storage   │
                      └─────────────┘
```

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
    
    def transform_to_bite_body(self, raw_data: dict, params: dict) -> dict:
        """Convert vendor data to BITE Body format
        
        Returns:
            {
                "sirup_type": "satellite_ndvi",
                "vendor": "vendor-name",
                "ndvi_stats": {...},
                ...
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

### Adapter Lifecycle

**1. Registration**: Vendor submits adapter to TAP registry
```bash
tap-cli register-adapter terrapipe_adapter.py
```

**2. Installation**: Farmer installs adapter
```bash
tap-cli install terrapipe
```

**3. Configuration**: Farmer provides credentials
```bash
tap-cli config terrapipe \
  --api-key "xyz123" \
  --secret "abc789"
```

**4. Subscription**: Farmer subscribes fields to vendor data
```bash
tap-cli subscribe \
  --adapter terrapipe \
  --geoid field-abc \
  --data-type ndvi \
  --frequency daily
```

**5. Execution**: TAP runs automatically
```
[2024-11-01 06:00] TAP: Running terrapipe adapter for field-abc
[2024-11-01 06:01] TAP: Fetched NDVI data (date: 2024-10-31)
[2024-11-01 06:02] TAP: Created BITE-12345 (imagery_sirup)
[2024-11-01 06:03] TAP: Stored in PANCAKE
[2024-11-01 06:03] TAP: Success. Next run: 2024-11-02 06:00
```

**6. Monitoring**: Farmer tracks status
```bash
tap-cli status terrapipe
# Output:
# Adapter: terrapipe
# Status: Active
# Last run: 2024-11-01 06:03 (Success)
# BITEs created today: 10
# Errors (last 7 days): 0
```

---

## How Vendors "Dock" Their SIRUP

### Step-by-Step: Vendor Perspective

**Scenario**: terrapipe.io wants to offer NDVI data through TAP.

**Step 1**: Understand TAP Adapter Interface
- Read TAP adapter spec (10 pages)
- Review example adapters (reference implementations)

**Step 2**: Implement Adapter
```python
# terrapipe_adapter.py

from tap import TAPAdapter
import requests

class TerrapipeAdapter(TAPAdapter):
    def __init__(self):
        self.base_url = "https://appserver.terrapipe.io"
    
    def authenticate(self, credentials):
        # Terrapipe uses secretkey + client headers
        self.headers = {
            "secretkey": credentials["api_key"],
            "client": credentials["client_name"]
        }
        # Test auth
        response = requests.get(f"{self.base_url}/health", headers=self.headers)
        return response.status_code == 200
    
    def fetch_data(self, params):
        # Terrapipe API call
        url = f"{self.base_url}/getNDVIImg"
        response = requests.get(url, headers=self.headers, params={
            "geoid": params["geoid"],
            "date": params["date"]
        })
        return response.json()
    
    def transform_to_bite_body(self, raw_data, params):
        # Extract NDVI statistics
        ndvi_features = raw_data.get("ndvi_img", {}).get("features", [])
        ndvi_values = [f["properties"]["NDVI"] for f in ndvi_features]
        
        # Create SIRUP-structured body
        return {
            "sirup_type": "satellite_ndvi",
            "vendor": "terrapipe.io",
            "date": params["date"],
            "boundary": raw_data.get("boundary_geoDataFrameDict"),
            "ndvi_stats": {
                "mean": float(np.mean(ndvi_values)),
                "min": float(np.min(ndvi_values)),
                "max": float(np.max(ndvi_values)),
                "std": float(np.std(ndvi_values)),
                "count": len(ndvi_values)
            },
            "ndvi_image": raw_data.get("ndvi_img"),
            "metadata": raw_data.get("metadata")
        }
    
    def get_metadata(self):
        return {
            "vendor": "terrapipe.io",
            "version": "1.0.0",
            "data_types": ["ndvi", "rgb", "boundary"],
            "rate_limit": "unlimited",
            "cost": "$0.10/field/month",
            "documentation": "https://terrapipe.io/docs/tap"
        }
```

**Step 3**: Test Adapter
```bash
tap-cli test terrapipe_adapter.py \
  --geoid test-field \
  --date 2024-10-31 \
  --credentials '{"api_key": "xyz", "client": "dev"}'
```

**Step 4**: Submit to TAP Registry
```bash
tap-cli publish terrapipe_adapter.py \
  --name "terrapipe" \
  --description "Terrapipe.io NDVI satellite imagery" \
  --tags "satellite,ndvi,imagery"
```

**Step 5**: Done!
- Adapter is now available to all TAP users
- terrapipe.io gets new customers (farmers discover via TAP marketplace)
- Farmers get standardized access to terrapipe data (BITEs)

**Time to build**: 1-2 days (vs. weeks for custom integrations)

---

## Design Rationale

### Decision 1: Adapter Pattern vs Direct API

**Options**:
1. **Adapter pattern** (vendor writes adapter)
2. **Direct API** (TAP calls vendor API directly)
3. **Middleware** (TAP translates all vendors)

**Decision**: Adapter pattern

**Rationale**:
- **Vendor expertise**: Vendor knows their API best
- **Scalability**: TAP team can't maintain 100+ vendor clients
- **Flexibility**: Vendors can optimize (caching, batching)
- **Ownership**: Vendors control updates (no TAP bottleneck)

**Direct API rejected**:
- **Unsustainable**: TAP team maintains 100+ clients
- **Breaking changes**: Vendor updates → TAP breaks
- **No vendor buy-in**: Vendors not invested

**Middleware rejected**:
- **Translation layer**: Complex, error-prone
- **Lossy**: Vendor-specific features lost
- **Vendor lock-in** (to TAP)

### Decision 2: CLI vs GUI Configuration

**Options**:
1. **CLI** (command-line interface)
2. **GUI** (web dashboard)
3. **Config files** (YAML/JSON)

**Decision**: CLI (with optional GUI later)

**Rationale**:
- **Automation**: CLI scriptable (cron jobs, CI/CD)
- **Simplicity**: No server infrastructure needed
- **Accessibility**: Works on any OS (Windows, Mac, Linux)
- **Git-friendly**: Config as code (version control)

**GUI rejected** (for v1.0):
- **Complexity**: Web server, auth, UI/UX
- **Maintenance**: More surface area for bugs
- **Future option**: CLI commands wrap API (GUI can use same API)

**Config files rejected** (as primary):
- **Discoverability**: CLI has `--help`, YAML docs are external
- **Validation**: CLI validates input interactively

### Decision 3: Sync vs Async Execution

**Options**:
1. **Synchronous** (TAP waits for response)
2. **Asynchronous** (TAP queues, processes later)

**Decision**: Asynchronous (with sync option for testing)

**Rationale**:
- **Vendor latency**: Satellite APIs can take minutes
- **Failures**: Retry without blocking
- **Scheduling**: Run during off-peak hours

**Implementation**: Task queue (Celery, RabbitMQ)
```python
tap-cli subscribe terrapipe --geoid field-abc --schedule "daily at 6am"
# Creates recurring task: fetch data, create BITE, store
```

### Decision 4: Stateful vs Stateless Adapters

**Options**:
1. **Stateful** (adapter remembers last run)
2. **Stateless** (adapter requires explicit params)

**Decision**: Stateless (with TAP Core managing state)

**Rationale**:
- **Simplicity**: Adapters are pure functions
- **Testability**: No hidden state
- **Reliability**: TAP Core handles persistence (database)

**Example**: TAP Core tracks "last successful fetch for field-abc"
```python
# TAP Core logic
last_fetch = db.get("terrapipe", "field-abc", "last_fetch_date")
params = {"geoid": "field-abc", "date": last_fetch + 1_day}
adapter.fetch_data(params)
```

### Decision 5: Plugin vs Monorepo

**Options**:
1. **Plugin system** (adapters in separate repos)
2. **Monorepo** (adapters in TAP repo)

**Decision**: Plugin system

**Rationale**:
- **Vendor autonomy**: Vendors own their adapter repos
- **Update cycle**: Vendors update independently (no TAP release dependency)
- **Discovery**: TAP registry points to adapter repos

**Monorepo rejected**:
- **Bottleneck**: TAP team reviews every adapter change
- **Complexity**: One repo with 100+ adapters (messy)
- **Vendor control**: TAP controls release schedule

**Implementation**: Adapters as packages
```bash
pip install tap-adapter-terrapipe
tap-cli install terrapipe
```

---

## TAP CLI Framework

### Installation

```bash
pip install tap-cli
```

### Core Commands

#### 1. Adapter Management

**List available adapters**:
```bash
tap-cli list
# Output:
# Available TAP Adapters:
# - terrapipe (terrapipe.io NDVI satellite imagery) [installed]
# - planet (Planet.com satellite imagery)
# - dtnagronom (DTN weather and agronomic insights)
# - cropx (CropX soil sensors)
# - semios (Semios pest monitoring)
```

**Install adapter**:
```bash
tap-cli install terrapipe
# Output:
# Downloading terrapipe adapter v1.0.2...
# Installing dependencies...
# ✓ Installed successfully
```

**Uninstall adapter**:
```bash
tap-cli uninstall terrapipe
```

#### 2. Configuration

**Configure adapter credentials**:
```bash
tap-cli config terrapipe \
  --api-key "dkpnSTZVeWRhWG5NNmdpY2xPM2kzNnJ3cXJkbWpFaQ==" \
  --client "Dev"
```

**View configuration**:
```bash
tap-cli config terrapipe --show
# Output:
# Adapter: terrapipe
# API Key: dkpn****aQ== (masked)
# Client: Dev
```

#### 3. Subscriptions

**Subscribe field to vendor data**:
```bash
tap-cli subscribe \
  --adapter terrapipe \
  --geoid 63f764609b85eb356d387c1630a0671d3a8a56ffb6c91d1e52b1d7f2fe3c4213 \
  --data-type ndvi \
  --frequency daily \
  --start-date 2024-10-01
```

**List subscriptions**:
```bash
tap-cli subscriptions
# Output:
# Active Subscriptions:
# 1. terrapipe → field-abc (ndvi, daily, next run: 2024-11-02 06:00)
# 2. planet → field-xyz (rgb, weekly, next run: 2024-11-05 08:00)
```

**Unsubscribe**:
```bash
tap-cli unsubscribe 1
```

#### 4. Execution

**Run adapter manually (test)**:
```bash
tap-cli run terrapipe \
  --geoid field-abc \
  --date 2024-10-31
# Output:
# [2024-11-01 10:30] Authenticating...
# [2024-11-01 10:31] Fetching data...
# [2024-11-01 10:32] Creating BITE...
# [2024-11-01 10:33] ✓ Success! BITE ID: 01HQXYZ...
```

**View logs**:
```bash
tap-cli logs terrapipe --tail 50
```

#### 5. Monitoring

**Check status**:
```bash
tap-cli status
# Output:
# TAP System Status:
# - Adapters installed: 5
# - Active subscriptions: 12
# - BITEs created today: 47
# - Errors (last 24h): 1 (rate limit exceeded - planet)
```

**View metrics**:
```bash
tap-cli metrics terrapipe --period 7d
# Output:
# Terrapipe Adapter (last 7 days):
# - Runs: 70
# - Success: 68 (97%)
# - Failures: 2 (3%)
# - BITEs created: 68
# - Avg runtime: 32 seconds
```

---

## Example: terrapipe.io Integration

### Real-World Walkthrough

**Goal**: Get daily NDVI data for a coffee farm.

**Step 1**: Install TAP CLI
```bash
pip install tap-cli
```

**Step 2**: Install terrapipe adapter
```bash
tap-cli install terrapipe
```

**Step 3**: Configure credentials
```bash
tap-cli config terrapipe \
  --api-key "dkpnSTZVeWRhWG5NNmdpY2xPM2kzNnJ3cXJkbWpFaQ==" \
  --client "Dev"
```

**Step 4**: Subscribe field
```bash
tap-cli subscribe \
  --adapter terrapipe \
  --geoid 63f764609b85eb356d387c1630a0671d3a8a56ffb6c91d1e52b1d7f2fe3c4213 \
  --data-type ndvi \
  --frequency daily \
  --time "06:00"
```

**Step 5**: Done! TAP runs automatically
```
[2024-11-01 06:00] TAP: Running terrapipe for field-abc
[2024-11-01 06:01] TAP: Fetched NDVI (date: 2024-10-31)
[2024-11-01 06:02] TAP: Created BITE-12345
[2024-11-01 06:03] TAP: Stored in PANCAKE

[2024-11-02 06:00] TAP: Running terrapipe for field-abc
[2024-11-02 06:01] TAP: Fetched NDVI (date: 2024-11-01)
[2024-11-02 06:02] TAP: Created BITE-12346
[2024-11-02 06:03] TAP: Stored in PANCAKE

...continues daily...
```

**Step 6**: Query BITEs
```sql
SELECT * FROM bites 
WHERE geoid = '63f764609b85...' 
AND type = 'imagery_sirup'
ORDER BY timestamp DESC
LIMIT 30;  -- Last 30 days of NDVI
```

**Step 7**: Visualize trend
```python
import matplotlib.pyplot as plt

ndvi_values = [bite["Body"]["ndvi_stats"]["mean"] for bite in bites]
dates = [bite["Header"]["timestamp"] for bite in bites]

plt.plot(dates, ndvi_values)
plt.title("NDVI Trend (Terrapipe via TAP)")
plt.xlabel("Date")
plt.ylabel("NDVI")
plt.show()
```

---

## Vendor Benefits

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

## Farmer Benefits

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

## Future: TAP Marketplace

### Vision

**TAP Marketplace**: App store for agricultural data vendors

**Features**:
1. **Discover vendors**: Browse 100+ adapters
2. **Compare**: Price, data types, update frequency, reviews
3. **Subscribe**: One-click (automatic TAP configuration)
4. **Manage**: Dashboard (usage, costs, data quality)
5. **Community**: Ratings, reviews, support forums

### Example Marketplace Listing

```
┌─────────────────────────────────────────────┐
│ Terrapipe.io NDVI Satellite Imagery         │
├─────────────────────────────────────────────┤
│ ⭐⭐⭐⭐⭐ 4.8 (142 reviews)                 │
│                                             │
│ Price: $0.10/field/month                    │
│ Data types: NDVI, RGB, field boundaries     │
│ Update frequency: Daily                     │
│ Coverage: Global (Sentinel-2)               │
│ Latency: 1-3 days                          │
│                                             │
│ Features:                                   │
│ ✓ Cloud masking                            │
│ ✓ Historical data (2015-present)           │
│ ✓ API rate limit: Unlimited                │
│                                             │
│ [Subscribe Now]  [View Documentation]      │
└─────────────────────────────────────────────┘
```

### Marketplace Benefits

**For Vendors**:
- Marketing channel (reach thousands of farmers)
- Credibility (reviews, ratings)
- Analytics (usage trends, customer demographics)

**For Farmers**:
- Discovery (find best vendor for their needs)
- Transparency (compare objectively)
- Trust (community reviews, not just vendor claims)

**For Ecosystem**:
- Network effects (more vendors → more farmers → more vendors)
- Standards (best practices emerge from reviews)
- Innovation (vendors compete on quality, not lock-in)

---

## Conclusion

TAP solves the agricultural vendor integration crisis by providing a **universal docking mechanism**:
- **Vendors**: Build one adapter, reach all TAP users
- **Farmers**: Add vendors in minutes, no custom integration
- **Ecosystem**: Network effects, data portability, innovation

**Why TAP matters**:
- **Today**: 100+ vendors, 1000s of redundant integrations, $1B wasted
- **Future**: 1 TAP standard, 100+ adapters, unified BITE ecosystem

**TAP is the "USB-C" of agricultural data—one port, infinite possibilities.**

**Next steps**:
- **Vendors**: Build your TAP adapter (1-2 days)
- **Developers**: Integrate TAP CLI into your app
- **Farmers**: Subscribe to vendor data via TAP

**The future of agricultural data integration is open, standardized, and plug-and-play—just like TAP.** 🚰

---

**Document Status**: Conceptual design (v1.0 POC)  
**Last Updated**: November 2024  
**Feedback**: https://github.com/agstack/tap/issues  
**License**: CC BY 4.0 (Creative Commons Attribution)


---

## Vendor Integration System

### Universal Adapter Interface

TAP provides a universal adapter interface that enables plug-and-play vendor integration. Every vendor implements three simple methods:

```python
class VendorAdapter(TAPAdapter):
    def get_vendor_data(self, geoid, params):
        """Fetch raw data from vendor API"""
        # Your vendor-specific API call
        return vendor_response
    
    def transform_to_sirup(self, vendor_data, sirup_type):
        """Normalize vendor data into SIRUP format"""
        # Transform to standard structure
        return sirup_dict
    
    def sirup_to_bite(self, sirup, geoid, params):
        """Convert SIRUP into BITE"""
        # Create standard BITE envelope
        return bite_dict
```

**That's it!** ~100-300 lines of Python, and your vendor is integrated.

### Adapter Factory

The TAP Adapter Factory automatically discovers and loads vendor adapters from a simple YAML config:

```yaml
vendors:
  - vendor_name: your_vendor
    adapter_class: tap_adapters.YourVendorAdapter
    base_url: https://api.yourvendor.com
    auth_method: api_key
    credentials:
      api_key: ${YOUR_API_KEY}
    sirup_types:
      - weather_forecast
      - soil_moisture
```

**Add a vendor** = Add a config block. No code changes needed.

### Supported SIRUP Types

TAP supports a standardized set of SIRUP (data payload) types:

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

### Multi-Vendor Demo

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

### Vendor Onboarding

**For vendors wanting to integrate with TAP:**

1. **Read the guide**: See [TAP_VENDOR_GUIDE.md](TAP_VENDOR_GUIDE.md)
2. **Implement adapter**: ~100-300 lines, inherit from `TAPAdapter`
3. **Add config**: Single YAML block
4. **Test**: Use provided test framework
5. **Submit**: Pull request to AgStack PANCAKE repo
6. **Deploy**: Instantly available to all PANCAKE users

**Time to integrate**: 1-2 days (vs weeks/months for custom integration)

**Community support**: AgStack TAC reviews and assists

### Benefits for Vendors

- **Market access**: Reach all AgStack members instantly
- **Reduced support**: Standardized interface = fewer integration questions
- **Free marketing**: Listed in TAP vendor registry
- **Community validation**: Open-source trust and transparency
- **Future-proof**: TAP evolves with ecosystem, your adapter stays compatible

### Benefits for Users

- **Vendor choice**: Easy to switch or multi-source
- **Unified interface**: Query all vendors the same way
- **Cost optimization**: Compare vendor pricing/quality easily
- **Data portability**: All data in standard BITE format
- **No lock-in**: Change vendors without changing code

---

## Implementation Files

### Core Python Modules

- **`tap_adapter_base.py`**: Base classes (`TAPAdapter`, `TAPAdapterFactory`, `SIRUPType`, `AuthMethod`)
- **`tap_adapters.py`**: Reference adapter implementations (Terrapipe NDVI, SoilGrids, Terrapipe Weather)
- **`tap_vendors.yaml`**: Vendor configuration registry with auth and metadata

### Documentation

- **[TAP.md](TAP.md)**: This document - architecture and design philosophy
- **[TAP_VENDOR_GUIDE.md](TAP_VENDOR_GUIDE.md)**: Step-by-step vendor integration guide (onboarding)
- **[SIRUP.md](SIRUP.md)**: SIRUP data format specification
- **[BITE.md](BITE.md)**: BITE envelope specification

### Demo and Testing

- **[POC_Nov20_BITE_PANCAKE.ipynb](POC_Nov20_BITE_PANCAKE.ipynb)**: Part 12 - Multi-vendor TAP demo with live API calls
- **`tests/test_tap_adapters.py`**: Unit and integration tests for adapters

---

**TAP is the universal "dock" for agricultural data.** Any vendor can plug in, any farmer can tap into it, and every BITE flows seamlessly into PANCAKE.

**Implementation Status**: Working proof of concept with 3 live vendors  
**License**: Apache 2.0  
**Community**: AgStack open source  
**Support**: pancake-support@agstack.org
