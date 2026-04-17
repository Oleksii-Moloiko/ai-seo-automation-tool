from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_content_success():
    response = client.post(
        "/generate",
        json={"keyword": "crm software"}
    )

    assert response.status_code == 200

    data = response.json()

    assert "keyword" in data
    assert "title" in data
    assert "meta_description" in data
    assert "outline" in data
    assert "used_fallback" in data

    assert data["keyword"] == "crm software"
    assert isinstance(data["title"], str)
    assert isinstance(data["meta_description"], str)
    assert isinstance(data["outline"], list)
    assert isinstance(data["used_fallback"], bool)


def test_generate_content_invalid_keyword():
    response = client.post(
        "/generate",
        json={"keyword": "a"}
    )

    assert response.status_code == 422