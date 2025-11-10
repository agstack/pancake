# Module 2: BITE (Bidirectional Interchange Transport Envelope)
## The Universal Data Format for Agricultural Intelligence

**An AgStack Project of The Linux Foundation**

**Episode**: Module 2 of 10  
**Duration**: ~25 minutes  
**Prerequisites**: Episode 0 (Core Narrative), Module 1 (PANCAKE Core)  
**Technical Level**: Intermediate to Advanced

---

## Introduction

In Module 1, we explored PANCAKE's storage engine. Now, let's dive into **BITE**—the universal data format that makes agricultural data truly interoperable, AI-native, and future-proof.

**What you'll learn:**
- BITE structure (Header, Body, Footer)
- Why BITE beats GeoJSON, ADAPT, and OCSM
- Content addressing with SHA-256 hashing
- BITE types (observation, imagery_sirup, lab_result, etc.)
- How BITE wraps existing formats (ADAPT, OCSM, vendor APIs)
- Creating and validating BITEs in Python
- Real-world BITE examples from the POC

**Who this is for:**
- Data architects designing interoperability solutions
- Backend developers implementing BITE producers/consumers
- Agronomists and data scientists working with multi-source agricultural data
- Standards committee members evaluating BITE vs alternatives

---

## Chapter 1: The BITE Structure (Header, Body, Footer)

### Anatomy of a BITE

Every BITE has **exactly three sections**:

```json
{
  "Header": {
    "id": "01K8YZ...",
    "hash": "a3f5e8...",
    "geoid": "63f764...",
    "timestamp": "2025-03-15T14:32:00Z",
    "type": "observation",
    "source": {...},
    "agent": {...}
  },
  "Body": {
    // Arbitrary JSON - polyglot by design
  },
  "Footer": {
    "provenance": [...],
    "references": [...],
    "security": {...}
  }
}
```

### Header (Required, Standardized)

**Purpose**: Identity, spatio-temporal indexing, type classification

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | ULID | ✅ | Unique identifier (time-ordered) |
| `hash` | SHA-256 | ✅ | Content hash (Header + Body + Footer) |
| `geoid` | String | ✅ | GeoID (S2-based spatial index) |
| `timestamp` | ISO 8601 | ✅ | UTC timestamp with timezone |
| `type` | String | ✅ | BITE type (observation, imagery_sirup, etc.) |
| `source` | Object | ❌ | Data source (vendor, pipeline, device) |
| `agent` | Object | ❌ | Author (human, AI, sensor) |

**Example Header**:
```json
{
  "id": "01K8YZ0YDRTSTWWEZA276GNS9",
  "hash": "a3f5e8d2c9b1f4e7a6c3d8b2e5f1a9c4d7b6e3f8a1c5d2b9e7f4a6c8d3b1e5f2",
  "geoid": "63f764609b85eb356d387c1630a0671d3a8a56ffb6c91d1e52b1d7f2fe3c4213",
  "timestamp": "2025-03-15T14:32:00Z",
  "type": "observation",
  "source": {
    "name": "TerraTrac Mobile App",
    "version": "2.1.3",
    "vendor": "AgStack Community"
  },
  "agent": {
    "type": "human",
    "id": "user-jose-123",
    "name": "José Martinez",
    "role": "Farm Scout"
  }
}
```

**Key design decisions**:

1. **ULID (Universally Unique Lexicographically Sortable Identifier)**
   - 26 characters (vs 36 for UUID)
   - Time-ordered (unlike UUIDv4)
   - Monotonically increasing (sorts by creation time)
   - Example: `01K8YZ0YDRTSTWWEZA276GNS9`

2. **SHA-256 hash** (content addressing)
   - Tamper-proof (change 1 byte → entirely different hash)
   - Deduplication (identical BITEs have identical hashes)
   - Verification (recalculate hash to detect corruption)

