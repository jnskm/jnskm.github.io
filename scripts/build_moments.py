#!/usr/bin/env python3
"""
build_moments.py — hydrate the approved Stay a Moment map into a shipped asset.

Reads:  _data/moments.yml          (human-approved: feeling → scripture + song)
        data/library/library.json  (the built library: verse text, excerpts, songs)
Writes: assets/data/moments.json   (curated scripture/song per feeling + a deduped
                                    pool of Tails of Grace passages, referenced by id)

Each feeling's PASSAGE is drawn from the whole library — every kept excerpt whose
themes include the feeling, across all nine books. The site surfaces one at random.
No network, no API key: the pastoral choices already live in moments.yml + the
library's theme tags (Claude proposed, human approved).

Run after editing moments.yml or rebuilding the library:
    python scripts/build_moments.py
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
MAP_FILE = ROOT / "_data" / "moments.yml"
LIB_FILE = ROOT / "data" / "library" / "library.json"
OUT_FILE = ROOT / "assets" / "data" / "moments.json"

# Homepage chip order (must match index.html data-key values).
CHIP_ORDER = ["anxious", "weary", "grieving", "lonely",
              "ashamed", "doubting", "hopeful", "grateful"]

# A verse long enough to warrant a snippet + "read the whole passage" link.
LONG_SCRIPTURE_CHARS = 320


def full_passage_url(display: str) -> str:
    """Link to the whole passage (ASV, public domain — matches the library text)."""
    q = urllib.parse.urlencode({"search": display, "version": "ASV"})
    return f"https://www.biblegateway.com/passage/?{q}"


def clean_text(text: str) -> str:
    """Trim stray leading/trailing page numbers and collapse whitespace."""
    t = " ".join((text or "").split())
    t = re.sub(r"^\d+\s+", "", t)
    t = re.sub(r"\s+\d+$", "", t)
    return t.strip()


# A dangling verse reference some excerpts open with, e.g. "— Matthew 11:28-29 ",
# "— 2 Corinthians 1:3-4 " — an artifact of the book quoting a verse inline.
_LEADING_CITE = re.compile(
    r"^[—–-]\s*(?:[1-3]\s)?[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s+\d+:\d+(?:[-–]\d+)?\s+"
)

# A page number that landed mid-passage at a page boundary: a bare 1-3 digit
# number between the end of one sentence and the start of the next (next token
# is a capital letter or an opening quote — never a lowercase word, so real
# numbers like "82 people came" are left alone).
_INTERIOR_PAGENO = re.compile(r"([.!?”\"'’])\s+\d{1,3}\s+(?=[A-Z“\"‘'])")

# Guards so the page-matched strip never touches a real number. A number after
# these words is an ordinal/count ("stage 4", "chapter 2"); a number before
# these is a count ("40 years").
_ORDINAL_BEFORE = {"stage", "chapter", "verse", "psalm", "grade", "level", "phase",
                   "part", "book", "age", "number", "room", "floor", "unit", "size",
                   "apartment", "day", "week", "month", "year", "hour", "lesson"}
_UNIT_AFTER = {"year", "years", "day", "days", "week", "weeks", "month", "months",
               "hour", "hours", "minute", "minutes", "second", "seconds", "people",
               "person", "dog", "dogs", "cat", "cats", "time", "times", "mile", "miles",
               "dollar", "dollars", "child", "children", "man", "men", "woman", "women",
               "percent", "page", "pages", "year-old", "sheep"}


def strip_matched_pageno(text: str, page) -> str:
    """Remove a bare number that equals this chunk's own page — a page number
    that was inlined at a page boundary (e.g. '..., and 53 persistence ...' on
    page 53). Guarded so real numbers ('stage 4', '40 years') are left alone."""
    if not page:
        return text
    pat = re.compile(r"(?P<b>\S+)\s+" + re.escape(str(page)) + r"\s+(?P<a>\S+)")

    def repl(m):
        b = m.group("b").lower().strip("“”\"'‘’.,;:()")
        a = m.group("a").lower().strip("“”\"'‘’.,;:()")
        if b in _ORDINAL_BEFORE or a in _UNIT_AFTER:
            return m.group(0)
        return m.group("b") + " " + m.group("a")

    return pat.sub(repl, text)


def trim_leading_fragment(text: str) -> str:
    """If a passage opens mid-sentence — starting with a lowercase letter, i.e. the
    tail of a sentence carried over from the previous chunk — start it at the first
    full sentence instead. Left unchanged if no sentence boundary follows soon
    enough (better a fragment than an empty passage)."""
    t = text.lstrip()
    if not t or not t[0].islower():
        return text
    m = re.search(r"[.!?][”\"’']?\s+(?=[“\"‘'A-Z])", t)
    if m:
        rest = t[m.end():].strip()
        if len(rest) > 40:
            return rest
    return text


def clean_passage(text: str, page=None) -> str:
    """Clean a passage while preserving its paragraph breaks (blank lines between
    paragraphs, as the book has them). Within each paragraph, collapse whitespace;
    then remove artifacts: a leading dangling verse citation, page numbers
    (leading/trailing, standalone, mid-sentence-boundary, and any matching this
    chunk's page), a leading mid-sentence fragment, and line-break hyphens.
    Conservative throughout — never merges two words. Paragraphs are '\\n\\n'-joined."""
    paras = []
    for p in re.split(r"\n\s*\n", text or ""):
        t = " ".join(p.split())
        if t and not re.fullmatch(r"\d{1,3}", t):   # drop standalone page-number paragraphs
            paras.append(t)
    if not paras:
        return ""

    # Start of passage: drop a leading dangling citation / page number.
    paras[0] = re.sub(r"^\d+\s+", "", _LEADING_CITE.sub("", paras[0])).strip()
    paras = [p for p in paras if p]
    if not paras:
        return ""

    # Drop or trim a leading mid-sentence fragment (first paragraph starts lowercase).
    while paras and paras[0] and paras[0][0].islower():
        trimmed = trim_leading_fragment(paras[0])
        if trimmed != paras[0]:
            paras[0] = trimmed
            break
        if len(paras) > 1:
            paras.pop(0)
        else:
            break
    if not paras:
        return ""

    # End of passage: trailing page number.
    paras[-1] = re.sub(r"\s+\d+$", "", paras[-1]).strip()

    out = []
    for t in paras:
        t = _INTERIOR_PAGENO.sub(r"\1 ", t)
        t = strip_matched_pageno(t, page)
        t = re.sub(r"(\w)-\s+(\w)", r"\1-\2", t)
        t = t.strip()
        if t and not re.fullmatch(r"\d{1,3}", t):
            out.append(t)
    return "\n\n".join(out)


# An inline Scripture quote with its citation: "…quote…" — Book c:v
_QUOTE_CITE = re.compile(
    r"[“\"](?P<quote>[^“”\"]{12,}?)[”\"]\s*[—–-]\s*"
    r"(?P<ref>(?:[1-3]\s)?[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s+\d+:\d+(?:[-–]\d+)?)"
)


def split_scripture(text: str):
    """Split a passage into segments so a quoted verse can be set apart on its own
    line with a right-aligned reference. Returns a list of {t:'text', v} and
    {t:'quote', v, ref}. When there's no inline quote, one text segment."""
    segments = []
    pos = 0
    for m in _QUOTE_CITE.finditer(text):
        before = text[pos:m.start()].strip()
        if before:
            segments.append({"t": "text", "v": before})
        segments.append({"t": "quote", "v": m.group("quote").strip(), "ref": m.group("ref").strip()})
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        segments.append({"t": "text", "v": tail})
    return segments or [{"t": "text", "v": text}]


def die(msg: str):
    sys.exit(f"build_moments: {msg}")


def main():
    if not MAP_FILE.exists():
        die(f"missing {MAP_FILE}")
    if not LIB_FILE.exists():
        die(f"missing {LIB_FILE} — build the library first")

    cfg = yaml.safe_load(MAP_FILE.read_text(encoding="utf-8")) or {}
    feelings = cfg.get("feelings") or {}
    overrides = cfg.get("excerpt_overrides") or {}
    lib = json.loads(LIB_FILE.read_text(encoding="utf-8"))

    scripture = lib["scripture"]
    songs = {s["slug"]: s for s in lib["songs"]}
    books = lib["books"]
    excerpts = lib["excerpts"]  # library stores only kept excerpts

    missing = [k for k in CHIP_ORDER if k not in feelings]
    if missing:
        die(f"no mapping for chip(s): {', '.join(missing)}")

    passage_pool = {}   # id -> hydrated passage (stored once)
    out_feelings = {}

    def add_passage(e):
        pid = e["id"]
        if pid not in passage_pool:
            book = books.get(e["book_id"], {})
            raw = overrides[pid] if pid in overrides else e["text"]
            text = clean_passage(raw, e.get("page"))
            passage_pool[pid] = {
                "segments": split_scripture(text),
                "book_title": book.get("title", ""),
                "book_amazon_url": book.get("amazon_url", ""),
            }
        return pid

    for feeling in CHIP_ORDER:
        m = feelings[feeling]
        sk, slug = m.get("scripture"), m.get("song")
        if sk not in scripture:
            die(f"[{feeling}] scripture key not in library: {sk!r}")
        if slug not in songs:
            die(f"[{feeling}] song slug not in library: {slug!r}")

        s = scripture[sk]
        s_text = clean_text(m["scripture_text"]) if m.get("scripture_text") else s["text"]
        s_text = s_text.replace("[", "").replace("]", "")  # drop ASV supplied-word brackets
        excerpted = bool(m.get("scripture_excerpted")) or len(s_text) > LONG_SCRIPTURE_CHARS

        song = songs[slug]

        passage_ids = [add_passage(e) for e in excerpts if feeling in (e.get("themes") or [])]
        if not passage_ids:
            die(f"[{feeling}] no themed passages found in the library")

        out_feelings[feeling] = {
            "scripture": {
                "display": s["display"],
                "text": s_text,
                "translation": s.get("translation", "ASV"),
                "excerpted": excerpted,
                "full_url": full_passage_url(s["display"]),
            },
            "song": {
                "slug": song["slug"],
                # Title only — drop any trailing parenthetical (e.g. "(Remix)")
                # and the collaboration/remix/korean qualifiers.
                "title": re.sub(r"\s*\([^)]*\)\s*$", "", song["title"]).strip(),
                "url": f"/music/{song['slug']}/",
                "scripture_ref": song.get("scripture_ref", ""),
                "streaming": song.get("streaming", {}),
            },
            "passage_ids": passage_ids,
        }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps({"version": 2, "moments": out_feelings, "passages": passage_pool},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    size_kb = OUT_FILE.stat().st_size // 1024
    print(f"build_moments: wrote {OUT_FILE.relative_to(ROOT)} "
          f"({len(passage_pool)} passages, {size_kb} KB)")
    for f in CHIP_ORDER:
        t = out_feelings[f]
        print(f"  {f:9} {t['scripture']['display']:20} · {t['song']['title']:16} · {len(t['passage_ids'])} passages")


if __name__ == "__main__":
    main()
