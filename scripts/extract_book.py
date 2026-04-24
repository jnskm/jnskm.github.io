#!/usr/bin/env python3
"""
Extract book PDFs into paragraph-level JSON chunks for the jnskm.com
"Stay a moment" encouragement library.

Each chunk is ~80-180 words of connected prose, tagged with book slug,
lesson number (when detectable), lesson title, page, and word count.
Chunks respect paragraph and lesson boundaries; no mid-sentence splits.

Usage:
    python3 scripts/extract_book.py               # Extract every book in the manifest
    python3 scripts/extract_book.py 01-sit-stay-preach   # Extract one book by slug
    python3 scripts/extract_book.py --list        # List manifest entries

Output: data/library/books/<slug>.json
"""

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import pdfplumber
import yaml

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = REPO_ROOT / "scripts" / "books_manifest.yml"
OUTPUT_DIR = REPO_ROOT / "data" / "library" / "books"

TARGET_MIN_WORDS = 80
TARGET_MAX_WORDS = 180
HARD_MIN_WORDS = 40   # chunks below this are dropped as fragments
HARD_MAX_WORDS = 260  # chunks above this get sentence-split

# pdfplumber collapses paragraph gaps into single newlines in extract_text(),
# so we use extract_text_lines() and detect paragraph breaks via y-gap.
# In the Tails of Grace PDFs, within-paragraph line gaps are ~2.2pt while
# between-paragraph gaps are ~18-20pt. A threshold of 8pt safely separates them.
PARAGRAPH_GAP_THRESHOLD = 8.0

LESSON_HEADING_RE = re.compile(r"^\s*Lesson\s+(\d+)\s*:?\s*$", re.IGNORECASE)
PAGE_FOOTER_RE = re.compile(r"^\s*Page\s+\d+\s*$")
# Front/back-matter section headings we want to mark as non-lesson context
NONLESSON_HEADINGS = {
    "introduction",
    "last thoughts",
    "about the authors",
    "about the author",
    "acknowledgments",
    "acknowledgements",
    "preface",
    "foreword",
    "dedication",
}


@dataclass
class Chunk:
    id: str
    lesson_number: Optional[int]
    lesson_title: Optional[str]
    section: Optional[str]  # e.g. "introduction", "last thoughts" for non-lesson chunks
    page: int
    word_count: int
    text: str


def load_manifest() -> dict:
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)


def word_count(text: str) -> int:
    return len(text.split())


