from fastapi.testclient import TestClient

from src.app.main import app


def test_security_headers_present():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    # Common security headers
    assert "Content-Security-Policy" in r.headers
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Referrer-Policy") == "same-origin"
