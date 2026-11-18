# AI SEO Automation Tool

Two ways to get validated on-page SEO for your content:

1. **`skill/` — SEO Pre-Publish Check.** An agent skill for Claude Code, Cursor, Codex CLI and similar. Audits a draft, scores it 0–100 with a deterministic Python validator, and returns severity-ranked findings with ready-to-paste fixes. Also generates validated title/meta/outline packs, single or in batch from CSV. Published on Agensi: https://agensi.io/skills/seo-pre-publish-check-score-fix-your-draft-before-it-goes-live
2. **`app/` — FastAPI service.** A self-hosted HTTP API that generates an SEO title, meta description and outline from a keyword via OpenAI, with template fallback and JSON storage.

Both support English and Ukrainian.

---

## SEO Pre-Publish Check (agent skill)

### What it does

| Mode | Input | Output |
|---|---|---|
| **audit** | Markdown, HTML or plain-text draft + primary keyword | Score, grade, findings by severity, replacement title/meta/headings |
| **generate** | Keyword (+ optional audience, intent, brand) | 3 scored titles, 2 scored metas, 4–6 item H2 outline |
| **batch** | CSV with `keyword,language` | `seo_pack_results.csv` with one validated pack per row |

The validator (`skill/scripts/seo_check.py`) is standard-library Python with no network access. It measures:

- title and meta description width in **pixels**, not characters (Google truncates at ~600 px / ~920 px)
- keyword in title, meta, H1 and the first 100 words; keyword density
- one H1, at least 3 H2s, no skipped heading levels, no generic or duplicate headings
- word count, average sentence length, oversized paragraphs
- internal and external links, image alt text, secondary keywords
- Cyrillic share for Ukrainian content

Keyword matching is inflection-aware, so «SEO оптимізацію сайту» counts for the keyword «SEO оптимізація сайту».

### Use it with your agent

Load the skill from Agensi (link above), or point your agent at the `skill/` folder, then ask:

```
Run an SEO pre-publish check on draft.md for the keyword "ai seo tools"
```

### Run the validator directly

```bash
# audit a draft
python3 skill/scripts/seo_check.py audit \
  --file skill/examples/sample_draft.md \
  --keyword "ai seo tools" --language en --json seo_report.json

# score generated candidates
python3 skill/scripts/seo_check.py validate seo_candidates.json --json seo_validation.json

# batch export
python3 skill/scripts/seo_check.py export seo_validation.json --csv seo_pack_results.csv
```

Exit code is `0` when every check passes, `1` when any check fails, `2` on input errors. See `skill/examples/output.json` for a full report and `skill/references/seo_rules.md` for thresholds and scoring weights.

---

## FastAPI service (self-hosted API)

### Endpoints

```
GET  /          service status message
GET  /health    {"status": "ok"}
POST /generate  SEO content for a keyword
```

Example request:

```json
{ "keyword": "crm software", "language": "en" }
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

`language` accepts `en` or `uk`. `used_fallback` is `true` when the OpenAI call was unavailable and the template response was returned instead.

### How it works

1. A keyword is posted to `/generate`.
2. The service asks OpenAI for a title, meta description and 4-item outline, then validates the payload.
3. If the API key is missing, the call fails, or the payload is malformed, a template fallback is returned.
4. The result is appended to `data/results.json` and returned as JSON.

### Installation

```bash
git clone https://github.com/Oleksii-Moloiko/ai-seo-automation-tool.git
cd ai-seo-automation-tool
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.4          # optional
RESULTS_FILE=data/results.json # optional
```

Run:

```bash
python3 -m uvicorn app.main:app --reload
# Swagger UI: http://127.0.0.1:8000/docs
```

### Tests

```bash
python3 -m pytest -v
```

---

## Project structure

```
ai-seo-automation-tool/
├── skill/                      # agent skill (published on Agensi)
│   ├── SKILL.md                # instructions for the agent
│   ├── scripts/seo_check.py    # deterministic validator
│   ├── references/seo_rules.md # thresholds, weights, language notes
│   └── examples/               # sample draft, CSV input, JSON report
├── app/                        # FastAPI service
│   ├── main.py
│   ├── config.py
│   ├── exceptions.py
│   ├── schemas/seo.py
│   ├── services/seo_generator.py
│   └── repositories/seo_results.py
├── tests/test_api.py
├── data/results.json           # created at runtime, git-ignored
├── requirements.txt
└── README.md
```

## Tech stack

Python 3.11, FastAPI, Pydantic, OpenAI Python SDK, Uvicorn, python-dotenv, pytest. The skill's validator has no dependencies beyond the standard library (Python 3.9+).

## Roadmap

- More languages in the skill's language-specific checks
- Real font metrics for pixel widths
- Batch keyword processing in the API
- Docker support

## Support

Open an issue: https://github.com/Oleksii-Moloiko/ai-seo-automation-tool/issues
