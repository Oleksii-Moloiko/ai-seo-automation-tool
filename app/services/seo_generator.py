import json
import logging

from openai import OpenAI

from app.config import get_config
from app.exceptions import AIServiceError
from app.repositories.seo_results import save_result

logger = logging.getLogger(__name__)


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=get_config().openai_api_key)


def get_language_name(language: str) -> str:
    language_names = {
        "en": "English",
        "uk": "Ukrainian",
    }
    return language_names.get(language, "English")


def build_seo_prompt(keyword: str, language: str) -> str:
    language_name = get_language_name(language)

    return f"""
Generate high-quality SEO content for the keyword "{keyword}".
Write the response in {language_name}.

Return valid JSON with exactly these keys:
- title
- meta_description
- outline

SEO requirements:
- title must be clear, compelling, and include the keyword naturally
- title should be about 50 to 60 characters when possible
- meta_description must include the keyword naturally
- meta_description should be about 140 to 160 characters when possible
- outline must contain exactly 4 specific article sections
- each outline item should be actionable and reader-friendly
- avoid vague phrases like "Introduction" or "Conclusion"
- do not use markdown
- do not include any extra keys
- do not wrap the JSON in code fences
"""


def normalize_text(value: str) -> str:
    return " ".join(value.split()).strip(' "\'')


def extract_json_payload(content: str) -> dict:
    cleaned_content = content.strip()

    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content.strip("`")
        if cleaned_content.startswith("json"):
            cleaned_content = cleaned_content[4:].strip()

    try:
        return json.loads(cleaned_content)
    except json.JSONDecodeError:
        start = cleaned_content.find("{")
        end = cleaned_content.rfind("}")

        if start == -1 or end == -1 or start >= end:
            raise

        return json.loads(cleaned_content[start : end + 1])


def build_fallback_response(keyword: str, language: str) -> dict:
    normalized = keyword.strip().capitalize()

    if language == "uk":
        return {
            "keyword": keyword,
            "language": language,
            "title": f"{normalized}: повний SEO-гід",
            "meta_description": (
                f"Дізнайтеся все про {keyword} у цьому SEO-матеріалі: "
                "переваги, сценарії використання та найкращі практики."
            ),
            "outline": [
                f"Що таке {keyword}?",
                f"Основні переваги {keyword}",
                f"Як ефективно використовувати {keyword}",
                f"Типові помилки під час роботи з {keyword}",
            ],
            "used_fallback": True,
        }

    return {
        "keyword": keyword,
        "language": language,
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


def validate_ai_payload(keyword: str, language: str, payload: dict) -> dict:
    title = normalize_text(payload.get("title", ""))
    meta_description = normalize_text(payload.get("meta_description", ""))
    outline = payload.get("outline", [])

    if isinstance(outline, list):
        outline = [normalize_text(item) for item in outline if isinstance(item, str) and normalize_text(item)]

    if (
        not title
        or not meta_description
        or not isinstance(outline, list)
        or len(outline) != 4
        or not all(outline)
    ):
        return build_fallback_response(keyword, language)

    return {
        "keyword": keyword,
        "language": language,
        "title": title,
        "meta_description": meta_description,
        "outline": outline,
        "used_fallback": False,
    }


def request_ai_content(keyword: str, language: str) -> dict:
    try:
        config = get_config()
        if not config.openai_api_key:
            raise AIServiceError("OPENAI_API_KEY is not configured")

        client = get_openai_client()

        response = client.responses.create(
            model=config.openai_model,
            input=build_seo_prompt(keyword, language),
        )

        return extract_json_payload(response.output_text)

    except AIServiceError:
        raise

    except Exception as error:
        raise AIServiceError("AI generation is currently unavailable") from error


def generate_seo_content(keyword: str, language: str = "en") -> dict:
    try:
        payload = request_ai_content(keyword, language)
        result = validate_ai_payload(keyword, language, payload)
    except AIServiceError:
        logger.warning(
            "Falling back to template SEO response for keyword='%s' language='%s'",
            keyword,
            language,
            exc_info=True,
        )
        result = build_fallback_response(keyword, language)

    save_result(result)
    return result
