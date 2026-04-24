#!/usr/bin/env python3
"""
Assemble the final jnskm.com visitor library for the Netlify serverless function.

Combines:
- Kept, theme-tagged book excerpts from data/library/books/*.json
- Released, theme-tagged songs from data/library/songs.json
- ASV Scripture text + LTB availability from data/library/scripture.json
- Book metadata from scripts/books_manifest.yml

Writes a single data/library/library.json that the serverless endpoint
loads into Claude's system prompt at runtime.

Usage:
    python3 scripts/build_library.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
BOOKS_DIR = REPO_ROOT / "data" / "library" / "books"
SONGS_JSON = REPO_ROOT / "data" / "library" / "songs.json"
SCRIPTURE_JSON = REPO_ROOT / "data" / "library" / "scripture.json"
PLAYLISTS_JSON = REPO_ROOT / "data" / "library" / "playlists.json"
MANIFEST_PATH = REPO_ROOT / "scripts" / "books_manifest.yml"
OUTPUT_PATH = REPO_ROOT / "data" / "library" / "library.json"
# Jekyll-consumable data files for the playlist pages
JEKYLL_DATA_DIR = REPO_ROOT / "_data"
JEKYLL_PLAYLISTS_DIR = REPO_ROOT / "_playlists"

# Canonical theme vocabulary — must match the filter and tagging prompts.
VALID_THEMES = {
    # Hard seasons
    "anxious", "weary", "grieving", "doubting", "lonely", "ashamed", "guilty",
    "discouraged", "forgotten", "afraid", "tempted", "confused", "striving", "proud",
    # Gentler seasons
    "hopeful", "grateful", "joyful", "peaceful", "loved", "forgiven", "restored",
    "trusting", "waiting", "resting", "surrendered", "called",
}

# Silent normalization for out-of-vocab themes that occasionally slipped past
# the filter/tag prompts. Only closely-related mappings.
THEME_ALIAS = {
    "resentful": "proud",
    "lost": "lonely",
    "humble": "surrendered",
    "distracted": "confused",
    "faithful": "trusting",
    "known": "loved",
    "longing": "lonely",
}


def normalize_themes(themes: list[str]) -> list[str]:
    out: list[str] = []
    for t in themes or []:
        if t in VALID_THEMES:
            out.append(t)
        elif t in THEME_ALIAS:
            alias = THEME_ALIAS[t]
            if alias not in out:
                out.append(alias)
        # else: drop silently — other valid themes on the same item remain
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for t in out:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def load_book_metadata() -> dict:
    with open(MANIFEST_PATH) as f:
        m = yaml.safe_load(f)
    return {
        b["slug"]: {
            "title": b["title"],
            "subtitle": b.get("subtitle", ""),
            "authors": b.get("authors", []),
            "cover_image": b.get("cover_image", ""),
            "amazon_url": b.get("amazon_url", ""),
        }
        for b in m["books"]
    }


def collect_excerpts() -> list[dict]:
    excerpts: list[dict] = []
    for p in sorted(BOOKS_DIR.glob("*.json")):
        with open(p) as f:
            data = json.load(f)
        for c in data["chunks"]:
            if not c.get("keep"):
                continue
            excerpts.append(
                {
                    "id": c["id"],
                    "book_id": data["book_id"],
                    "lesson_number": c["lesson_number"],
                    "lesson_title": c.get("lesson_title"),
                    "lesson_subtitle": c.get("lesson_subtitle"),
                    "section": c.get("section"),
                    "page": c["page"],
                    "text": c["text"],
                    "themes": normalize_themes(c.get("themes", [])),
                }
            )
    return excerpts


def collect_songs() -> tuple[list[dict], dict]:
    with open(SONGS_JSON) as f:
        data = json.load(f)
    songs = []
    for s in data["songs"]:
        if not s.get("is_released"):
            continue
        songs.append(
            {
                "slug": s["slug"],
                "title": s["title"],
                "scripture_ref": s["scripture_ref"],
                "scripture_book": s.get("scripture_book"),
                "scripture_chapter": s.get("scripture_chapter"),
                "scripture_verses": s.get("scripture_verses"),
                "collaboration": s.get("collaboration"),
                "is_remix": s.get("is_remix", False),
                "is_korean": s.get("is_korean", False),
                "streaming": s.get("streaming", {}),
                "themes": normalize_themes(s.get("themes", [])),
            }
        )
    return songs, data.get("artist_search", {})


def collect_scripture() -> tuple[dict, list[str]]:
    with open(SCRIPTURE_JSON) as f:
        data = json.load(f)

    refs = {}
    missing_asv: list[str] = []
    for key, entry in data["references"].items():
        asv = entry.get("asv") or {}
        # Use verse-level breakdown to build clean text with proper verse spacing
        verses = asv.get("verses", [])
        if verses:
            clean_text = " ".join(
                f"{v['text']}" for v in verses if v.get("text")
            ).strip()
        else:
            clean_text = asv.get("text", "").strip()
            if not clean_text:
                missing_asv.append(key)

        ltb = entry.get("ltb") or {}
        refs[key] = {
            "key": key,
            "display": entry.get("display", key),
            "book": entry.get("book"),
            "chapter": entry.get("chapter"),
            "verses": entry.get("verses"),
            "is_chapter_only": entry.get("is_chapter_only", False),
            "text": clean_text,
            "translation": asv.get("translation", "ASV"),
            "translation_note": asv.get("translation_note", ""),
            "ltb_url": ltb.get("url") if ltb.get("available") else None,
            "ltb_available": bool(ltb.get("available")),
        }
    return refs, missing_asv


def load_playlists() -> dict:
    if not PLAYLISTS_JSON.exists():
        return {"playlists": [], "song_to_playlists": {}}
    with open(PLAYLISTS_JSON) as f:
        return json.load(f)


def write_jekyll_playlist_pages(playlists: list[dict], songs: list[dict]) -> None:
    """Emit _data/playlists.json, _data/songs_lite.json, and one .md file
    per playlist under _playlists/ so Jekyll can render visitor pages."""
    JEKYLL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    JEKYLL_PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)

    # songs_lite: just the fields playlist pages need to render
    songs_by_slug = {
        s["slug"]: {
            "slug": s["slug"],
            "title": s["title"],
            "scripture_ref": s["scripture_ref"],
            "streaming": s.get("streaming", {}),
            "collaboration": s.get("collaboration"),
            "is_remix": s.get("is_remix", False),
            "is_korean": s.get("is_korean", False),
        }
        for s in songs
    }
    with open(JEKYLL_DATA_DIR / "songs_lite.json", "w") as f:
        json.dump(songs_by_slug, f, indent=2, ensure_ascii=False)

    with open(JEKYLL_DATA_DIR / "playlists.json", "w") as f:
        json.dump(playlists, f, indent=2, ensure_ascii=False)

    # One .md file per playlist in the _playlists collection
    for p in playlists:
        md = [
            "---",
            f'slug: "{p["slug"]}"',
            f'title: "{p["title"]}"',
            f'description: "{p["description"]}"',
            "layout: playlist",
            "---",
            "",
        ]
        (JEKYLL_PLAYLISTS_DIR / f"{p['slug']}.md").write_text("\n".join(md))


def main():
    book_metadata = load_book_metadata()
    excerpts = collect_excerpts()
    songs, artist_search = collect_songs()
    scripture, missing_asv = collect_scripture()
    playlists_data = load_playlists()
    playlists = playlists_data.get("playlists", [])
    song_to_playlists = playlists_data.get("song_to_playlists", {})

    # Coverage stats
    themes_in_excerpts = {t for e in excerpts for t in e["themes"]}
    themes_in_songs = {t for s in songs for t in s["themes"]}

    library = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vocabulary": {
            "themes": sorted(VALID_THEMES),
        },
        "books": book_metadata,
        "excerpts": excerpts,
        "songs": songs,
        "scripture": scripture,
        "playlists": playlists,
        "song_to_playlists": song_to_playlists,
        "artist_search": artist_search,
        "stats": {
            "excerpt_count": len(excerpts),
            "song_count": len(songs),
            "scripture_ref_count": len(scripture),
            "playlist_count": len(playlists),
            "themes_covered_by_excerpts": sorted(themes_in_excerpts),
            "themes_covered_by_songs": sorted(themes_in_songs),
            "missing_asv_text": missing_asv,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(library, f, indent=2, ensure_ascii=False)

    # Emit Jekyll-consumable files for the playlist pages
    write_jekyll_playlist_pages(playlists, songs)

    # Pretty summary
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({size_kb:.1f} KB)")
    print(f"  Excerpts: {len(excerpts)}")
    print(f"  Songs: {len(songs)}")
    print(f"  Scripture refs: {len(scripture)}")
    print(f"  Book metadata: {len(book_metadata)} books")
    print()

    # Theme coverage — which themes lack excerpts, which lack songs?
    uncovered_excerpts = sorted(VALID_THEMES - themes_in_excerpts)
    uncovered_songs = sorted(VALID_THEMES - themes_in_songs)
    if uncovered_excerpts:
        print(f"  Themes with NO excerpts ({len(uncovered_excerpts)}):")
        print(f"    {', '.join(uncovered_excerpts)}")
    if uncovered_songs:
        print(f"  Themes with NO songs ({len(uncovered_songs)}):")
        print(f"    {', '.join(uncovered_songs)}")

    if missing_asv:
        print(f"\n  WARNING: {len(missing_asv)} scripture refs have no ASV text:")
        for k in missing_asv:
            print(f"    {k}")


if __name__ == "__main__":
    main()
