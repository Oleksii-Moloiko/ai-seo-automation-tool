from pydantic import BaseModel, Field


class KeywordRequest(BaseModel):
    keyword: str = Field(..., min_length=3, max_length=200, description="SEO keyword")


class SEOResponse(BaseModel):
    keyword: str
    title: str
    meta_description: str
    outline: list[str]
    used_fallback: bool