3. **GeoID** (spatial index)
   - S2-based (Google's spherical geometry)
   - Privacy-preserving (hash obscures exact coordinates)
   - Hierarchical (can query by region, farm, field)

4. **ISO 8601 timestamp** (with timezone)
   - Always UTC (no ambiguity)
   - Machine-readable (parseable by all languages)
   - Human-readable (`2025-03-15T14:32:00Z`)

5. **Type** (extensible taxonomy)
   - Core types: `observation`, `imagery_sirup`, `lab_result`, `equipment`, `weather`, `recommendation`
   - Custom types allowed: `my_custom_type` (prefixed with vendor name)
   - Enables type-specific queries: `SELECT * FROM bites WHERE type = 'observation'`

### Body (Flexible, Polyglot)

**Purpose**: Store arbitrary agricultural data (no schema enforcement)

**Design philosophy**:
- **No required fields** (unlike ADAPT, OCSM)
- **Any JSON structure** (flat, nested, arrays, primitives)
- **Vendor-specific schemas** (SoilGrids, Terrapipe, Leaf, etc.)
- **AI can understand** via semantic embeddings (even if schema unknown)

**Example Bodies**:

**Observation BITE** (field scout report):
```json
{
  "pest": "coffee rust",
  "severity": "moderate",
  "affected_area_percent": 30,
  "notes": "Yellow-orange spots on leaves, premature leaf drop observed",
  "photo_urls": [
    "https://storage.pancake.org/images/coffee-rust-2025-03-15-001.jpg",
    "https://storage.pancake.org/images/coffee-rust-2025-03-15-002.jpg"
  ],
  "weather_conditions": {
    "temperature_c": 24,
    "humidity_percent": 87,
    "recent_rainfall_mm": 15
  }
}
```

**Imagery SIRUP BITE** (satellite data from Terrapipe):
```json
{
  "satellite": "Sentinel-2",
  "cloud_cover_percent": 5,
  "ndvi_stats": {
    "mean": 0.65,
    "min": 0.42,
    "max": 0.81,
    "std": 0.08
  },
  "raster_url": "https://api.terrapipe.io/rasters/2025-03-15/field-abc.tif",
  "resolution_m": 10,
  "bands": ["B4", "B8", "B11"],
  "processing": {
    "atmospheric_correction": "Sen2Cor",
    "cloud_masking": "FMask"
  }
}
```

**Lab Result BITE** (soil analysis):
```json
{
  "lab_name": "AgriLab Colombia",
  "report_id": "SOIL-2025-03-001",
  "sample_depth_cm": 20,
  "nutrients": {
    "nitrogen_ppm": 42,
    "phosphorus_ppm": 18,
    "potassium_ppm": 156,
    "organic_matter_percent": 3.2
  },
  "ph": 5.8,
  "texture": {
    "sand_percent": 35,
    "silt_percent": 40,
    "clay_percent": 25,
    "classification": "loam"
  },
  "recommendations": [
    "Apply 50 kg/ha urea to address nitrogen deficiency",
    "Monitor pH (5.8 is low for coffee, target 6.0-6.5)"
  ]
}
```

**Equipment Event BITE** (tractor operation):
```json
{
  "equipment_id": "tractor-007",
  "operation": "spray",
  "operator": "Carlos Rodriguez",
  "product_applied": {
    "name": "Copper Hydroxide Fungicide",
    "active_ingredient": "copper hydroxide",
    "concentration_percent": 50,
    "application_rate_l_ha": 2.5,
    "total_volume_l": 125
  },
  "area_treated_ha": 50,
  "duration_minutes": 180,
  "weather_at_application": {
    "temperature_c": 22,
    "wind_speed_kmh": 8,
    "humidity_percent": 65
  }
}
```

**Notice**:
- Each Body has a **completely different schema**
- No common required fields (unlike ADAPT's mandatory fields)
- Rich, context-specific data (weather, photos, lab IDs, equipment details)
- AI can still search across all of them via semantic embeddings

### Footer (Optional, Provenance & References)

**Purpose**: Audit trail, data lineage, cryptographic verification

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `provenance` | Array | Chain of custody (who created, modified, forwarded) |
| `references` | Array | Links to other BITEs, SIPs, MEALs, external resources |
| `security` | Object | Signatures, encryption metadata, access control |
| `metadata` | Object | Custom metadata (vendor-specific) |

**Example Footer**:
```json
{
  "provenance": [
    {
      "action": "created",
      "timestamp": "2025-03-15T14:32:00Z",
      "agent": {
        "type": "human",
        "id": "user-jose-123",
        "name": "José Martinez"
      }
    },
    {
      "action": "validated",
      "timestamp": "2025-03-15T14:35:00Z",
      "agent": {
        "type": "ai",
        "id": "sirup-validator-v1",
        "name": "SIRUP Quality Checker"
      },
      "validation_result": {
        "status": "pass",
        "confidence": 0.95,
        "flags": []
      }
    },
    {
      "action": "forwarded",
      "timestamp": "2025-03-15T14:40:00Z",
      "agent": {
        "type": "human",
        "id": "user-agronomist-456",
        "name": "Dr. Maria Silva"
      },
      "destination": "meal-abc123"
    }
  ],
  "references": [
    {
      "type": "bite",
      "id": "01K8YZ0YDRTSTWWEZA276GNS8",
      "description": "Previous observation (coffee rust, 1 week ago)"
    },
    {
      "type": "sip",
      "id": "sip-2025-03-15-sensor-007",
      "description": "Humidity sensor data (correlates with fungal disease)"
    },
    {
      "type": "external",
      "url": "https://coffeescience.org/rust-identification-guide",
      "description": "Coffee rust identification guide"
    }
  ],
  "security": {
    "signature": "MEUCIQD...",
    "public_key_fingerprint": "SHA256:abc123...",
    "encryption": null,
    "access_control": {
      "visibility": "cooperative",
      "allowed_users": ["user-jose-123", "user-agronomist-456"],
      "allowed_roles": ["agronomist", "farm_manager"]
    }
  },
  "metadata": {
    "mobile_app_version": "2.1.3",
    "gps_accuracy_m": 5.2,
    "photo_compression": "jpeg-85",
    "submission_method": "online"
  }
}
```

**Key design decisions**:

1. **Provenance is append-only**
   - Cannot modify history (immutable audit trail)
   - Chain of custody (created → validated → forwarded → ...)
   - AI agent actions recorded (SIRUP validator, recommendation engine)

2. **References link data**
   - BITE → BITE (observations over time)
   - BITE → SIP (correlate sensor data with events)
   - BITE → MEAL (connect data to discussions)
   - BITE → External (link to research papers, manuals, etc.)

3. **Security is optional but powerful**
   - Digital signatures (cryptographic proof of authorship)
   - Encryption metadata (if BITE body is encrypted)
   - Access control (who can view this BITE)

---

## Chapter 2: Why BITE Beats the Alternatives

### BITE vs GeoJSON

**GeoJSON** is a popular geospatial format:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-75.5, 4.6]
  },
  "properties": {
    "name": "Field ABC",
    "crop": "coffee"
  }
}
```

**Why GeoJSON is insufficient for agriculture**:

| Feature | GeoJSON | BITE |
|---------|---------|------|
| Geometry support | ✅ Yes | ✅ Yes (in Body) |
| Temporal indexing | ❌ No | ✅ Required (Header.timestamp) |
| Content addressing | ❌ No | ✅ Yes (Header.hash) |
| Provenance tracking | ❌ No | ✅ Yes (Footer.provenance) |
| Type taxonomy | ❌ No | ✅ Yes (Header.type) |
| AI-native embeddings | ❌ No | ✅ Yes (embedding column) |
| Polyglot data support | ⚠️ Limited (properties object) | ✅ Full (Body is freeform) |

**Verdict**: GeoJSON is great for **mapping**, but BITE is designed for **agricultural intelligence** (AI, provenance, time-series).

### BITE vs ADAPT

**ADAPT (Agricultural Data Application Programming Toolkit)** is AgGateway's data model:

**ADAPT strengths**:
- Comprehensive (covers planting, harvest, yield, applications)
- Industry-backed (John Deere, CNH, Trimble, Raven)
- Vendor adoption (many FMIS tools export ADAPT)

**Why ADAPT is insufficient for AI-era agriculture**:

| Feature | ADAPT | BITE |
|---------|-------|------|
| Structured schema | ✅ Yes (highly detailed) | ⚠️ Optional (Body is freeform) |
| Machine interoperability | ✅ Excellent (equipment data) | ✅ Excellent (via TAP adapters) |
| AI-native embeddings | ❌ No | ✅ Yes |
| Semantic search | ❌ No | ✅ Yes (pgvector) |
| Conversational queries | ❌ No | ✅ Yes ("What happened?") |
| Polyglot data | ❌ No (must fit ADAPT schema) | ✅ Yes (any JSON) |
| Observations/notes | ⚠️ Limited (not primary focus) | ✅ Native (observation type) |
| Provenance tracking | ⚠️ Basic (data source only) | ✅ Full (chain of custody) |
| Satellite imagery | ❌ No | ✅ Yes (imagery_sirup type) |
| Real-time sensors | ❌ No | ✅ Yes (SIP layer) |
| Collaboration threads | ❌ No | ✅ Yes (MEAL layer) |

**BITE's positioning vs ADAPT**:
- **BITE complements ADAPT** (not replaces)
- **ADAPT data can be wrapped in BITE** (Body contains ADAPT payload)
- **BITE handles what ADAPT doesn't** (observations, imagery, sensors, AI queries)

**Example: ADAPT inside BITE**:
```json
{
  "Header": {
    "id": "01K8YZ...",
    "type": "planting_operation",
    "geoid": "field-abc",
    "timestamp": "2025-03-01T08:00:00Z"
  },
  "Body": {
    "adapt_version": "2.0",
    "adapt_data": {
      // Full ADAPT payload here (OperationData, Equipment, etc.)
    }
  },
  "Footer": {
    "provenance": [...],
    "references": [...]
  }
}
```

**Verdict**: BITE **extends** ADAPT to the AI era (embeddings, semantic search, conversational queries).

### BITE vs OCSM (Open Common Semantic Model)

**OCSM** is AgStack's RDF/JSON-LD semantic model:

**OCSM strengths**:
- Semantic web standards (RDF, JSON-LD, SHACL)
- Ontology-driven (formal definitions, reasoning)
- Linked data (URIs for everything)

**Example OCSM (simplified)**:
```json
{
  "@context": "https://agstack.org/ocsm/v1/context.json",
  "@type": "ocsm:Field",
  "@id": "urn:uuid:abc-123",
  "ocsm:hasLocation": {
    "@type": "ocsm:Location",
    "ocsm:geometry": {
      "@type": "ocsm:Polygon",
      "ocsm:coordinates": [[[-75.5, 4.6], ...]]
    }
  },
  "ocsm:hasCrop": {
    "@type": "ocsm:Crop",
    "ocsm:cropType": "coffee",
    "ocsm:variety": "Arabica Caturra"
  }
}
```

**Why OCSM is insufficient for rapid AI adoption**:

| Feature | OCSM | BITE |
|---------|------|------|
| Semantic richness | ✅ Excellent (RDF ontology) | ⚠️ Good (via embeddings) |
| Reasoning capability | ✅ Yes (SHACL, OWL) | ⚠️ Via AI (not formal logic) |
| Learning curve | ❌ High (RDF, JSON-LD, SPARQL) | ✅ Low (plain JSON) |
| Developer adoption | ⚠️ Slow (few ag developers know RDF) | ✅ Fast (every developer knows JSON) |
| AI-native embeddings | ❌ No | ✅ Yes |
| Conversational queries | ❌ No (must write SPARQL) | ✅ Yes (natural language) |
| Vendor integration | ⚠️ Requires full ontology mapping | ✅ Simple (JSON wrapper) |
| Real-time performance | ⚠️ Slower (RDF triple stores) | ✅ Fast (PostgreSQL + pgvector) |

**BITE's positioning vs OCSM**:
- **BITE wraps OCSM** (Body contains OCSM payload)
- **BITE makes OCSM queryable by AI** (embeddings + semantic search)
- **BITE lowers barrier to entry** (plain JSON → easier adoption)

**Example: OCSM inside BITE**:
```json
{
  "Header": {
    "id": "01K8YZ...",
    "type": "ocsm_field",
    "geoid": "field-abc",
    "timestamp": "2025-03-15T00:00:00Z"
  },
  "Body": {
    "@context": "https://agstack.org/ocsm/v1/context.json",
    "@type": "ocsm:Field",
    // ... full OCSM payload
  },
  "Footer": {...}
}
```

**Verdict**: BITE **democratizes** OCSM (makes it AI-queryable and developer-friendly).

---

## Chapter 3: Content Addressing (SHA-256 Hashing)

### What is Content Addressing?

**Traditional addressing**: "Where is the data?"
- Database: Row ID = 12345
- File system: `/data/observations/2025-03-15.json`
- API: `GET /observations/abc-123`

**Content addressing**: "What is the data?"
- Hash = `a3f5e8d2c9b1f4e7a6c3d8b2e5f1a9c4d7b6e3f8a1c5d2b9e7f4a6c8d3b1e5f2`
- If content changes → hash changes
- Same content → same hash (deduplication)

### How BITE Uses SHA-256

**Step 1: Serialize BITE (deterministic)**
```python
import json
import hashlib

