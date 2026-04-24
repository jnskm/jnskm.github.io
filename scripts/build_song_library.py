#!/usr/bin/env python3
"""
Build the song library for the jnskm.com "Stay a moment" feature.

Reads .wav filenames from ~/Documents/JNSKM/JNSKM_YouTube/DDD/Christian_Songs/,
parses each filename into (title, scripture reference, variant), deduplicates
variants (keeps latest of _v2 / _Remastered / _Edited / stems etc.), cross-
references the existing _music/*.md files for YouTube URLs and lyrics, and
writes data/library/songs.json.

Usage:
    python3 scripts/build_song_library.py
"""

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    from slugify import slugify
except ImportError:
    # Minimal slugify fallback
    def slugify(text):
        text = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[-\s]+", "-", text).strip("-")

REPO_ROOT = Path(__file__).parent.parent
SONGS_DIR = Path("/Users/jnskm/Documents/JNSKM/JNSKM_YouTube/DDD/Christian_Songs").expanduser()
MUSIC_DIR = REPO_ROOT / "_music"
OUTPUT_PATH = REPO_ROOT / "data" / "library" / "songs.json"

# Bible books, ordered so multi-word names match before partial matches.
BIBLE_BOOKS = {
    # Old Testament
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth",
    "1_Samuel", "2_Samuel", "1_Kings", "2_Kings",
    "1_Chronicles", "2_Chronicles", "Ezra", "Nehemiah", "Esther",
    "Job", "Psalm", "Psalms", "Proverbs", "Ecclesiastes", "Song_of_Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel",
    "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
    "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
    # New Testament
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans",
    "1_Corinthians", "2_Corinthians", "2Cor",
    "Galatians", "Ephesians", "Philippians", "Colossians",
    "1_Thessalonians", "2_Thessalonians",
    "1_Timothy", "2_Timothy", "Titus", "Philemon",
    "Hebrews", "James",
    "1_Peter", "2_Peter",
    "1_John", "2_John", "3_John",
    "Jude", "Revelation",
}

# Separator tokens between song name and Scripture reference.
SEPARATOR_TOKENS = (
    "_inspired_by_",
    "_Inspired_By_",
    "_Inspired_by_",
    "_inspred_by_",     # typo found in one filename
    "_Inspired By_",    # space variant
    "_based_on_",
    "_Based_On_",
    " based on ",       # in one file with actual spaces
)

# Trailing variant suffixes we treat as non-canonical versions to skip
# (kept for posterity in `variants` but not promoted to song entries).
STEM_SUFFIXES = (
    "_Backing", "_Vocals", "_Vocal", "_Instrumental",
)
# Suffixes that indicate a version worth preferring over an unsuffixed older file.
VERSION_SUFFIXES = re.compile(r"_(v\d+|Edited|Remastered)$", re.IGNORECASE)
# Prefixes that indicate this track is a collaboration/album.
COLLAB_PREFIXES = {
    "KAChoir": "KA Choir",
    "Mareon": "Mareon",
    "Breakthru_Me&You": "Breakthru Me&You",
}


@dataclass
class Song:
    slug: str
    title: str
    scripture_ref: str
    scripture_book: str | None
    scripture_chapter: int | None
    scripture_verses: str | None
    source_wav: str
    is_released: bool = False   # True when a matching _music/*.md exists (canonical "public")
    streaming: dict = field(default_factory=dict)  # {youtube, spotify, apple_music, amazon_music, youtube_music}
    collaboration: str | None = None
    is_remix: bool = False
    is_korean: bool = False
    variant_files: list[str] = field(default_factory=list)
    themes: list = field(default_factory=list)  # preserved across rebuilds; set by tag_song_themes.py


def normalize(text: str) -> str:
    return text.replace("_", " ").strip()


def find_separator(stem: str) -> tuple[str, str] | None:
    """Return (left, right) split on the first separator found, else None."""
    lower = stem.lower()
    for sep in SEPARATOR_TOKENS:
        idx = lower.find(sep.lower())
        if idx >= 0:
            return stem[:idx], stem[idx + len(sep):]
    return None


def strip_stem_suffix(name: str) -> tuple[str, str | None]:
    """Strip _Backing/_Vocals/_Instrumental. Returns (base, stem_tag|None)."""
    for suf in STEM_SUFFIXES:
        if name.endswith(suf):
            return name[: -len(suf)], suf.lstrip("_")
    return name, None


