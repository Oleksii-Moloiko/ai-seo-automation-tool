import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.exceptions import AIServiceError, StorageError

load_dotenv()

RESULTS_FILE = "data/results.json"


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def save_result(data: dict) -> None:
    try:
        os.makedirs("data", exist_ok=True)

        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, "r", encoding="utf-8") as file:
                raw_content = file.read().strip()

            if not raw_content:
                existing_data = []
            else:
                existing_data = json.loads(raw_content)
        else:
            existing_data = []

        if not isinstance(existing_data, list):
            raise StorageError("Stored SEO results must be a JSON array")

        existing_data.append(data)

        with open(RESULTS_FILE, "w", encoding="utf-8") as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=2)
    except StorageError:
        raise
    except (OSError, json.JSONDecodeError) as error:
        raise StorageError("Failed to save SEO result") from error


def build_fallback_response(keyword: str) -> dict:
    normalized = keyword.strip().capitalize()

    return {
        "keyword": keyword,
        "title": f"{normalized}: Complete SEO Guide",
        "meta_description": (
            f"Learn everything about {keyword} in this SEO-friendly guide, "
            "including benefits, use cases, and best practices."
        ),
        "outline": [
            f"What is {keyword}?",
            f"Key benefits of {keyword}",
            f"How to use {keyword} effectively",
            f"Common mistakes to avoid with {keyword}",
        ],
        "used_fallback": True,
    }


def validate_ai_payload(keyword: str, payload: dict) -> dict:
    title = payload.get("title", "").strip()
    meta_description = payload.get("meta_description", "").strip()
    outline = payload.get("outline", [])

    if (
        not title
        or not meta_description
        or not isinstance(outline, list)
        or len(outline) == 0
        or not all(isinstance(item, str) and item.strip() for item in outline)
    ):
        return build_fallback_response(keyword)

    return {
        "keyword": keyword,
        "title": title,
        "meta_description": meta_description,
        "outline": outline,
        "used_fallback": False,
    }


def request_ai_content(keyword: str) -> dict:
    try:
        client = get_openai_client()

        prompt = f"""
Generate SEO content for the keyword "{keyword}".

Return valid JSON with exactly these keys:
- title
- meta_description
- outline

Rules:
- outline must be an array of 4 strings
- do not include markdown
- do not include any extra keys
"""

        response = client.responses.create(
            model="gpt-5.4",
            input=prompt,
        )

        return json.loads(response.output_text)

    except Exception as error:
        raise AIServiceError("AI generation is currently unavailable") from error


def generate_seo_content(keyword: str) -> dict:
    try:
        payload = request_ai_content(keyword)
        result = validate_ai_payload(keyword, payload)
    except AIServiceError:
        result = build_fallback_response(keyword)

    save_result(result)
    return result
