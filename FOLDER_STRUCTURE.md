# PANCAKE Folder Structure
## Organized for Easy Implementation

**Last Updated**: November 2025

---

## Overview

The PANCAKE repository is organized into clear directories for easy navigation and implementation:

```
pancake/
├── README.md                 # Main entry point
├── ROADMAP.md               # Unified 48-week roadmap
├── MOTIVATION.md            # Why PANCAKE exists (AI-enablement focus)
├── FOLDER_STRUCTURE.md      # This file
├── GOVERNANCE.md            # Contribution guidelines
│
├── docs/                    # Core specifications
│   ├── BITE.md             # Universal data format
│   ├── PANCAKE.md           # Core storage & AI
│   ├── SIP.md               # Sensor/actuator protocol
│   ├── MEAL.md              # Collaboration ledger
│   ├── TAP.md               # Vendor integration
│   ├── SIRUP.md             # Enriched data payload
│   └── TAP_VENDOR_GUIDE.md  # Vendor integration guide
│
├── sprints/                 # Sprint plans (12 weeks each)
│   ├── SPRINT_1_USER_AUTHENTICATION_UPGRADE.md
│   ├── SPRINT_2_ENTERPRISE_MIGRATION.md
│   ├── SPRINT_3_PAYMENTS.md
│   └── SPRINT_4_DATA_WALLETS.md
│
├── testing/                 # Testing profiles
│   ├── testing_EUDR.md      # EUDR compliance tests
│   └── testing_food_safety.md # Food safety tests
│
├── strategic/               # Strategic documents
│   ├── PANCAKE_WHITEPAPER_DPI.md
│   ├── EU_HORIZON_GRANTS_STRATEGY.md
│   ├── EU_HORIZON_GRANTS_PROPOSAL.md
│   ├── OECD_AUTHENTICATION_ALIGNMENT.md
│   ├── openagri_integration.md
│   ├── CRITICAL_ANALYSIS_PANCAKE_VALUE_PROPOSITION.md
│   ├── RESEARCH_ANALYSIS_SPATIO_TEMPORAL_RAG.md
│   └── research/            # Research documents
│       ├── DPI for Agriculture Sector_Final.pdf
│       ├── DPI_Agriculture.txt
│       ├── Permissively Licensed Data Stores with Spatio-Temporal & AI Capabilities.pdf
│       ├── StateAIReport-2025.txt
│       └── StateAIReport-2025ONLINE.pdf
│
├── implementation/          # POC and code
│   ├── POC_Nov20_BITE_PANCAKE.ipynb
│   ├── POC_README.md
│   ├── SETUP_GUIDE.md
│   ├── IMPLEMENTATION.md
│   ├── requirements_poc.txt
│   ├── setup_postgres.sh
│   ├── pancake_config.yaml  # Configuration reference
│   ├── benchmark_results.png # Performance benchmarks
│   ├── meal.py
│   ├── tap_adapter_base.py
│   ├── tap_adapters.py
│   ├── tap_vendors.yaml
│   └── migrations/
│       └── meal_schema.sql
│
├── podcast/                 # Podcast series
│   ├── Episode-0-Core-Narrative.md
│   ├── Module-1-PANCAKE-Core-Platform.md
│   ├── Module-2-BITE-Rich-Data-Exchange.md
│   ├── Module-3-SIP-Sensor-Actuator-Stream.md
│   ├── Module-4-MEAL-Collaboration-Persistence.md
│   ├── Module-5-TAP-SIRUP-IO-System.md
│   ├── Module-6-Multi-Pronged-RAG-Query-Engine.md
│   ├── Module-7-EUDR-Compliance-for-Coffee.md
│   ├── Module-8-FMIS-Integration-Private-Sector.md
│   ├── Module-9-Governance-Community.md
│   ├── Module-10-POC-Results-Road-Ahead.md
│   ├── LINKEDIN_LAUNCH_POST.md
│   └── PLATFORM_LAUNCH_STRATEGY.md
│
└── archive/                 # Historical documentation
    ├── CRITICAL_REVIEW_REVISED.md
    ├── DELIVERY_SUMMARY.md
    ├── DEMO_FINAL_STATUS.md
    ├── DEMO_READINESS.md
    ├── EXECUTIVE_SUMMARY.md
    ├── MEAL_IMPLEMENTATION_COMPLETE.md
    ├── MEAL_POC_COMPLETE.md
    ├── MOBILE_MEAL_SPEC.md
    ├── PGVECTOR_SUCCESS.md
    ├── PHASE_1_COMPLETE.md
    ├── PHASE_2_PLAN.md
    ├── POLYGLOT_TESTING_COMPLETE.md
    ├── SETUP_COMPLETE.md
    ├── TAP_MULTI_VENDOR_COMPLETE.md
    ├── WHITEPAPER_OUTLINE.md
    └── [various fix scripts]
```

---

## Directory Descriptions

### `/docs` - Core Specifications
**Purpose**: Core technical specifications for PANCAKE components

