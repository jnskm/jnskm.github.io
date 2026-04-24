#!/usr/bin/env python3
"""
Build the Scripture library for the jnskm.com "Stay a moment" feature.

Collects every unique Scripture reference from data/library/songs.json,
fetches the ASV text from bible-api.com (public domain, no auth), marks
which references are available on thelighttranslationbible.org, and
writes data/library/scripture.json.

Caches results so re-runs only fetch new refs. ASV is embedded so the
Netlify function has no runtime external-API dependency.

Usage:
    python3 scripts/build_scripture_library.py
    python3 scripts/build_scripture_library.py --refresh   # re-fetch all
"""

import json
import sys
import time
import urllib.parse
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).parent.parent
SONGS_JSON = REPO_ROOT / "data" / "library" / "songs.json"
OUTPUT_PATH = REPO_ROOT / "data" / "library" / "scripture.json"

BIBLE_API = "https://bible-api.com"
LTB_BASE = "https://thelighttranslationbible.org"
# LTB currently has only John 1 and John 2 complete (as of 2026-04-17)
LTB_AVAILABLE = {("John", 1), ("John", 2)}

RATE_LIMIT_SECONDS = 1.2  # polite pacing for the public API
RETRY_BACKOFF = (5, 15, 30)  # seconds to wait after consecutive 429s

# A few universal passages included even if no song references them — used
# as the fallback when a visitor picks "something else" or types something
# the model can't match well.
UNIVERSAL_SEED_REFS = [
    ("Psalm 23", "Psalm", 23, None),
    ("Matthew 11:28-30", "Matthew", 11, "28-30"),
    ("Isaiah 41:10", "Isaiah", 41, "10"),
    ("Lamentations 3:22-23", "Lamentations", 3, "22-23"),
    ("Romans 8:38-39", "Romans", 8, "38-39"),
    ("John 3:16", "John", 3, "16"),
]


def canonical_ref_key(book: str, chapter: int, verses: str | None) -> str:
    """Stable key for deduplication and caching."""
    if verses:
        return f"{book} {chapter}:{verses}"
    return f"{book} {chapter}"


def api_query(book: str, chapter: int, verses: str | None) -> str:
    """Build the bible-api.com query string."""
    if verses:
        # bible-api expects e.g. "john 14:1-3" or "john 14:1,5"
        ref = f"{book} {chapter}:{verses}"
    else:
        ref = f"{book} {chapter}"
    return urllib.parse.quote(ref)


def fetch_asv(book: str, chapter: int, verses: str | None) -> dict | None:
    """Fetch text from bible-api.com with retry-on-429. Returns dict or None."""
    url = f"{BIBLE_API}/{api_query(book, chapter, verses)}?translation=asv"
    req = Request(url, headers={"User-Agent": "jnskm-scripture-builder/1.0"})

    for attempt in range(len(RETRY_BACKOFF) + 1):
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                break
        except HTTPError as exc:
            if exc.code == 429 and attempt < len(RETRY_BACKOFF):
                wait = RETRY_BACKOFF[attempt]
                print(f"    429 — backing off {wait}s (attempt {attempt + 1})", flush=True)
                time.sleep(wait)
                continue
            print(f"    FAILED: {exc}", file=sys.stderr)
            return None
        except (URLError, json.JSONDecodeError) as exc:
            print(f"    FAILED: {exc}", file=sys.stderr)
            return None
    else:
        return None

    # bible-api returns `text` as the concatenated passage and `verses` as a list
    # of {book_id, book_name, chapter, verse, text}.
    text = data.get("text", "").strip()
    # Clean up: bible-api uses backticks for apostrophes sometimes; normalize.
    text = text.replace("`", "'")
    # Collapse any run of whitespace or consecutive verses missing spaces
    text = " ".join(text.split())

    verses_list = data.get("verses", [])
    # Normalize verse-level text too
    for v in verses_list:
        v["text"] = " ".join(v.get("text", "").replace("`", "'").split())

    return {
        "text": text,
        "verses": verses_list,
        "translation": "ASV",
        "translation_note": "American Standard Version (1901), Public Domain",
    }


