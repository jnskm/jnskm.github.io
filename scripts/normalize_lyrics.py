#!/usr/bin/env python3
"""
Normalize a song's Lyrics: capitalize the first letter of every line.

That single rule covers both things you do by hand:
  * section labels  [intro] -> [Intro], [pre-chorus] -> [Pre-chorus]
  * lyric lines     "even when I can't see" -> "Even when I can't see"

It only touches the first *alphabetic* character of each line, so:
  * HTML wrapper lines (<pre ...>, </pre>, <span ...>) are left alone
  * Korean (and other non-cased scripts) pass through unchanged
  * blank lines and punctuation-led lines are preserved

Idempotent — running it again changes nothing.

Usage:
  python scripts/normalize_lyrics.py <slug> [<slug> ...]
  python scripts/normalize_lyrics.py --all
  python scripts/normalize_lyrics.py --all --diff   # preview only, write nothing
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MUSIC_DIR = REPO_ROOT / "_music"
LYRIC_PLACEHOLDER = "(Add lyrics here)"

# Reuse the section read/write + slug safety from the edit server.
_spec = importlib.util.spec_from_file_location("edit_server", Path(__file__).parent / "edit_server.py")
es = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(es)


# The rule lives in edit_server (also applied automatically on every editor save).
normalize = es.normalize_lyrics


def process(slug: str, diff_only: bool) -> None:
    path = es.song_path(slug)
    if not path:
        print(f"  {slug}: no such song file")
        return
    text = path.read_text()
    current = es.read_section(text, "Lyrics")
    if current is None:
        print(f"  {slug}: no Lyrics section")
        return
    if LYRIC_PLACEHOLDER in current:
        print(f"  {slug}: skipped (placeholder lyrics)")
        return

    updated = normalize(current)
    if updated == current:
        print(f"  {slug}: already normalized")
        return

    if diff_only:
        changed = [
            (a, b)
            for a, b in zip(current.split("\n"), updated.split("\n"))
            if a != b
        ]
        print(f"  {slug}: {len(changed)} line(s) would change:")
        for a, b in changed[:12]:
            print(f"      - {a}\n      + {b}")
        if len(changed) > 12:
            print(f"      … and {len(changed) - 12} more")
        return

    new_text = es.write_section(text, "Lyrics", updated)
    path.write_text(new_text)
    n = sum(1 for a, b in zip(current.split("\n"), updated.split("\n")) if a != b)
    print(f"  {slug}: normalized ({n} line(s) changed)")


def all_slugs() -> list[str]:
    return sorted(p.stem for p in MUSIC_DIR.glob("*.md") if not p.name.startswith("_"))


def main(argv: list[str]) -> int:
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    diff_only = "--diff" in flags
    slugs = all_slugs() if "--all" in flags else args
    if not slugs:
        print(__doc__)
        return 1
    print(("Previewing" if diff_only else "Normalizing") + f" lyrics for {len(slugs)} song(s):")
    for slug in slugs:
        process(slug, diff_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
