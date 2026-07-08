#!/usr/bin/env python3
"""FATFD integrity validator for Pancake.

Checks:
  A  pending_work count >= knowledge.json open count
  B  fatfd_state.json parses and has required top-level keys
  C  findings.open_count in state matches knowledge.json
  D  test count never decreases vs the last completed cycle
  E  no open critical findings when the current cycle is marked complete

Exit code 0 = pass, 1 = failure.
"""
import json
import sys
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent

REQUIRED_STATE_KEYS = {"version", "current_cycle", "findings", "pending_work", "testing"}


def load(name):
    path = AUDIT_DIR / name
    try:
        return json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001 - report any parse/read failure
        fail(f"cannot read {name}: {e}")


failures = []


def fail(msg):
    failures.append(msg)


def main():
    state = load("fatfd_state.json")
    knowledge = load("knowledge.json")
    if failures:
        report()

    # Check B: required keys
    missing = REQUIRED_STATE_KEYS - set(state)
    if missing:
        fail(f"B: fatfd_state.json missing keys: {sorted(missing)}")

    open_findings = [f for f in knowledge.get("findings", []) if f.get("status") == "open"]

    # Check A
    pending = state.get("pending_work", [])
    if len(pending) < len(open_findings):
        fail(
            f"A: pending_work has {len(pending)} items but knowledge.json has "
            f"{len(open_findings)} open findings"
        )

    # Check C
    stated_open = state.get("findings", {}).get("open")
    if stated_open != len(open_findings):
        fail(
            f"C: state findings.open={stated_open} but knowledge.json has "
            f"{len(open_findings)} open findings"
        )

    # Check D: test count non-decreasing vs last completed cycle
    history = state.get("cycle_history", [])
    completed = [c for c in history if c.get("status") == "complete" and c.get("test_count") is not None]
    if completed:
        baseline = completed[-1]["test_count"]
        current = state.get("testing", {}).get("test_count", 0)
        if current < baseline:
            fail(f"D: test count decreased ({current} < baseline {baseline})")

    # Check E: no open criticals when current cycle marked complete
    if state.get("current_cycle", {}).get("status") == "complete":
        crit = [f["id"] for f in open_findings if f.get("severity") == "critical"]
        if crit:
            fail(f"E: cycle marked complete with open critical findings: {crit}")

    report()


def report():
    if failures:
        print("FATFD VALIDATION FAILED")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("FATFD validation passed (checks A-E)")
    sys.exit(0)


if __name__ == "__main__":
    main()
