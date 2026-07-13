#!/usr/bin/env python3
"""
build_moments.py — hydrate the approved Stay a Moment map into a shipped asset.

Reads:  _data/moments.yml          (human-approved: feeling → scripture/excerpt/song ids)
        data/library/library.json  (the built library: verse text, excerpts, songs)
Writes: assets/data/moments.json   (fully hydrated; the static site fetches this)

Every id in the map is validated against the library — a typo fails the build
rather than shipping a blank. No network, no API key, no Claude at build time:
the pastoral choices already live in moments.yml (Claude proposed, human approved).

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
    t = re.sub(r"^\d+\s+", "", t)        # leading page number
    t = re.sub(r"\s+\d+$", "", t)        # trailing page number
    return t.strip()


def die(msg: str):
    sys.exit(f"build_moments: {msg}")


def main():
    if not MAP_FILE.exists():
        die(f"missing {MAP_FILE}")
    if not LIB_FILE.exists():
        die(f"missing {LIB_FILE} — build the library first")

    moments_map = yaml.safe_load(MAP_FILE.read_text(encoding="utf-8")) or {}
    lib = json.loads(LIB_FILE.read_text(encoding="utf-8"))

    scripture = lib["scripture"]
    excerpts = {e["id"]: e for e in lib["excerpts"]}
    songs = {s["slug"]: s for s in lib["songs"]}
    books = lib["books"]

    keys = list(moments_map.keys())
    missing_chips = [k for k in CHIP_ORDER if k not in moments_map]
    if missing_chips:
        die(f"no mapping for chip(s): {', '.join(missing_chips)}")
    extra = [k for k in keys if k not in CHIP_ORDER]
    if extra:
        die(f"map has feeling(s) with no matching chip: {', '.join(extra)}")

    out = {}
    for feeling in CHIP_ORDER:
        m = moments_map[feeling]
        sk, eid, slug = m.get("scripture"), m.get("excerpt"), m.get("song")

        if sk not in scripture:
            die(f"[{feeling}] scripture key not in library: {sk!r}")
        if eid not in excerpts:
            die(f"[{feeling}] excerpt id not in library: {eid!r}")
        if slug not in songs:
            die(f"[{feeling}] song slug not in library: {slug!r}")

        s = scripture[sk]
        s_text = clean_text(m["scripture_text"]) if m.get("scripture_text") else s["text"]
        excerpted = bool(m.get("scripture_excerpted")) or len(s_text) > LONG_SCRIPTURE_CHARS

        e = excerpts[eid]
        e_text = clean_text(m["excerpt_text"]) if m.get("excerpt_text") else clean_text(e["text"])
        book = books.get(e["book_id"], {})

        song = songs[slug]

        out[feeling] = {
            "scripture": {
                "display": s["display"],
                "text": s_text,
                "translation": s.get("translation", "ASV"),
                "excerpted": excerpted,
                "full_url": full_passage_url(s["display"]),
            },
            "excerpt": {
                "id": e["id"],
                "text": e_text,
                "book_title": book.get("title", ""),
                "book_amazon_url": book.get("amazon_url", ""),
            },
            "song": {
                "slug": song["slug"],
                "title": song["title"],
                "url": f"/music/{song['slug']}/",
                "scripture_ref": song.get("scripture_ref", ""),
                "streaming": song.get("streaming", {}),
                "collaboration": song.get("collaboration"),
                "is_remix": song.get("is_remix", False),
                "is_korean": song.get("is_korean", False),
            },
        }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({"version": 1, "moments": out},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"build_moments: wrote {OUT_FILE.relative_to(ROOT)} ({len(out)} feelings)")
    for f in CHIP_ORDER:
        t = out[f]
        print(f"  {f:9} {t['scripture']['display']:20} · {t['song']['title']}")


if __name__ == "__main__":
    main()
