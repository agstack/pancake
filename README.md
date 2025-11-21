# PANCAKE: AI-Native Geospatial Storage for Agriculture

**An AgStack Project | Powered by The Linux Foundation**

**PANCAKE** (Persistent-Agentic-Node + Contextual Accretive Knowledge Ensemble) is an open-source, AI-native data platform designed as Digital Public Infrastructure (DPI) for agriculture.

**Vision**: "An AI-native Operating System for Agriculture"

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/agstack/pancake.git
cd pancake

# Set up dockerised PostgreSQL with pgvector
bash implementation/setup_postgres_docker.sh

# Install dependencies
pip install -r implementation/requirements_poc.txt

# Run POC notebook
jupyter notebook implementation/POC_Nov20_BITE_PANCAKE.ipynb
```

**See**: `implementation/POC_README.md` for detailed setup instructions

---

## What is PANCAKE?

PANCAKE is **"ChatGPT for spatio-temporal farm data"** - query your agricultural data with natural language, not SQL.

### Core Components

- **BITE** (Bidirectional Interchange Transport Envelope): Universal JSON format for agricultural data
- **SIP** (Sensor Index Pointer): IoT/Streaming layer for sensors and actuators
- **MEAL** (Multi-User Engagement Asynchronous Ledger): Collaboration persistence layer
- **TAP** (Third-party Agentic-Pipeline): Vendor integration framework
- **PANCAKE Core**: AI-native geospatial storage with multi-pronged RAG

### Key Features

- ✅ **Natural Language Queries**: "What pests affected Field A last week?"
- ✅ **Multi-Pronged RAG**: Semantic + Spatial + Temporal similarity search
- ✅ **Polyglot Data**: One table stores all data types (observations, imagery, operations, etc.)
- ✅ **Spatio-Temporal Indexing**: Automatic spatial relationships via GeoID
- ✅ **Immutable Audit Trails**: Cryptographic hash chains for compliance
- ✅ **Vendor-Agnostic**: TAP adapters for any agricultural data source

---

## Documentation Structure

### Core Documentation (`/docs`)
- `BITE.md` - Universal data format specification
- `PANCAKE.md` - Core storage and AI architecture
- `SIP.md` - Sensor/actuator streaming protocol
- `MEAL.md` - Collaboration and audit ledger
- `TAP.md` - Vendor integration framework
- `SIRUP.md` - Enriched data payload concept

### Sprint Plans (`/sprints`)
- `SPRINT_1_USER_AUTHENTICATION_UPGRADE.md` - OECD-compliant authentication (Weeks 1-12)
- `SPRINT_2_ENTERPRISE_MIGRATION.md` - Enterprise FMIS migration (Weeks 13-24)
- `SPRINT_3_PAYMENTS.md` - Digital payments integration (Weeks 25-36)
- `SPRINT_4_DATA_WALLETS.md` - Data wallets & chain of custody (Weeks 37-48)

### Testing Profiles (`/testing`)
- `testing_EUDR.md` - EUDR compliance testing scenarios
- `testing_food_safety.md` - Food safety traceability testing scenarios

### Strategic Documents (`/strategic`)
- `PANCAKE_WHITEPAPER_DPI.md` - Business white paper
- `EU_HORIZON_GRANTS_STRATEGY.md` - EU grant strategy
- `EU_HORIZON_GRANTS_PROPOSAL.md` - EU grant proposal
- `OECD_AUTHENTICATION_ALIGNMENT.md` - OECD compliance analysis
- `openagri_integration.md` - OpenAgri integration guide

### Implementation (`/implementation`)
- `POC_Nov20_BITE_PANCAKE.ipynb` - Proof of Concept notebook
- `POC_README.md` - POC setup instructions
- `requirements_poc.txt` - Python dependencies
- `setup_postgres.sh` - PostgreSQL setup script
- `meal.py` - MEAL implementation
- `tap_adapter_base.py` - TAP adapter base class
- `tap_adapters.py` - TAP adapter implementations
- `migrations/` - Database migration scripts

### Podcast Series (`/podcast`)
- Complete podcast series for NotebookLM
- 11 modules covering all aspects of PANCAKE

### Archive (`/archive`)
- Historical documentation and completed phase summaries

---

## Roadmap

**See**: `ROADMAP.md` for complete 12-month sprint-based development plan

**Current Status**: Sprint 1 (User Authentication) - Planning

**Timeline**:
- **Sprint 1**: Weeks 1-12 (User Authentication)
- **Sprint 2**: Weeks 13-24 (Enterprise Migration)
- **Sprint 3**: Weeks 25-36 (Payments)
- **Sprint 4**: Weeks 37-48 (Data Wallets)

---

## Key Use Cases

### 1. Natural Language Queries
```python
# Query PANCAKE with natural language
answer = pancake.ask(
    "What pests or diseases have been observed in the coffee fields in the last week?",
    geoid="field-coffee-123"
)
```

### 2. Multi-Vendor Data Integration
```python
# Fetch data from multiple vendors via TAP
ndvi_data = tap_factory.fetch('terrapipe_ndvi', geoid='field-abc')
soil_data = tap_factory.fetch('soilgrids', geoid='field-abc')
weather_data = tap_factory.fetch('terrapipe_weather', geoid='field-abc')
```

### 3. Enterprise FMIS Migration
```python
# Migrate FMIS data to PANCAKE
migration_tool = MigrationTool(pancake_client, adapter)
result = migration_tool.migrate_csv('fieldview_export.csv')
```

### 4. EUDR Compliance
```python
# Generate EUDR compliance report
eudr_report = eudr_compliance.generate_eudr_report(shipment_geoid='shipment-123')
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              PANCAKE Application Layer                  │
│  (Natural Language Queries, Voice API, Mobile/Desktop) │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              PANCAKE Core (Storage + AI)                │
│  • BITE Storage (PostgreSQL + pgvector)                │
│  • SIP Storage (Time-series optimized)                 │
│  • MEAL Storage (Immutable ledger)                      │
│  • Multi-Pronged RAG (Semantic + Spatial + Temporal)    │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              TAP (Vendor Integration)                   │
│  • Terrapipe (NDVI, Weather)                            │
│  • SoilGrids (Soil data)                               │
│  • Custom TAP Adapters                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Technology Stack

- **Database**: PostgreSQL 14+ with pgvector extension
- **AI/ML**: OpenAI GPT-4 (embeddings and queries), local models supported
- **Blockchain**: Hyperledger Fabric (payments), Hyperledger Indy/Aries (identity)
- **Languages**: Python 3.9+
- **License**: Apache 2.0 (Code) | CC BY 4.0 (Documentation)

---

## Contributing

PANCAKE is an AgStack project under The Linux Foundation. We welcome contributions!

**Getting Started**:
1. Review `ROADMAP.md` for current development priorities
2. Check `GOVERNANCE.md` for contribution guidelines
3. Join AgStack community: https://agstack.org

**Areas for Contribution**:
- TAP adapter development
- Core PANCAKE improvements
- Documentation
- Testing
- Use case implementations

---

## License

- **Code**: Apache 2.0
- **Documentation**: CC BY 4.0

---

## Contact & Resources

- **GitHub**: https://github.com/agstack/pancake
- **Documentation**: See `/docs/` directory
- **AgStack**: https://agstack.org
- **Email**: pancake@agstack.org

---

## Status

**Current Version**: POC (Proof of Concept)  
**Next Milestone**: Sprint 1 completion (Week 12)  
**Production Target**: After Sprint 4 (Week 48)

---

**An AgStack Project | Powered by The Linux Foundation**
