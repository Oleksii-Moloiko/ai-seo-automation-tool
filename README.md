# AI SEO Automation Tool

## Overview

AI SEO Automation Tool is a FastAPI-based backend service that generates structured SEO content from a user-provided keyword.

The API accepts a keyword and optional language and returns:
- SEO title
- meta description
- article outline

The project also stores generated results in a local JSON file and includes fallback generation logic when the external AI provider is unavailable.

---

## Features

- Generate SEO content from a keyword
- Support English and Ukrainian responses
- Structured API response
- Fallback content generation when AI is unavailable
- Persistent JSON storage for generated results
- Request and response validation with Pydantic
- API testing with pytest

---

## Tech Stack

- Python 3.11
- FastAPI
- Pydantic
- OpenAI Python SDK
- pytest
- Uvicorn
- python-dotenv

---

## Project Structure

```bash
ai-seo-automation-tool/
├── app/
│   ├── main.py
│   ├── exceptions.py
│   ├── schemas/
│   │   └── seo.py
│   └── services/
│       └── seo_generator.py
├── data/
│   └── results.json
├── tests/
│   └── test_api.py
├── .env
├── .gitignore
├── README.md
└── requirements.txt
```

---

## How It Works
- User sends a keyword to the /generate endpoint
- The service attempts to generate SEO content via AI
- If AI is unavailable, fallback SEO content is generated
- The result is saved to data/results.json
- The API returns a structured JSON response

---

## API Endpoints
```
GET /
```
Returns a basic service status message.
```
GET /health
```
Returns service health status.

Example response:
```json
{
  "status": "ok"
}
```

```
POST /generate
```
Generates SEO content for a given keyword.

Example request:
```json
{
  "keyword": "crm software",
  "language": "en"
}
```
Example response:
```json
{
  "keyword": "crm software",
  "language": "en",
  "title": "Crm software: Complete SEO Guide",
  "meta_description": "Learn everything about crm software in this SEO-friendly guide, including benefits, use cases, and best practices.",
  "outline": [
    "What is crm software?",
    "Key benefits of crm software",
    "How to use crm software effectively",
    "Common mistakes to avoid with crm software"
  ],
  "used_fallback": true
}
```

Ukrainian example request:
```json
{
  "keyword": "crm система",
  "language": "uk"
}
```

---

## Installation

1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/ai-seo-automation-tool.git
cd ai-seo-automation-tool
```
2. Create and activate virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```
3. Install dependencies
```bash
pip install -r requirements.txt
```
4. Create .env
```bash
OPENAI_API_KEY=your_api_key_here
```
5. Run the server
```bash
python3.11 -m uvicorn app.main:app --reload
```
6. Open Swagger docs
```
http://127.0.0.1:8000/docs
```

---

## Running Tests
```bash
python3.11 -m pytest -v
```

---

## Error Handling

The project includes:

- custom exceptions for AI service failures
- custom exceptions for storage failures
- fallback response generation
- proper HTTP 500 handling for storage-related errors

---

## Future Improvements
- Add batch keyword processing
- Save results to Google Sheets
- Add Docker support
- Add logging
- Add prompt templates
- Add authentication
- Add database storage instead of local JSON

---

## Why This Project Matters

This project demonstrates:

- backend API design
- third-party AI integration
- request/response validation
- fallback handling
- persistent storage
- automated API testing

It is a good example of a practical automation service that could be useful for SEO teams and content operations.
