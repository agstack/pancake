"""Grant-gated weather BITE reads (WS1): X-Field-Grant enforcement when enabled."""
import hashlib
import json

from fastapi.testclient import TestClient

from pancake_services.store.bites import BiteStore

GEOID = "3f1a9f0f36e44c0cb1ad4c2f8e3a7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f"
OTHER_GEOID = "7d6b1c5e9d8f7a6b5c4d3e2f1a0b9c8d7e6f3f1a9f0f36e44c0cb1ad4c2f8e3a"


def _weather_bite(geoid=GEOID, bite_id="01WEATHER00000000000000001"):
    header = {
        "id": bite_id, "geoid": geoid, "timestamp": "2026-07-07T12:00:00+00:00",
        "type": "weather_historical", "source": {"pipeline": "TAP", "vendor": "seed"},
    }
    body = {"sirup_data": {"series": {"air_temperature": [20.0]}}, "metadata": {}, "units": {}}
    digest = hashlib.sha256(
        (json.dumps(header, sort_keys=True) + json.dumps(body, sort_keys=True)).encode()
    ).hexdigest()
    return {"Header": header, "Body": body, "Footer": {"hash": digest, "tags": ["seed"]}}


def _headers(fake_hub, account="acct-owner"):
    return {"Authorization": f"Bearer {fake_hub.token(account, email='o@x.org')}"}


def _issue_owner_grant(client, headers, geoids, account="acct-owner"):
    fl = client.post("/fieldlists", json={"name": "Demo", "geoids": geoids}, headers=headers)
    assert fl.status_code == 201, fl.text
    list_id = fl.json()["list_id"]
    issued = client.post(
        "/grants/issue",
        json={"list_id": list_id, "grantee_account": account, "purpose": "owner",
              "validity_days": 30},
        headers=headers,
    )
    assert issued.status_code == 201, issued.text
    return issued.json()["credential"]


def test_gating_off_by_default(client, app, owner_headers):
    BiteStore(app.state.session_factory).save(_weather_bite())
    resp = client.get("/bites", params={"geoid": GEOID, "type": "weather_historical"},
                      headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_weather_read_blocked_without_grant(make_app, fake_hub):
    app = make_app(require_grant_for_weather=True)
    client = TestClient(app)
    BiteStore(app.state.session_factory).save(_weather_bite())
    resp = client.get("/bites", params={"geoid": GEOID, "type": "weather_historical"},
                      headers=_headers(fake_hub))
    assert resp.status_code == 401  # missing X-Field-Grant


def test_weather_read_requires_geoid_when_gated(make_app, fake_hub):
    app = make_app(require_grant_for_weather=True)
    client = TestClient(app)
    resp = client.get("/bites", params={"type": "weather_historical"}, headers=_headers(fake_hub))
    assert resp.status_code == 400


def test_weather_read_allowed_with_valid_grant(make_app, fake_hub):
    app = make_app(require_grant_for_weather=True)
    client = TestClient(app)
    headers = _headers(fake_hub)
    credential = _issue_owner_grant(client, headers, [GEOID, OTHER_GEOID])
    BiteStore(app.state.session_factory).save(_weather_bite())

    resp = client.get(
        "/bites", params={"geoid": GEOID, "type": "weather_historical"},
        headers={**headers, "X-Field-Grant": credential},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 1


def test_grant_for_other_field_rejected(make_app, fake_hub):
    app = make_app(require_grant_for_weather=True)
    client = TestClient(app)
    headers = _headers(fake_hub)
    # Grant covers OTHER_GEOID only; requesting GEOID must be refused.
    credential = _issue_owner_grant(client, headers, [OTHER_GEOID])
    BiteStore(app.state.session_factory).save(_weather_bite(geoid=GEOID))

    resp = client.get(
        "/bites", params={"geoid": GEOID, "type": "weather_historical"},
        headers={**headers, "X-Field-Grant": credential},
    )
    assert resp.status_code == 403


def test_non_weather_reads_never_gated(make_app, fake_hub):
    app = make_app(require_grant_for_weather=True)
    client = TestClient(app)
    # A non-weather BITE type is unaffected by weather grant-gating.
    resp = client.get("/bites", params={"geoid": GEOID, "type": "soil_profile"},
                      headers=_headers(fake_hub))
    assert resp.status_code == 200
