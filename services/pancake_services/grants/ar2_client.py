"""Headers for Pancake's server-to-server calls into AR2.

Kept in one place because the interesting part is a refusal, and a refusal
duplicated across three routers is a refusal that will be right in two of them.

AR2 guards artifact reads with ``AR2_INTERNAL_SHARED_SECRET``: a caller that
presents the matching value in ``X-Pancake-Internal`` is trusted, and any other
caller must present a grant token. Pancake calls the artifact read *in order to
issue* the first grant, so it has no grant to present and must be the trusted
caller.

Until 2026-09-03 the three call sites read the variable with a default of the
string ``"true"``. When the variable was unset -- as it was on the first live
deployment, because nothing documented it -- Pancake sent that placeholder, AR2
found no configured secret, declined to trust the caller, and fell through to
grant authorisation, which failed. The failure AR2 returns in that case is a
deliberate 404 that hides whether the artifact exists, so what reached the
operator was "Failed to fetch list artifact from AR2: 404 Not Found" for an
artifact that existed and whose id was correct.

An unset secret is now refused here, by name, before the request is made.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Request

SECRET_ENV = "AR2_INTERNAL_SHARED_SECRET"


def internal_headers(request: Request) -> dict[str, str]:
    """Trusted-caller headers for an AR2 artifact read, or a 500 naming the gap."""
    secret = os.getenv(SECRET_ENV)
    if not secret:
        raise HTTPException(
            status_code=500,
            detail=(
                f"{SECRET_ENV} is not set on Pancake, so AR2 cannot recognise this node as a "
                "trusted caller and will refuse to return list members. Set it to the same "
                "value on the Pancake service and on the AR2 node, and restart both. "
                "Both sides must match; AR2 with no secret set trusts nobody."
            ),
        )
    headers = {"x-pancake-internal": secret}
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]
    return headers
