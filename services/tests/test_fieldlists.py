"""FieldList endpoints: idempotent creation, owner scoping, proofs."""
from pancake_services.grants.merkle import merkle_root, verify_inclusion


def test_create_returns_merkle_listid(client, owner_headers, geoids):
    response = client.post(
        "/fieldlists", json={"name": "Finca A", "geoids": geoids}, headers=owner_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["list_id"] == merkle_root(geoids)
    assert body["geoids"] == sorted(set(geoids))


def test_create_is_idempotent(client, owner_headers, geoids):
    first = client.post(
        "/fieldlists", json={"name": "Finca A", "geoids": geoids}, headers=owner_headers
    )
    again = client.post(
        "/fieldlists",
        json={"name": "Renamed", "geoids": list(reversed(geoids))},
        headers=owner_headers,
    )
    assert first.json()["list_id"] == again.json()["list_id"]
    listing = client.get("/fieldlists", headers=owner_headers).json()
    assert len(listing) == 1


def test_requires_auth(client, geoids):
    assert client.post("/fieldlists", json={"name": "x", "geoids": geoids}).status_code == 401
    assert client.get("/fieldlists").status_code == 401


def test_empty_geoids_rejected(client, owner_headers):
    response = client.post(
        "/fieldlists", json={"name": "empty", "geoids": []}, headers=owner_headers
    )
    assert response.status_code == 422


def test_owner_scoping(client, owner_headers, buyer_headers, fieldlist):
    list_id = fieldlist["list_id"]
    assert client.get(f"/fieldlists/{list_id}", headers=owner_headers).status_code == 200
    # Another account cannot see it -- and gets 404, not 403.
    assert client.get(f"/fieldlists/{list_id}", headers=buyer_headers).status_code == 404
    assert client.get("/fieldlists", headers=buyer_headers).json() == []


def test_inclusion_proof_endpoint(client, owner_headers, fieldlist, geoids):
    list_id = fieldlist["list_id"]
    response = client.get(f"/fieldlists/{list_id}/proof/{geoids[0]}", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert verify_inclusion(body["geoid"], body["proof"], body["list_id"])


def test_proof_for_nonmember_404(client, owner_headers, fieldlist):
    list_id = fieldlist["list_id"]
    response = client.get(f"/fieldlists/{list_id}/proof/unknown-geoid", headers=owner_headers)
    assert response.status_code == 404
