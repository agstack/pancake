"""What the three terrapipe-os adapters share: a client, a grant, and a refusal policy.

The refusal policy is the substantive part. ``TAPAdapter.fetch_and_transform``
treats ``None`` as "skip, log, retry later", and the runtime retries three
times before recording a failure. That is right for a node that is down and
wrong for a node that answered plainly. Retrying a ``no_data`` costs three
round trips to be told the same thing, and retrying a ``grant_required``
cannot succeed at all until somebody issues a grant.

So a refusal the node is entitled to make is recorded and not retried: the
adapter returns ``None`` immediately with the reason logged. Only a transport
failure or an unexplained status is worth another attempt. The distinction is
carried by the node's own ``reason`` field rather than inferred here.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pancake_services.tap.adapter_base import TAPAdapter, create_bite_from_sirup
from pancake_services.tap.adapters.terrapipe_os.client import (
    GrantRequired,
    HubTokenSource,
    NoDataHere,
    TerrapipeOSClient,
    TerrapipeOSError,
)

logger = logging.getLogger(__name__)

VENDOR_DEFAULT = "terrapipe-os"


class TerrapipeOSAdapter(TAPAdapter):
    """Base for adapters that read one terrapipe-os node.

    Configuration (from the vendor YAML, credentials interpolated from the
    environment):

    ``base_url``
        The node, e.g. ``http://terrapipe-os:8200``.
    ``credentials.hub_url``, ``credentials.client_id``, ``credentials.client_secret``
        Client credentials for the AR hub. The node verifies the resulting
        token against the hub's JWKS; it never sees these.
    ``credentials.access_token``
        A pre-minted token instead of the above, for a demo or a test.
    ``credentials.field_grant``
        A field-access grant to present. Optional, and its absence is not an
        error: without it the node answers about the neighbourhood and says so.
    ``metadata.grant_env_template``
        Where to look for a per-GeoID grant, e.g. ``PANCAKE_GRANT_{geoid}``.
        Checked before ``credentials.field_grant``, so one adapter can serve
        several fields with different grants.
    """

    def _initialize(self) -> None:
        credentials = self.credentials or {}
        token_source = None
        if credentials.get("client_id") and credentials.get("client_secret"):
            token_source = HubTokenSource(
                hub_url=credentials.get("hub_url", ""),
                client_id=credentials["client_id"],
                client_secret=credentials["client_secret"],
                timeout=self.timeout,
            )
        self.client = TerrapipeOSClient(
            base_url=self.base_url,
            token_source=token_source,
            static_token=credentials.get("access_token"),
            timeout=self.timeout,
        )
        self._configured_grant = credentials.get("field_grant")
        self._grant_env_template = (self.metadata or {}).get("grant_env_template")

    # -- grants -------------------------------------------------------------

    def grant_for(self, geoid: str, params: Dict[str, Any]) -> Optional[str]:
        """The grant to present for this field, if we hold one.

        Per-task first, then a per-GeoID environment variable, then the
        adapter-wide one. None is a legitimate answer and produces a
        neighbourhood-scoped result, not a failure.
        """
        if params.get("field_grant"):
            return str(params["field_grant"])
        if self._grant_env_template:
            safe = "".join(ch if ch.isalnum() else "_" for ch in geoid)
            found = os.environ.get(self._grant_env_template.format(geoid=safe))
            if found:
                return found
        return self._configured_grant

    # -- refusals -----------------------------------------------------------

    def call(self, what: str, geoid: str, thunk) -> Optional[Any]:
        """Run one node call, turning an entitled refusal into a logged ``None``.

        Re-raises anything the node did not explain, so the runtime retries it.
        """
        try:
            return thunk()
        except GrantRequired as exc:
            logger.info(
                "terrapipe-os %s for %s needs a field grant we do not hold: %s", what, geoid, exc
            )
            return None
        except NoDataHere as exc:
            logger.info("terrapipe-os has no %s for %s: %s", what, geoid, exc)
            return None
        except TerrapipeOSError as exc:
            if exc.reason in ("geoid_not_found", "layer_not_found", "regime_mismatch"):
                logger.warning("terrapipe-os refused %s for %s: %s", what, geoid, exc)
                return None
            raise

    def sirup_to_bite(
        self, sirup: Dict[str, Any], geoid: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        bite = create_bite_from_sirup(sirup, sirup["sirup_type"], self.bite_tags())
        if geoid:
            bite["Header"]["geoid"] = geoid
        return bite

    def bite_tags(self) -> list:
        return ["terrapipe-os", "open-science"]


def envelope(
    geoid: str,
    vendor: str,
    sirup_type_value: str,
    data: Dict[str, Any],
    metadata: Dict[str, Any],
    units: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """The SIRUP envelope the runtime expects, around a terrapipe-os answer."""
    return {
        "sirup_type": sirup_type_value,
        "vendor": vendor,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "geoid": geoid,
        "data": data,
        "metadata": metadata,
        "units": units or {},
    }
