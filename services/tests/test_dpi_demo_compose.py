"""The demo stack's wiring, checked without needing Docker.

``docker compose up`` is the only thing that truly proves this file, and it is
not available in every environment this suite runs in. What can be checked
anywhere is the wiring: that a build context exists, that a service publishes
the variable another service is gated on, and that every ``${VAR}`` the TAP
config demands is supplied with a default so the stack starts without a
``.env`` full of values nobody has yet.

Those are the failures that actually happen to this file. A wrong image tag
announces itself the first time anyone runs it; a variable named
``TERRAPIPE_OS_URL`` in one service and ``TERRAPIPEOS_URL`` in another starts
cleanly, skips the vendor it was supposed to enable, and looks exactly like a
working demo with no deforestation data.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

DEMO = Path(__file__).resolve().parents[2] / "dpi-demo"
COMPOSE = DEMO / "docker-compose.yml"
VENDORS = DEMO / "tap_vendors.yaml"

# The gate in tap_vendors.yaml that turns the open-science vendors on.
GATE = "TERRAPIPE_OS_URL"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


def _environment(service: dict) -> dict:
    """Compose allows a mapping or a list of KEY=VALUE; normalise to a mapping."""
    env = service.get("environment") or {}
    if isinstance(env, list):
        return dict(item.split("=", 1) for item in env if "=" in item)
    return {str(k): "" if v is None else str(v) for k, v in env.items()}


def test_the_open_science_profile_exists_and_holds_the_node(compose):
    node = compose["services"]["terrapipe-os"]
    assert node["profiles"] == ["openscience"]
    assert "8200:8200" in node["ports"]


def test_the_node_image_can_actually_be_built(compose):
    """A build context that does not exist fails at `up`, not at parse."""
    build = compose["services"]["terrapipe-os"]["build"]
    context = (DEMO / build["context"]).resolve()

    assert context.is_dir(), f"build context missing: {context}"
    assert (context / build["dockerfile"]).is_file(), "no Dockerfile at the named path"
    assert (context / "layers" / "layers.json").is_file(), "the image copies the layer library"


def test_the_node_gets_the_three_urls_it_refuses_to_start_without(compose):
    """terrapipe-os fails loudly if AR2 and the hub are not named. Name them."""
    env = _environment(compose["services"]["terrapipe-os"])

    for required in ("AR2_NODE_URL", "AR2_HUB_URL", "HUB_JWKS_URL"):
        assert required in env, required
        assert env[required].strip(), f"{required} is present but empty"


def test_the_mirrors_are_mounted_read_only(compose):
    """A node that can write to the mirror can quietly disagree with the publisher."""
    volumes = compose["services"]["terrapipe-os"]["volumes"]

    assert volumes, "the node needs the share mounted to answer with data"
    for volume in volumes:
        assert volume.endswith(":ro"), f"mirror mounted writable: {volume}"


def test_the_worker_is_handed_the_variable_the_vendor_file_is_gated_on(compose):
    """The typo class this test exists for: two spellings of one variable."""
    worker_env = _environment(compose["services"]["pancake-tap"])
    vendors = yaml.safe_load(VENDORS.read_text())["vendors"]

    gated = {v["vendor_name"] for v in vendors if v.get("enabled_if_env") == GATE}
    assert gated, f"no vendor is gated on {GATE}; this test is checking nothing"
    assert GATE in worker_env, f"{GATE} is never passed to the worker, so {gated} can never run"


def test_every_variable_the_vendor_file_needs_is_supplied_by_the_worker(compose):
    """Interpolation raises on an unset ${VAR}, so a gap here stops the worker dead."""
    worker_env = _environment(compose["services"]["pancake-tap"])
    referenced = set(re.findall(r"\$\{([A-Z0-9_]+)\}", VENDORS.read_text()))

    missing = referenced - set(worker_env)
    assert not missing, f"tap_vendors.yaml needs {sorted(missing)}, which the worker never receives"


def test_the_stack_starts_without_a_dotenv_full_of_secrets(compose):
    """Every optional variable defaults, so `up` works before any credential exists.

    ``${VAR:?...}`` is compose's "refuse to start" form and is reserved for
    things with no safe default. Only the issuer key qualifies: a demo that
    minted grants under a default key would be issuing real-looking
    credentials signed by a key everybody has.
    """
    required = []
    for name, service in compose["services"].items():
        for key, value in _environment(service).items():
            if ":?" in value:
                required.append((name, key))

    assert required == [("pancake-grants", "PANCAKE_ISSUER_KEY")], required


def test_the_open_science_vendors_stay_off_until_the_node_is_named(compose):
    """`--profile core` alone must still be a working demo."""
    worker_env = _environment(compose["services"]["pancake-tap"])

    assert worker_env[GATE] == "${" + GATE + ":-}", (
        "the gate must default to empty, or the core-only demo tries to reach a node "
        "that was never started"
    )
