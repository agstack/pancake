"""TAP vendor configuration loading with ${VAR} environment interpolation.

Vendor credentials are never written into config files; the YAML references
environment variables (e.g. ``secretkey: ${TERRAPIPE_SECRET}``) which are
resolved at load time. A missing variable is a hard error -- better to fail
at startup than to call a vendor with empty credentials.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List

import yaml

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class MissingEnvironmentVariable(Exception):
    pass


def _interpolate(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            name = match.group(1)
            resolved = os.environ.get(name)
            if resolved is None:
                raise MissingEnvironmentVariable(
                    f"config references ${{{name}}} but it is not set in the environment"
                )
            return resolved

        return _VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def load_vendor_configs(config_path: str) -> List[Dict[str, Any]]:
    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}
    return [_interpolate(v) for v in raw.get("vendors", [])]
