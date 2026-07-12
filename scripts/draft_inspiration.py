#!/usr/bin/env python3
"""
Propose a draft "Inspiration" for a song, from its lyrics + the Scripture
that inspired it.

    AI PROPOSES, THE SONGWRITER APPROVES.

This never touches a song's published Inspiration. Proposals are written to
drafts/inspiration/ (git-ignored, excluded from the Jekyll build) for the
writer to read, edit into their own voice, and paste in by hand.

Pipeline per song: extract lyrics -> find the inspiring Scripture -> draft.

Usage:
  python scripts/draft_inspiration.py <slug> [<slug> ...]
  python scripts/draft_inspiration.py --all           # every eligible song
  python scripts/draft_inspiration.py --all --list    # just show eligibility

Eligibility: the song has REAL lyrics (not the template placeholder) and its
Inspiration is still open (empty, placeholder, or a bare verse with no
reflection).

With ANTHROPIC_API_KEY set, calls Claude and writes drafts/inspiration/<slug>.md.
Without a key, writes drafts/inspiration/<slug>.prompt.md (system + user prompt)
so you can run it through Claude yourself.
"""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MUSIC_DIR = REPO_ROOT / "_music"
DRAFTS_DIR = REPO_ROOT / "drafts" / "inspiration"
SYSTEM_PROMPT_FILE = Path(__file__).parent / "prompts" / "inspiration.system.md"

MODEL = os.environ.get("INSPIRATION_MODEL", "claude-opus-4-8")
LYRIC_PLACEHOLDER = "(Add lyrics here)"
INSPIRATION_PLACEHOLDER = "Add inspiration"


def split_front_matter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Minimal — only the keys we need."""
    fm = {}
    body = text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            km = re.match(r'^\s*([A-Za-z_]+)\s*:\s*"?(.*?)"?\s*$', line)
            if km:
                fm[km.group(1)] = km.group(2)
        body = m.group(2)
    return fm, body


def get_section(body: str, heading: str) -> str:
    """Return the text under `## heading` up to the next `## ` (or end)."""
    m = re.search(
        rf"^#+\s*{re.escape(heading)}\s*\n(.*?)(?=^#+\s|\Z)",
        body,
        re.DOTALL | re.MULTILINE,
    )
    return m.group(1).strip() if m else ""


def extract_lyrics(body: str) -> str | None:
    """Pull the lyrics out of the <pre class="lyrics..."> block, as plain text.
    Returns None if the lyrics are still the template placeholder."""
    m = re.search(r'<pre[^>]*class="lyrics[^"]*"[^>]*>(.*?)</pre>', body, re.DOTALL)
    if not m:
        return None
    inner = m.group(1)
    # <span class="lyrics-section-header">[Chorus]</span> -> [Chorus]
    inner = re.sub(r"<[^>]+>", "", inner)
    inner = inner.strip()
    if not inner or LYRIC_PLACEHOLDER in inner:
        return None
    return inner


def extract_scripture(body: str) -> str:
    """The Scripture that inspired the song. Prefer the ## Bible Verse section;
    fall back to the opening lines of ## Inspiration (some songs put the seed
    verse there)."""
    verse = get_section(body, "Bible Verse")
    if verse and "Add Bible verse" not in verse:
        return verse
    insp = get_section(body, "Inspiration")
    if insp and INSPIRATION_PLACEHOLDER not in insp:
        # Take the first paragraph — that's usually the seed verse.
        return insp.split("\n\n")[0].strip()
    return ""


def inspiration_is_open(body: str) -> bool:
    """True when there's no real reflection yet: placeholder, empty, or just a
    bare verse (like Hidden's Isaiah 45:15 with nothing after it)."""
    insp = get_section(body, "Inspiration")
    if not insp or INSPIRATION_PLACEHOLDER in insp:
        return True
    # A bare seed verse is short; a written reflection is not.
    return len(insp.split()) < 30


def eligibility(body: str) -> tuple[bool, str]:
    """(eligible, reason)."""
    lyrics = extract_lyrics(body)
    if not lyrics:
        return False, "no real lyrics yet"
    if not inspiration_is_open(body):
        return False, "Inspiration already written"
    if not extract_scripture(body):
        return False, "no inspiring Scripture found"
    return True, "ready"


def build_user_prompt(title: str, scripture: str, lyrics: str) -> str:
    return (
        f"Title: {title}\n\n"
        f"Scripture that inspired the song:\n{scripture}\n\n"
        f"Lyrics:\n{lyrics}\n\n"
        "Draft the Inspiration section."
    )


def call_claude(system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic()  # resolves ANTHROPIC_API_KEY / profile
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def process(slug: str, system: str, have_key: bool) -> None:
    path = MUSIC_DIR / f"{slug}.md"
    if not path.exists():
        print(f"  {slug}: no such song file")
        return
    _, body = split_front_matter(path.read_text())
    fm, _ = split_front_matter(path.read_text())
    eligible, reason = eligibility(body)
    if not eligible:
        print(f"  {slug}: skipped ({reason})")
        return

    title = fm.get("title", slug)
    scripture = extract_scripture(body)
    lyrics = extract_lyrics(body)
    user = build_user_prompt(title, scripture, lyrics)

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    header = (
        f"<!-- DRAFT Inspiration for '{title}' — AI PROPOSAL, not final.\n"
        f"     Edit into your own voice, then paste into _music/{slug}.md by hand.\n"
        f"     Inspiring Scripture: {scripture.splitlines()[0] if scripture else '?'} -->\n\n"
    )

    if have_key:
        try:
            draft = call_claude(system, user)
        except Exception as e:
            print(f"  {slug}: draft failed ({e}); writing the prompt instead")
            have_key = False
        else:
            out = DRAFTS_DIR / f"{slug}.md"
            out.write_text(header + draft + "\n")
            print(f"  {slug}: draft -> {out.relative_to(REPO_ROOT)}")
            return

    # No key (or the call failed): write the assembled prompt for manual use.
    out = DRAFTS_DIR / f"{slug}.prompt.md"
    out.write_text(
        "# System\n\n" + system + "\n\n# User\n\n" + user + "\n"
    )
    print(f"  {slug}: prompt -> {out.relative_to(REPO_ROOT)} (run it through Claude)")


def all_slugs() -> list[str]:
    return sorted(
        p.stem for p in MUSIC_DIR.glob("*.md") if not p.name.startswith("_")
    )


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}

    if "--all" in flags:
        slugs = all_slugs()
    elif args:
        slugs = args
    else:
        print(__doc__)
        return 1

    if "--list" in flags:
        print("Eligibility:")
        for slug in slugs:
            path = MUSIC_DIR / f"{slug}.md"
            if not path.exists():
                print(f"  {slug}: no such song file")
                continue
            _, body = split_front_matter(path.read_text())
            eligible, reason = eligibility(body)
            mark = "✓" if eligible else "·"
            print(f"  {mark} {slug}: {reason}")
        return 0

    system = SYSTEM_PROMPT_FILE.read_text()
    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not have_key:
        print("No ANTHROPIC_API_KEY set — writing prompts for manual use.\n")

    print(f"Drafting for {len(slugs)} song(s):")
    for slug in slugs:
        process(slug, system, have_key)
    print(f"\nProposals are in {DRAFTS_DIR.relative_to(REPO_ROOT)}/ — review before using any of them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
