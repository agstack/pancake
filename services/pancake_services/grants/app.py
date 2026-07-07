"""FastAPI application factory for the Pancake grants service."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from pancake_services import __version__
from pancake_services.common.config import Settings, load_settings
from pancake_services.common.db import Base, make_engine, make_session_factory
from pancake_services.grants.auth import JWKSCache, get_current_user
from pancake_services.grants.issuer import IssuerIdentity, load_issuer_identity
from pancake_services.grants.models import User


def create_app(
    settings: Settings | None = None,
    issuer: IssuerIdentity | None = None,
    jwks_cache: JWKSCache | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    issuer = issuer or load_issuer_identity()

    app = FastAPI(
        title="Pancake Grants Service",
        version=__version__,
        description=(
            "Field-ownership and permission-grant service for the AgStack DPI. "
            "FieldLists (Merkle ListIDs) + SD-JWT VC grant credentials + "
            "StatusList2021 revocation + MEAL audit ledger."
        ),
    )

    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.jwks_cache = jwks_cache or JWKSCache(
        settings.hub_jwks_url, settings.jwks_cache_ttl_seconds
    )
    app.state.issuer = issuer

    @app.get("/healthz", tags=["health"])
    def healthz():
        return {"status": "ok", "service": "pancake-grants", "version": __version__}

    @app.get("/healthz/me", tags=["health"])
    def healthz_me(user: User = Depends(get_current_user)):
        """Echo the authenticated hub identity (auth smoke check)."""
        return {"hub_account_id": user.hub_account_id, "email": user.email}

    from pancake_services.grants.routers import audit, fieldlists, grants  # noqa: PLC0415

    app.include_router(fieldlists.router)
    app.include_router(grants.router)
    app.include_router(audit.router)

    return app
