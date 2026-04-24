#!/usr/bin/env python3
"""
Backfill Spotify / Apple Music / Amazon Music / YouTube Music URLs into
_music/*.md frontmatter using the Songlink/Odesli API.

Given each released song's YouTube URL (already in the frontmatter), this
script queries Odesli to resolve the same release on every other major
platform and writes the URLs back into the same .md file. A dry-run mode
is supported; the default behavior is to actually write the files.

Re-run any time new songs release or platform listings update. After
running, rebuild with:

    python3 scripts/build_song_library.py
    python3 scripts/build_library.py

Usage:
    python3 scripts/fetch_streaming_urls.py            # backfill missing only
    python3 scripts/fetch_streaming_urls.py --refresh  # re-fetch even if set
    python3 scripts/fetch_streaming_urls.py --dry-run  # print changes only
"""

import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).parent.parent
MUSIC_DIR = REPO_ROOT / "_music"

SONGLINK_API = "https://api.song.link/v1-alpha.1/links"
RATE_LIMIT_SECONDS = 7.0  # Odesli free tier is tight — ~10 req/min
RETRY_BACKOFF = (30, 60, 120)

# Map Odesli platform keys → our frontmatter field names
PLATFORM_MAP = {
    "spotify": "spotify",
    "appleMusic": "apple_music",
    "amazonMusic": "amazon_music",
    "youtubeMusic": "youtube_music",
}
ALL_PLATFORMS = list(PLATFORM_MAP.values())


def fetch_songlink(youtube_url: str) -> dict | None:
    """Return dict of platform→url, or None on total failure."""
    encoded = quote(youtube_url, safe="")
    url = f"{SONGLINK_API}?url={encoded}"
    req = Request(url, headers={"User-Agent": "jnskm-streaming-backfill/1.0"})
    for attempt in range(len(RETRY_BACKOFF) + 1):
        try:
            with urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
            break
        except HTTPError as e:
            if e.code == 429 and attempt < len(RETRY_BACKOFF):
                wait = RETRY_BACKOFF[attempt]
                print(f"    429 — backing off {wait}s", flush=True)
                time.sleep(wait)
                continue
            print(f"    FAILED: {e}", file=sys.stderr)
            return None
        except (URLError, json.JSONDecodeError) as e:
            print(f"    FAILED: {e}", file=sys.stderr)
            return None
    else:
        return None

    links_by_platform = data.get("linksByPlatform", {}) or {}
    result: dict[str, str] = {}
    for odesli_key, our_key in PLATFORM_MAP.items():
        entry = links_by_platform.get(odesli_key) or {}
        u = entry.get("url") or ""
        if u:
            result[our_key] = u
    return result


def parse_md(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Preserves unknown keys."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4:]
    fm: dict = {}
    for line in fm_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        k, v = stripped.split(":", 1)
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def render_md(frontmatter: dict, body: str, original_order: list[str]) -> str:
    """Render frontmatter + body. Preserve original key order, append new keys."""
    seen: set = set()
    lines = ["---"]
    for k in original_order:
        if k in frontmatter:
            v = frontmatter[k]
            lines.append(f'{k}: "{v}"' if v else f"{k}: ")
            seen.add(k)
    for k in frontmatter:
        if k in seen:
            continue
        v = frontmatter[k]
        lines.append(f'{k}: "{v}"' if v else f"{k}: ")
    lines.append("---")
    out = "\n".join(lines)
    if not body.startswith("\n"):
        out += "\n"
    return out + body


def original_key_order(text: str) -> list[str]:
    """Return keys in the order they appear in the original frontmatter."""
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    if end < 0:
        return []
    order = []
    for line in text[3:end].split("\n"):
        s = line.strip()
        if s and not s.startswith("#") and ":" in s:
            order.append(s.split(":", 1)[0].strip())
    return order


def main():
    refresh = "--refresh" in sys.argv[1:]
    dry_run = "--dry-run" in sys.argv[1:]

    md_files = sorted(p for p in MUSIC_DIR.glob("*.md") if not p.name.startswith("_"))
    print(f"Checking {len(md_files)} _music/*.md files ...")
    print()

    updated = 0
    fetched = 0
    skipped_no_yt = 0
    already_complete = 0
    errored = 0

    for i, path in enumerate(md_files, 1):
        text = path.read_text()
        fm, body = parse_md(text)
        yt = (fm.get("youtube") or "").strip()

        if not yt:
            skipped_no_yt += 1
            continue

        missing = [p for p in ALL_PLATFORMS if not fm.get(p)]
        if not missing and not refresh:
            already_complete += 1
            continue

        print(f"[{i:2d}/{len(md_files)}] {path.stem} — fetching ...", flush=True)
        result = fetch_songlink(yt)
        fetched += 1
        time.sleep(RATE_LIMIT_SECONDS)

        if result is None:
            errored += 1
            continue

        changed: list[str] = []
        for p in ALL_PLATFORMS:
            new_url = result.get(p)
            if not new_url:
                continue
            if refresh or not fm.get(p):
                if fm.get(p) != new_url:
                    fm[p] = new_url
                    changed.append(p)

        if changed:
            if dry_run:
                print(f"    [dry-run] would add: {', '.join(changed)}")
            else:
                order = original_key_order(text)
                new_text = render_md(fm, body, order)
                path.write_text(new_text)
                print(f"    wrote: {', '.join(changed)}")
            updated += 1
        else:
            print("    no new links found")

    print()
    print(f"Summary:")
    print(f"  fetched:           {fetched}")
    print(f"  updated files:     {updated}" + (" (DRY RUN — no files written)" if dry_run else ""))
    print(f"  already complete:  {already_complete}")
    print(f"  no YouTube URL:    {skipped_no_yt}")
    print(f"  errored:           {errored}")
    if not dry_run and updated:
        print()
        print("Next: rebuild songs + library")
        print("  python3 scripts/build_song_library.py")
        print("  python3 scripts/build_library.py")


if __name__ == "__main__":
    main()
