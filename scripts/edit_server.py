#!/usr/bin/env python3
"""
Local inline-edit writer — LOCAL DEV ONLY.

Backs the "Edit" buttons on song pages during `jekyll serve`. Reads and writes
the body sections of _music/<slug>.md so you can edit a song right on its page.
Jekyll's --watch rebuilds and livereload refreshes after each save.

    GET  /api/section?slug=<slug>&section=<Name>   -> {"content": "<raw markdown>"}
    POST /api/section  {slug, section, content}     -> {"ok": true}

Hard-wired safety: binds to 127.0.0.1 only; only these body sections are
editable; slug must be a bare kebab-case name of an existing song file. This
is never part of the published site — it runs only next to your local server.
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

REPO_ROOT = Path(__file__).parent.parent
MUSIC_DIR = REPO_ROOT / "_music"
HOST, PORT = "127.0.0.1", 4001

EDITABLE_SECTIONS = {"Bible Verse", "Inspiration", "Lyrics", "Listen On"}
ALLOWED_ORIGINS = {"http://127.0.0.1:4000", "http://localhost:4000"}
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")  # traversal is blocked separately below


def song_path(slug: str) -> Path | None:
    if not SLUG_RE.match(slug or ""):
        return None
    p = (MUSIC_DIR / f"{slug}.md").resolve()
    # Confine strictly to _music/ — no traversal.
    if p.parent != MUSIC_DIR.resolve() or not p.is_file():
        return None
    return p


def section_regex(section: str) -> re.Pattern:
    # Heading of any level, then everything up to the next heading or EOF.
    return re.compile(
        rf"(^#{{1,6}}[ \t]*{re.escape(section)}[ \t]*$)(.*?)(?=^#{{1,6}}[ \t]|\Z)",
        re.MULTILINE | re.DOTALL,
    )


def read_section(text: str, section: str) -> str | None:
    m = section_regex(section).search(text)
    return m.group(2).strip("\n") if m else None


def write_section(text: str, section: str, content: str) -> str | None:
    body = content.strip("\n")
    def repl(m):
        return f"{m.group(1)}\n{body}\n\n"
    new_text, n = section_regex(section).subn(repl, text, count=1)
    return new_text if n else None


def capitalize_first_letter(line: str) -> str:
    """Uppercase the first alphabetic char of a line, leaving the rest as-is.
    HTML tag lines (<pre>, <span>, …) are left untouched, and non-cased scripts
    like Korean pass through unchanged."""
    if line.lstrip().startswith("<"):
        return line
    for i, ch in enumerate(line):
        if ch.isalpha():
            up = ch.upper()
            return line if up == ch else line[:i] + up + line[i + 1:]
    return line


def normalize_lyrics(lyrics: str) -> str:
    """The lyrics rule: capitalize the first letter of every line.
    Covers section labels ([intro] -> [Intro]) and lyric lines alike. Idempotent."""
    return "\n".join(capitalize_first_letter(ln) for ln in lyrics.split("\n"))


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/section":
            return self._json(404, {"error": "not found"})
        q = parse_qs(parsed.query)
        slug = (q.get("slug") or [""])[0]
        section = (q.get("section") or [""])[0]
        if section not in EDITABLE_SECTIONS:
            return self._json(400, {"error": "section not editable"})
        path = song_path(slug)
        if not path:
            return self._json(404, {"error": "unknown song"})
        content = read_section(path.read_text(), section)
        if content is None:
            return self._json(404, {"error": "section not found in file"})
        self._json(200, {"content": content})

    def do_POST(self):
        if urlparse(self.path).path != "/api/section":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "bad JSON"})
        slug = data.get("slug", "")
        section = data.get("section", "")
        content = data.get("content", "")
        if section not in EDITABLE_SECTIONS:
            return self._json(400, {"error": "section not editable"})
        if not isinstance(content, str):
            return self._json(400, {"error": "content must be a string"})
        # Rule: lyrics are always capitalized line-by-line, automatically on save.
        if section == "Lyrics":
            content = normalize_lyrics(content)
        path = song_path(slug)
        if not path:
            return self._json(404, {"error": "unknown song"})
        new_text = write_section(path.read_text(), section, content)
        if new_text is None:
            return self._json(404, {"error": "section not found in file"})
        path.write_text(new_text)
        print(f"  saved: {section} -> _music/{slug}.md")
        self._json(200, {"ok": True})

    def log_message(self, *args):
        pass  # quiet; we print our own save lines


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"inline-edit writer on http://{HOST}:{PORT} (local dev only)")
    print(f"editable sections: {', '.join(sorted(EDITABLE_SECTIONS))}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
