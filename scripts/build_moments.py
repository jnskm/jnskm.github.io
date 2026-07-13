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
    import re
    t = " ".join((text or "").split())
    t = re.sub(r"^\d+\s+", "", t)
    t = re.sub(r"\s+\d+$", "", t)
    return t.strip()


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
            text = overrides[pid] if pid in overrides else e["text"]
            passage_pool[pid] = {
                "text": clean_text(text),
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
