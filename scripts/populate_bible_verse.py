#!/usr/bin/env python3
"""
Populate a song's Bible Verse from the library, replacing "(Add Bible verse here)".

Reference comes from data/library/songs.json (per-song `scripture_ref`); the verse
text comes from data/library/scripture.json (ASV — public domain). Writes:

    <reference> (ASV)

    <verse text>

Only ever replaces the placeholder — a Bible Verse you wrote by hand is left
untouched. Idempotent.

Usage:
  python scripts/populate_bible_verse.py <slug> [<slug> ...]
  python scripts/populate_bible_verse.py --all
  python scripts/populate_bible_verse.py --all --diff   # preview, write nothing
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MUSIC_DIR = REPO_ROOT / "_music"
SONGS_JSON = REPO_ROOT / "data" / "library" / "songs.json"
SCRIPTURE_JSON = REPO_ROOT / "data" / "library" / "scripture.json"
PLACEHOLDER = "Add Bible verse here"

_spec = importlib.util.spec_from_file_location("edit_server", Path(__file__).parent / "edit_server.py")
es = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(es)


def load_library():
    songs = {s["slug"]: s for s in json.loads(SONGS_JSON.read_text())["songs"]}
    lib = json.loads(SCRIPTURE_JSON.read_text())
    refs = lib.get("references", {})
    translation = lib.get("translation", "ASV")
    return songs, refs, translation


def verse_block(ref: str, refs: dict, translation: str) -> str | None:
    entry = refs.get(ref)
    if not entry:
        return None
    asv = entry.get("asv") or {}
    text = (asv.get("text") or "").strip()
    if not text:
        return None
    display = entry.get("display", ref)
    return f"{display} ({translation})\n\n{text}"


def process(slug: str, songs: dict, refs: dict, translation: str, diff_only: bool) -> str:
    path = es.song_path(slug)
    if not path:
        return f"  {slug}: no such song file"
    text = path.read_text()
    current = es.read_section(text, "Bible Verse")
    if current is None:
        return f"  {slug}: no Bible Verse section"
    if PLACEHOLDER not in current:
        return f"  {slug}: skipped (already has a verse)"
    ref = (songs.get(slug) or {}).get("scripture_ref", "")
    if not ref:
        return f"  {slug}: no scripture_ref in songs.json — leave for you"
    block = verse_block(ref, refs, translation)
    if not block:
        return f"  {slug}: {ref} has no {translation} text in the library — leave for you"
    if diff_only:
        return f"  {slug}: would fill -> {ref} ({block.splitlines()[2][:50]}…)"
    path.write_text(es.write_section(text, "Bible Verse", block))
    return f"  {slug}: filled -> {ref}"


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
    songs, refs, translation = load_library()
    print(("Previewing" if diff_only else "Populating") + f" Bible Verse for {len(slugs)} song(s):")
    for slug in slugs:
        line = process(slug, songs, refs, translation, diff_only)
        # Keep the output focused on what changed / needs attention.
        if "skipped (already" not in line:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
