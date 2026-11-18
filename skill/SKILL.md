---
name: seo-pre-publish-check
description: Score and fix an article, blog post, or landing page draft for on-page SEO before it goes live. Audits title, meta description, heading structure, keyword placement, density, readability, links, and image alt text, then returns a 0-100 score with severity-ranked findings and ready-to-paste fixes. Also generates validated SEO title, meta description, and H2 outline packs from a keyword or a CSV keyword list. English and Ukrainian. Use when the user asks to check, audit, score, optimize, or fix SEO of a draft, page, or article, or asks for SEO titles, meta descriptions, outlines, or bulk SEO metadata.
---

# SEO Pre-Publish Check

Check a draft the way an SEO editor would, with a deterministic validator instead of guesses.
Every score, pixel width, and count in your answer must come from `scripts/seo_check.py`. Never estimate them.

## Modes

| Mode | Trigger | What you return |
|---|---|---|
| **audit** (default) | User has a draft, page, URL content, or Markdown/HTML file | Score 0-100, findings by severity, fixes |
| **generate** | User has only a keyword and wants title/meta/outline | Validated content pack with scored candidates |
| **batch** | User gives a CSV of keywords | `seo_pack_results.csv` with one validated pack per row |

If the user gives a keyword *and* a draft, run **audit**. If no keyword is given for a draft, infer the primary keyword from the H1 and first paragraph, state your assumption in one line, and continue.

## Requirements

- Python 3.9 or newer. The script uses only the standard library.
- Permission to read the draft file and to write report and CSV files in the working directory.
- No API keys, no network access.

## Mode: audit

1. **Collect inputs.** Draft text (Markdown, HTML, or plain text), primary keyword, language (`en` or `uk`, default `en`). Optional: current title and meta description if they are not inside the file, target word count, secondary keywords.
   - If the draft was pasted in chat, save it to `seo_draft.md` first.
   - If the user gives a URL and you have web access, fetch the page and save its HTML to `seo_draft.html`. Without web access, ask for the text.
2. **Run the validator.**
   ```bash
   python3 scripts/seo_check.py audit --file seo_draft.md --keyword "primary keyword" --language en --json seo_report.json
   ```
   Add `--title "..."` and `--meta "..."` when they are not in the file. Add `--min-words 1200` when the user has a target length. Add `--secondary "kw1,kw2"` for secondary keywords.
3. **Read `seo_report.json`.** It contains `score`, `grade`, `stats`, and `checks` with `id`, `status` (`pass`, `warn`, `fail`), `severity` (`critical`, `high`, `medium`, `low`), `detail`, and `fix_hint`.
4. **Write the fixes.** For every `fail` and `warn`, produce the concrete replacement, following `references/seo_rules.md`:
   - New title and meta description candidates (3 titles, 2 metas). Validate them with the `validate` command below before showing them, and show only candidates whose own status is `PASS`.
   - Missing or weak headings: the exact H2/H3 text to add and where.
   - Keyword placement: the rewritten first paragraph.
   - Everything else: a one-line instruction the writer can apply.
5. **Re-run audit on the fixed draft** if you edited the file. Report both scores.

### Audit output format

```
## SEO Pre-Publish Check: <keyword>
Score: <score>/100 (<grade>)  ·  Words: <n>  ·  Language: <en|uk>

### Must fix (critical / high)
1. <check name> — <detail>
   Fix: <ready-to-paste replacement or exact instruction>

### Should fix (medium)
...

### Nice to have (low)
...

### Passed
<comma-separated list of passed check names>

### Replacement title and meta
Title (<px> px, <chars> chars): <text>
Meta (<px> px, <chars> chars): <text>
```

Keep severity order. Do not pad the list: if only two checks failed, list two. If the score is 90 or above with no critical findings, say the draft is ready to publish.

## Mode: generate

1. Collect keyword, language, and optional audience, intent, brand, tone.
2. Read `references/seo_rules.md`.
3. Draft 3 title candidates, 2 meta candidates, and a 4-6 item H2 outline. Vary the angle between candidates (how-to, list, question, benefit).
4. Write them to `seo_candidates.json`:
   ```json
   {"items": [{"keyword": "...", "language": "en", "titles": ["...", "...", "..."], "metas": ["...", "..."], "outline": ["...", "...", "...", "..."]}]}
   ```
5. Run:
   ```bash
   python3 scripts/seo_check.py validate seo_candidates.json --json seo_validation.json
   ```
6. If any candidate has `failures`, rewrite it and run the validator again. Repeat until every item is `PASS` or you have tried three times; in that case show the best candidates and name the remaining failures.
7. Return the pack:

```
## SEO Content Pack: <keyword> (<language>)
Search intent: <informational | commercial | transactional | navigational>

Title: <best title>  (<px> px · <chars> chars · score <n>)
Alternatives:
- <title 2>  (<px> px · score <n>)
- <title 3>  (<px> px · score <n>)

Meta description: <best meta>  (<px> px · <chars> chars · score <n>)
Alternative: <meta 2>  (<px> px · score <n>)

Outline:
1. H2 <heading>
   - H3 <optional subheading>
2. H2 ...

Validation: PASS · <n> checks
```

## Mode: batch

1. Read the CSV. Required column `keyword`; optional `language` (default `en`), `audience`, `intent`.
2. Generate candidates for every row exactly as in **generate**, all into one `seo_candidates.json`.
3. Run `validate` once on the whole file. Fix failing rows and re-run; do not skip rows silently.
4. Export:
   ```bash
   python3 scripts/seo_check.py export seo_validation.json --csv seo_pack_results.csv
   ```
   Columns: `keyword, language, title, title_px, meta_description, meta_px, outline, score, status, failures`.
5. Reply with a summary table (keyword, score, status) and the path to the CSV. Mention any row that still fails and why.

## Rules

- Never report a score, width, or pass/fail that the script did not produce. If the script errors, show the error and stop.
- Keep the user's facts, brand names, and claims. Do not invent statistics or features to make copy stronger.
- Keyword use must read naturally. If a check can only pass by stuffing the keyword, say so and prefer the natural version.
- For `uk`, write native Ukrainian, not translated English. Keep the keyword in the grammatical form users actually search.
- Do not edit the user's file unless they ask. Put rewrites in the answer or in a new file next to the original.

## Known limitations

- Pixel widths use an average-glyph-width model, not real font rendering. Treat them as ±5%.
- Readability checks are length-based heuristics and are not a substitute for an editor.
- The audit does not check rankings, backlinks, Core Web Vitals, or indexability. Use a site audit skill for those.
