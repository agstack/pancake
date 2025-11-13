# SIP: Sensor Index Pointer

**Version**: 1.0  
**Status**: Specification  
**Purpose**: Lightweight, high-speed data ingestion and query protocol for PANCAKE

---

## Table of Contents

1. [Overview](#overview)
2. [The Time-Series Problem](#the-time-series-problem)
3. [What is SIP?](#what-is-sip)
4. [SIP Design Philosophy](#sip-design-philosophy)
5. [SIP Packet Structure](#sip-packet-structure)
6. [SIP vs BITE](#sip-vs-bite)
7. [Write Path: Sensor → SIP → PANCAKE](#write-path-sensor--sip--pancake)
8. [Read Path: Agent → SIP Query → Response](#read-path-agent--sip-query--response)
9. [Storage: Parquet + GeoID](#storage-parquet--geoid)
10. [PANCAKE Dual-Agent Architecture](#pancake-dual-agent-architecture)
11. [TAP Integration](#tap-integration)
12. [Performance Characteristics](#performance-characteristics)

---

## Overview

**SIP** (Sensor Index Pointer) is a minimal, high-speed protocol for ingesting and querying time-series sensor data in PANCAKE. While BITEs handle rich, contextual agricultural data, SIPs handle millions of lightweight sensor readings.

### The Core Concept

**BITE**: Rich, contextual, immutable agricultural intelligence  
**SIP**: Fast, minimal, high-throughput sensor telemetry

**Analogy**:
- **BITE** = Email (rich formatting, attachments, metadata)
- **SIP** = Text message (fast, simple, ephemeral)

---

## The Time-Series Problem

### Scenario: IoT Sensor Network

**Farm setup**:
- 100 soil moisture sensors
- Reading every 30 seconds
- = 2 readings/minute/sensor
- = 200 readings/minute total
- = 288,000 readings/day
- = 105 million readings/year

### BITE Approach (Inefficient)

**Creating 105M BITEs/year**:
```json
{
  "Header": {
    "id": "01HQXYZ...",
    "geoid": "field-abc-sensor-001",
    "timestamp": "2024-11-01T10:00:00Z",
    "type": "sensor_reading"
  },
  "Body": {
    "sensor_id": "A1-3",
    "metric": "soil_moisture",
    "value": 7.4,
    "unit": "percent"
  },
  "Footer": {
    "hash": "abc123...",
    "schema_version": "1.0"
  }
}
```

**Problems**:
- **Size**: ~500 bytes/BITE × 105M = **52.5 GB/year** (just for sensor data!)
- **Overhead**: Hash computation, JSONB parsing, embedding generation
- **Latency**: INSERT takes ~10ms (too slow for 200 writes/sec)
- **Cost**: Embeddings would cost $105K/year (infeasible)

### SIP Approach (Efficient)

**Creating 105M SIPs/year**:
```json
{"sensor_id": "A1-3", "time": "2024-11-01T10:00:00Z", "value": 7.4}
```

**Benefits**:
- **Size**: ~60 bytes/SIP × 105M = **6.3 GB/year** (8x smaller)
- **Overhead**: None (append-only to Parquet)
- **Latency**: Batch write ~0.1ms/SIP (2000x faster)
- **Cost**: $0 (no embeddings needed for time-series)

---

## What is SIP?

**SIP** is a minimal data packet for high-frequency sensor data:

### As an Ingest Packet (Write)

**Purpose**: Sensor → PANCAKE ingestion

**Structure** (minimal):
```json
{
  "sensor_id": "A1-3",
  "time": "2024-11-01T10:00:00Z",
  "value": 7.4
}
```

**Characteristics**:
- **Tiny**: 60 bytes (vs 500 bytes for BITE)
- **Asynchronous**: Fire-and-forget (no response needed)
- **Fast**: Batch inserts, no hash computation, no embedding
- **Schema-less**: Just 3 fields (sensor_id, time, value)

### As a Response Packet (Read)

**Purpose**: Agent query → PANCAKE response

**Query** (SIP-query):
```json
{
  "sensor_id": "A1-3",
  "op": "GET_LATEST"
}
```

**Response** (SIP):
```json
{
  "sensor_id": "A1-3",
  "time": "2024-11-01T10:30:00Z",
  "value": 7.4
}
```

**Characteristics**:
- **Low-latency**: <10ms (no JSONB parsing, direct Parquet read)
- **Simple**: Single value, not aggregated context
- **Lightweight**: No embeddings, no semantic search

---

## SIP Design Philosophy

### Principle 1: Minimal is Maximal

**Less is more for high-frequency data.**

**BITE philosophy**: Rich context (Header + Body + Footer)  
**SIP philosophy**: Just the facts (`sensor_id`, `time`, `value`)

**Why**:
- Sensors generate millions of readings → Every byte matters
- Context is in metadata (sensor registration, field boundaries) → Don't repeat
- Speed > semantics for time-series

### Principle 2: Fire-and-Forget

**Sensors don't wait for responses.**

**Traditional DB**:
```python
result = db.insert(reading)
if result.success:
    sensor.acknowledge()
else:
    sensor.retry()
```
**Problem**: Network latency (100-500ms) blocks sensor

**SIP approach**:
```python
pancake.sip_queue.append(reading)  # Async, returns immediately
```
**Benefit**: Sensor continues sampling (no blocking)

### Principle 3: Separate Storage, Unified Query

**SIPs and BITEs stored differently, queried together.**

**Storage**:
- **SIPs**: Parquet files (columnar, compressed, time-partitioned)
- **BITEs**: PostgreSQL JSONB (flexible, indexed, semantic)

**Query**:
- **Agent**: Single interface (asks PANCAKE)
- **PANCAKE**: Orchestrates (routes to SIP engine or BITE engine)
- **Result**: Unified (SIPs and BITEs combined in response)

### Principle 4: Summary BITEs from SIPs

**Don't query raw SIPs for AI/ML; use summary BITEs.**

**Process**:
```
1. Sensors → 288K SIPs/day (raw readings)
2. PANCAKE → Nightly aggregation (compute stats)
3. Create 1 BITE/day (summary with embeddings)
4. AI/LLM queries → Use BITE (semantic search)
5. Low-latency queries → Use SIP (latest value)
```

**Example summary BITE** (from 2880 SIPs):
```json
{
  "Header": {
    "type": "sensor_summary",
    "geoid": "field-abc",
    "timestamp": "2024-11-01"
  },
  "Body": {
    "sensor_id": "A1-3",
    "metric": "soil_moisture",
    "statistics": {
      "mean": 23.5,
      "min": 18.2,
      "max": 28.7,
      "count": 2880
    },
    "sip_data_uri": "s3://farm-data/sips/2024-11-01/A1-3.parquet"
  }
}
```

---

## SIP Packet Structure

### Ingest SIP (Write)

**Minimal fields**:
```json
{
  "sensor_id": "A1-3",           // Required: Unique sensor identifier
  "time": "2024-11-01T10:00:00Z", // Required: UTC timestamp (ISO 8601)
  "value": 7.4                    // Required: Measurement value (float)
}
```

**Optional fields** (if needed):
```json
{
  "sensor_id": "A1-3",
  "time": "2024-11-01T10:00:00Z",
  "value": 7.4,
  "unit": "percent",              // Optional: For clarity
  "quality": 0.95                 // Optional: Confidence/quality score
}
```

**Design rationale**:
- **No geoid**: Sensor metadata (registration) stores geoid mapping
- **No hash**: Not immutable like BITE (can be overwritten/aggregated)
- **No embedding**: Time-series don't need semantic search
- **No provenance**: Sensor ID is sufficient

### Query SIP (Read)

**Operations**:

**1. GET_LATEST** (most common):
```json
{
  "sensor_id": "A1-3",
  "op": "GET_LATEST"
}
```
Response:
```json
{
  "sensor_id": "A1-3",
  "time": "2024-11-01T10:30:00Z",
  "value": 7.4
}
```

**2. GET_RANGE**:
```json
{
  "sensor_id": "A1-3",
  "op": "GET_RANGE",
  "start": "2024-11-01T00:00:00Z",
  "end": "2024-11-01T23:59:59Z"
}
```
Response:
```json
{
  "sensor_id": "A1-3",
  "count": 2880,
  "data_uri": "s3://farm-data/sips/2024-11-01/A1-3.parquet"
}
```

**3. GET_STATS**:
```json
{
  "sensor_id": "A1-3",
  "op": "GET_STATS",
  "start": "2024-11-01T00:00:00Z",
  "end": "2024-11-01T23:59:59Z"
}
```
Response:
```json
{
  "sensor_id": "A1-3",
  "mean": 23.5,
  "min": 18.2,
  "max": 28.7,
  "count": 2880
}
```

---

## SIP vs BITE

### Comparison Table

| Aspect | SIP | BITE |
|--------|-----|------|
| **Purpose** | High-frequency sensor data | Rich agricultural intelligence |
| **Size** | ~60 bytes | ~500 bytes |
| **Frequency** | Seconds/minutes | Hours/days/events |
| **Structure** | 3 fields (sensor_id, time, value) | 3 sections (Header, Body, Footer) |
| **Immutability** | No (can aggregate/downsample) | Yes (cryptographic hash) |
| **Embedding** | No (not semantic) | Yes (AI-ready) |
| **Storage** | Parquet (columnar) | PostgreSQL JSONB |
| **Query latency** | <10ms (indexed lookup) | 10-100ms (semantic search) |
| **Use case** | "What's the current soil moisture?" | "Why is my crop stressed?" |

### When to Use SIP

✅ **Use SIP for**:
- Sensor readings (every 30 seconds)
- GPS tracks (every second)
- Weather station telemetry (every 5 minutes)
- Equipment metrics (RPM, fuel, speed)
- Any high-frequency time-series

### When to Use BITE

✅ **Use BITE for**:
- Field observations (scout reports)
- Satellite imagery summaries (daily NDVI)
- Lab results (soil tests)
- Events (planting, harvest, spraying)
- Recommendations (agronomist advice)
- Daily sensor summaries (aggregated from SIPs)

### Hybrid Pattern (Best Practice)

**Raw data**: SIPs (millions)  
**Summaries**: BITEs (hundreds)  
**AI queries**: BITEs only  
**Real-time dashboards**: SIPs + BITEs

**Example**:
```
Soil moisture sensor:
├── SIPs: 2880/day (every 30 seconds)
├── BITE: 1/day (daily summary with stats)
└── AI query: "Is soil too dry?" → Queries BITE (semantic search)
└── Dashboard: "Current moisture?" → Queries SIP (latest value)
```

---

## Write Path: Sensor → SIP → PANCAKE

### Architecture

```
┌─────────┐
│ Sensor  │ (reads every 30 seconds)
└────┬────┘
     │ SIP: {"sensor_id": "A1-3", "time": "...", "value": 7.4}
     ▼
┌─────────────┐
│ SIP Queue   │ (in-memory buffer, batches 1000 SIPs)
└──────┬──────┘
       │ Batch write (every 10 seconds)
       ▼
┌─────────────────┐
│ Parquet Writer  │ (append to daily partition)
└──────┬──────────┘
       │ File: s3://farm-data/sips/2024-11-01/field-abc.parquet
       ▼
┌─────────────┐
│ PANCAKE PAN │ (indexes for fast retrieval)
└─────────────┘
```

### Implementation

**1. Sensor sends SIP** (fire-and-forget):
```python
import requests

sip = {
    "sensor_id": "A1-3",
    "time": datetime.utcnow().isoformat() + "Z",
    "value": 7.4
}

# Async POST (no wait for response)
requests.post("https://pancake.farm/sip/ingest", json=sip, timeout=1)
```

**2. PANCAKE buffers SIPs**:
```python
# In-memory queue (thread-safe)
from queue import Queue

sip_queue = Queue(maxsize=10000)

def ingest_sip(sip):
    sip_queue.put(sip)  # O(1), non-blocking
    return {"status": "queued"}  # Immediate response
```

**3. Background worker flushes to Parquet**:
```python
import pyarrow.parquet as pq
import pandas as pd

def flush_sips_to_parquet():
    while True:
        # Batch 1000 SIPs (or 10 seconds, whichever first)
        batch = []
        for _ in range(1000):
            if not sip_queue.empty():
                batch.append(sip_queue.get())
        
        if batch:
            # Convert to DataFrame
            df = pd.DataFrame(batch)
            
            # Append to daily partition
            date = df['time'].iloc[0][:10]  # "2024-11-01"
            filepath = f"s3://farm-data/sips/{date}/all_sensors.parquet"
            
            # Write (append mode)
            pq.write_to_dataset(
                pa.Table.from_pandas(df),
                root_path=filepath,
                partition_cols=['sensor_id']
            )
        
        time.sleep(10)  # Flush every 10 seconds
```

**4. Index updates**:
```python
# PostgreSQL metadata table (for fast lookups)
CREATE TABLE sip_index (
    sensor_id TEXT,
    date DATE,
    count INT,
    parquet_uri TEXT,
    PRIMARY KEY (sensor_id, date)
);

# After Parquet write
INSERT INTO sip_index (sensor_id, date, count, parquet_uri)
VALUES ('A1-3', '2024-11-01', 2880, 's3://...')
ON CONFLICT (sensor_id, date) DO UPDATE SET count = count + 1;
```

---

## Read Path: Agent → SIP Query → Response

### Architecture

```
┌────────┐
│ Agent  │ (queries: "What's current soil moisture?")
└───┬────┘
    │ SIP Query: {"sensor_id": "A1-3", "op": "GET_LATEST"}
    ▼
┌──────────────────┐
│ PANCAKE Query    │ (orchestrator)
│ Router           │
└───┬──────────────┘
    │ Routes to SIP Engine (fast path)
    ▼
┌──────────────────┐
│ SIP Query Engine │ (in-memory cache + Parquet)
└───┬──────────────┘
    │ SIP Response: {"sensor_id": "A1-3", "time": "...", "value": 7.4}
    ▼
┌────────┐
│ Agent  │ (receives answer in <10ms)
└────────┘
```

### Implementation

**1. Agent sends SIP query**:
```python
query = {
    "sensor_id": "A1-3",
    "op": "GET_LATEST"
}

response = requests.post("https://pancake.farm/sip/query", json=query)
sip = response.json()
print(f"Current moisture: {sip['value']}%")
```

**2. PANCAKE SIP Engine**:
```python
# In-memory cache (LRU, 10K sensors)
from functools import lru_cache

@lru_cache(maxsize=10000)
def get_latest_sip(sensor_id):
    # Check cache first
    if sensor_id in sip_cache:
        return sip_cache[sensor_id]
    
    # Query index
    result = db.query("""
        SELECT parquet_uri, date 
        FROM sip_index 
        WHERE sensor_id = %s 
        ORDER BY date DESC 
        LIMIT 1
    """, [sensor_id])
    
    # Read from Parquet
    df = pd.read_parquet(result['parquet_uri'])
    latest = df.sort_values('time').iloc[-1]
    
    sip = {
        "sensor_id": latest['sensor_id'],
        "time": latest['time'],
        "value": latest['value']
    }
    
    # Update cache
    sip_cache[sensor_id] = sip
    
    return sip
```

**Performance**:
- **Cache hit**: <1ms
- **Cache miss**: <10ms (Parquet read)
- **Network overhead**: ~5ms
- **Total**: <15ms (vs 50-100ms for BITE semantic search)

---

## Storage: Parquet + GeoID

### Why Parquet?

**Parquet**: Columnar storage format (Apache Arrow project)

**Benefits**:
1. **Compression**: 10x smaller than JSON (gzip/snappy)
2. **Columnar**: Read only columns needed (fast)
3. **Partitioned**: Time-based partitions (skip irrelevant files)
4. **Standard**: Works with Pandas, Spark, DuckDB, Polars

**Alternative rejected**:
- **InfluxDB**: Requires separate database (adds complexity)
- **TimescaleDB**: PostgreSQL extension (but Parquet is simpler for append-only)
- **PostgreSQL**: Too slow for 200 writes/sec

### Partitioning Strategy

**By date + sensor_id**:
```
s3://farm-data/sips/
├── 2024-11-01/
│   ├── A1-1.parquet (2880 readings)
│   ├── A1-2.parquet (2880 readings)
│   └── A1-3.parquet (2880 readings)
├── 2024-11-02/
│   ├── A1-1.parquet
│   ├── A1-2.parquet
│   └── A1-3.parquet
└── 2024-11-03/
    └── ...
```

**Query optimization**:
- "Latest value" → Read only today's file (1 Parquet)
- "Last 7 days" → Read 7 Parquets (parallel)
- "Specific sensor" → Read only that sensor's files (skip others)

### GeoID Integration

**Sensor metadata table**:
```sql
CREATE TABLE sensors (
    sensor_id TEXT PRIMARY KEY,
    geoid TEXT NOT NULL,           -- Field location
    sensor_type TEXT,              -- soil_moisture, temperature, etc.
    install_date DATE,
    depth_cm INT,                  -- For soil sensors
    metadata JSONB
);
```

**Query by GeoID**:
```python
# "Show all sensors for field-abc"
sensors = db.query("""
    SELECT sensor_id FROM sensors WHERE geoid = 'field-abc'
""")

# Read SIPs for all sensors in that field
sips = []
for sensor in sensors:
    sips.extend(read_sip_parquet(sensor['sensor_id'], date='2024-11-01'))
```

---

## PANCAKE Dual-Agent Architecture

### Two Query Engines

**PANCAKE now has TWO agents**:

**1. BITE Agent** (semantic, slow, rich):
- Queries PostgreSQL JSONB + pgvector
- Semantic search (embeddings)
- Multi-pronged similarity (semantic + spatial + temporal)
- Latency: 50-100ms
- Use case: "Why is my crop stressed?"

**2. SIP Agent** (indexed, fast, simple):
- Queries Parquet files (or in-memory cache)
- Key-value lookup (sensor_id → latest value)
- Latency: <10ms
- Use case: "What's current soil moisture?"

### Query Router

**Orchestrator decides which agent to use**:

```python
def pancake_query(query):
    """Route query to appropriate agent"""
    
    # Parse query type
    if is_sip_query(query):
        # Fast path: SIP Agent
        return sip_agent.query(query)
    
    elif is_bite_query(query):
        # Semantic path: BITE Agent
        return bite_agent.query(query)
    
    elif is_hybrid_query(query):
        # Orchestrate: Query both, combine results
        sip_results = sip_agent.query(extract_sip_query(query))
        bite_results = bite_agent.query(extract_bite_query(query))
        return combine(sip_results, bite_results)
```

**Example hybrid query**:
```python
query = "Is field-abc's soil moisture below optimal based on recent observations?"

# Router breaks down:
# 1. SIP query: Get latest soil moisture for all sensors in field-abc
sips = sip_agent.query({"geoid": "field-abc", "metric": "soil_moisture", "op": "GET_LATEST"})

# 2. BITE query: Get recent observations about field-abc
bites = bite_agent.rag_query("soil conditions field-abc", geoid_filter="field-abc", days_back=7)

# 3. Synthesize answer (LLM)
context = {
    "current_moisture": [s['value'] for s in sips],
    "observations": [b['Body'] for b in bites]
}
answer = llm.synthesize(query, context)
# "Soil moisture is 18% (below optimal 20-30%). Recent observation noted 'soil cracking' 3 days ago."
```

---

## TAP Integration

### TAP Generates SIPs (Future Enhancement)

**Scenario**: CropX sensor vendor

**Today** (without SIP):
- CropX API returns readings every 10 minutes
- TAP creates 144 BITEs/day (inefficient)

**Future** (with SIP):
- CropX API returns readings every 10 minutes
- **TAP creates 144 SIPs/day** (efficient)
- **PLUS: TAP creates 1 BITE/day** (summary with embeddings)

**TAP Adapter Configuration** (future):
```yaml
# tap_config.yaml
adapters:
  cropx:
    vendor: "cropx"
    data_type: "soil_moisture"
    output_mode: "hybrid"  # SIP + BITE
    
    sip_config:
      frequency: "10min"           # Create SIP every 10 minutes
      format: "fire_and_forget"    # Async ingestion
    
    bite_config:
      frequency: "daily"           # Create BITE summary once/day
      statistics: ["mean", "min", "max", "std"]
      include_sip_uri: true        # Link to raw SIPs
```

**TAP Output**:
```
Day 1:
- 144 SIPs (raw readings)
- 1 BITE (summary: mean=23.5%, links to Parquet)

Day 2:
- 144 SIPs
- 1 BITE (summary: mean=24.1%, links to Parquet)
...
```

**Note**: TAP SIP generation is **future work** (mark as TODO).

---

## Performance Characteristics

### Benchmarks (Projected)

| Operation | SIP | BITE | Speedup |
|-----------|-----|------|---------|
| **Write latency** | 0.1ms (batched) | 10ms (individual) | **100x** |
| **Read latency** | <10ms (cached) | 50-100ms (semantic) | **10x** |
| **Storage size** | 60 bytes | 500 bytes | **8x smaller** |
| **Throughput** | 10,000 writes/sec | 100 writes/sec | **100x** |

### Scalability

**Small farm** (10 sensors):
- 28,800 SIPs/day
- Storage: 1.8 MB/day = 657 MB/year
- Cost: $0.02/year (S3)

**Medium farm** (100 sensors):
- 288,000 SIPs/day
- Storage: 18 MB/day = 6.6 GB/year
- Cost: $0.15/year (S3)

**Large farm** (1000 sensors):
- 2.88M SIPs/day
- Storage: 180 MB/day = 66 GB/year
- Cost: $1.50/year (S3)

**Co-op** (10,000 sensors):
- 28.8M SIPs/day
- Storage: 1.8 GB/day = 660 GB/year
- Cost: $15/year (S3)

**Conclusion**: SIP is economically viable at any scale.

---

## Conclusion

SIP complements BITE perfectly:
- **SIP**: Fast, minimal, high-throughput (time-series sensors)
- **BITE**: Rich, contextual, semantic (agricultural intelligence)

Together, they form a complete data architecture:
- **PAN**: Ingests millions of SIPs + thousands of BITEs
- **CAKE**: Builds knowledge from both (summaries, relationships)
- **PANCAKE**: Dual-agent system (SIP engine + BITE engine)

**The future of agricultural data is multi-modal: BITEs for context, SIPs for speed.** 🥞⚡

---

**Document Status**: Specification (v1.0)  
**Last Updated**: November 2024  
**Feedback**: https://github.com/agstack/sip-spec/issues  
**License**: Apache 2.0

