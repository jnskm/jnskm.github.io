# Session Handoff — JNSKM site (2026-07-13)

This session built and refined **"Stay a Moment"** into a fully static feature and
polished the **book & song pages**. All work is on `main` and live at jnskm.com.
(The prior 2026-07-12 handoff — homepage redesign, music automation, local authoring
tools — is still in place; its still-open items are carried into "Open items" below.)

---

## The big picture

**Stay a Moment** is the homepage: a visitor is asked *"How are you doing?"*, taps one
of eight feeling chips, and is met by a **Scripture + a Tails of Grace passage + a song**.

The key architectural decision this session: **it is 100% static.** There is no runtime
AI, no serverless function, no API key in production. Claude is used **locally, at build
time**, to choose the pairings; the human approves; the approved result is baked into a
JSON file the page reads. (We removed the old Netlify/Cloudflare `/api/listen` function
entirely — see "Hosting" — which is why the site can live on plain GitHub Pages.)

The 8 chips / feelings: `anxious, weary, grieving, lonely, ashamed, doubting, hopeful, grateful`.

---

## How Stay a Moment works (data flow)

```
data/library/books/<slug>.json   ← extracted book chunks (keep/themes tags)
  + scripts/books_manifest.yml    ← book metadata (title, cover, amazon_url, source_pdf)
        │  scripts/build_library.py
        ▼
data/library/library.json         ← books, excerpts (themed), songs, scripture(ASV), playlists
  + _data/moments.yml             ← HUMAN-APPROVED map: feeling → scripture + song (+ overrides)
        │  scripts/build_moments.py
        ▼
assets/data/moments.json          ← SHIPPED. per-feeling {scripture, song, passage_ids}
                                     + a deduped `passages` pool (segments + book_url)
        │  fetch()
        ▼
assets/js/stay-a-moment.js        ← renders on chip click (random passage from the pool)
```

- **Scripture + song are curated per feeling** in `_data/moments.yml` (fixed).
- **The passage is NOT fixed** — for each feeling, `build_moments.py` gathers *every kept
  excerpt themed to that feeling, across all nine books* into a pool; the client shows one
  **at random** (so a returning visitor / a second tap gets a different passage). ~331 passages.
- **UX**: choosing a feeling hides the chips; the browser **Back button** returns to them
  (a history entry is pushed). No on-screen "back" link.

