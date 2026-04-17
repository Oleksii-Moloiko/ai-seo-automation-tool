
from fastapi import FastAPI

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