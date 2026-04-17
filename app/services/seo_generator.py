import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

RESULTS_FILE = "data/results.json"


def save_result(data: dict) -> None:
    os.makedirs("data", exist_ok=True)

    with open(RESULTS_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(data, ensure_ascii=False) + "\n")


def build_fallback_response(keyword: str) -> dict:
    normalized = keyword.strip().capitalize()

    return {
        "keyword": keyword,
        "title": f"{normalized}: Complete SEO Guide",
        "meta_description": f"Learn everything about {keyword} in this SEO-friendly guide, including benefits, use cases, and best practices.",
        "outline": [
            f"What is {keyword}?",
            f"Key benefits of {keyword}",
            f"How to use {keyword} effectively",
            f"Common mistakes to avoid with {keyword}",
        ],
        "used_fallback": True,
    }


def parse_ai_output(keyword: str, content: str) -> dict:
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    title = ""
    meta_description = ""
    outline = []

    for line in lines:
        lower_line = line.lower()

        if lower_line.startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif lower_line.startswith("meta description:"):
            meta_description = line.split(":", 1)[1].strip()
        elif line[0].isdigit() and "." in line:
            outline.append(line.split(".", 1)[1].strip())

    if not title or not meta_description or not outline:
        return build_fallback_response(keyword)

    return {
        "keyword": keyword,
        "title": title,
        "meta_description": meta_description,
        "outline": outline,
        "used_fallback": False,
    }


def generate_seo_content(keyword: str) -> dict:
    try:
        prompt = f"""
Generate SEO content for the keyword: "{keyword}".

Return exactly in this format:

Title: ...
Meta Description: ...
Outline:
1. ...
2. ...
3. ...
4. ...
"""

        response = client.responses.create(
            model="gpt-5.4",
            input=prompt
        )

        content = response.output_text
        result = parse_ai_output(keyword, content)

    except Exception:
        result = build_fallback_response(keyword)

    save_result(result)
    return result