def ltb_info(book: str, chapter: int) -> dict | None:
    """Return LTB link info if the ref is available, else None."""
    if (book, chapter) not in LTB_AVAILABLE:
        return None
    return {
        "url": LTB_BASE,
        "note": "Read in the Light Translation Bible",
        "available": True,
    }


def collect_refs_from_songs(songs: list[dict]) -> list[tuple[str, str, int, str | None]]:
    """Return list of (key, book, chapter, verses) for every unique parseable ref
    among released songs. Unreleased songs contribute refs too — the visitor
    might still want the scripture even if the song isn't yet on streaming."""
    seen: dict[str, tuple[str, str, int, str | None]] = {}
    for s in songs:
        book = s.get("scripture_book")
        chapter = s.get("scripture_chapter")
        if not book or chapter is None:
            continue
        verses = s.get("scripture_verses")
        key = canonical_ref_key(book, chapter, verses)
        if key not in seen:
            seen[key] = (key, book, chapter, verses)
    return list(seen.values())


def load_existing_cache() -> dict:
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            return json.load(f).get("references", {})
    return {}


def main():
    refresh = "--refresh" in sys.argv[1:]

    if not SONGS_JSON.exists():
        print(f"ERROR: {SONGS_JSON} not found. Run build_song_library.py first.", file=sys.stderr)
        sys.exit(1)
    with open(SONGS_JSON) as f:
        songs_data = json.load(f)
    songs = songs_data["songs"]

    refs = collect_refs_from_songs(songs)

    # Add universal seeds that aren't already covered
    existing_keys = {r[0] for r in refs}
    for key, book, chapter, verses in UNIVERSAL_SEED_REFS:
        if key not in existing_keys:
            refs.append((key, book, chapter, verses))
            existing_keys.add(key)

    refs.sort()
    print(f"Unique Scripture references to cover: {len(refs)}")

    cache = {} if refresh else load_existing_cache()
    results: dict[str, dict] = {}
    fetched = 0
    reused = 0

    for key, book, chapter, verses in refs:
        # Only reuse cache if we successfully fetched ASV before.
        cached = cache.get(key)
        if cached and cached.get("asv"):
            results[key] = cached
            reused += 1
            continue

        print(f"  fetching {key} ...", flush=True)
        asv = fetch_asv(book, chapter, verses)
        time.sleep(RATE_LIMIT_SECONDS)

        entry = {
            "key": key,
            "display": key,
            "book": book,
            "chapter": chapter,
            "verses": verses,
            "is_chapter_only": verses is None,
            "asv": asv,
            "ltb": ltb_info(book, chapter),
        }
        results[key] = entry
        fetched += 1

    # Count how many songs reference each ref — useful for the LLM's routing signal
    ref_song_count: dict[str, int] = {k: 0 for k in results}
    for s in songs:
        if not s.get("is_released"):
            continue
        b = s.get("scripture_book")
        c = s.get("scripture_chapter")
        v = s.get("scripture_verses")
        if b and c is not None:
            k = canonical_ref_key(b, c, v)
            if k in ref_song_count:
                ref_song_count[k] += 1
    for k, n in ref_song_count.items():
        results[k]["released_song_count"] = n

    output = {
        "total_references": len(results),
        "fetched_this_run": fetched,
        "reused_from_cache": reused,
        "translation": "ASV",
        "ltb_available_books": sorted({f"{b} {c}" for (b, c) in LTB_AVAILABLE}),
        "references": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print()
    print(f"Wrote {len(results)} references to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  Fetched {fetched} new, reused {reused} from cache")

    # Failure report
    failures = [k for k, v in results.items() if v.get("asv") is None]
    if failures:
        print(f"  WARNING: {len(failures)} refs had no ASV text fetched:")
        for k in failures:
            print(f"    {k}")

    # LTB coverage
    ltb_refs = [k for k, v in results.items() if v.get("ltb")]
    print(f"  LTB-linkable refs: {len(ltb_refs)}")
    for k in ltb_refs:
        print(f"    {k}")


if __name__ == "__main__":
    main()