**Contents**:
- `BITE.md` - Universal data format specification
- `PANCAKE.md` - Core storage and AI architecture
- `SIP.md` - Sensor/actuator streaming protocol
- `MEAL.md` - Collaboration and audit ledger
- `TAP.md` - Vendor integration framework
- `SIRUP.md` - Enriched data payload concept

**Audience**: Architects, developers, standards bodies

---

### `/sprints` - Sprint Plans
**Purpose**: Detailed 12-week sprint plans for implementation

**Contents**:
- `SPRINT_1_USER_AUTHENTICATION_UPGRADE.md` - Weeks 1-12 (OECD-compliant authentication)
- `SPRINT_2_ENTERPRISE_MIGRATION.md` - Weeks 13-24 (Enterprise FMIS migration)
- `SPRINT_3_PAYMENTS.md` - Weeks 25-36 (Digital payments integration)
- `SPRINT_4_DATA_WALLETS.md` - Weeks 37-48 (Data wallets & chain of custody)

**Audience**: Project managers, developers, stakeholders

---

### `/testing` - Testing Profiles
**Purpose**: Testing scenarios and validation criteria for specific use cases

**Contents**:
- `testing_EUDR.md` - EUDR compliance testing scenarios
- `testing_food_safety.md` - Food safety traceability testing scenarios

**Audience**: QA engineers, testers, compliance officers

---

### `/strategic` - Strategic Documents
**Purpose**: Business strategy, grants, and high-level planning documents

**Contents**:
- `PANCAKE_WHITEPAPER_DPI.md` - Business white paper
- `EU_HORIZON_GRANTS_STRATEGY.md` - EU grant strategy
- `EU_HORIZON_GRANTS_PROPOSAL.md` - EU grant proposal
- `OECD_AUTHENTICATION_ALIGNMENT.md` - OECD compliance analysis
- `openagri_integration.md` - OpenAgri integration guide
- `OPENAGRI_INTEGRATION_ANALYSIS.md` - OpenAgri analysis

**Audience**: Executives, grant writers, strategic planners

---

### `/implementation` - POC and Code
**Purpose**: Working code, POC notebooks, and implementation guides

**Contents**:
- `POC_Nov20_BITE_PANCAKE.ipynb` - Proof of Concept Jupyter notebook
- `POC_README.md` - POC setup instructions
- `SETUP_GUIDE.md` - Setup guide
- `IMPLEMENTATION.md` - Implementation guide
- `requirements_poc.txt` - Python dependencies
- `setup_postgres.sh` - PostgreSQL setup script
- `meal.py` - MEAL implementation
- `tap_adapter_base.py` - TAP adapter base class
- `tap_adapters.py` - TAP adapter implementations
- `tap_vendors.yaml` - TAP vendor configuration
- `migrations/` - Database migration scripts

**Audience**: Developers, implementers

---

### `/podcast` - Podcast Series
**Purpose**: Complete podcast series for NotebookLM

**Contents**: 11 modules covering all aspects of PANCAKE

**Audience**: General audience, marketing, community

---

### `/archive` - Historical Documentation
**Purpose**: Old documentation and completed phase summaries

**Contents**: Historical documents, completed phase summaries, old fix scripts

**Audience**: Historical reference only

---

## Quick Navigation Guide

### For Developers Starting Implementation
1. Read `README.md` for overview
2. Review `ROADMAP.md` for timeline
3. Check `/sprints/` for current sprint plan
4. Review `/docs/` for technical specifications
5. Run `/implementation/POC_Nov20_BITE_PANCAKE.ipynb` for hands-on experience

### For Project Managers
1. Read `ROADMAP.md` for complete timeline
2. Review `/sprints/` for detailed sprint plans
3. Check `/strategic/` for business context
4. Review `/testing/` for validation criteria

### For Architects
1. Review `/docs/` for all technical specifications
2. Check `/strategic/PANCAKE_WHITEPAPER_DPI.md` for design rationale
3. Review `/sprints/` for implementation approach

### For Contributors
1. Read `GOVERNANCE.md` for contribution guidelines
2. Review `ROADMAP.md` for current priorities
3. Check `/sprints/` for areas needing contribution
4. Review `/implementation/` for code structure

---

## File Naming Conventions

- **Specifications**: `COMPONENT.md` (e.g., `BITE.md`, `PANCAKE.md`)
- **Sprint Plans**: `SPRINT_N_DESCRIPTION.md` (e.g., `SPRINT_1_USER_AUTHENTICATION_UPGRADE.md`)
- **Testing Profiles**: `testing_USECASE.md` (e.g., `testing_EUDR.md`)
- **Strategic Docs**: `DESCRIPTION.md` (e.g., `PANCAKE_WHITEPAPER_DPI.md`)
- **Implementation**: Descriptive names (e.g., `POC_Nov20_BITE_PANCAKE.ipynb`)

---

## Maintenance

**When to Archive**:
- Phase completion summaries → `/archive`
- Completed phase plans → `/archive`
- Old fix scripts → `/archive`
- Superseded documentation → `/archive`

**When to Update**:
- Core specifications → `/docs` (version controlled)
- Sprint plans → `/sprints` (update as sprints progress)
- Roadmap → `ROADMAP.md` (update quarterly)

---

**An AgStack Project | Powered by The Linux Foundation**

