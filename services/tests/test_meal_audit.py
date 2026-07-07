"""MEAL ledger persistence, signatures, chain verification, and the audit API."""
from sqlalchemy import select

from pancake_services.grants.models import MealPacket


def _issue(client, owner_headers, fieldlist, grantee="hub-acct-buyer"):
    return client.post(
        "/grants/issue",
        json={"list_id": fieldlist["list_id"], "grantee_account": grantee, "purpose": "p"},
        headers=owner_headers,
    ).json()


def test_events_logged_for_lifecycle(client, owner_headers, buyer_headers, fieldlist, geoids):
    issued = _issue(client, owner_headers, fieldlist)
    client.get("/grants/received", headers=buyer_headers)
    client.post("/grants/revoke", json={"jti": issued["jti"]}, headers=owner_headers)

    report = client.get(f"/audit/{geoids[0]}", headers=owner_headers).json()
    types = [e["event"]["event_type"] for e in report["events"]]
    assert types == ["fieldlist.created", "grant.issued", "grant.retrieved", "grant.revoked"]


def test_audit_by_member_geoid_not_just_listid(client, owner_headers, fieldlist, geoids):
    """Audit lookups work per member GeoID even though events index the ListID."""
    for geoid in geoids:
        report = client.get(f"/audit/{geoid}", headers=owner_headers).json()
        assert report["event_count"] >= 1


def test_audit_requires_auth(client, geoids):
    assert client.get(f"/audit/{geoids[0]}").status_code == 401


def test_packets_are_signed_and_chained(app, client, owner_headers, fieldlist):
    _issue(client, owner_headers, fieldlist)
    session = app.state.session_factory()
    try:
        packets = list(
            session.execute(select(MealPacket).order_by(MealPacket.sequence_number)).scalars()
        )
        assert len(packets) == 2  # fieldlist.created + grant.issued
        assert all(p.signature for p in packets)
        assert packets[0].previous_packet_hash is None
        assert packets[1].previous_packet_hash == packets[0].packet_hash
        assert packets[1].previous_packet_id == packets[0].packet_id
    finally:
        session.close()


def test_chain_verification_endpoint(client, owner_headers, fieldlist, geoids):
    _issue(client, owner_headers, fieldlist)
    report = client.get(f"/audit/{geoids[0]}/report", headers=owner_headers).json()
    assert report["all_chains_valid"] is True
    assert report["events_by_type"]["grant.issued"] == 1
    meal_id = report["events"][0]["meal_id"]

    verify = client.get(f"/audit/meals/{meal_id}/verify", headers=owner_headers).json()
    assert verify == {"valid": True, "packet_count": 2}


def test_tampered_payload_detected(app, client, owner_headers, fieldlist, geoids):
    """Write-then-tamper: chain verification must fail after payload mutation."""
    _issue(client, owner_headers, fieldlist)
    session = app.state.session_factory()
    try:
        packet = session.execute(
            select(MealPacket).where(MealPacket.sequence_number == 2)
        ).scalar_one()
        tampered = dict(packet.payload)
        tampered["grantee"] = "hub-acct-attacker"
        packet.payload = tampered
        session.commit()
        meal_id = packet.meal_id
    finally:
        session.close()

    report = client.get(f"/audit/{geoids[0]}/report", headers=owner_headers).json()
    assert report["all_chains_valid"] is False
    verify = client.get(f"/audit/meals/{meal_id}/verify", headers=owner_headers).json()
    assert verify["valid"] is False
    assert "content hash mismatch" in verify["error"]


def test_time_range_filter(client, owner_headers, fieldlist, geoids):
    _issue(client, owner_headers, fieldlist)
    all_events = client.get(f"/audit/{geoids[0]}", headers=owner_headers).json()
    future_only = client.get(
        f"/audit/{geoids[0]}", params={"from": "2099-01-01T00:00:00"}, headers=owner_headers
    ).json()
    assert all_events["event_count"] >= 2
    assert future_only["event_count"] == 0


def test_unknown_meal_verify_404(client, owner_headers):
    response = client.get("/audit/meals/01UNKNOWNMEAL000000000000/verify", headers=owner_headers)
    assert response.status_code == 404
