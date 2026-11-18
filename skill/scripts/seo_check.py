#!/usr/bin/env python3
"""seo_check.py - deterministic on-page SEO validator for the seo-pre-publish-check skill.

Commands
  audit     Score a Markdown/HTML/plain-text draft against a primary keyword.
  validate  Score generated title/meta/outline candidates from a JSON file.
  export    Turn a validate report into a CSV (batch mode).

Standard library only. Exit code 0 when everything passes, 1 when any check fails,
2 on usage or input errors.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from html.parser import HTMLParser

# --------------------------------------------------------------------------- #
# Thresholds (keep in sync with references/seo_rules.md)
# --------------------------------------------------------------------------- #

TITLE_PX_MIN, TITLE_PX_WARN, TITLE_PX_MAX = 200, 580, 600
TITLE_CHARS_MIN, TITLE_CHARS_MAX = 30, 65
META_PX_MIN, META_PX_WARN, META_PX_MAX = 400, 900, 920
META_CHARS_MIN, META_CHARS_MAX = 70, 160
H2_MIN = 3
OUTLINE_MIN, OUTLINE_MAX = 4, 6
INTRO_WORDS = 100
DENSITY_MIN, DENSITY_MAX = 0.5, 2.5
DEFAULT_MIN_WORDS = 600
SENTENCE_MAX_AVG = 25.0
PARAGRAPH_MAX_WORDS = 120
CYRILLIC_MIN_RATIO = 0.5

GENERIC_HEADINGS = {
    "introduction", "intro", "overview", "conclusion", "conclusions", "summary",
    "final thoughts", "wrap up", "wrap-up", "about",
    "вступ", "огляд", "висновок", "висновки", "підсумок", "підсумки", "резюме",
}

WEIGHTS = {
    "critical": 20,
    "high": 12,
    "medium": 8,
    "low": 4,
}

# Per-check overrides where the rules file deviates from the severity default.
CHECK_WEIGHTS = {
    "title_width": 10, "meta_width": 10, "h1_multiple": 10, "keyword_density_high": 10,
    "generic_headings": 6, "duplicate_headings": 6, "keyword_density_low": 6,
    "internal_links": 3, "external_links": 3, "image_alt": 3,
    "secondary_keywords": 3, "cyrillic_ratio": 3,
}

# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #

# Average glyph widths for a ~20px sans-serif title font. Google renders titles at
# 20px Arial on desktop; descriptions at 14px. We scale the 20px table for metas.
_NARROW = set("iljtfr.,:;'|!I ")
_WIDE = set("mwMW@")
_UPPER_EXTRA = 1.25  # uppercase letters other than I/M/W
_BASE_PX_TITLE = 9.6
_BASE_PX_META = 6.7


def pixel_width(text: str, kind: str = "title") -> int:
    base = _BASE_PX_TITLE if kind == "title" else _BASE_PX_META
    total = 0.0
    for ch in text:
        if ch in _NARROW:
            total += 0.5
        elif ch in _WIDE:
            total += 1.4
        elif ch.isupper():
            total += _UPPER_EXTRA
        elif ch.isdigit():
            total += 1.0
        else:
            total += 1.0
    return int(round(total * base))


def normalize(text: str) -> str:
    text = text.replace("ʼ", "'").replace("’", "'")
    return " ".join(text.split()).strip(" \"'")


def fold(text: str) -> str:
    return normalize(text).lower()


_WORD_RE = re.compile(r"[\w'ʼ’-]+", re.UNICODE)


def words(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(text) if any(c.isalnum() for c in w)]


def _stem(word: str) -> str:
    """Crude inflection-tolerant stem: keep the first len-2 letters of longer words.

    'оптимізація' / 'оптимізацію' -> 'оптимізац'; 'tools' / 'tool' -> 'tool'.
    """
    w = word.lower().replace("ʼ", "'").replace("’", "'")
    if len(w) <= 4:
        return w
    cut = 2 if len(w) >= 7 else 1
    return w[: len(w) - cut]


def _stems(text: str) -> list[str]:
    return [_stem(w) for w in words(text)]


def _stem_eq(t: str, k: str) -> bool:
    """Two stems match when equal, or when one extends the other and the shorter one
    is long enough to be meaningful (prevents 'a' matching 'ai')."""
    if t == k:
        return True
    if len(k) > 3 and t.startswith(k):
        return True
    return len(t) > 3 and k.startswith(t)


def keyword_matches(text: str, keyword: str) -> list[int]:
    """Word offsets where the keyword occurs, allowing inflected forms."""
    tw, kw = _stems(text), _stems(keyword)
    if not kw or len(kw) > len(tw):
        return []
    hits = []
    n = len(kw)
    for i in range(len(tw) - n + 1):
        if all(_stem_eq(tw[i + j], kw[j]) for j in range(n)):
            hits.append(i)
    return hits


def contains_keyword(text: str, keyword: str) -> bool:
    return bool(keyword_matches(text, keyword))


def contains_keyword_loose(text: str, keyword: str) -> bool:
    """Heading-friendly match: every keyword stem appears somewhere in the text, any order.

    'Чому сайт без SEO оптимізації' matches 'seo оптимізація сайту'.
    """
    if contains_keyword(text, keyword):
        return True
    tw, kw = _stems(text), _stems(keyword)
    if not kw:
        return False
    return all(any(_stem_eq(t, k) for t in tw) for k in kw)


def keyword_position(text: str, keyword: str) -> float | None:
    """Return the keyword's start offset as a fraction of the text's words, or None."""
    hits = keyword_matches(text, keyword)
    if not hits:
        return None
    total = max(len(words(text)), 1)
    return hits[0] / total


def count_keyword(text: str, keyword: str) -> int:
    return len(keyword_matches(text, keyword))


def cyrillic_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    return cyr / len(letters)


def is_generic_heading(text: str) -> bool:
    t = fold(text).rstrip(":.")
    return t in GENERIC_HEADINGS


# --------------------------------------------------------------------------- #
# Document parsing
# --------------------------------------------------------------------------- #


class Doc:
    def __init__(self) -> None:
        self.title: str | None = None
        self.meta: str | None = None
        self.headings: list[tuple[int, str]] = []
        self.paragraphs: list[str] = []
        self.links: list[str] = []
        self.images: list[dict] = []
        self.body_text: str = ""


class _HTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doc = Doc()
        self._stack: list[str] = []
        self._buf: list[str] = []
        self._heading_level: int | None = None
        self._in_title = False
        self._skip = 0
        self._block: list[str] = []

    def _space(self) -> None:
        # Tag boundaries separate words: "Пам'ять, що<br>залишається" must not glue.
        if self._in_title or self._heading_level:
            self._buf.append(" ")
        else:
            self._block.append(" ")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "nav", "footer", "header"):
            self._skip += 1
            return
        if self._skip:
            return
        self._space()
        if tag == "title":
            self._in_title = True
            self._buf = []
        elif tag == "meta" and (a.get("name") or "").lower() == "description":
            self.doc.meta = normalize(a.get("content") or "")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading_level = int(tag[1])
            self._buf = []
        elif tag == "a":
            href = a.get("href") or ""
            if href:
                self.doc.links.append(href)
        elif tag == "img":
            self.doc.images.append({"src": a.get("src") or "", "alt": (a.get("alt") or "").strip()})
        elif tag in ("p", "li", "td", "th", "blockquote", "pre"):
            self._block = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "nav", "footer", "header"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        self._space()
        if tag == "title":
            self._in_title = False
            self.doc.title = normalize("".join(self._buf))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._heading_level:
            self.doc.headings.append((self._heading_level, normalize("".join(self._buf))))
            self._heading_level = None
        elif tag in ("p", "li", "td", "th", "blockquote", "pre"):
            text = normalize("".join(self._block))
            if text:
                self.doc.paragraphs.append(text)
            self._block = []

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title or self._heading_level:
            self._buf.append(data)
        else:
            self._block.append(data)


def parse_html(raw: str) -> Doc:
    p = _HTMLExtractor()
    p.feed(raw)
    p.close()
    doc = p.doc
    doc.body_text = "\n".join(doc.paragraphs)
    return doc


_MD_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_MD_LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
_HTML_LINK = re.compile(r"<a\s[^>]*href=[\"']([^\"']+)[\"']", re.I)
_HTML_IMG = re.compile(r"<img\s[^>]*>", re.I)
_HTML_ALT = re.compile(r"alt=[\"']([^\"']*)[\"']", re.I)


def parse_markdown(raw: str) -> Doc:
    doc = Doc()
    m = _MD_FRONT.match(raw)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = normalize(val)
                if key in ("title", "seo_title") and val:
                    doc.title = val
                elif key in ("description", "meta_description", "meta") and val:
                    doc.meta = val
        raw = raw[m.end():]

    for mm in _MD_IMAGE.finditer(raw):
        doc.images.append({"src": mm.group(2), "alt": mm.group(1).strip()})
    for mm in _HTML_IMG.finditer(raw):
        alt = _HTML_ALT.search(mm.group(0))
        doc.images.append({"src": "", "alt": (alt.group(1) if alt else "").strip()})
    doc.links.extend(mm.group(2) for mm in _MD_LINK.finditer(raw))
    doc.links.extend(_HTML_LINK.findall(raw))

    in_code = False
    para: list[str] = []
    plain_lines: list[str] = []

    def flush():
        if para:
            text = normalize(" ".join(para))
            if text:
                doc.paragraphs.append(text)
            para.clear()

    for line in raw.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            flush()
            continue
        if in_code:
            continue
        hm = _MD_HEADING.match(line)
        if hm:
            flush()
            doc.headings.append((len(hm.group(1)), normalize(strip_inline_md(hm.group(2)))))
            continue
        if not line.strip():
            flush()
            continue
        if re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            # list items are their own short paragraphs; do not merge into walls
            flush()
            para.append(strip_inline_md(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", line)))
            flush()
            continue
        para.append(strip_inline_md(line))
    flush()

    doc.body_text = "\n".join(doc.paragraphs)
    return doc


def strip_inline_md(text: str) -> str:
    text = _MD_IMAGE.sub(lambda m: m.group(1), text)
    text = _MD_LINK.sub(lambda m: m.group(1), text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_`~]{1,3}", "", text)
    return html.unescape(text)


def load_document(path: str, fmt: str | None) -> Doc:
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    if fmt is None:
        lower = path.lower()
        if lower.endswith((".html", ".htm")) or re.search(r"<(html|body|h1|p)[\s>]", raw[:4000], re.I):
            fmt = "html"
        else:
            fmt = "markdown"
    return parse_html(raw) if fmt == "html" else parse_markdown(raw)


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, cid: str, status: str, severity: str, detail: str, fix_hint: str = "") -> None:
        self.checks.append({
            "id": cid,
            "status": status,
            "severity": severity,
            "detail": detail,
            "fix_hint": fix_hint,
        })

    def ok(self, cid: str, severity: str, detail: str) -> None:
        self.add(cid, "pass", severity, detail)

    def score(self) -> tuple[int, str]:
        total = 100.0
        has_critical_fail = False
        for c in self.checks:
            if c["status"] == "pass":
                continue
            w = CHECK_WEIGHTS.get(c["id"], WEIGHTS[c["severity"]])
            if c["status"] == "warn":
                w = w / 2
            else:
                if c["severity"] == "critical":
                    has_critical_fail = True
            total -= w
        score = max(0, int(round(total)))
        if score >= 90:
            grade = "A"
        elif score >= 75:
            grade = "B"
        elif score >= 60:
            grade = "C"
        else:
            grade = "D"
        if has_critical_fail and grade in ("A", "B"):
            grade = "C"
        return score, grade

    def failed(self) -> bool:
        return any(c["status"] == "fail" for c in self.checks)


def check_title(rep: Report, title: str | None, keyword: str, language: str) -> dict:
    if not title:
        rep.add("title_missing", "fail", "critical", "No title found (no <title>, no front matter title).",
                "Add a title of 30-65 characters that contains the keyword near the start.")
        return {}
    px, chars = pixel_width(title, "title"), len(title)
    info = {"text": title, "pixel_width": px, "chars": chars}
    if px > TITLE_PX_MAX or chars > TITLE_CHARS_MAX:
        rep.add("title_width", "fail", "high", f"Title is {px}px / {chars} chars; Google truncates near {TITLE_PX_MAX}px.",
                "Shorten the title; drop filler words or the brand suffix.")
    elif px > TITLE_PX_WARN:
        rep.add("title_width", "warn", "high", f"Title is {px}px, close to the {TITLE_PX_MAX}px cutoff.",
                "Trim a few characters for safety.")
    elif px < TITLE_PX_MIN or chars < TITLE_CHARS_MIN:
        rep.add("title_width", "warn", "high", f"Title is short ({px}px / {chars} chars).",
                "Add a benefit or qualifier so the title uses the available space.")
    else:
        rep.ok("title_width", "high", f"{px}px / {chars} chars")

    if not contains_keyword(title, keyword):
        rep.add("title_keyword", "fail", "high", "Primary keyword is not in the title.",
                "Put the keyword, or a close variant, in the first half of the title.")
    else:
        pos = keyword_position(title, keyword) or 0
        if pos > 0.5:
            rep.add("title_keyword", "warn", "high", "Keyword appears in the second half of the title.",
                    "Move the keyword towards the start.")
        else:
            rep.ok("title_keyword", "high", "Keyword present near the start")

    if language == "uk" and cyrillic_ratio(title) < CYRILLIC_MIN_RATIO:
        rep.add("cyrillic_ratio", "warn", "low", "Title is mostly non-Cyrillic for a Ukrainian page.",
                "Write the title in Ukrainian.")
    return info


def check_meta(rep: Report, meta: str | None, title: str | None, keyword: str, language: str) -> dict:
    if not meta:
        rep.add("meta_missing", "fail", "critical", "No meta description found.",
                "Add a 70-160 character description with the keyword and a reason to click.")
        return {}
    px, chars = pixel_width(meta, "meta"), len(meta)
    info = {"text": meta, "pixel_width": px, "chars": chars}
    if px > META_PX_MAX or chars > META_CHARS_MAX:
        rep.add("meta_width", "fail", "high", f"Meta is {px}px / {chars} chars; Google truncates near {META_PX_MAX}px.",
                "Cut to one promise plus one call to action.")
    elif px > META_PX_WARN:
        rep.add("meta_width", "warn", "high", f"Meta is {px}px, close to the cutoff.", "Trim slightly.")
    elif px < META_PX_MIN or chars < META_CHARS_MIN:
        rep.add("meta_width", "warn", "high", f"Meta is short ({px}px / {chars} chars).",
                "Use the space: add the benefit and a call to action.")
    else:
        rep.ok("meta_width", "high", f"{px}px / {chars} chars")

    if not contains_keyword(meta, keyword):
        rep.add("meta_keyword", "fail", "high", "Primary keyword is not in the meta description.",
                "Mention the keyword once, naturally.")
    else:
        rep.ok("meta_keyword", "high", "Keyword present")

    if title and fold(meta) == fold(title):
        rep.add("meta_equals_title", "fail", "low", "Meta description duplicates the title.",
                "Write a distinct description that expands on the title.")
    else:
        rep.ok("meta_equals_title", "low", "Distinct from title")

    if language == "uk" and cyrillic_ratio(meta) < CYRILLIC_MIN_RATIO:
        rep.add("cyrillic_ratio", "warn", "low", "Meta is mostly non-Cyrillic for a Ukrainian page.",
                "Write the meta in Ukrainian.")
    return info


def check_headings(rep: Report, headings: list[tuple[int, str]], keyword: str) -> dict:
    h1s = [t for lvl, t in headings if lvl == 1]
    h2s = [t for lvl, t in headings if lvl == 2]
    info = {"h1": h1s, "h2_count": len(h2s), "total": len(headings)}

    if not h1s:
        rep.add("h1_missing", "fail", "critical", "No H1 heading.", "Add one H1 that contains the keyword.")
    elif len(h1s) > 1:
        rep.add("h1_multiple", "fail", "high", f"{len(h1s)} H1 headings found.", "Keep exactly one H1; demote the rest to H2.")
    else:
        if contains_keyword_loose(h1s[0], keyword):
            rep.ok("h1_missing", "critical", "One H1 with keyword")
        else:
            rep.add("h1_keyword", "warn", "high", "H1 does not contain the primary keyword.",
                    "Include the keyword or a close variant in the H1.")

    if len(h2s) < H2_MIN:
        rep.add("h2_count", "fail", "medium", f"Only {len(h2s)} H2 sections; expected at least {H2_MIN}.",
                "Split the body into 4-6 H2 sections, one idea each.")
    else:
        rep.ok("h2_count", "medium", f"{len(h2s)} H2 sections")

    skips = []
    prev = 1
    for lvl, text in headings:
        if lvl > prev + 1:
            skips.append(f"H{prev}→H{lvl} at '{text[:40]}'")
        prev = lvl
    if skips:
        rep.add("heading_skip", "fail", "medium", "Heading levels skip: " + "; ".join(skips[:3]),
                "Do not jump more than one level (H2 → H3, not H2 → H4).")
    else:
        rep.ok("heading_skip", "medium", "No level skips")

    generic = [t for _, t in headings if is_generic_heading(t)]
    if generic:
        rep.add("generic_headings", "warn", "medium", "Generic headings: " + ", ".join(generic[:4]),
                "Rename to say what the section gives the reader.")
    else:
        rep.ok("generic_headings", "medium", "No generic headings")

    seen, dups = set(), []
    for _, t in headings:
        f = fold(t)
        if f in seen:
            dups.append(t)
        seen.add(f)
    if dups:
        rep.add("duplicate_headings", "warn", "medium", "Duplicate headings: " + ", ".join(dups[:3]),
                "Make every heading unique.")
    else:
        rep.ok("duplicate_headings", "medium", "All headings unique")
    return info


def check_body(rep: Report, doc: Doc, keyword: str, secondary: list[str], min_words: int, language: str) -> dict:
    body = doc.body_text
    heading_text = " ".join(t for _, t in doc.headings)
    full = heading_text + "\n" + body
    ws = words(body)
    n = len(ws)
    info = {"word_count": n}

    if n < min_words:
        rep.add("word_count", "fail", "medium", f"{n} words; target is at least {min_words}.",
                "Expand the thinnest H2 sections or add a FAQ.")
    else:
        rep.ok("word_count", "medium", f"{n} words")

    intro = " ".join(ws[:INTRO_WORDS])
    if contains_keyword(intro, keyword):
        rep.ok("keyword_in_intro", "high", f"Keyword within first {INTRO_WORDS} words")
    else:
        rep.add("keyword_in_intro", "fail", "high", f"Keyword not in the first {INTRO_WORDS} words.",
                "Rewrite the opening paragraph to state the keyword and the promise.")

    kw_count = count_keyword(full, keyword)
    n_full = len(words(full))
    density = (kw_count / n_full * 100) if n_full else 0.0
    info.update({"keyword_count": kw_count, "keyword_density": round(density, 2)})
    if n == 0:
        pass
    elif density > DENSITY_MAX:
        rep.add("keyword_density_high", "fail", "high", f"Density {density:.1f}% ({kw_count} uses) looks like stuffing.",
                "Replace repeats with pronouns, synonyms, or variants.")
    elif density < DENSITY_MIN:
        rep.add("keyword_density_low", "warn", "medium", f"Density {density:.1f}% ({kw_count} uses) is low.",
                "Use the keyword in one or two more H2s or paragraphs where it reads naturally.")
    else:
        rep.ok("keyword_density_low", "medium", f"Density {density:.1f}% ({kw_count} uses)")

    if secondary:
        missing = [k for k in secondary if not contains_keyword(full, k)]
        info["secondary_missing"] = missing
        if missing:
            rep.add("secondary_keywords", "warn", "low", "Secondary keywords missing: " + ", ".join(missing),
                    "Work each one into an H2/H3 or a paragraph.")
        else:
            rep.ok("secondary_keywords", "low", "All secondary keywords present")

    sentences = [s for s in re.split(r"(?<=[.!?…])\s+", body) if words(s)]
    avg = (sum(len(words(s)) for s in sentences) / len(sentences)) if sentences else 0.0
    info["avg_sentence_words"] = round(avg, 1)
    if avg > SENTENCE_MAX_AVG:
        rep.add("sentence_length", "warn", "low", f"Average sentence is {avg:.0f} words.",
                "Split long sentences; aim for under 25 words on average.")
    else:
        rep.ok("sentence_length", "low", f"Average sentence {avg:.0f} words")

    long_paras = [p for p in doc.paragraphs if len(words(p)) > PARAGRAPH_MAX_WORDS]
    info["long_paragraphs"] = len(long_paras)
    if long_paras:
        rep.add("paragraph_length", "warn", "low", f"{len(long_paras)} paragraph(s) over {PARAGRAPH_MAX_WORDS} words.",
                "Break walls of text into 2-4 sentence paragraphs or lists.")
    else:
        rep.ok("paragraph_length", "low", "No oversized paragraphs")

    internal = [l for l in doc.links if l.startswith(("/", "#", ".")) or not re.match(r"^[a-z]+://", l)]
    external = [l for l in doc.links if re.match(r"^https?://", l)]
    info.update({"internal_links": len(internal), "external_links": len(external)})
    if internal:
        rep.ok("internal_links", "low", f"{len(internal)} internal link(s)")
    else:
        rep.add("internal_links", "warn", "low", "No internal links.", "Link to 1-3 related pages on your site.")
    if external:
        rep.ok("external_links", "low", f"{len(external)} external link(s)")
    else:
        rep.add("external_links", "warn", "low", "No external links.", "Cite at least one credible source.")

    no_alt = [i for i in doc.images if not i["alt"]]
    info.update({"images": len(doc.images), "images_without_alt": len(no_alt)})
    if doc.images and no_alt:
        rep.add("image_alt", "warn", "low", f"{len(no_alt)} of {len(doc.images)} images lack alt text.",
                "Describe each image in a short phrase.")
    elif doc.images:
        rep.ok("image_alt", "low", "All images have alt text")

    if language == "uk" and doc.headings:
        ratio = cyrillic_ratio(heading_text)
        if ratio < CYRILLIC_MIN_RATIO:
            rep.add("cyrillic_ratio", "warn", "low", f"Only {ratio:.0%} of heading letters are Cyrillic.",
                    "Write headings in Ukrainian.")
    return info


def run_audit(args) -> int:
    try:
        doc = load_document(args.file, args.format)
    except OSError as e:
        print(json.dumps({"error": f"cannot read {args.file}: {e}"}), file=sys.stderr)
        return 2

    keyword = normalize(args.keyword)
    language = args.language
    secondary = [normalize(s) for s in (args.secondary or "").split(",") if normalize(s)]
    title = normalize(args.title) if args.title else doc.title
    meta = normalize(args.meta) if args.meta else doc.meta
    if title is None and doc.headings and doc.headings[0][0] == 1:
        title = doc.headings[0][1]
        title_source = "h1"
    else:
        title_source = "explicit" if args.title else ("document" if doc.title else "none")

    rep = Report()
    t_info = check_title(rep, title, keyword, language)
    m_info = check_meta(rep, meta, title, keyword, language)
    h_info = check_headings(rep, doc.headings, keyword)
    b_info = check_body(rep, doc, keyword, secondary, args.min_words, language)
    score, grade = rep.score()

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    status_order = {"fail": 0, "warn": 1, "pass": 2}
    rep.checks.sort(key=lambda c: (status_order[c["status"]], order[c["severity"]], c["id"]))

    out = {
        "mode": "audit",
        "file": args.file,
        "keyword": keyword,
        "language": language,
        "score": score,
        "grade": grade,
        "status": "FAIL" if rep.failed() else "PASS",
        "title": {**t_info, "source": title_source},
        "meta": m_info,
        "headings": h_info,
        "stats": b_info,
        "checks": rep.checks,
    }
    emit(out, args.json)
    return 1 if rep.failed() else 0


# --------------------------------------------------------------------------- #
# validate: generated candidates
# --------------------------------------------------------------------------- #

PENALTY = {
    "keyword_missing": 30,
    "too_wide": 20,
    "too_narrow": 10,
    "duplicate": 10,
    "not_cyrillic": 15,
    "keyword_late": 5,
    "generic": 15,
    "count": 20,
    "stacked": 10,
    "near_limit": 5,
    "empty": 100,
}


def score_candidate(text: str, kind: str, keyword: str, language: str, seen: set) -> dict:
    text = normalize(text)
    failures: list[str] = []
    if not text:
        return {"text": text, "score": 0, "pixel_width": 0, "chars": 0, "failures": ["empty"]}
    px = pixel_width(text, kind)
    chars = len(text)
    if kind == "title":
        if px > TITLE_PX_MAX or chars > TITLE_CHARS_MAX:
            failures.append("too_wide")
        elif px > TITLE_PX_WARN:
            failures.append("near_limit")
        elif px < TITLE_PX_MIN or chars < TITLE_CHARS_MIN:
            failures.append("too_narrow")
        if text.count("|") >= 2:
            failures.append("stacked")
    else:
        if px > META_PX_MAX or chars > META_CHARS_MAX:
            failures.append("too_wide")
        elif px > META_PX_WARN:
            failures.append("near_limit")
        elif px < META_PX_MIN or chars < META_CHARS_MIN:
            failures.append("too_narrow")
    if not contains_keyword(text, keyword):
        failures.append("keyword_missing")
    elif kind == "title" and (keyword_position(text, keyword) or 0) > 0.5:
        failures.append("keyword_late")
    if language == "uk" and cyrillic_ratio(text) < CYRILLIC_MIN_RATIO:
        failures.append("not_cyrillic")
    f = fold(text)
    if f in seen:
        failures.append("duplicate")
    seen.add(f)
    score = max(0, 100 - sum(PENALTY[x] for x in failures))
    return {"text": text, "score": score, "pixel_width": px, "chars": chars, "failures": failures}


def score_outline(outline: list, keyword: str, language: str) -> dict:
    items = [normalize(x) for x in outline if isinstance(x, str) and normalize(x)]
    failures: list[str] = []
    if not (OUTLINE_MIN <= len(items) <= OUTLINE_MAX):
        failures.append("count")
    if any(is_generic_heading(x) for x in items):
        failures.append("generic")
    if len({fold(x) for x in items}) != len(items):
        failures.append("duplicate")
    if items and not any(contains_keyword_loose(x, keyword) for x in items):
        failures.append("keyword_missing")
    if language == "uk" and items and cyrillic_ratio(" ".join(items)) < CYRILLIC_MIN_RATIO:
        failures.append("not_cyrillic")
    score = max(0, 100 - sum(PENALTY[x] for x in failures))
    return {"items": items, "count": len(items), "score": score, "failures": failures}


HARD_FAILURES = {"keyword_missing", "too_wide", "empty", "not_cyrillic", "count", "generic"}


def run_validate(args) -> int:
    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": f"cannot read {args.input}: {e}"}), file=sys.stderr)
        return 2
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        print(json.dumps({"error": "expected {\"items\": [...]}"}), file=sys.stderr)
        return 2

    results = []
    passed = 0
    for raw in items:
        keyword = normalize(str(raw.get("keyword", "")))
        language = str(raw.get("language", "en")).lower()
        seen_t, seen_m = set(), set()
        titles = [score_candidate(t, "title", keyword, language, seen_t) for t in raw.get("titles", [])]
        metas = [score_candidate(m, "meta", keyword, language, seen_m) for m in raw.get("metas", [])]
        outline = score_outline(raw.get("outline", []), keyword, language)

        def best(cands):
            ok = [i for i, c in enumerate(cands) if not (set(c["failures"]) & HARD_FAILURES)]
            pool = ok or list(range(len(cands)))
            return max(pool, key=lambda i: cands[i]["score"]) if pool else None

        bt, bm = best(titles), best(metas)
        failures = []
        if not titles:
            failures.append("no_titles")
        elif set(titles[bt]["failures"]) & HARD_FAILURES:
            failures.append("title")
        if not metas:
            failures.append("no_metas")
        elif set(metas[bm]["failures"]) & HARD_FAILURES:
            failures.append("meta")
        if set(outline["failures"]) & HARD_FAILURES:
            failures.append("outline")
        status = "PASS" if not failures else "FAIL"
        passed += status == "PASS"
        results.append({
            "keyword": keyword,
            "language": language,
            "titles": titles,
            "metas": metas,
            "outline": outline,
            "best_title": bt,
            "best_meta": bm,
            "status": status,
            "failures": failures,
            "score": int(round((
                (titles[bt]["score"] if bt is not None else 0) * 0.4
                + (metas[bm]["score"] if bm is not None else 0) * 0.35
                + outline["score"] * 0.25
            ))),
        })

    out = {
        "mode": "validate",
        "items": results,
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
    }
    emit(out, args.json)
    return 0 if passed == len(results) else 1


def run_export(args) -> int:
    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": f"cannot read {args.input}: {e}"}), file=sys.stderr)
        return 2
    rows = []
    for it in data.get("items", []):
        bt, bm = it.get("best_title"), it.get("best_meta")
        t = it["titles"][bt] if bt is not None and it.get("titles") else {}
        m = it["metas"][bm] if bm is not None and it.get("metas") else {}
        rows.append({
            "keyword": it.get("keyword", ""),
            "language": it.get("language", ""),
            "title": t.get("text", ""),
            "title_px": t.get("pixel_width", ""),
            "meta_description": m.get("text", ""),
            "meta_px": m.get("pixel_width", ""),
            "outline": " | ".join(it.get("outline", {}).get("items", [])),
            "score": it.get("score", ""),
            "status": it.get("status", ""),
            "failures": ";".join(it.get("failures", [])),
        })
    with open(args.csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else
                           ["keyword", "language", "title", "title_px", "meta_description", "meta_px",
                            "outline", "score", "status", "failures"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"mode": "export", "csv": args.csv, "rows": len(rows)}, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #


def emit(payload: dict, path: str | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="score a draft")
    a.add_argument("--file", required=True)
    a.add_argument("--keyword", required=True)
    a.add_argument("--language", default="en", choices=["en", "uk"])
    a.add_argument("--title")
    a.add_argument("--meta")
    a.add_argument("--secondary", help="comma-separated secondary keywords")
    a.add_argument("--min-words", type=int, default=DEFAULT_MIN_WORDS)
    a.add_argument("--format", choices=["markdown", "html"])
    a.add_argument("--json", help="also write the report to this path")
    a.set_defaults(func=run_audit)

    v = sub.add_parser("validate", help="score generated candidates")
    v.add_argument("input")
    v.add_argument("--json", help="also write the report to this path")
    v.set_defaults(func=run_validate)

    e = sub.add_parser("export", help="validate report -> CSV")
    e.add_argument("input")
    e.add_argument("--csv", required=True)
    e.set_defaults(func=run_export)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
