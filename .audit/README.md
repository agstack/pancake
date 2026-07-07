# FATFD — Feedback, Audit, Test & Fix, Deploy

The quality harness for the Pancake DPI services.

## What is FATFD?

FATFD is a structured development lifecycle that ensures every change to Pancake is audited, tested, verified, and documented before it ships. Each unit of work runs as a **cycle** through the phases below, and every cycle leaves a written trace in this directory.

## Directory Structure

```
.audit/
├── README.md              <- You are here
├── GUARDRAILS.md          <- Human-owned invariants (NEVER auto-modified)
├── fatfd_state.json       <- Harness state (version, cycle history, test counts)
├── knowledge.json         <- All findings: fixed, open, learned, deferred
├── validate_fatfd.py      <- Integrity validator (quality gate)
├── hooks/                 <- Git hooks
│   ├── pre-commit         <- Blocks commits that violate FATFD integrity
│   └── install.sh         <- Symlink installer
└── reports/               <- Cycle reports (timestamped)
```

## Lifecycle Phases

| Phase | Name | What it does |
|-------|------|-------------|
| F | Collect Feedback | Ingest blockers, grant acceptance criteria, GitHub issues |
| 1 | Audit | Static analysis (ruff), pattern grep for last finding's root-cause class, knowledge regression scan |
| 2 | Test & Fix | Per-finding fix loop; tests written before code for every new endpoint |
| 2.5 | Adversarial Review | Self-review against the credential-security checklist in GUARDRAILS.md |
| 3 | Docs | README + spec docs updated in the same change |
| 4 | Re-Audit | Full test suite + end-to-end demo script |
| 5 | Version | Semver bump in `services/pyproject.toml`; minor bump per cycle |
| 6 | Git | Feature branch, descriptive commits; no direct pushes to main |
| 7 | Deploy | Staging bring-up (compose or local uvicorn); demo script green |
| 8 | Learn | Append findings to `knowledge.json` (IDs `PC-2026-NNNN`) |
| 9 | State | Update `fatfd_state.json`; validator must pass |

## Validator

Run: `python3 .audit/validate_fatfd.py`

| Check | What it verifies |
|-------|-----------------|
| A | `pending_work` count >= knowledge.json open count |
| B | State file freshness (updated within current cycle) |
| C | `findings.open_count` matches knowledge.json |
| D | Test count never decreases between cycles (zero-regression rule) |
| E | No open critical findings when a cycle is marked complete |

Exit code 0 = all checks pass; 1 = integrity failure (pre-commit hook blocks the commit).

## Knowledge Base

Every finding ever discovered lives in `knowledge.json` with:
- Unique ID (`PC-2026-NNNN`)
- Severity (critical, high, medium, low)
- Status (fixed, open, partial, learned, deferred)
- Area (grants, meal, tap, store, harness, docs)
- Description and fix version

## Getting Started

```bash
# Install git hooks
bash .audit/hooks/install.sh

# Run the validator
python3 .audit/validate_fatfd.py

# Run the full test suite
.venv/bin/python -m pytest services/tests -q
```