def normalize_paragraph(text: str) -> str:
    """Collapse internal whitespace and newlines into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def extract_page_paragraphs(page) -> list[str]:
    """Return paragraph-level strings for a page using line-level y-gap detection.

    pdfplumber's extract_text() collapses paragraph breaks into single newlines,
    so we use extract_text_lines() and group consecutive lines whose vertical
    gap is below PARAGRAPH_GAP_THRESHOLD. The "Page N" footer is filtered.
    """
    lines = page.extract_text_lines() or []
    # Drop page-number footers
    lines = [l for l in lines if not PAGE_FOOTER_RE.match(l["text"])]
    if not lines:
        return []

    paragraphs: list[str] = []
    current: list[str] = [lines[0]["text"]]
    prev_bottom = lines[0]["bottom"]
    for line in lines[1:]:
        gap = line["top"] - prev_bottom
        if gap > PARAGRAPH_GAP_THRESHOLD:
            paragraphs.append(normalize_paragraph(" ".join(current)))
            current = [line["text"]]
        else:
            current.append(line["text"])
        prev_bottom = line["bottom"]
    if current:
        paragraphs.append(normalize_paragraph(" ".join(current)))
    return [p for p in paragraphs if p]


# Match "Lesson N:" as a prefix within a paragraph (heading paragraphs group
# the lesson number + title + subtitle into one paragraph via gap detection).
LESSON_PREFIX_RE = re.compile(r"^Lesson\s+(\d+)\s*:?\s+(.+)$", re.IGNORECASE)


def detect_page_context(paragraphs: list[str]) -> tuple[Optional[int], Optional[str], Optional[str], int]:
    """Detect whether this page opens a new lesson or a named section.

    Returns (lesson_number, lesson_title, section_name, heading_paragraphs_consumed).
    The consumer uses heading_paragraphs_consumed to skip heading paragraphs
    before chunking body content.
    """
    if not paragraphs:
        return None, None, None, 0

    first = paragraphs[0].strip()

    # Lesson heading: "Lesson N: <title> [<subtitle>]" on one grouped paragraph
    lesson_match = LESSON_PREFIX_RE.match(first)
    if lesson_match:
        lesson_number = int(lesson_match.group(1))
        title_and_sub = lesson_match.group(2).strip()
        # Keep the whole title + subtitle string; the filter pass can clean up.
        return lesson_number, title_and_sub, None, 1

    # Front/back-matter section heading as its own short paragraph
    first_lc = first.lower().rstrip(":.")
    if first_lc in NONLESSON_HEADINGS:
        return None, None, first_lc, 1

    return None, None, None, 0


def greedy_chunk(paragraphs: list[str]) -> list[str]:
    """Combine paragraphs into ~80-180 word chunks on paragraph boundaries.

    Greedy: start with the first paragraph, keep adding following paragraphs
    while total word count is under TARGET_MIN. Stop adding once we're in the
    target band. Single paragraphs larger than HARD_MAX get sentence-split.
    """
    if not paragraphs:
        return []

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_wc = 0

    def flush():
        nonlocal buffer, buffer_wc
        if buffer:
            merged = " ".join(buffer).strip()
            if word_count(merged) >= HARD_MIN_WORDS:
                chunks.append(merged)
        buffer = []
        buffer_wc = 0

    for para in paragraphs:
        pwc = word_count(para)

        # Oversized single paragraph — sentence-split it
        if pwc > HARD_MAX_WORDS:
            flush()
            chunks.extend(_sentence_split(para))
            continue

        if buffer_wc + pwc <= TARGET_MAX_WORDS:
            buffer.append(para)
            buffer_wc += pwc
            if buffer_wc >= TARGET_MIN_WORDS:
                flush()
        else:
            # Adding this paragraph would overflow — flush current and start new
            flush()
            buffer.append(para)
            buffer_wc = pwc
            if buffer_wc >= TARGET_MIN_WORDS:
                flush()

    flush()
    return chunks


def _sentence_split(text: str) -> list[str]:
    """Split an oversized paragraph into sentence-aligned target-size chunks."""
    # Simple sentence splitter on ., !, ? followed by space + capital
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text)
    result: list[str] = []
    buffer: list[str] = []
    buffer_wc = 0
    for s in sentences:
        swc = word_count(s)
        if buffer_wc + swc > TARGET_MAX_WORDS and buffer:
            result.append(" ".join(buffer).strip())
            buffer, buffer_wc = [s], swc
        else:
            buffer.append(s)
            buffer_wc += swc
    if buffer and buffer_wc >= HARD_MIN_WORDS:
        result.append(" ".join(buffer).strip())
    return result


def _merges_into_previous(first_paragraph: str) -> bool:
    """Heuristic: a paragraph starting with a lowercase letter is continuing
    the previous page's paragraph."""
    stripped = first_paragraph.lstrip()
    return bool(stripped) and stripped[0].islower()


