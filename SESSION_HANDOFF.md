# Session Handoff — JNSKM site (2026-07-12)

Two arcs of work this session, both now on `main`:
1. **Homepage redesign + Music streaming automation** (pushed earlier).
2. **Local authoring tools + content population** (this set of commits).

---

## What's on `main` now

- **Homepage** stripped to *"How are you doing?"* + the eight feeling chips. Nav
  collapsed into a right-anchored hamburger (all widths). Full-bleed (no side
  borders). Unified on EB Garamond; footer in Courier Prime Code, right-aligned,
  with **JNSKM** as the `mailto:hello@jnskm.com` link.
- **Music link resolution** anchored on the canonical Spotify release, with the
  YouTube-Odesli path as fallback. Diagnostics + dual auth-method token request.
  ⚠️ **Spotify credentials still failing — see Open Issues #1.**
- **CI**: `actions/checkout@v5` + `setup-python@v6` (Node 24); a `test_spotify`
  self-test input on the music workflow.
- **Inline section editor** for local dev (Edit buttons on song pages).
- **Lyrics rule**: first letter of every line auto-capitalized.
- **Bible Verse**: auto-populated from the library (ASV) across the catalog.
- **`hard_wrap` markdown**: one Return = one line break (site-wide).
- **Inspiration draft tooling** (proposal → you approve).

---

## New local authoring tools (this commit)

### Run the site locally
```
cd ~/Documents/Code/jnskm.github.io
./bin/serve            # http://127.0.0.1:4000  (+ edit writer on 127.0.0.1:4001)
```
Ruby note: it must run through `ruby -S bundle exec jekyll serve` (baked into
`bin/serve`) — the `bundle` on your PATH belongs to a different Ruby; the project
runs on frum's Ruby 3.1.2.

### Inline editor — `scripts/edit_server.py`, `assets/js/inline-edit.js`
On any song page (local dev only) each body section — **Bible Verse, Inspiration,
Lyrics, Listen On** — has an **Edit** button → textarea → **Save** writes
`_music/<slug>.md`; `--watch` rebuilds and livereload refreshes.
- **Dev-gated two ways** (layout emits it only in `development`; the JS refuses to
  run off localhost), so it never ships to jnskm.com.
- **Rules applied automatically on save**:
  - *Lyrics* → every line's first letter capitalized (`[intro]`→`[Intro]`, etc.).
    HTML wrapper lines and Korean lines are left alone.
  - One Return = one line break (kramdown `hard_wrap: true`).

### Batch tools (I run these; you don't have to)
- `python scripts/normalize_lyrics.py --all` — same capitalization rule, whole catalog.
- `python scripts/populate_bible_verse.py --all` — fills `(Add Bible verse here)`
  from `data/library/songs.json` (reference) + `data/library/scripture.json`
  (**ASV**, public domain). Replaces the placeholder only; never overwrites a
  hand-written verse. Idempotent.
- Both have a `--diff` preview that writes nothing.

### Inspiration drafts — `scripts/draft_inspiration.py` + `scripts/prompts/inspiration.system.md`
Extracts the lyrics + seed verse and drafts an Inspiration in the writer's spare
voice. Output goes to `drafts/` (git-ignored, never published) for you to approve
and paste in. With `ANTHROPIC_API_KEY` set it calls Claude; without, it writes the
assembled prompt. The **Hidden** Inspiration in this commit is a draft you then
edited on the page.

---

## Open issues / follow-ups

1. **Spotify token still returns `invalid_client`.** Both auth methods 400; both
   credential lengths are 32. This is app/credential-level, not code. Next step:
   verify the Client ID against the dashboard, or create a fresh Spotify app.
   (Paused at your request.)
2. **7 songs need a manual Bible Verse** (data issues in `songs.json`):
   - No `scripture_ref`: `be-still-rmx…`, `my-shepherd-rmx-ko…`, `step-by-step`,
     `private-video`, `king-of-kings-inspred-by-revelation-19-16` (ref is in the slug).
   - Bad ref: `golden` → "Psalm 24:17" (out of range), `persist` → "Galatians 6 9-10"
     (missing colon; should be `Galatians 6:9-10`). Fix in `songs.json`, then re-run populate.
3. **Bible-Verse fill is not yet wired into CI.** Applied to the whole catalog now;
   new songs won't auto-fill until the script re-runs. Decision pending: add it to
   the daily Action, or keep re-running locally.
4. **Migration WIP is still uncommitted** in your LOCAL tree (netlify→cloudflare:
   `functions/`, `package.json`, `wrangler.toml`, `tsconfig.json`, netlify deletions,
   plus `_config.yml`/`.gitignore` edits). Untouched this session.
5. **Your local clone is stale** (~89 commits behind origin). All session commits
   were landed via a clean worktree off `origin/main`, so your local tree is
   untouched. To sync: stash the migration WIP → `git pull` → pop.

---

## Repo facts (important)

- **Live site**: `~/Documents/Code/jnskm.github.io` → `github.com/jnskm/jnskm.github.io`
  → jnskm.com (GitHub Pages). `origin` had been mis-pointed at
  `github.com/jnskm/authentication` (an unrelated CAD project) and was **repointed**
  to jnskm.github.io this session.
- `~/Documents/jnskm.com` is a **separate** "Encouragement Library" planning repo
  (songs/, needs.json, categorizer) — not the live site.
- Library data lives in `data/library/` (`songs.json`, `scripture.json`), excluded
  from the Jekyll build but committed for the scripts/functions to read.
