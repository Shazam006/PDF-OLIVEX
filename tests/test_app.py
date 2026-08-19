from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "4.2"


def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "PDF OLIVEX" in response.text


def test_capabilities():
    response = client.get("/api/system/capabilities")
    assert response.status_code == 200
    payload = response.json()
    for key in ("libreoffice", "tesseract", "ocrmypdf", "ghostscript", "verapdf"):
        assert key in payload
