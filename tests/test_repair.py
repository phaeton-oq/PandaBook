from fastapi.testclient import TestClient

from app.main import app


def test_demo_user_login():
    with TestClient(app) as client:
        r = client.post("/api/auth/login", json={
            "email": "demo@pandabook.local",
            "password": "demo12345",
        })
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "demo@pandabook.local"