def serialize_bite(bite: dict) -> str:
    """
    Serialize BITE to deterministic JSON string
    (sorted keys, no whitespace)
    """
    return json.dumps(bite, sort_keys=True, separators=(',', ':'))

bite = {
    "Header": {...},
    "Body": {...},
    "Footer": {...}
}

bite_json = serialize_bite(bite)
```

**Step 2: Hash with SHA-256**
```python
def hash_bite(bite: dict) -> str:
    """Calculate SHA-256 hash of BITE"""
    bite_json = serialize_bite(bite)
    return hashlib.sha256(bite_json.encode('utf-8')).hexdigest()

bite_hash = hash_bite(bite)
print(f"BITE hash: {bite_hash}")
# Output: a3f5e8d2c9b1f4e7a6c3d8b2e5f1a9c4d7b6e3f8a1c5d2b9e7f4a6c8d3b1e5f2
```

**Step 3: Store hash in Header**
```python
bite['Header']['hash'] = bite_hash
```

### Benefits of Content Addressing

**1. Tamper Detection**
```python
# Retrieve BITE from database
bite = db.get_bite("01K8YZ...")

# Recalculate hash
stored_hash = bite['Header']['hash']
calculated_hash = hash_bite(bite)

if stored_hash != calculated_hash:
    raise ValueError("BITE has been tampered with!")
