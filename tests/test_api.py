import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.exceptions import AIServiceError, StorageError
from app.main import app
from app.repositories import seo_results
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
    assert data["language"] == "en"
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
    assert data["language"] == "en"
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


@patch("app.services.seo_generator.save_result")
@patch("app.services.seo_generator.request_ai_content")
def test_generate_content_in_ukrainian(mock_request_ai_content, mock_save_result):
    mock_request_ai_content.return_value = {
        "title": "CRM система для бізнесу: повний гід",
        "meta_description": "Дізнайтеся, як CRM система допомагає бізнесу покращити продажі, комунікацію з клієнтами та автоматизацію процесів.",
        "outline": [
            "Що таке CRM система?",
            "Основні переваги CRM для бізнесу",
            "Як обрати CRM систему",
            "Поширені помилки під час впровадження CRM",
        ],
    }

    response = client.post("/generate", json={"keyword": "crm система", "language": "uk"})

    assert response.status_code == 200

    data = response.json()

    assert data["keyword"] == "crm система"
    assert data["language"] == "uk"
    assert data["title"] == "CRM система для бізнесу: повний гід"
    assert data["used_fallback"] is False

    mock_save_result.assert_called_once()


def test_save_result_handles_empty_results_file(tmp_path, monkeypatch):
    results_file = tmp_path / "results.json"
    results_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("RESULTS_FILE", str(results_file))

    payload = {
        "keyword": "crm software",
        "language": "en",
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

    seo_results.save_result(payload)

    saved_data = json.loads(results_file.read_text(encoding="utf-8"))

    assert saved_data == [payload]


def test_validate_ai_payload_normalizes_text():
    payload = {
        "title": '  "CRM Software for Small Business"  ',
        "meta_description": "  Discover the best CRM software for small business teams and improve sales workflows today.  ",
        "outline": [
            "  What is CRM software?  ",
            "Key benefits for small teams",
            "How to choose the right CRM",
            "Common CRM mistakes to avoid",
        ],
    }

    result = seo_generator.validate_ai_payload("crm software", "en", payload)

    assert result["used_fallback"] is False
    assert result["language"] == "en"
    assert result["title"] == "CRM Software for Small Business"
    assert result["outline"][0] == "What is CRM software?"


def test_validate_ai_payload_requires_exactly_four_outline_items():
    payload = {
        "title": "CRM Software Guide",
        "meta_description": "Learn how CRM software supports sales teams and improves customer management.",
        "outline": [
            "What is CRM software?",
            "Key benefits of CRM software",
            "How to choose CRM software",
        ],
    }

    result = seo_generator.validate_ai_payload("crm software", "en", payload)

    assert result["used_fallback"] is True


def test_build_fallback_response_in_ukrainian():
    result = seo_generator.build_fallback_response("crm система", "uk")

    assert result["language"] == "uk"
    assert result["used_fallback"] is True
    assert "повний SEO-гід" in result["title"]
    assert result["outline"][0] == "Що таке crm система?"


def test_extract_json_payload_handles_code_fences():
    content = """```json
{
  "title": "CRM Software Guide",
  "meta_description": "Learn how CRM software improves sales and customer management.",
  "outline": [
    "What is CRM software?",
    "Key benefits of CRM software",
    "How to choose CRM software",
    "Common CRM mistakes"
  ]
}
```"""

    result = seo_generator.extract_json_payload(content)

    assert result["title"] == "CRM Software Guide"


def test_extract_json_payload_handles_extra_text():
    content = """
Here is the JSON result:
{
  "title": "CRM Software Guide",
  "meta_description": "Learn how CRM software improves sales and customer management.",
  "outline": [
    "What is CRM software?",
    "Key benefits of CRM software",
    "How to choose CRM software",
    "Common CRM mistakes"
  ]
}
"""

    result = seo_generator.extract_json_payload(content)

    assert result["outline"][1] == "Key benefits of CRM software"


def test_request_ai_content_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        seo_generator.request_ai_content("crm software", "en")
    except AIServiceError as error:
        assert "OPENAI_API_KEY is not configured" in str(error)
    else:
        raise AssertionError("AIServiceError was not raised when API key is missing")