### `build_moments.py` does the passage cleanup + formatting (all automatic)
`clean_passage()` is **paragraph-aware** (preserves the book's paragraph breaks) and removes
OCR artifacts: leading dangling citations, page numbers (leading/trailing, standalone,
sentence-boundary, and any matching the chunk's own page — guarded so "stage 4" survives),
leading mid-sentence fragments, and line-break hyphens. `split_scripture()` sets an inline
verse quote apart on its own line with a right-aligned reference. `BOOK_PAGE` maps each book
to its on-site page so the attribution links to jnskm.com.

---

## How to make common changes

- **Re-pair a feeling's Scripture or song:** edit `_data/moments.yml` → `python scripts/build_moments.py`
  → commit/push. (Everything else — passage pool, cleanup — regenerates.)
- **Fix/clean a specific passage's shown text:** add an entry under `excerpt_overrides:` in
  `_data/moments.yml` (excerpt id → the exact snippet) → rebuild moments.
- **Surface a specific book-09 (or any) passage for a feeling:** its excerpts are already in
  the pool if themed; to *force* one, we'd extend moments.yml (currently one triad each).
- **Add a book:** manifest entry + cover in `assets/images/books/` → `python scripts/extract_book.py <slug>`
  → tag chunks (`scripts/filter_chunks.py` calls Claude; book 09 was tagged by hand) →
  `python scripts/build_library.py` → `python scripts/build_moments.py` → create
  `_books/tails-of-grace/<slug>.md` → add the id to `BOOK_PAGE` in `build_moments.py`.

The extraction is deterministic: re-running `extract_book.py` reproduces identical chunk
**ids** (only the text is refreshed), so you can re-extract and re-apply `keep`/`themes` by id.

---

## Book & song pages

- Layouts: `_layouts/book.html`, `_layouts/music.html`. Both use `.post-content-wrapper`.
- **Centered single-column layout** (this session): `.post-content-wrapper:has(.book-cover)`
  and `:has(.album-cover)` in `custom.css` cap the text to **~34rem (~12–15 words/line)**,
  center the block, keep text left-aligned, and put the cover centered on top. Scoped so
  video/blog pages are untouched.
- **Book pages** (`_books/tails-of-grace/*.md`): all 9 books, each with a full
  `amazon.com/dp/<ASIN>` link (the author prefers full, self-verifying links over `a.co`).
  Not Just Pedigree links **both** parts. The 9th book, **The Third Strand** (added this
  session), links to `amazon.com/dp/B0H1W8SBM8`.
- **Song pages** (`_music/*.md`): the `## Bible Verse` run-ons were cleaned across 27 songs
  (missing spaces after punctuation, `Selah` run-ons, trailing next-psalm headings).

---

## Hosting, deploy, local dev

- **Live host is GitHub Pages** → jnskm.com (via repo `jnskm.github.io` + the `CNAME`).
  Confirmed by `Server: GitHub.com`. (Mid-session I briefly mis-read a leftover `netlify.toml`
  as evidence of Netlify; it was vestigial and is now removed.)
- **Deploy = `git push origin main`.** GitHub Pages rebuilds automatically. The CDN caches
  assets with `max-age=600` (10 min): brand-new files appear in seconds, but changes to
  *existing* CSS/JS/JSON take up to ~10 min — or hard-refresh (Cmd+Shift+R).
- **Git note:** a GitHub Action (`check-new-music`) periodically auto-commits *"Add new music:"*
  to `main`. Before pushing, `git fetch origin && git rebase origin/main` (it only touches
  `.music-tracker.json`, so it rebases cleanly).
- **Local preview:** `./bin/serve` (runs `ruby -S bundle exec jekyll serve` on frum's Ruby
  3.1.2; the `bundle` on PATH is a different Ruby). NOTE: in a bare shell, `bundle exec jekyll`
  fails on a logger/version clash — this session I built by temporarily moving `Gemfile`/`Gemfile.lock`
  aside and running the standalone `jekyll` (4.4.1); `bin/serve` is the intended path.
- Local jekyll (4.4.1) differs from GitHub Pages' Jekyll 3.10, but only features common to
  both are used.

---

## Open items / follow-ups

Resolved this session (from the prior handoff): the Netlify→Cloudflare migration WIP was
discarded (site is static on GitHub Pages), and the stale local clone was reconciled to
`origin/main` (this repo is now the working, current tree).

Still open:
1. **Spotify token still returns `invalid_client`** (prior #1) — app/credential-level, untouched.
2. **Some songs still have `(Add Bible verse here)` placeholders** — including a few with a
   missing/bad `scripture_ref` (e.g. `golden` → out-of-range; `persist` → missing colon). The
   verse-cleanup this session only fixed run-ons in the ~27 songs that *had* real verses.
3. **Bible-Verse fill isn't wired into CI** (prior #3) — new songs won't auto-fill.
4. **Stay a Moment passages are theme-matched, not hand-cohered** with the exact verse/song.
   Quality is good (all passed the keep rubric), but a passage can occasionally feel loose for
   a feeling. Fix by adding an `excerpt_overrides` entry or refining themes in the library.
5. **Trailing fragments not trimmed** — we trim passages that *start* mid-sentence, not ones
   that *end* mid-sentence (trickier; deferred, offered).
6. **The Third Strand's page description is my draft**, built from the book's own intro/closing
   (the authors' own words) — the author may want to refine it.
7. **Single-digit mid-sentence page numbers** are deliberately left (stripping them risks real
   numbers like "stage 4"); the common 2-digit case is handled.

---

## Repo facts

- **Live site:** `~/Documents/Code/jnskm.github.io` → `github.com/jnskm/jnskm.github.io` → jnskm.com.
- `~/Documents/jnskm.com` is a **separate, non-git** "Encouragement Library" prototype folder —
  NOT the live site. (Early this session I mistakenly worked there before switching.)
- `data/library/` (chunks, `library.json`, scripture, songs) is committed but **excluded from
  the Jekyll build** — the build scripts read it.
- Book PDFs (source of extraction) live at `~/Documents/J&K/Tails_of_Grace/` (not in the repo).