```

**2. Deduplication**
```sql
-- Prevent duplicate BITEs
CREATE UNIQUE INDEX idx_unique_hash ON bites(hash);

-- If same BITE submitted twice → database rejects
INSERT INTO bites (id, hash, ...) VALUES ('01K8YZ...', 'a3f5e8...', ...);
-- ^ Succeeds

INSERT INTO bites (id, hash, ...) VALUES ('01K8Z0...', 'a3f5e8...', ...);
-- ^ Fails with "duplicate key" error
```

**3. Content-Based Retrieval**
```python
# Retrieve BITE by hash (instead of ID)
bite = db.query("SELECT * FROM bites WHERE hash = %s", [bite_hash])

# Useful for verifying data provenance
# "Does this BITE exist in PANCAKE?"
# "Has this data been seen before?"
```

**4. Distributed Synchronization**
```python
# Two PANCAKE instances (farm A, farm B)
# Farm A sends BITE to Farm B

# Farm B checks if it already has this BITE
if db.exists("SELECT 1 FROM bites WHERE hash = %s", [bite_hash]):
    print("Already have this BITE, skipping")
else:
    db.insert_bite(bite)
    print("New BITE, inserted")
```

---

## Chapter 4: BITE Types (Extensible Taxonomy)

### Core BITE Types

PANCAKE defines **7 core types** (with room for custom types):

| Type | Description | Example Use Cases |
|------|-------------|-------------------|
| `observation` | Field scout reports, pest/disease sightings, visual assessments | Coffee rust spotted, weed pressure high, flower bloom started |
| `imagery_sirup` | Satellite, drone, or tractor-mounted imagery (processed via SIRUP) | NDVI, RGB orthomosaic, thermal imagery |
| `lab_result` | Soil, tissue, water lab analyses | Soil nutrients, plant tissue analysis, water quality |
| `equipment` | Tractor operations, irrigation events, machinery logs | Planting, spraying, harvesting, tillage |
| `weather` | Weather station data, forecasts | Temperature, rainfall, wind, humidity |
| `recommendation` | Agronomist advice, AI-generated recommendations | Fertilizer plan, pest treatment, irrigation schedule |
| `event` | Generic events (harvest date, certification audit, etc.) | Organic certification, field split, boundary change |

### Custom Types (Vendor Extensions)

Vendors can define custom types with namespace prefix:

**Format**: `vendor:custom_type`

**Examples**:
- `leaf_agriculture:yield_prediction`
- `semios:trap_count`
- `telus:variable_rate_prescription`
- `agworld:spray_plan`

**Stored in PANCAKE as-is**:
```json
{
  "Header": {
    "type": "leaf_agriculture:yield_prediction",
    ...
  },
  "Body": {
    // Leaf Agriculture's custom schema
  }
}
```

**AI can still understand it** via semantic embeddings (even if PANCAKE doesn't know the schema).

### Type-Specific Queries

```sql
-- Find all observations in last 7 days
SELECT * FROM bites
WHERE type = 'observation'
AND timestamp > NOW() - INTERVAL '7 days';