def strip_version_suffix(name: str) -> tuple[str, str | None]:
    """Strip _v2 / _Edited / _Remastered. Returns (base, version_tag|None)."""
    m = VERSION_SUFFIXES.search(name)
    if m:
        return name[: m.start()], m.group(1).lower()
    return name, None


def detect_collaboration(name: str) -> tuple[str, str | None]:
    """If the title starts with a collab prefix, strip it and return (rest, label)."""
    for prefix, label in COLLAB_PREFIXES.items():
        pat = re.compile(rf"^{re.escape(prefix)}_(?:\d+_)?", re.IGNORECASE)
        m = pat.match(name)
        if m:
            return name[m.end():], label
    return name, None


def detect_remix_or_korean(name: str) -> tuple[str, bool, bool]:
    """Strip _RMX* and _KO markers, return (clean_name, is_remix, is_korean)."""
    is_remix = False
    is_korean = False
    # _RMX<optional digits>
    m = re.search(r"_RMX[0-9A-Z]*", name, re.IGNORECASE)
    if m:
        is_remix = True
        name = name[: m.start()] + name[m.end():]
    if re.search(r"_KO(?:$|_)", name):
        is_korean = True
        name = re.sub(r"_KO(?:$|_)", "", name)
    return name.strip("_"), is_remix, is_korean


def parse_scripture_ref(raw: str) -> tuple[str, str | None, int | None, str | None]:
    """Parse a scripture reference from a filename fragment.

    Returns (display_ref, book, chapter, verses). `display_ref` is human-
    readable ("John 14:1-3"); the others are structured.

    Handles compound refs by returning display only (e.g., "Matthew 6:26;
    10:29-31" or "Psalm 147:3; 2 Corinthians 4:8-10") and leaving the
    structured fields null so the caller knows to handle specially.
    """
    if not raw:
        return "", None, None, None

    # Normalize en-dash to hyphen
    raw = raw.replace("\u2013", "-").replace("\u2014", "-")
    # Strip any leading/trailing underscores
    raw = raw.strip("_")
    tokens = raw.split("_")

    # Try to match the book name — can be one or two tokens
    book = None
    book_token_count = 0
    # Check two-token book names first (e.g., "1_Samuel", "2_Corinthians")
    if len(tokens) >= 2:
        two = f"{tokens[0]}_{tokens[1]}"
        if two in BIBLE_BOOKS:
            book = two
            book_token_count = 2
    if book is None and tokens[0] in BIBLE_BOOKS:
        book = tokens[0]
        book_token_count = 1

    if book is None:
        # Unknown book, return raw as display
        return normalize(raw), None, None, None

    rest = tokens[book_token_count:]
    book_display = book.replace("_", " ")

    # If the rest contains a second book name (compound ref), return display only
    for i in range(len(rest)):
        if rest[i] in BIBLE_BOOKS or (
            i + 1 < len(rest) and f"{rest[i]}_{rest[i + 1]}" in BIBLE_BOOKS
        ):
            # Compound reference; return a loose display
            display = f"{book_display} " + "_".join(rest).replace("_", " ").replace(" _", "; ")
            # Best-effort cleanup
            display = re.sub(r"\s+", " ", display).strip()
            return display, None, None, None

    if not rest:
        return book_display, book_display, None, None

    # Normal case: first token is chapter, rest are verses
    try:
        chapter = int(rest[0])
    except ValueError:
        return f"{book_display} {' '.join(rest)}", book_display, None, None

    if len(rest) == 1:
        return f"{book_display} {chapter}", book_display, chapter, None

    # Verses: can be "1-3", "1", "28-29", or "1_5" (meaning 1,5)
    verse_parts = rest[1:]
    if len(verse_parts) == 1:
        verses = verse_parts[0]
    else:
        # Multiple verse tokens — join with comma
        verses = ",".join(verse_parts)

    # Validate verses look like digits/hyphens/commas
    if re.fullmatch(r"[\d\-,]+", verses):
        return f"{book_display} {chapter}:{verses}", book_display, chapter, verses
    return f"{book_display} {chapter}:{verses}", book_display, chapter, verses


STREAMING_KEYS = ("youtube", "spotify", "apple_music", "amazon_music", "youtube_music")


