#!/usr/bin/env python3
"""
Build consolidated playlists for the jnskm.com "Stay a moment" feature.

For each playlist in scripts/playlists_manifest.yml:
  - Starts with `song_slugs` as manual overrides (if provided).
  - Otherwise, gathers every released song whose themes intersect with
    the playlist's `themes_include`.
  - Orders songs within the playlist by theme-overlap score (most overlap
    first), then alphabetically.

Writes data/library/playlists.json with the resolved playlists, ready to
be consumed by build_library.py and the playlist pages.

Usage:
    python3 scripts/build_playlists.py
"""

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = REPO_ROOT / "scripts" / "playlists_manifest.yml"
SONGS_JSON = REPO_ROOT / "data" / "library" / "songs.json"
OUTPUT_PATH = REPO_ROOT / "data" / "library" / "playlists.json"


def main():
    with open(MANIFEST_PATH) as f:
        manifest = yaml.safe_load(f)

    with open(SONGS_JSON) as f:
        songs_data = json.load(f)
    released = [s for s in songs_data["songs"] if s.get("is_released")]
    by_slug = {s["slug"]: s for s in released}

    playlists = []
    for p in manifest["playlists"]:
        themes = set(p.get("themes_include") or [])
        manual = p.get("song_slugs") or []

        if manual:
            song_slugs = [s for s in manual if s in by_slug]
            missing = [s for s in manual if s not in by_slug]
            if missing:
                print(f"  warning: playlist '{p['slug']}' references unknown slugs: {missing}")
        else:
            # Score by theme overlap; drop 0-overlap.
            scored: list[tuple[int, str, str]] = []
            for s in released:
                song_themes = set(s.get("themes") or [])
                overlap = len(song_themes & themes)
                if overlap == 0:
                    continue
                scored.append((-overlap, s["title"].lower(), s["slug"]))
            scored.sort()
            song_slugs = [s for _, _, s in scored]

        playlists.append(
            {
                "slug": p["slug"],
                "title": p["title"],
                "description": p.get("description", ""),
                "themes_include": sorted(themes),
                "song_slugs": song_slugs,
                "song_count": len(song_slugs),
                "streaming_playlists": p.get("streaming_playlists") or {},
            }
        )

    # Also build a reverse index: song_slug → [playlist_slug, ...] so the
    # live endpoint knows which playlist to recommend for each song pick.
    song_to_playlists: dict[str, list[str]] = {}
    for p in playlists:
        for s in p["song_slugs"]:
            song_to_playlists.setdefault(s, []).append(p["slug"])

    output = {
        "playlist_count": len(playlists),
        "playlists": playlists,
        "song_to_playlists": song_to_playlists,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print()
    print(f"{'slug':20s}  {'songs':>6s}  title")
    print("-" * 80)
    for p in playlists:
        print(f"{p['slug']:20s}  {p['song_count']:>6d}  {p['title']}")

    # Songs that landed in no playlist — diagnostic
    orphans = [s["slug"] for s in released if s["slug"] not in song_to_playlists]
    if orphans:
        print()
        print(f"Songs in no playlist ({len(orphans)}):")
        for slug in orphans:
            print(f"  {slug}  themes={by_slug[slug].get('themes')}")


if __name__ == "__main__":
    main()
