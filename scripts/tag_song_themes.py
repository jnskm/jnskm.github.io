#!/usr/bin/env python3
"""
Tag released songs with emotional/spiritual themes using Claude Sonnet 4.6.

Reads data/library/songs.json, sends all released songs with metadata
(title, scripture ref, lyrics/inspiration from _music/*.md if present)
to Claude, and writes themes back into the same songs.json.

Usage:
    python3 scripts/tag_song_themes.py
"""

import json
import os
import re
import sys
from pathlib import Path

from anthropic import Anthropic

REPO_ROOT = Path(__file__).parent.parent
SONGS_JSON = REPO_ROOT / "data" / "library" / "songs.json"
MUSIC_DIR = REPO_ROOT / "_music"
PROMPT_PATH = REPO_ROOT / "scripts" / "prompts" / "tag_songs.system.md"
MODEL = "claude-sonnet-4-6"


def load_env():
    for name in (".env", ".env.local"):
        path = REPO_ROOT / name
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if v:
                    os.environ[k] = v


def read_system_prompt() -> str:
    with open(PROMPT_PATH) as f:
        text = f.read()
    lines = text.split("\n")
    sep = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    return "\n".join(lines[sep + 1:]).strip() if sep is not None else text.strip()


def read_md_body(slug: str) -> str:
    """Return inspiration + lyrics body from _music/<slug>.md, or empty string."""
    p = MUSIC_DIR / f"{slug}.md"
    if not p.exists():
        return ""
    text = p.read_text()
    # Strip frontmatter
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            text = text[end + 4:]
    # Drop placeholder stubs
    text = re.sub(r"\(Add [^)]*\)", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]  # cap per-song context


def build_user_message(songs: list[dict]) -> str:
    parts = [f"Tag themes for these {len(songs)} songs.", ""]
    for s in songs:
        parts.append(f'<song slug="{s["slug"]}">')
        parts.append(f'Title: {s["title"]}')
        parts.append(f'Scripture: {s["scripture_ref"]}')
        if s.get("collaboration"):
            parts.append(f'Collaboration: {s["collaboration"]}')
        body = read_md_body(s["slug"])
        if body:
            parts.append("Context:")
            parts.append(body)
        parts.append("</song>")
        parts.append("")
    return "\n".join(parts)


def _extract_json_array(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        after_open = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if after_open.rstrip().endswith("```"):
            after_open = after_open.rstrip()[:-3]
        raw = after_open.strip()
    return raw


def main():
    load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found", file=sys.stderr)
        sys.exit(1)

    with open(SONGS_JSON) as f:
        data = json.load(f)

    released = [s for s in data["songs"] if s.get("is_released")]
    print(f"Tagging {len(released)} released songs with Claude ...")

    system_prompt = read_system_prompt()
    user_msg = build_user_message(released)

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    try:
        classifications = json.loads(_extract_json_array(raw))
    except json.JSONDecodeError:
        print(f"JSON parse failed. Raw response:\n{raw[:500]}", file=sys.stderr)
        raise

    by_slug = {c["slug"]: c["themes"] for c in classifications}
    missing = 0
    for s in data["songs"]:
        if not s.get("is_released"):
            continue
        if s["slug"] in by_slug:
            s["themes"] = by_slug[s["slug"]]
        else:
            s["themes"] = []
            missing += 1

    with open(SONGS_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    usage = response.usage
    cost = (
        usage.input_tokens * 3.0 / 1_000_000
        + usage.output_tokens * 15.0 / 1_000_000
    )
    print(f"Tagged {len(classifications)}/{len(released)} songs")
    if missing:
        print(f"  WARNING: {missing} songs got no themes")
    print(f"  tokens: in={usage.input_tokens} out={usage.output_tokens}  cost=${cost:.4f}")

    # Theme distribution summary
    from collections import Counter
    tc = Counter()
    for s in data["songs"]:
        if s.get("is_released"):
            tc.update(s.get("themes", []))
    print("Theme distribution:")
    for t, n in tc.most_common():
        print(f"  {t:15s} {n}")


if __name__ == "__main__":
    main()