def load_music_mdfiles() -> dict[str, dict]:
    """Read all _music/*.md frontmatter, keyed by lowercase slug.

    Returns {slug_lower: {"slug": original_slug, "streaming": {...}, ...}}.
    Case-insensitive lookup avoids issues like `thank-you-Jesus.md` vs
    slugified `thank-you-jesus`.
    """
    by_slug: dict[str, dict] = {}
    if not MUSIC_DIR.exists():
        return by_slug
    for p in MUSIC_DIR.glob("*.md"):
        if p.name.startswith("_"):
            continue
        slug = p.stem
        fm = _parse_frontmatter(p.read_text())
        streaming = {k: fm[k] for k in STREAMING_KEYS if fm.get(k)}
        by_slug[slug.lower()] = {
            "slug": slug,
            "streaming": streaming,
            "frontmatter": fm,
        }
    return by_slug


def _parse_frontmatter(text: str) -> dict:
    """Light frontmatter parser — reads YAML-like key: value lines between --- markers."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm_text = text[3:end].strip()
    out = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out


def parse_filename(filename: str) -> tuple[str, str, dict] | None:
    """Parse one .wav filename into (clean_title, raw_scripture_ref, flags).

    Returns None if the filename doesn't look like a song.
    """
    if not filename.startswith("Christian_Songs_"):
        return None
    stem = filename[len("Christian_Songs_"):]
    if stem.endswith(".wav"):
        stem = stem[:-4]

    # 1. Strip stem suffixes (backing / vocals / instrumental) — these indicate
    #    the file is a stem, not a standalone song.
    stem, stem_tag = strip_stem_suffix(stem)
    if stem_tag is not None:
        return None  # Skip stems entirely

    # 2. Find the "inspired_by" / "based_on" separator
    split = find_separator(stem)
    if split is None:
        # Fallback: look for a Bible book name directly (e.g., "Christ_in_Me_Galatians_2_20")
        tokens = stem.split("_")
        for i in range(1, len(tokens)):
            candidate = tokens[i]
            two = tokens[i] + "_" + tokens[i + 1] if i + 1 < len(tokens) else None
            if candidate in BIBLE_BOOKS or (two and two in BIBLE_BOOKS):
                left = "_".join(tokens[:i])
                right = "_".join(tokens[i:])
                split = (left, right)
                break
    if split is None:
        # Anomaly like "Love_Is_Not_Easy_inspired_by_" (empty ref) already
        # returns None here; flag in the return value.
        return None
    left, right = split

    # 3. Strip version suffix from the Scripture side (e.g. "..._v2")
    right_clean, version_tag = strip_version_suffix(right)

    # 4. Detect collaboration prefix on the left
    left, collab = detect_collaboration(left)

    # 5. Detect remix/korean
    left, is_remix, is_korean = detect_remix_or_korean(left)

    return left.strip("_"), right_clean.strip("_"), {
        "version_tag": version_tag,
        "collaboration": collab,
        "is_remix": is_remix,
        "is_korean": is_korean,
    }


def main():
    if not SONGS_DIR.exists():
        print(f"ERROR: Song folder not found: {SONGS_DIR}", file=sys.stderr)
        sys.exit(1)

    music_md = load_music_mdfiles()
    print(f"Found {len(music_md)} _music/*.md files for cross-reference")

    # Preserve already-tagged themes from a prior run, so this build script
    # is safely re-runnable without wiping tag_song_themes.py output.
    existing_themes_by_slug: dict[str, list] = {}
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH) as f:
                prior = json.load(f)
            for s in prior.get("songs", []):
                if s.get("themes"):
                    existing_themes_by_slug[s["slug"]] = s["themes"]
        except (OSError, json.JSONDecodeError):
            pass

    # Gather candidate files with mtime for newest-wins dedup
    candidates: dict[tuple, list[tuple[Path, dict, str]]] = {}
    skipped_stems = 0
    skipped_unparseable = 0
    anomalies: list[str] = []

    for wav in sorted(SONGS_DIR.glob("*.wav")):
        parsed = parse_filename(wav.name)
        if parsed is None:
            # Only flag if it started with Christian_Songs_ (real anomaly)
            if wav.name.startswith("Christian_Songs_"):
                # Differentiate stems from unparseable
                cleaned, stem_tag = strip_stem_suffix(wav.stem)
                if stem_tag:
                    skipped_stems += 1
                else:
                    skipped_unparseable += 1
                    anomalies.append(wav.name)
            continue

        left, right, flags = parsed

        # Skip files with an empty Scripture reference (filename like
        # "..._inspired_by_.wav" — unfinished artwork).
        if not right.strip("_ "):
            skipped_unparseable += 1
            anomalies.append(f"{wav.name} (empty scripture ref)")
            continue

        # Strip trailing punctuation from title (e.g. "Persist," from filename
        # "Persist, based on Galatians 6_9-10").
        left = re.sub(r"[,;:.\s]+$", "", left)

        title_slug = slugify(normalize(left))
        ref_slug = slugify(normalize(right))

        # Dedup key includes remix/korean flags so those stay as separate songs
        key = (title_slug, ref_slug, flags["is_remix"], flags["is_korean"])
        candidates.setdefault(key, []).append((wav, flags, left))

    songs: list[Song] = []
    for key, entries in sorted(candidates.items()):
        # Pick the latest by mtime (so _v2 wins over original automatically)
        entries.sort(key=lambda e: e[0].stat().st_mtime, reverse=True)
        chosen, flags, left_raw = entries[0]
        variants = [e[0].name for e in entries[1:]]

        title = normalize(left_raw)
        if flags["is_remix"]:
            title += " (Remix)"
        if flags["is_korean"]:
            title += " (Korean)"

        right_raw = parse_filename(chosen.name)[1]
        display_ref, book, chapter, verses = parse_scripture_ref(right_raw)

        base_slug = key[0]
        full_slug = base_slug
        if flags["is_remix"]:
            full_slug += "-remix"
        if flags["is_korean"]:
            full_slug += "-ko"

        # Match to _music/*.md (case-insensitive). A matching entry means
        # the song is publicly released on at least one platform.
        md_candidate = music_md.get(full_slug.lower()) or music_md.get(base_slug.lower())
        if md_candidate is None and flags["is_remix"]:
            # Fallback: try a version-dated slug like "be-still-rmx20250501"
            for cand_slug in music_md:
                if cand_slug.startswith(base_slug.lower() + "-rmx"):
                    md_candidate = music_md[cand_slug]
                    break

        streaming = md_candidate["streaming"] if md_candidate else {}
        is_released = md_candidate is not None

        songs.append(
            Song(
                slug=full_slug,
                title=title,
                scripture_ref=display_ref,
                scripture_book=book,
                scripture_chapter=chapter,
                scripture_verses=verses,
                source_wav=chosen.name,
                is_released=is_released,
                streaming=streaming,
                collaboration=flags["collaboration"],
                is_remix=flags["is_remix"],
                is_korean=flags["is_korean"],
                variant_files=variants,
                themes=existing_themes_by_slug.get(full_slug, []),
            )
        )

    # Sort songs by title (case-insensitive)
    songs.sort(key=lambda s: s.title.lower())

    # Build artist search URLs (no per-song maintenance required)
    artist_search = {
        "youtube": "https://www.youtube.com/@JNSKM",
        "youtube_music": "https://music.youtube.com/search?q=JNSKM",
        "spotify": "https://open.spotify.com/search/JNSKM/artists",
        "apple_music": "https://music.apple.com/search?term=JNSKM",
        "amazon_music": "https://music.amazon.com/search/JNSKM",
    }

    output = {
        "total_songs": len(songs),
        "artist_search": artist_search,
        "songs": [asdict(s) for s in songs],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(songs)} songs to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  Skipped {skipped_stems} stem files (backing/vocals/instrumental)")
    if anomalies:
        print(f"  Anomalies (couldn't parse scripture ref): {len(anomalies)}")
        for a in anomalies:
            print(f"    {a}")

    # Quick summary
    released = [s for s in songs if s.is_released]
    unreleased = [s for s in songs if not s.is_released]
    with_yt = sum(1 for s in released if s.streaming.get("youtube"))
    with_multi = sum(
        1 for s in released if sum(1 for k in STREAMING_KEYS if s.streaming.get(k)) >= 2
    )
    print(f"  Released (matched _music/*.md): {len(released)}")
    print(f"    with YouTube URL: {with_yt}")
    print(f"    with 2+ streaming platforms: {with_multi}")
    print(f"  Unreleased (no _music/*.md match, excluded from visitor library): {len(unreleased)}")
    remixes = sum(1 for s in songs if s.is_remix)
    korean = sum(1 for s in songs if s.is_korean)
    collabs = sum(1 for s in songs if s.collaboration)
    print(f"  Remixes: {remixes}, Korean: {korean}, Collaborations: {collabs}")

    # Top Scripture books referenced
    from collections import Counter
    books = Counter(s.scripture_book for s in songs if s.scripture_book)
    print(f"  Top Scripture books:")
    for b, n in books.most_common(10):
        print(f"    {b}: {n}")


if __name__ == "__main__":
    main()
