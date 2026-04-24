#!/usr/bin/env python3
"""
Split merged lesson titles into {title, subtitle} using Claude Haiku 4.5.

The extract_book.py script groups a lesson's heading lines into one
paragraph (e.g. "Faithful in the Shade Learning to Stay Close"). This
script asks Haiku to cleanly split every unique lesson title found
across all book JSONs into title + subtitle, then rewrites the book
JSONs in place with `lesson_title` (short) and `lesson_subtitle` (the
descriptive second line) fields.

Usage:
    python3 scripts/split_lesson_titles.py
"""

import json
import os
import re
import sys
from pathlib import Path

from anthropic import Anthropic

REPO_ROOT = Path(__file__).parent.parent
LIBRARY_DIR = REPO_ROOT / "data" / "library" / "books"
MODEL = "claude-sonnet-4-6"  # Sonnet for consistency (Haiku dropped ~half the subtitles on the first run)

SYSTEM_PROMPT = """You are splitting book lesson titles from the Tails of Grace series into two parts: a short title and a descriptive subtitle.

Each input has the title and subtitle jammed together because they were extracted from a PDF. Your job: identify where the short title ends and the descriptive subtitle begins.

Examples:
- "Faithful in the Shade Learning to Stay Close" → title: "Faithful in the Shade", subtitle: "Learning to Stay Close"
- "Still Welcome on the Porch" → title: "Still Welcome on the Porch", subtitle: null (no subtitle)
- "The Burden Bearer The Weight of Being Good" → title: "The Burden Bearer", subtitle: "The Weight of Being Good"
- "Rest Without Guilt Rest is not the reward — it's the rhythm." → title: "Rest Without Guilt", subtitle: "Rest is not the reward — it's the rhythm."
- "The Expected Shepherd Identitiy Crisis: 'Am I Called or Just Expected?'" → title: "The Expected Shepherd", subtitle: "Identity Crisis: 'Am I Called or Just Expected?'" (fix obvious typos)

Rules:
- The title is always a short phrase (2-7 words), often starting with "The" or a verb.
- The subtitle (when present) is the rest — typically a sentence or phrase starting with a new capital letter, "Learning", "On", "Why", "How", "When", etc.
- Some titles have no subtitle (rare). Return subtitle: null in that case.
- Fix obvious typos in the subtitle (e.g. "Identitiy" → "Identity") but do NOT paraphrase or add anything.
- Preserve the original punctuation and capitalization otherwise.

Return a JSON array only — no prose, no markdown, no code fences — one object per input, same order:

[
  {"input": "Faithful in the Shade Learning to Stay Close", "title": "Faithful in the Shade", "subtitle": "Learning to Stay Close"},
  {"input": "Still Welcome on the Porch", "title": "Still Welcome on the Porch", "subtitle": null},
  ...
]

Every input must appear in your output with the same `input` string."""


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

    # Collect all unique lesson titles across all book JSONs
    unique_titles: set[str] = set()
    book_files = sorted(LIBRARY_DIR.glob("*.json"))
    for p in book_files:
        with open(p) as f:
            data = json.load(f)
        for c in data["chunks"]:
            t = c.get("lesson_title")
            if t:
                unique_titles.add(t)

    titles = sorted(unique_titles)
    print(f"Splitting {len(titles)} unique lesson titles with Haiku ...")

    user_msg = "Split these titles:\n\n" + "\n".join(f"- {t}" for t in titles)

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    try:
        splits = json.loads(_extract_json_array(raw))
    except json.JSONDecodeError:
        print(f"JSON parse failed. Raw:\n{raw[:500]}", file=sys.stderr)
        raise

    def normalize(s: str) -> str:
        """Quote/dash normalization for fuzzy dict matching."""
        if not s:
            return ""
        return (
            s.replace("\u2019", "'")
            .replace("\u2018", "'")
            .replace("\u201C", '"')
            .replace("\u201D", '"')
            .replace("\u2014", "-")
            .replace("\u2013", "-")
            .strip()
        )

    by_input = {normalize(s["input"]): s for s in splits}
    missing = [t for t in titles if normalize(t) not in by_input]
    if missing:
        print(f"WARNING: {len(missing)} titles missing from response:")
        for t in missing:
            print(f"  {t!r}")

    # Apply to each book JSON
    for p in book_files:
        with open(p) as f:
            data = json.load(f)
        updated = 0
        for c in data["chunks"]:
            t = c.get("lesson_title")
            if t and normalize(t) in by_input:
                split = by_input[normalize(t)]
                c["lesson_title"] = split["title"]
                c["lesson_subtitle"] = split.get("subtitle")
                updated += 1
        with open(p, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  {data['book_id']}: updated {updated} chunks")

    usage = response.usage
    cost = (
        usage.input_tokens * 3.0 / 1_000_000     # Sonnet 4.6 input rate
        + usage.output_tokens * 15.0 / 1_000_000 # Sonnet 4.6 output rate
    )
    print(f"\nTokens: in={usage.input_tokens} out={usage.output_tokens}  cost=${cost:.4f}")


if __name__ == "__main__":
    main()
