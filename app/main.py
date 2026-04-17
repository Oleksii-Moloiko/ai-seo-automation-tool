from fastapi import FastAPI

from app.schemas.seo import KeywordRequest
from app.services.seo_generator import generate_seo_content

app = FastAPI(
    title="AI SEO Automation Tool",
    description="API for generating SEO content from keywords using AI",
    version="1.0.0"
)


@app.get("/")
def root():
    return {"message": "AI SEO Automation Tool is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/generate")
def generate_content(request: KeywordRequest):
    result = generate_seo_content(request.keyword)
    return result