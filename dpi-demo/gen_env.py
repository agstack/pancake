#!/usr/bin/env python3
"""Create .env from .env.example with a freshly generated Pancake issuer key.

Idempotent: does nothing if .env already exists. Kept as a separate script so
the Makefile stays simple and portable.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SERVICES = HERE.parent / "services"


def generate_issuer_key() -> str:
    sys.path.insert(0, str(SERVICES))
    from pancake_services.grants.issuer import generate_keypair_pem

    private_pem, _public_pem = generate_keypair_pem()
    return private_pem


def main() -> int:
    env = HERE / ".env"
    if env.exists():
        print(".env already exists; leaving it untouched")
        return 0

    text = (HERE / ".env.example").read_text()
    try:
        key = generate_issuer_key()
        # Store as a single line with escaped newlines (docker-compose passes it verbatim).
        one_line = key.replace("\n", "\\n")
        text = re.sub(
            r"^PANCAKE_ISSUER_KEY=.*$",
            "PANCAKE_ISSUER_KEY=" + one_line,
            text,
            flags=re.M,
        )
        print("Generated a Pancake issuer key into .env")
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not generate issuer key ({exc}); set PANCAKE_ISSUER_KEY manually")

    env.write_text(text)
    print("Created .env (local dev only -- do not commit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
