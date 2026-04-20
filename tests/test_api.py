import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.exceptions import AIServiceError, StorageError
from app.main import app
from app.services import seo_generator

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("app.services.seo_generator.save_result")
@patch("app.services.seo_generator.request_ai_content")
def test_generate_content_success(mock_request_ai_content, mock_save_result):
    mock_request_ai_content.return_value = {
        "title": "CRM Software: Complete Guide",
        "meta_description": "Learn how CRM software helps sales and marketing teams grow.",
        "outline": [
            "What is CRM software?",
            "Key benefits of CRM software",
            "How to choose CRM software",
            "Common CRM implementation mistakes",
        ],
    }

    response = client.post("/generate", json={"keyword": "crm software"})

    assert response.status_code == 200

    data = response.json()

    assert data["keyword"] == "crm software"
    assert data["title"] == "CRM Software: Complete Guide"
    assert data["used_fallback"] is False
    assert len(data["outline"]) == 4

    mock_save_result.assert_called_once()


@patch("app.services.seo_generator.save_result")
@patch("app.services.seo_generator.request_ai_content")
def test_generate_content_fallback(mock_request_ai_content, mock_save_result):
    mock_request_ai_content.side_effect = AIServiceError("AI generation is currently unavailable")

    response = client.post("/generate", json={"keyword": "crm software"})

    assert response.status_code == 200

    data = response.json()

    assert data["keyword"] == "crm software"
    assert data["used_fallback"] is True
    assert isinstance(data["outline"], list)

    mock_save_result.assert_called_once()


def test_generate_content_invalid_keyword():
    response = client.post("/generate", json={"keyword": "a"})

    assert response.status_code == 422


@patch("app.services.seo_generator.save_result")
@patch("app.services.seo_generator.request_ai_content")
def test_generate_content_storage_error(mock_request_ai_content, mock_save_result):
    mock_request_ai_content.return_value = {
        "title": "CRM Software: Complete Guide",
        "meta_description": "Learn how CRM software helps sales and marketing teams grow.",
        "outline": [
            "What is CRM software?",
            "Key benefits of CRM software",
            "How to choose CRM software",
            "Common CRM implementation mistakes",
        ],
    }
    mock_save_result.side_effect = StorageError("Failed to save SEO result")

    response = client.post("/generate", json={"keyword": "crm software"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to save SEO result"}


def test_save_result_handles_empty_results_file(tmp_path, monkeypatch):
    results_file = tmp_path / "results.json"
    results_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(seo_generator, "RESULTS_FILE", str(results_file))

    payload = {
        "keyword": "crm software",
        "title": "CRM Software: Complete Guide",
        "meta_description": "Learn how CRM software helps sales and marketing teams grow.",
        "outline": [
            "What is CRM software?",
            "Key benefits of CRM software",
            "How to choose CRM software",
            "Common CRM implementation mistakes",
        ],
        "used_fallback": False,
    }

    seo_generator.save_result(payload)

    saved_data = json.loads(results_file.read_text(encoding="utf-8"))

    assert saved_data == [payload]
