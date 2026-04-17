from fastapi import FastAPI, HTTPException

from app.exceptions import StorageError
from app.schemas.seo import KeywordRequest, SEOResponse
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


@app.post("/generate", response_model=SEOResponse)
def generate_content(request: KeywordRequest):
    try:
        result = generate_seo_content(request.keyword)
        return result
    except StorageError as error:
        raise HTTPException(status_code=500, detail=str(error))