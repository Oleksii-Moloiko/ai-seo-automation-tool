def generate_seo_content(keyword: str) -> dict:
    return {
        "keyword": keyword,
        "title": f"Best {keyword.title()} Guide",
        "meta_description": f"Discover everything you need to know about {keyword} in this practical SEO guide.",
        "outline": [
            f"What is {keyword}?",
            f"Benefits of {keyword}",
            f"How to choose the best {keyword}",
            f"Common mistakes when using {keyword}",
        ],
    }