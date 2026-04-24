#!/usr/bin/env python3
"""
Filter and theme-tag book chunks using Claude Sonnet 4.6.

Reads every `data/library/books/<slug>.json` produced by extract_book.py,
sends each book's chunks through Claude with the system prompt in
scripts/prompts/filter_chunks.system.md, and writes classifications back
into the same JSON files (adding `keep` and `themes` fields per chunk).

Also produces a per-book markdown review file at
`data/library/review/<slug>.md` showing all kept chunks grouped by lesson,
plus a short list of dropped chunks for spot-check.

Usage:
    python3 scripts/filter_chunks.py                      # all books
    python3 scripts/filter_chunks.py 01-sit-stay-preach   # one book by slug
"""

import json
import os
import sys
from pathlib import Path

from anthropic import Anthropic

REPO_ROOT = Path(__file__).parent.parent
LIBRARY_DIR = REPO_ROOT / "data" / "library" / "books"
REVIEW_DIR = REPO_ROOT / "data" / "library" / "review"
PROMPT_PATH = REPO_ROOT / "scripts" / "prompts" / "filter_chunks.system.md"
MODEL = "claude-sonnet-4-6"
MAX_OUTPUT_TOKENS = 16000


def load_env():
    """Load .env then .env.local into os.environ (.env.local wins)."""
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
    """Return the body of the prompt file (content after the first `---` line)."""
    with open(PROMPT_PATH) as f:
        text = f.read()
    lines = text.split("\n")
    sep_idx = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    if sep_idx is None:
        return text.strip()
    return "\n".join(lines[sep_idx + 1:]).strip()


def build_user_message(book_data: dict) -> str:
    header = f"Book: {book_data['title']}"
    if book_data.get("subtitle"):
        header += f" — {book_data['subtitle']}"
    parts = [
        header,
        "",
        f"Chunks to classify ({len(book_data['chunks'])} total):",
        "",
    ]
    for c in book_data["chunks"]:
        if c["lesson_number"]:
            context = f"Lesson {c['lesson_number']}"
        elif c.get("section"):
            context = c["section"]
        else:
            context = "Front/back matter"
        parts.append(f'<chunk id="{c["id"]}" context="{context}" page="{c["page"]}">')
        parts.append(c["text"])
        parts.append("</chunk>")
        parts.append("")
    return "\n".join(parts)


def _extract_json_array(raw: str) -> str:
    """Strip code-fence wrapping if Claude returned ```json ... ``` despite instructions."""
    raw = raw.strip()
    if raw.startswith("```"):
        after_open = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if after_open.rstrip().endswith("```"):
            after_open = after_open.rstrip()[:-3]
        raw = after_open.strip()
    return raw


