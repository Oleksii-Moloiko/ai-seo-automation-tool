# SEO rules used by seo-pre-publish-check

The validator enforces the measurable rules. This file explains them and adds the judgement rules the agent applies while writing.

## Title

| Rule | Threshold | Why |
|---|---|---|
| Pixel width | 200-600 px (warn above 580) | Google desktop truncates titles around 600 px |
| Characters | 30-65 | Secondary guard for the width model |
| Keyword | present, ideally in the first half | Truncation keeps the start, users scan the start |
| One idea | no "\|" stacking of 3+ phrases | Stacked titles read as spam and lose clicks |
| Brand | optional suffix " \| Brand" only when the width allows | Brand adds trust but costs width |

Angles that work: how-to ("How to X in Y steps"), number list ("7 X that Y"), question ("What is X?"), benefit ("X: get Y without Z"), year freshness ("X in 2026") only when the content is actually updated.

## Meta description

| Rule | Threshold | Why |
|---|---|---|
| Pixel width | 400-920 px (warn above 900) | Google desktop truncates around 920 px |
| Characters | 70-160 | Secondary guard |
| Keyword | present once, naturally | Google bolds matching words in the snippet |
| Call to action or promise | present | A meta is an ad for the click, not a summary |
| No duplicate of the title | must differ | Duplicates waste the snippet |

## Headings

- Exactly one H1. It may differ from the title tag but must contain the keyword or a close variant.
- At least 3 H2 sections. 4-6 is the usual sweet spot for 800-1500 words.
- No level skipping (H2 followed by H4).
- No generic headings: Introduction, Overview, Conclusion, Summary, Final thoughts, Вступ, Огляд, Висновок, Висновки, Підсумок. Name the actual benefit or step instead.
- No duplicate headings.
- Each H2 should be answerable: a reader skimming only the H2s should get the article's argument.

## Keyword placement and density

- Primary keyword in the first 100 words.
- Density between 0.5% and 2.5% of words. Above 2.5% is stuffing; the validator fails it.
- Secondary keywords: each at least once, ideally in an H2 or H3.
- Prefer natural variants and synonyms over exact repeats.

## Length and readability

- Minimum 600 words for an informational article unless the user sets another target. Landing pages may be shorter; pass `--min-words 300`.
- Average sentence length under 25 words.
- Paragraphs under 120 words. Long walls of text fail on mobile.
- Lists and tables where the content is enumerable.

## Links and media

- At least one internal link and one external link to a credible source.
- Every image has descriptive alt text. Alt text is a sentence fragment that describes the image, not a keyword list.

## Language-specific notes

### Ukrainian (uk)

- Use the keyword in the case users search. Search queries are usually nominative singular or plural, but "як вибрати [знахідний]" patterns are common for how-to intent.
- Avoid calques from English: "найкращі практики" is acceptable but "вживайте" instead of "використовуйте" sounds formal; match the audience.
- Apostrophe is `'` (U+0027) or `ʼ` (U+02BC); the validator accepts both. Use «» quotes in body copy.
- The validator requires at least 50% Cyrillic letters in title, meta, and headings for `uk`.

### English (en)

- Sentence case or title case is fine, but be consistent across title and H2s.
- Avoid clickbait punctuation: no "!!!", no ALL CAPS words except acronyms.

## Scoring

Score starts at 100. Each failed check subtracts its weight; a warning subtracts half.

| Check | Severity | Weight |
|---|---|---|
| title_missing, meta_missing, h1_missing | critical | 20 |
| title_keyword, meta_keyword, keyword_in_intro | high | 12 |
| title_width, meta_width, h1_multiple, keyword_density_high | high | 10 |
| h2_count, heading_skip, word_count | medium | 8 |
| generic_headings, duplicate_headings, keyword_density_low | medium | 6 |
| sentence_length, paragraph_length, meta_equals_title | low | 4 |
| internal_links, external_links, image_alt, secondary_keywords, cyrillic_ratio | low | 3 |

Grades: A 90-100, B 75-89, C 60-74, D below 60. A draft with any critical finding cannot be graded above C regardless of score.