def extract_book(book_config: dict, books_root: Path) -> dict:
    """Extract one book into the library JSON structure."""
    pdf_path = books_root / book_config["source_pdf"]
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    slug = book_config["slug"]

    # First pass: gather paragraph-level data per page with context tracking.
    # We record each paragraph with its lesson/section context, then chunk
    # after handling cross-page paragraph continuations.
    @dataclass
    class Paragraph:
        text: str
        page: int
        lesson_number: Optional[int]
        lesson_title: Optional[str]
        section: Optional[str]

    all_paragraphs: list[Paragraph] = []
    current_lesson_number: Optional[int] = None
    current_lesson_title: Optional[str] = None
    current_section: Optional[str] = None

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_index, page in enumerate(pdf.pages):
            page_num = page_index + 1
            page_paragraphs = extract_page_paragraphs(page)
            if not page_paragraphs:
                continue

            new_lesson, new_title, new_section, consumed = detect_page_context(page_paragraphs)
            if new_lesson is not None:
                current_lesson_number = new_lesson
                current_lesson_title = new_title
                current_section = None
            elif new_section is not None:
                current_lesson_number = None
                current_lesson_title = None
                current_section = new_section

            body_paragraphs = page_paragraphs[consumed:]
            if not body_paragraphs:
                continue

            # Handle cross-page continuation: if first body paragraph starts
            # lowercase, merge it into the last paragraph of the prior page.
            if (
                all_paragraphs
                and consumed == 0  # only non-heading pages continue
                and _merges_into_previous(body_paragraphs[0])
                and all_paragraphs[-1].lesson_number == current_lesson_number
                and all_paragraphs[-1].section == current_section
            ):
                all_paragraphs[-1].text = (
                    all_paragraphs[-1].text + " " + body_paragraphs[0]
                ).strip()
                body_paragraphs = body_paragraphs[1:]

            for para_text in body_paragraphs:
                all_paragraphs.append(
                    Paragraph(
                        text=para_text,
                        page=page_num,
                        lesson_number=current_lesson_number,
                        lesson_title=current_lesson_title,
                        section=current_section,
                    )
                )

    # Second pass: chunk paragraphs, respecting lesson/section boundaries.
    chunks: list[Chunk] = []
    chunk_counter = 0
    i = 0
    while i < len(all_paragraphs):
        # Group consecutive paragraphs sharing the same lesson/section context
        group_start = i
        ctx = (
            all_paragraphs[i].lesson_number,
            all_paragraphs[i].section,
        )
        while (
            i < len(all_paragraphs)
            and (all_paragraphs[i].lesson_number, all_paragraphs[i].section) == ctx
        ):
            i += 1
        group = all_paragraphs[group_start:i]

        for chunk_text in greedy_chunk([p.text for p in group]):
            chunk_counter += 1
            # Attribute the chunk to the first page among the paragraphs
            # whose text appears in the chunk (use group's first page as an
            # approximation — good enough for citation).
            chunks.append(
                Chunk(
                    id=f"{slug}-{chunk_counter:03d}",
                    lesson_number=group[0].lesson_number,
                    lesson_title=group[0].lesson_title,
                    section=group[0].section,
                    page=_infer_chunk_page(chunk_text, group),
                    word_count=word_count(chunk_text),
                    text=chunk_text,
                )
            )

    return {
        "book_id": slug,
        "title": book_config["title"],
        "subtitle": book_config.get("subtitle", ""),
        "authors": book_config.get("authors", []),
        "source_pdf": book_config["source_pdf"],
        "cover_image": book_config.get("cover_image", ""),
        "amazon_url": book_config.get("amazon_url", ""),
        "total_pages": total_pages,
        "total_chunks": len(chunks),
        "chunks": [asdict(c) for c in chunks],
    }


def _infer_chunk_page(chunk_text: str, group) -> int:
    """Find the page of the first paragraph whose opening words start the chunk."""
    chunk_head = chunk_text[:40]
    for p in group:
        if p.text[:40] == chunk_head or chunk_head.startswith(p.text[:30]):
            return p.page
    return group[0].page


def write_book_json(book_data: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{book_data['book_id']}.json"
    with open(out_path, "w") as f:
        json.dump(book_data, f, indent=2, ensure_ascii=False)
    return out_path


def list_books(manifest: dict):
    print(f"Books in manifest ({len(manifest['books'])}):")
    for b in manifest["books"]:
        print(f"  {b['slug']:45s}  {b['title']}")


def main():
    manifest = load_manifest()
    books_root = Path(manifest["books_root"]).expanduser()

    args = sys.argv[1:]
    if "--list" in args:
        list_books(manifest)
        return

    if args:
        requested = set(args)
        targets = [b for b in manifest["books"] if b["slug"] in requested]
        missing = requested - {b["slug"] for b in targets}
        if missing:
            print(f"Unknown slugs: {', '.join(sorted(missing))}", file=sys.stderr)
            print("Run with --list to see available slugs.", file=sys.stderr)
            sys.exit(1)
    else:
        targets = manifest["books"]

    for book_config in targets:
        print(f"Extracting {book_config['slug']} ...", end=" ", flush=True)
        try:
            book_data = extract_book(book_config, books_root)
            out_path = write_book_json(book_data)
            print(
                f"{book_data['total_chunks']} chunks from {book_data['total_pages']} pages "
                f"→ {out_path.relative_to(REPO_ROOT)}"
            )
        except Exception as e:
            print(f"FAILED: {e}")
            raise


if __name__ == "__main__":
    main()
