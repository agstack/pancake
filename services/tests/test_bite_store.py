"""BITE store: write-read round trips, dedupe by content hash, query API."""
from datetime import datetime, timezone

import pytest

from pancake_services.store.bites import BiteStore


def make_bite(geoid="geo-1", bite_type="weather_forecast", vendor="dummy",
              timestamp="2026-07-07T12:00:00+00:00", value=21.5, bite_id="01BITE0000000000000000001"):
    import hashlib
    import json

    header = {
        "id": bite_id,
        "geoid": geoid,
        "timestamp": timestamp,
        "type": bite_type,
        "source": {"pipeline": "TAP", "vendor": vendor},
    }
    body = {"sirup_data": {"value": value}, "metadata": {}, "units": {"value": "°C"}}
    digest = hashlib.sha256(
        (json.dumps(header, sort_keys=True) + json.dumps(body, sort_keys=True)).encode()
    ).hexdigest()
    return {"Header": header, "Body": body, "Footer": {"hash": digest, "tags": []}}


@pytest.fixture()
def store(app):
    return BiteStore(app.state.session_factory)


def test_write_read_roundtrip(store):
    bite = make_bite()
    assert store.save(bite) is True
    # Immediate read-back verification (write-read round-trip rule).
    fetched = store.get_by_hash(bite["Footer"]["hash"])
    assert fetched is not None
    assert fetched.envelope == bite
    assert fetched.geoid == "geo-1"
    assert fetched.vendor == "dummy"


def test_duplicate_content_stored_once(store):
    bite = make_bite()
    assert store.save(bite) is True
    assert store.save(bite) is False
    assert len(store.query(geoid="geo-1")) == 1


def test_invalid_envelope_rejected(store):
    with pytest.raises(ValueError, match="Header missing"):
        store.save({"Header": {"id": "x"}, "Footer": {"hash": "h"}})
    with pytest.raises(ValueError, match="Footer missing"):
        store.save({
            "Header": {"id": "x", "geoid": "g", "timestamp": "2026-01-01T00:00:00Z", "type": "t"},
            "Footer": {},
        })


def test_query_filters(store):
    store.save(make_bite(geoid="geo-1", bite_type="weather_forecast", value=1))
    store.save(make_bite(geoid="geo-1", bite_type="satellite_imagery", vendor="terrapipe", value=2))
    store.save(make_bite(geoid="geo-2", bite_type="weather_forecast", value=3))

    assert len(store.query()) == 3
    assert len(store.query(geoid="geo-1")) == 2
    assert len(store.query(geoid="geo-1", bite_type="weather_forecast")) == 1
    assert len(store.query(vendor="terrapipe")) == 1
    assert store.query(geoid="nope") == []


def test_query_time_range(store):
    store.save(make_bite(timestamp="2026-07-01T00:00:00+00:00", value=1))
    store.save(make_bite(timestamp="2026-07-05T00:00:00+00:00", value=2))
    store.save(make_bite(timestamp="2026-07-09T00:00:00+00:00", value=3))

    middle = store.query(
        since=datetime(2026, 7, 3, tzinfo=timezone.utc),
        until=datetime(2026, 7, 7, tzinfo=timezone.utc),
    )
    assert len(middle) == 1
    assert middle[0].envelope["Body"]["sirup_data"]["value"] == 2


def test_query_pagination_ordering(store):
    for day in (1, 2, 3):
        store.save(make_bite(timestamp=f"2026-07-0{day}T00:00:00+00:00", value=day))
    newest_first = store.query(limit=2)
    assert [b.envelope["Body"]["sirup_data"]["value"] for b in newest_first] == [3, 2]
    page_two = store.query(limit=2, offset=2)
    assert [b.envelope["Body"]["sirup_data"]["value"] for b in page_two] == [1]


def test_bites_api_requires_auth(client):
    assert client.get("/bites").status_code == 401


def test_bites_api_query(client, app, owner_headers):
    BiteStore(app.state.session_factory).save(make_bite(geoid="geo-9"))
    response = client.get("/bites", params={"geoid": "geo-9"}, headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["bites"][0]["Header"]["geoid"] == "geo-9"


def test_tap_to_store_end_to_end(app):
    """The frozen ingest interface: TAP runtime -> BiteStore.save -> queryable."""
    from test_tap_runtime import make_factory, make_schedule

    from pancake_services.tap.runtime import TAPRuntime

    store = BiteStore(app.state.session_factory)
    runtime = TAPRuntime(make_factory(), store.save, sleep=lambda s: None)
    report = runtime.run_once(make_schedule())
    assert report.succeeded == 1
    stored = store.query(geoid="geo-1")
    assert len(stored) == 1
    assert stored[0].bite_type == "weather_forecast"
