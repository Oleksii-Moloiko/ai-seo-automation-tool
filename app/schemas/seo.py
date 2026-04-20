from typing import Literal

from pydantic import BaseModel, Field


class KeywordRequest(BaseModel):
    keyword: str = Field(..., min_length=3, max_length=200, description="SEO keyword")
    language: Literal["en", "uk"] = Field(default="en", description="Response language")


class SEOResponse(BaseModel):
    keyword: str
    language: Literal["en", "uk"]
    title: str
    meta_description: str
    outline: list[str]
    used_fallback: bool
