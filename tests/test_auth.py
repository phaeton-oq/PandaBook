from fastapi.testclient import TestClient

from app.main import app

_PROFILE = {
    "sex": "male",
    "age": 25,
    "weight_kg": 75,
    "height_cm": 180,
    "activity": "moderate",
    "goal": "maintain",
    "prefs": {},
}


def test_register_login_wrong_password():
    with TestClient(app) as client:
        email = "auth-test@panda.test"
        reg = client.post(
            "/api/auth/register",
            json={"email": email, "password": "securepass1", "name": "T", "profile": _PROFILE},
        )
        assert reg.status_code == 201
        bad = client.post("/api/auth/login", json={"email": email, "password": "wrongpass1"})
        assert bad.status_code == 401
        ok = client.post("/api/auth/login", json={"email": email, "password": "securepass1"})
        assert ok.status_code == 200
        token = ok.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == email


def test_short_password_rejected():
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/register",
            json={"email": "short@panda.test", "password": "123", "name": "", "profile": _PROFILE},
        )
        assert r.status_code == 422
