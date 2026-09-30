from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_profile_me_returns_placeholder() -> None:
    resp = client.get("/profiles/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "placeholder"
    assert "display_name" in body