-- Find all satellite imagery for field-abc
SELECT * FROM bites
WHERE type = 'imagery_sirup'
AND geoid = 'field-abc';

-- Find all recommendations by AI agents
SELECT * FROM bites
WHERE type = 'recommendation'
AND header->>'agent'->>'type' = 'ai';
```

---

## Chapter 5: Creating and Validating BITEs

### Python: Create a BITE

```python
import ulid
import hashlib
import json
from datetime import datetime, timezone

def create_bite(
    geoid: str,
    bite_type: str,
    body: dict,
    source: dict = None,
    agent: dict = None,
    footer: dict = None
) -> dict:
    """
    Create a valid BITE
    
    Args:
        geoid: GeoID (spatial index)
        bite_type: BITE type (observation, imagery_sirup, etc.)
        body: Arbitrary JSON data
        source: Optional source metadata
        agent: Optional agent (author) metadata
        footer: Optional footer (provenance, references, etc.)
    
    Returns:
        Complete BITE (Header + Body + Footer)
    """
    # Generate ULID (time-ordered unique ID)
    bite_id = str(ulid.new())
    
    # Current timestamp (UTC)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Build BITE
    bite = {
        "Header": {
            "id": bite_id,
            "geoid": geoid,
            "timestamp": timestamp,
            "type": bite_type
        },
        "Body": body,
        "Footer": footer or {}
    }
    
    # Add optional Header fields
    if source:
        bite["Header"]["source"] = source
    if agent:
        bite["Header"]["agent"] = agent
    
    # Calculate hash (before adding hash field)
    bite_json = json.dumps(bite, sort_keys=True, separators=(',', ':'))
    bite_hash = hashlib.sha256(bite_json.encode('utf-8')).hexdigest()
    
    # Add hash to Header
    bite["Header"]["hash"] = bite_hash
    
    return bite