def filter_book(client: Anthropic, book_path: Path, system_prompt: str) -> dict:
    with open(book_path) as f:
        data = json.load(f)

    user_msg = build_user_message(data)

    print(f"  calling Claude for {len(data['chunks'])} chunks ...", flush=True)
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
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
    except json.JSONDecodeError as exc:
        print(f"  JSON parse failed. Raw response starts with:\n    {raw[:300]}", file=sys.stderr)
        raise exc

    by_id = {c["id"]: c for c in classifications}

    kept = 0
    missing = 0
    for chunk in data["chunks"]:
        cid = chunk["id"]
        if cid in by_id:
            cls = by_id[cid]
            chunk["keep"] = bool(cls.get("keep"))
            chunk["themes"] = list(cls.get("themes") or [])
            if chunk["keep"]:
                kept += 1
        else:
            chunk["keep"] = False
            chunk["themes"] = []
            chunk["filter_missing"] = True
            missing += 1

    with open(book_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    usage = response.usage
    return {
        "book_id": data["book_id"],
        "title": data["title"],
        "total": len(data["chunks"]),
        "kept": kept,
        "dropped": len(data["chunks"]) - kept,
        "missing": missing,
        "input_tokens": usage.input_tokens,
        "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "output_tokens": usage.output_tokens,
    }


def write_review_md(book_path: Path) -> Path:
    with open(book_path) as f:
        data = json.load(f)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REVIEW_DIR / f"{data['book_id']}.md"

    kept_chunks = [c for c in data["chunks"] if c.get("keep")]
    dropped_chunks = [c for c in data["chunks"] if not c.get("keep")]

    lines: list[str] = [
        f"# Review — {data['title']}",
        "",
        f"Source PDF: `{data['source_pdf']}`",
        "",
        f"**{len(kept_chunks)} kept / {len(dropped_chunks)} dropped** (of {len(data['chunks'])} extracted chunks).",
        "",
        "## How to review",
        "",
        "- Kept excerpts are below, grouped by lesson.",
        "- If a kept excerpt shouldn't be in the library, add the line `DROP` immediately after its id/header, then re-run the build.",
        "- Dropped chunks are listed in brief at the bottom. If any should be kept, note the id.",
        "",
        "---",
        "",
        "## Kept",
        "",
    ]

    # Group key: integer lesson_number for lessons, or a string like
    # "intro"/"last"/"other" for non-lesson chunks so they get their own sections.
    def group_key(c):
        if c["lesson_number"] is not None:
            return c["lesson_number"]
        sec = (c.get("section") or "").lower()
        if sec == "introduction":
            return "__intro__"
        if sec == "last thoughts":
            return "__last__"
        return "__other__"

    def sort_key(k):
        # Intro first, then lessons in order, then Last Thoughts, then other
        if k == "__intro__":
            return (0, 0)
        if isinstance(k, int):
            return (1, k)
        if k == "__last__":
            return (2, 0)
        return (3, 0)

    by_group: dict = {}
    for c in kept_chunks:
        by_group.setdefault(group_key(c), []).append(c)

    for gkey in sorted(by_group.keys(), key=sort_key):
        chunks_here = by_group[gkey]
        if gkey == "__intro__":
            lines.append("### Introduction")
        elif gkey == "__last__":
            lines.append("### Last Thoughts")
        elif gkey == "__other__":
            lines.append("### Other")  # should be empty post-frontback-filter
        else:
            title = chunks_here[0].get("lesson_title") or ""
            subtitle = chunks_here[0].get("lesson_subtitle")
            heading = f"### Lesson {gkey}: {title}"
            if subtitle:
                heading += f" — *{subtitle}*"
            lines.append(heading)
        lines.append("")
        for c in chunks_here:
            themes = ", ".join(c.get("themes") or [])
            lines.append(f"**[{c['id']}]** · page {c['page']} · {c['word_count']}w · _{themes}_")
            lines.append("")
            lines.append(c["text"])
            lines.append("")
            lines.append("---")
            lines.append("")

    if dropped_chunks:
        lines.append("")
        lines.append(f"## Dropped ({len(dropped_chunks)})")
        lines.append("")
        lines.append("Brief list — skim for anything that should have been kept.")
        lines.append("")
        for c in dropped_chunks:
            if c["lesson_number"]:
                where = f"L{c['lesson_number']}"
            elif c.get("section"):
                where = c["section"]
            else:
                where = "front/back"
            preview = " ".join(c["text"].split())[:140]
            lines.append(f"- **[{c['id']}]** p{c['page']} {where} {c['word_count']}w: {preview}...")

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return out_path


def main():
    load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in .env or .env.local", file=sys.stderr)
        sys.exit(1)

    system_prompt = read_system_prompt()
    print(f"System prompt: {len(system_prompt)} chars")

    client = Anthropic(api_key=api_key)

    args = sys.argv[1:]
    if args:
        targets = [LIBRARY_DIR / f"{a}.json" for a in args]
        for t in targets:
            if not t.exists():
                print(f"ERROR: {t} not found", file=sys.stderr)
                sys.exit(1)
    else:
        targets = sorted(LIBRARY_DIR.glob("*.json"))

    results = []
    for path in targets:
        print(f"Filtering {path.stem} ...")
        result = filter_book(client, path, system_prompt)
        review_path = write_review_md(path)
        msg = f"  kept {result['kept']}/{result['total']}"
        if result["missing"]:
            msg += f" (WARNING: {result['missing']} missing classifications)"
        msg += f" → {review_path.relative_to(REPO_ROOT)}"
        print(msg)
        results.append(result)

    print()
    print("=" * 96)
    header = f'{"book":45s}  {"kept/total":12s}  {"in":>8s}  {"cache_w":>8s}  {"cache_r":>8s}  {"out":>6s}'
    print(header)
    print("-" * 96)
    totals = {"kept": 0, "total": 0, "in": 0, "cw": 0, "cr": 0, "out": 0}
    for r in results:
        print(
            f'{r["book_id"]:45s}  {r["kept"]:4d}/{r["total"]:4d}    '
            f'{r["input_tokens"]:8d}  {r["cache_creation_tokens"]:8d}  '
            f'{r["cache_read_tokens"]:8d}  {r["output_tokens"]:6d}'
        )
        totals["kept"] += r["kept"]
        totals["total"] += r["total"]
        totals["in"] += r["input_tokens"]
        totals["cw"] += r["cache_creation_tokens"]
        totals["cr"] += r["cache_read_tokens"]
        totals["out"] += r["output_tokens"]
    print("-" * 96)
    print(
        f'{"TOTAL":45s}  {totals["kept"]:4d}/{totals["total"]:4d}    '
        f'{totals["in"]:8d}  {totals["cw"]:8d}  {totals["cr"]:8d}  {totals["out"]:6d}'
    )

    cost = (
        totals["in"] * 3.0 / 1_000_000
        + totals["cw"] * 3.75 / 1_000_000
        + totals["cr"] * 0.30 / 1_000_000
        + totals["out"] * 15.0 / 1_000_000
    )
    print(f"Estimated cost (Sonnet 4.6 at $3/$15 per M with caching): ${cost:.4f}")


if __name__ == "__main__":
    main()
