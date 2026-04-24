#!/usr/bin/env python3
"""
Apply the "Lessons + Introduction + Last Thoughts only" policy.

For every chunk in data/library/books/*.json:
- Keep only if `lesson_number` is set, OR `section` is 'introduction'
  or 'last thoughts'.
- Otherwise, force keep=false and record why in `keep_override`.

Writes book JSONs in place. Caller should follow with:
    python3 scripts/build_library.py

Usage:
    python3 scripts/apply_frontback_filter.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from filter_chunks import write_review_md  # reuse existing markdown builder

REPO_ROOT = Path(__file__).parent.parent
BOOKS_DIR = REPO_ROOT / "data" / "library" / "books"

ALLOWED_SECTIONS = {"introduction", "last thoughts"}


def is_eligible(chunk: dict) -> bool:
    if chunk.get("lesson_number") is not None:
        return True
    if chunk.get("section") in ALLOWED_SECTIONS:
        return True
    return False


def main():
    total_dropped = 0
    per_book: list[tuple[str, int]] = []

    for p in sorted(BOOKS_DIR.glob("*.json")):
        with open(p) as f:
            data = json.load(f)

        dropped = 0
        for c in data["chunks"]:
            if c.get("keep") and not is_eligible(c):
                c["keep"] = False
                c["keep_override"] = "front-back-matter"
                dropped += 1

        with open(p, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Regenerate review markdown so the review experience stays in sync
        write_review_md(p)

        per_book.append((data["book_id"], dropped))
        total_dropped += dropped

    print("Applied Lesson/Introduction/LastThoughts-only rule:")
    print()
    print(f"{'book':45s}  dropped")
    print("-" * 56)
    for bid, n in per_book:
        print(f"{bid:45s}  {n}")
    print("-" * 56)
    print(f"{'TOTAL dropped':45s}  {total_dropped}")
    print()
    print("Review markdown files regenerated at data/library/review/*.md")
    print("Now run: python3 scripts/build_library.py")


if __name__ == "__main__":
    main()