```

**Example usage**:
```python
# Field scout observation
bite = create_bite(
    geoid="field-abc",
    bite_type="observation",
    body={
        "pest": "coffee rust",
        "severity": "moderate",
        "affected_area_percent": 30,
        "notes": "Yellow-orange spots on leaves",
        "photo_urls": [
            "https://storage.pancake.org/images/rust-001.jpg"
        ]
    },
    source={
        "name": "TerraTrac Mobile App",
        "version": "2.1.3"
    },
    agent={
        "type": "human",
        "id": "user-jose-123",
        "name": "José Martinez",
        "role": "Farm Scout"
    },
    footer={
        "provenance": [
            {
                "action": "created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": {
                    "type": "human",
                    "id": "user-jose-123",
                    "name": "José Martinez"
                }
            }
        ]
    }
)

print(json.dumps(bite, indent=2))
```

### Python: Validate a BITE

```python
from jsonschema import validate, ValidationError

# BITE JSON Schema (simplified)
BITE_SCHEMA = {
    "type": "object",
    "required": ["Header", "Body", "Footer"],
    "properties": {
        "Header": {
            "type": "object",
            "required": ["id", "hash", "geoid", "timestamp", "type"],
            "properties": {
                "id": {"type": "string", "minLength": 26, "maxLength": 26},
                "hash": {"type": "string", "minLength": 64, "maxLength": 64},
                "geoid": {"type": "string", "minLength": 64, "maxLength": 64},
                "timestamp": {"type": "string", "format": "date-time"},
                "type": {"type": "string", "minLength": 1}
            }
        },
        "Body": {"type": "object"},
        "Footer": {"type": "object"}
    }
}

def validate_bite(bite: dict) -> tuple[bool, str]:
    """
    Validate BITE structure and hash
    
    Returns:
        (is_valid, error_message)
    """
    # Step 1: Validate JSON schema
    try:
        validate(instance=bite, schema=BITE_SCHEMA)
    except ValidationError as e:
        return False, f"Schema validation failed: {e.message}"
    
    # Step 2: Verify hash
    stored_hash = bite['Header']['hash']
    bite_copy = json.loads(json.dumps(bite))  # Deep copy
    del bite_copy['Header']['hash']  # Remove hash before recalculating
    
    bite_json = json.dumps(bite_copy, sort_keys=True, separators=(',', ':'))
    calculated_hash = hashlib.sha256(bite_json.encode('utf-8')).hexdigest()
    
    if stored_hash != calculated_hash:
        return False, f"Hash mismatch: stored={stored_hash[:16]}..., calculated={calculated_hash[:16]}..."
    
    return True, "Valid"

