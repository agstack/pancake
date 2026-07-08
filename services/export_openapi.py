"""Export the service's OpenAPI spec to openapi.json (grant deliverable: API catalog)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from conftest import FakeHub, StaticJWKSCache  # noqa: E402

from pancake_services.common.config import Settings  # noqa: E402
from pancake_services.grants.app import create_app  # noqa: E402
from pancake_services.grants.issuer import IssuerIdentity, generate_keypair_pem  # noqa: E402


def main() -> None:
    priv, pub = generate_keypair_pem()
    app = create_app(
        settings=Settings(database_url="sqlite:///:memory:"),
        issuer=IssuerIdentity("did:web:pancake.agstack.org", "pancake-issuer-1", priv, pub),
        jwks_cache=StaticJWKSCache(FakeHub()),
    )
    out = Path(__file__).resolve().parent / "openapi.json"
    out.write_text(json.dumps(app.openapi(), indent=2))
    print(f"wrote {out} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()
