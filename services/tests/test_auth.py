"""Hub-delegated auth: RS256 JWKS verification, token-type checks, user mirroring."""


def test_healthz_public(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["service"] == "pancake-grants"


def test_me_requires_token(client):
    assert client.get("/healthz/me").status_code == 401


def test_me_with_valid_token(client, owner_headers):
    response = client.get("/healthz/me", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["hub_account_id"] == "hub-acct-owner"
    assert body["email"] == "owner@x.org"


def test_user_created_on_first_seen(client, fake_hub):
    headers = {"Authorization": f"Bearer {fake_hub.token('hub-acct-new')}"}
    first = client.get("/healthz/me", headers=headers)
    second = client.get("/healthz/me", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["hub_account_id"] == "hub-acct-new"


def test_garbage_token_rejected(client):
    response = client.get("/healthz/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401


def test_expired_token_rejected(client, fake_hub):
    token = fake_hub.token("hub-acct-owner", exp_offset=-100)
    response = client.get("/healthz/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_non_access_token_rejected(client, fake_hub):
    token = fake_hub.token("hub-acct-owner", token_type="refresh")
    response = client.get("/healthz/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "not an access token" in response.json()["detail"]


def test_wrong_signer_rejected(client):
    import time

    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = pyjwt.encode(
        {"sub": "hub-acct-owner", "type": "access",
         "iat": int(time.time()), "exp": int(time.time()) + 3600},
        rogue, algorithm="RS256", headers={"kid": "hub-key-1"},
    )
    response = client.get("/healthz/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
