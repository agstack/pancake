"""Deforestation (EUDR) adapter: one GeoID, one screen, one BITE.

This is what replaces a WHISP call in the Pancake pipeline. The differences
that matter are not in the interface, they are in what the answer admits:

- **It runs on public data mirrored locally.** JRC TMF for the verdict, the
  Honduran forestry authority's own maps for a second opinion and the
  commodity check. No Earth Engine account, no FAO credentials, no per-request
  call to a third party that may be down or rate-limited on the day a shipment
  needs clearing.
- **It carries its coverage.** Every screen says what share of the field was
  actually read. A clean verdict over 12% of a field is not a clean field, and
  the BITE says which one it is.
- **Absence is named.** A layer that is not mirrored here, a field outside a
  national map's country, a store not yet ingested -- each is a distinct
  reason in the evidence, never a zero.
- **Scope is explicit.** Without a field-access grant the node screens the
  neighbourhood cell around the field, not the field. That answer is useful
  and it is labelled ``neighbourhood``; a verdict about the field itself
  requires a grant, which Pancake is the party that issues.

The verdict is copied, never recomputed. Pancake's job here is to carry the
node's finding with its evidence intact into a BITE that a buyer can audit;
a second opinion computed in the connector would be a third number nobody
asked for.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pancake_services.tap.adapter_base import SIRUPType
from pancake_services.tap.adapters.terrapipe_os.base import (
    VENDOR_DEFAULT,
    TerrapipeOSAdapter,
    envelope,
)

VERDICTS = ("deforestation_detected", "no_deforestation_detected", "inconclusive")


def all_evidence(screen: Dict[str, Any]) -> list:
    """Every layer reading in a screen, flattened the way the node groups them.

    The node reports the primary layer on its own, the national second opinion
    and the commodity check each inside their own block, and the context
    layers in a list. Flattening here mirrors ``DeforestationScreen.evidence``
    so that "which layers were consulted" has one answer on both sides.
    """
    primary = screen.get("primary")
    items = [primary] if isinstance(primary, dict) else []
    for block in ("second_opinion", "commodity"):
        section = screen.get(block)
        if isinstance(section, dict):
            items.extend(e for e in section.get("evidence", []) if isinstance(e, dict))
    items.extend(e for e in (screen.get("context") or []) if isinstance(e, dict))
    return items


class DeforestationAdapter(TerrapipeOSAdapter):
    """Emits a ``land_use_screen`` SIRUP from ``GET /screen/{geoid}``."""

    def get_vendor_data(self, geoid: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        grant = self.grant_for(geoid, params)
        screen = self.call("screen", geoid, lambda: self.client.screen(geoid, grant=grant))
        if screen is None:
            return None
        return {"_geoid": geoid, "_grant_presented": bool(grant), "screen": screen}

    def transform_to_sirup(
        self, vendor_data: Dict[str, Any], sirup_type: SIRUPType
    ) -> Optional[Dict[str, Any]]:
        screen = vendor_data["screen"]
        verdict = screen.get("verdict")
        if verdict not in VERDICTS:
            # An unrecognised verdict means the node and this adapter disagree
            # about the vocabulary. Storing it would put a word into a
            # compliance record that nothing downstream knows how to read.
            return None

        scope = screen.get("scope")
        # The screen's body is carried through as the node wrote it. Restating
        # it in this adapter's own shape would mean two definitions of a
        # compliance record, and the one downstream reads would be the copy.
        data = {
            key: screen.get(key)
            for key in (
                "verdict",
                "scope",
                "cover_tier",
                "cutoff_year",
                "deforested_fraction",
                "deforested_by_year",
                "coverage_fraction",
                "coverage_threshold",
                "primary",
                "second_opinion",
                "commodity",
                "context",
                "caveats",
            )
        }
        evidence = all_evidence(screen)
        metadata = {
            "source": "terrapipe-os deforestation screen",
            "node": self.client.base_url,
            "scope": scope,
            "grant_presented": vendor_data["_grant_presented"],
            "field_scoped": scope == "field",
            "layers_consulted": [e.get("layer_id") for e in evidence],
            "layers_absent": {
                e.get("layer_id"): e.get("absent") for e in evidence if e.get("absent")
            },
            "provenance": screen.get("provenance") or {},
        }
        return envelope(
            geoid=vendor_data["_geoid"],
            vendor=self.vendor_name or VENDOR_DEFAULT,
            sirup_type_value=sirup_type.value,
            data=data,
            metadata=metadata,
            units={
                "deforested_fraction": "fraction_of_screened_area",
                "coverage_fraction": "fraction_of_screened_area",
            },
        )

    def bite_tags(self) -> list:
        return ["terrapipe-os", "open-science", "deforestation", "eudr"]