# Test
is_valid, message = validate_bite(bite)
print(f"BITE valid: {is_valid}, {message}")
```

---

## Chapter 6: Real-World BITE Examples (POC)

### Example 1: Field Scout Observation

```json
{
  "Header": {
    "id": "01K8YZ0YDRTSTWWEZA276GNS9",
    "hash": "a3f5e8d2c9b1f4e7a6c3d8b2e5f1a9c4d7b6e3f8a1c5d2b9e7f4a6c8d3b1e5f2",
    "geoid": "63f764609b85eb356d387c1630a0671d3a8a56ffb6c91d1e52b1d7f2fe3c4213",
    "timestamp": "2025-03-15T14:32:00Z",
    "type": "observation",
    "source": {
      "name": "TerraTrac Mobile",
      "version": "2.1.3",
      "vendor": "AgStack Community"
    },
    "agent": {
      "type": "human",
      "id": "user-jose-123",
      "name": "José Martinez",
      "role": "Farm Scout"
    }
  },
  "Body": {
    "pest": "coffee rust (Hemileia vastatrix)",
    "severity": "moderate",
    "affected_area_percent": 30,
    "symptoms": [
      "yellow-orange spots on leaves",
      "premature leaf drop",
      "lesions on lower canopy"
    ],
    "notes": "Rust more severe in low-lying areas with poor air circulation. Recent heavy rains (15mm in 3 days) likely triggered outbreak.",
    "photo_urls": [
      "https://storage.pancake.org/images/coffee-rust-2025-03-15-001.jpg",
      "https://storage.pancake.org/images/coffee-rust-2025-03-15-002.jpg"
    ],
    "weather_at_observation": {
      "temperature_c": 24,
      "humidity_percent": 87,
      "sky_condition": "overcast"
    },
    "recommended_action": "Consult agronomist for fungicide recommendation"
  },
  "Footer": {
    "provenance": [
      {
        "action": "created",
        "timestamp": "2025-03-15T14:32:00Z",
        "agent": {
          "type": "human",
          "id": "user-jose-123",
          "name": "José Martinez"
        }
      }
    ],
    "references": [
      {
        "type": "bite",
        "id": "01K8YZ0YDRTSTWWEZA276GNS8",
        "description": "Previous observation (coffee rust, 1 week ago, 10% affected)"
      }
    ]
  }
}
```

### Example 2: Satellite Imagery SIRUP

```json
{
  "Header": {
    "id": "01K8Z0YDRTSTWWEZA277ABC12",
    "hash": "b4e6d9c3a1f5e8b2d7c4a9f6e3b8d1c5a7f2e9b4d6c3a8f1e5b9d2c7a4f8e6b3",
    "geoid": "63f764609b85eb356d387c1630a0671d3a8a56ffb6c91d1e52b1d7f2fe3c4213",
    "timestamp": "2025-03-15T10:45:00Z",
    "type": "imagery_sirup",
    "source": {
      "vendor": "terrapipe_ndvi",
      "pipeline": "TAP",
      "api_version": "v1"
    },
    "agent": {
      "type": "ai",
      "id": "sirup-terrapipe-adapter",
      "name": "Terrapipe NDVI Adapter"
    }
  },
  "Body": {
    "satellite": "Sentinel-2",
    "acquisition_date": "2025-03-15",
    "cloud_cover_percent": 5,
    "ndvi_stats": {
      "mean": 0.65,
      "min": 0.42,
      "max": 0.81,
      "std": 0.08,
      "q25": 0.60,
      "q50": 0.65,
      "q75": 0.71
    },
    "stress_areas": [
      {
        "coordinates": [[-75.5, 4.6], [-75.49, 4.6], [-75.49, 4.61], [-75.5, 4.61]],
        "ndvi_mean": 0.45,
        "area_ha": 2.3,
        "severity": "moderate"
      }
    ],
    "raster_url": "https://api.terrapipe.io/rasters/2025-03-15/field-abc.tif",
    "thumbnail_url": "https://api.terrapipe.io/thumbnails/2025-03-15/field-abc.png",
    "resolution_m": 10,
    "bands_used": ["B4", "B8"],
    "processing": {
      "atmospheric_correction": "Sen2Cor",
      "cloud_masking": "FMask"
    }
  },
  "Footer": {
    "provenance": [
      {
        "action": "created",
        "timestamp": "2025-03-15T10:45:00Z",
        "agent": {
          "type": "ai",
          "id": "sirup-terrapipe-adapter"
        }
      }
    ],
    "references": [
      {
        "type": "bite",
        "id": "01K8YZ0YDRTSTWWEZA276GNS9",
        "description": "Field scout observation (confirms NDVI stress area matches rust location)"
      }
    ]
  }
}
```

### Example 3: Agronomist Recommendation

```json
{
  "Header": {
    "id": "01K8Z1YDRTSTWWEZA278DEF45",
    "hash": "c5f7a2e9b4d6c3a8f1e5b9d2c7a4f8e6b3d1c5a7f2e9b4d6c3a8f1e5b9d2c7a4",
    "geoid": "63f764609b85eb356d387c1630a0671d3a8a56ffb6c91d1e52b1d7f2fe3c4213",
    "timestamp": "2025-03-15T16:00:00Z",
    "type": "recommendation",
    "source": {
      "name": "Agronomist Portal",
      "version": "1.5.2"
    },
    "agent": {
      "type": "human",
      "id": "user-agronomist-456",
      "name": "Dr. Maria Silva",
      "role": "Certified Agronomist"
    }
  },
  "Body": {
    "recommendation_type": "fungicide_application",
    "urgency": "high",
    "disease": "coffee rust (Hemileia vastatrix)",
    "product": {
      "name": "Copper Hydroxide Fungicide",
      "active_ingredient": "copper hydroxide",
      "concentration_percent": 50,
      "application_rate_l_ha": 2.5,
      "application_method": "foliar spray",
      "water_volume_l_ha": 500
    },
    "timing": {
      "apply_within_hours": 48,
      "ideal_conditions": {
        "temperature_range_c": [18, 28],
        "max_wind_speed_kmh": 15,
        "avoid_rain_hours": 6
      }
    },
    "safety": {
      "ppe_required": ["gloves", "goggles", "respirator"],
      "restricted_entry_interval_hours": 24,
      "preharvest_interval_days": 30
    },
    "monitoring": {
      "reassess_after_days": 7,
      "indicators": [
        "new lesion development",
        "leaf drop rate",
        "NDVI recovery"
      ]
    },
    "rationale": "Field scout confirmed 30% infection rate. Satellite NDVI shows vegetation stress (0.65, declining from 0.75 two weeks ago). High humidity (87%) and recent rainfall (15mm) favor fungal spread. Immediate treatment critical to prevent further defoliation.",
    "references": [
      "Coffee rust management guide (PROMECAFE)",
      "Copper hydroxide efficacy trials (Colombia, 2023)"
    ]
  },
  "Footer": {
    "provenance": [
      {
        "action": "created",
        "timestamp": "2025-03-15T16:00:00Z",
        "agent": {
          "type": "human",
          "id": "user-agronomist-456",
          "name": "Dr. Maria Silva"
        }
      }
    ],
    "references": [
      {
        "type": "bite",
        "id": "01K8YZ0YDRTSTWWEZA276GNS9",
        "description": "Field scout observation (coffee rust)"
      },
      {
        "type": "bite",
        "id": "01K8Z0YDRTSTWWEZA277ABC12",
        "description": "Satellite NDVI (confirms vegetation stress)"
      }
    ],
    "security": {
      "signature": "MEUCIQD5z...",
      "public_key_fingerprint": "SHA256:abc123..."
    }
  }
}
```

---

## Conclusion

**BITE (Bidirectional Interchange Transport Envelope) provides:**
- ✅ Universal format (Header + Body + Footer)
- ✅ AI-native (semantic embeddings, conversational queries)
- ✅ Polyglot (any JSON in Body, no schema enforcement)
- ✅ Content-addressed (SHA-256 hash, tamper-proof)
- ✅ Provenance tracking (immutable audit trail in Footer)
- ✅ Interoperable (wraps ADAPT, OCSM, GeoJSON, vendor APIs)
- ✅ Developer-friendly (plain JSON, not RDF or XML)
- ✅ Extensible (custom types with vendor namespaces)

**BITE is the universal language for agricultural data in the AI era.**

**Next module**: SIP (Sensor/Actuator Stream) - High-frequency IoT data layer.

---

**An AgStack Project | Powered by The Linux Foundation**

**Learn more**: https://agstack.org/pancake  
**GitHub**: https://github.com/agstack/pancake  
**License**: Apache 2.0 (Code) | CC BY 4.0 (Documentation)

