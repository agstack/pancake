"""The five minted test credentials must behave exactly as the manifest promises."""
import json

import pytest

from pancake_services.grants import sdjwt
from pancake_services.grants.statuslist import StatusList
from pancake_services.grants.testkit.mint_test_credentials import REVOKED_INDEX, mint_all


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    out = tmp_path_factory.mktemp("dev_keys")
    manifest = mint_all(out)
    return out, manifest


def _load(out, name):
    return (out / name).read_text()


def test_manifest_written(kit):
    out, manifest = kit
    on_disk = json.loads((out / "manifest.json").read_text())
    assert on_disk["list_id"] == manifest["list_id"]
    assert len(on_disk["credentials"]) == 5


def test_valid_credential_accepts(kit):
    out, manifest = kit
    pub = (out / "dev_issuer_public.pem").read_bytes()
    result = sdjwt.verify(_load(out, "valid.sdjwt"), pub)
    assert result.claims["sub"] == manifest["list_id"]
    assert sorted(result.disclosed_geoids) == sorted(manifest["geoids"])
    # And its status bit is clear.
    status = StatusList.decode(_load(out, "status_list.txt"))
    idx = result.claims["status"]["status_list"]["idx"]
    assert not status.is_revoked(idx)


def test_expired_credential_rejects(kit):
    out, _ = kit
    pub = (out / "dev_issuer_public.pem").read_bytes()
    with pytest.raises(sdjwt.VerificationError, match="expired"):
        sdjwt.verify(_load(out, "expired.sdjwt"), pub)


def test_revoked_credential_flagged_in_status_list(kit):
    out, _ = kit
    pub = (out / "dev_issuer_public.pem").read_bytes()
    # Signature and expiry are fine...
    result = sdjwt.verify(_load(out, "revoked.sdjwt"), pub)
    idx = result.claims["status"]["status_list"]["idx"]
    assert idx == REVOKED_INDEX
    # ...but the status list marks it revoked.
    status = StatusList.decode(_load(out, "status_list.txt"))
    assert status.is_revoked(idx)


def test_tampered_credential_rejects(kit):
    out, _ = kit
    pub = (out / "dev_issuer_public.pem").read_bytes()
    with pytest.raises(sdjwt.VerificationError, match="signature"):
        sdjwt.verify(_load(out, "tampered.sdjwt"), pub)


def test_wrong_geoid_credential_rejects(kit):
    out, _ = kit
    pub = (out / "dev_issuer_public.pem").read_bytes()
    with pytest.raises(sdjwt.VerificationError, match="not present in _sd"):
        sdjwt.verify(_load(out, "wrong_geoid.sdjwt"), pub)


def test_odrl_policy_embedded(kit):
    out, manifest = kit
    pub = (out / "dev_issuer_public.pem").read_bytes()
    result = sdjwt.verify(_load(out, "valid.sdjwt"), pub)
    odrl = result.claims["odrl"]
    assert odrl["@type"] == "Agreement"
    assert odrl["permission"][0]["target"] == f"urn:agstack:fieldlist:{manifest['list_id']}"
    assert odrl["permission"][0]["action"] == "read"
