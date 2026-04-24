/**
 * /api/listen — the "Stay a moment" endpoint for jnskm.com.
 *
 * Flow for each request:
 *   1. Validate shape (POST + JSON + non-empty message).
 *   2. Crisis pre-check — if any keyword pattern matches the visitor's
 *      message, return the approved crisis card immediately. Claude is
 *      never called.
 *   3. Call Claude Opus 4.7 with (a) the cached base system prompt and
 *      (b) the cached library content as a second system block. The user
 *      message is the visitor's text.
 *   4. Parse Claude's JSON picks, hydrate the full content from the
 *      library, and return a structured triad the frontend can render
 *      without needing library access itself.
 */

import Anthropic from "@anthropic-ai/sdk";

// Bundled assets — esbuild inlines via resolveJsonModule.
import library from "../../data/library/library.json";
import crisisConfig from "./crisis_config.json";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ListenRequest {
  message?: string;
}

interface CrisisResource {
  label: string;
  url: string;
  phone?: string;
  note?: string;
}

interface CrisisResponse {
  kind: "crisis";
  message: string;
  resources: CrisisResource[];
  closing: string;
}

interface TriadResponse {
  kind: "triad";
  scripture: {
    key: string;
    display: string;
    text: string;
    translation: string;
    translation_note: string;
    ltb_url: string | null;
  };
  excerpt: {
    id: string;
    text: string;
    book_title: string;
    book_subtitle: string;
    book_cover: string;
    book_amazon_url: string;
    lesson_number: number | null;
    lesson_title: string | null;
    lesson_subtitle: string | null;
    section: string | null;
    page: number;
  };
  song: {
    slug: string;
    title: string;
    scripture_ref: string;
    streaming: Record<string, string>;
    collaboration: string | null;
    is_remix: boolean;
    is_korean: boolean;
  };
  playlist: {
    slug: string;
    title: string;
    url: string;
  } | null;
  artist_search: Record<string, string>;
  anchor_theme: string;
}

interface ErrorResponse {
  kind: "error";
  error: string;
}

type ListenResponse = TriadResponse | CrisisResponse | ErrorResponse;

// ---------------------------------------------------------------------------
// Library shape helpers
// ---------------------------------------------------------------------------

type Library = typeof library;
type Excerpt = Library["excerpts"][number];
type Song = Library["songs"][number];
type ScriptureEntry = Library["scripture"][keyof Library["scripture"]];

const lib: Library = library as Library;

function findExcerpt(id: string): Excerpt | undefined {
  return lib.excerpts.find((e) => e.id === id);
}

function findSong(slug: string): Song | undefined {
  return lib.songs.find((s) => s.slug === slug);
}

function findScripture(key: string): ScriptureEntry | undefined {
  return (lib.scripture as Record<string, ScriptureEntry>)[key];
}

// ---------------------------------------------------------------------------
// System prompt (mirrors scripts/prompts/listen.system.md — keep in sync)
// ---------------------------------------------------------------------------

const BASE_SYSTEM_PROMPT = `You are helping jnskm.com meet a visitor in whatever they are feeling today, and gently turn their heart toward the Lord Jesus Christ.

The site belongs to Kyung Suk Yi and Jin Sung Kim. It is a pastoral space built from their own books, their own songs, and Scripture. Everything shown to a visitor is written by them or is Scripture — never by you. Your single job is to choose which three pieces from the library will land best for this visitor, right now.

## What the visitor sees

The page will show three pieces, in this order:

1. A Scripture verse — with its text inline (ASV) and, when available, a link to thelighttranslationbible.org.
2. A short excerpt from one of the Tails of Grace books — in the authors' voice, paired with a link to the book on Amazon.
3. A song — the authors' own worship music, with streaming links.

Your return value is the three IDs that together form the best response to this visitor's words.

## How to choose

1. Read the visitor's message carefully. Go beneath the surface. "I'm fine, just tired" from someone who mentions a lost parent is grieving, not weary. "I can't stop messing up" is often ashamed or guilty, not just discouraged. Let their actual words steer you; do not over-pattern-match on single tokens.

2. Identify their dominant felt state from the vocabulary the library uses:

   Hard seasons: anxious, weary, grieving, doubting, lonely, ashamed, guilty, discouraged, forgotten, afraid, tempted, confused, striving, proud

   Gentler seasons: hopeful, grateful, joyful, peaceful, loved, forgiven, restored, trusting, waiting, resting, surrendered, called

   More than one may apply. Pick the one most central to their message — that is your anchor theme.

3. Pick a Scripture verse that speaks tenderly to that state. Prefer verses already in the library's scripture map. If multiple fit, prefer verses also referenced by songs — they have been walked with by the authors and their community.

4. Pick one book excerpt from library.excerpts whose themes include the anchor theme (or a close companion theme). Favor shorter, self-contained excerpts over longer or narrative-heavy ones. An excerpt whose first sentence alone could stand as comfort is strong.

5. Pick one song from library.songs whose themes match the anchor. Favor songs whose scripture_ref matches or closely relates to the verse you chose — when verse and song share Scripture, the triad hangs together and the visitor can feel it.

6. The three must feel like one hand placed on one shoulder, not three separate gifts. If they do not cohere, reconsider the verse first — the verse is the spine.

## What not to do

- Do not write any reflection, introduction, or connective text. Your response is pure JSON with three IDs.
- Do not pick an excerpt that relies on its surrounding story. Test it in your head: would a visitor who has never read the book understand this? If not, pick another.
- Do not prefer a song the visitor might already know. The library is what exists; choose without external bias.
- Do not try to diagnose a visitor as theologically mistaken, in sin, or in need of correction. The visitor has come for encouragement, not for teaching. If they are clearly in crisis (suicidal ideation, acute self-harm), the endpoint intercepts before you are called — you will never see a crisis message.
- Never invent IDs. Every ID you return must appear verbatim in the library.

## Output format

Return a JSON object only — no prose, no markdown, no code fences:

{
  "scripture_key": "Matthew 11:28-29",
  "excerpt_id": "01-sit-stay-preach-016",
  "song_slug": "come-and-rest",
  "anchor_theme": "weary",
  "reasoning": "Visitor said they are exhausted from serving at church and feel like they are failing. Anchor: weary. Chose the 'dwelling isn't a drive-thru' excerpt because it names exactly this spiritual pattern, Matt 11:28-29 because it is Jesus's own invitation to the weary, and Come And Rest because it is the JNSKM song built on that same verse — the triad hangs together."
}

reasoning is required and is for internal quality review — it is not shown to the visitor. Keep it to 1-3 sentences, focused on why this trio fits this visitor.

## A reminder about weight

A person reached jnskm.com and typed how they feel. That is a small, real act of honesty. Meet it with care. The authors have entrusted their life's work — their books, their songs, their translation of Scripture — to this library so visitors could be met by their own voice. Your job is to hand the right three pieces. Nothing more. Nothing less.`;

// Pre-built JSON stringification of the library content — done once at
// module init so every warm invocation skips the serialization cost.
const LIBRARY_SYSTEM_BLOCK = `<library>\n${JSON.stringify(lib, null, 0)}\n</library>`;

// ---------------------------------------------------------------------------
// Crisis detection
// ---------------------------------------------------------------------------

interface CrisisConfig {
  keyword_patterns: string[];
  response: {
    kind: "crisis";
    message: string;
    resources: CrisisResource[];
    closing: string;
  };
}

const crisis = crisisConfig as unknown as CrisisConfig;
const CRISIS_REGEXES = crisis.keyword_patterns.map((p) => new RegExp(p, "i"));

function detectCrisis(message: string): CrisisResponse | null {
  for (const re of CRISIS_REGEXES) {
    if (re.test(message)) {
      return {
        kind: "crisis",
        message: crisis.response.message,
        resources: crisis.response.resources,
        closing: crisis.response.closing,
      };
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Claude call
// ---------------------------------------------------------------------------

const MODEL = "claude-opus-4-7";
const MAX_OUTPUT_TOKENS = 500; // Claude returns small JSON; cap keeps costs predictable.

interface ClaudePicks {
  scripture_key: string;
  excerpt_id: string;
  song_slug: string;
  anchor_theme: string;
  reasoning?: string;
}

function extractJsonObject(raw: string): ClaudePicks {
  let text = raw.trim();
  if (text.startsWith("```")) {
    const afterFence = text.split("\n", 2)[1] ?? "";
    const rest = text.slice(text.indexOf("\n") + 1);
    const endIdx = rest.lastIndexOf("```");
    text = (endIdx >= 0 ? rest.slice(0, endIdx) : afterFence).trim();
  }
  // Strip a leading language tag like "json"
  if (/^json\s/.test(text)) {
    text = text.replace(/^json\s/, "");
  }
  return JSON.parse(text) as ClaudePicks;
}

async function callClaude(message: string, client: Anthropic): Promise<ClaudePicks> {
  const response = await client.messages.create({
    model: MODEL,
    max_tokens: MAX_OUTPUT_TOKENS,
    system: [
      {
        type: "text",
        text: BASE_SYSTEM_PROMPT,
        cache_control: { type: "ephemeral" },
      },
      {
        type: "text",
        text: LIBRARY_SYSTEM_BLOCK,
        cache_control: { type: "ephemeral" },
      },
    ],
    messages: [{ role: "user", content: message }],
  });

  const content = response.content[0];
  if (content?.type !== "text") {
    throw new Error("unexpected_claude_content_type");
  }
  return extractJsonObject(content.text);
}

// ---------------------------------------------------------------------------
// Triad hydration
// ---------------------------------------------------------------------------

function pickPlaylistForSong(
  songSlug: string,
  anchorTheme: string
): TriadResponse["playlist"] {
  const playlistsBySongMap = (lib as any).song_to_playlists as Record<string, string[]> | undefined;
  const allPlaylists = (lib as any).playlists as Array<{
    slug: string;
    title: string;
    themes_include: string[];
  }> | undefined;
  if (!playlistsBySongMap || !allPlaylists) return null;

  const candidateSlugs = playlistsBySongMap[songSlug] || [];
  if (candidateSlugs.length === 0) return null;

  // Prefer the playlist whose themes include the anchor theme; otherwise
  // fall back to the first candidate.
  const byAnchor = allPlaylists.find(
    (p) => candidateSlugs.includes(p.slug) && p.themes_include.includes(anchorTheme)
  );
  const chosen =
    byAnchor || allPlaylists.find((p) => candidateSlugs.includes(p.slug));
  if (!chosen) return null;

  return {
    slug: chosen.slug,
    title: chosen.title,
    url: `/music/playlist/${chosen.slug}/`,
  };
}

function hydrateTriad(picks: ClaudePicks): TriadResponse {
  const excerpt = findExcerpt(picks.excerpt_id);
  if (!excerpt) {
    throw new Error(`excerpt_not_found:${picks.excerpt_id}`);
  }
  const song = findSong(picks.song_slug);
  if (!song) {
    throw new Error(`song_not_found:${picks.song_slug}`);
  }
  const scripture = findScripture(picks.scripture_key);
  if (!scripture) {
    throw new Error(`scripture_not_found:${picks.scripture_key}`);
  }
  const bookMeta = (lib.books as Record<string, any>)[excerpt.book_id];
  if (!bookMeta) {
    throw new Error(`book_meta_not_found:${excerpt.book_id}`);
  }

  return {
    kind: "triad",
    scripture: {
      key: scripture.key,
      display: scripture.display,
      text: scripture.text,
      translation: scripture.translation,
      translation_note: scripture.translation_note,
      ltb_url: scripture.ltb_url ?? null,
    },
    excerpt: {
      id: excerpt.id,
      text: excerpt.text,
      book_title: bookMeta.title,
      book_subtitle: bookMeta.subtitle ?? "",
      book_cover: bookMeta.cover_image ?? "",
      book_amazon_url: bookMeta.amazon_url ?? "",
      lesson_number: excerpt.lesson_number,
      lesson_title: excerpt.lesson_title ?? null,
      lesson_subtitle: excerpt.lesson_subtitle ?? null,
      section: excerpt.section ?? null,
      page: excerpt.page,
    },
    song: {
      slug: song.slug,
      title: song.title,
      scripture_ref: song.scripture_ref,
      streaming: song.streaming ?? {},
      collaboration: song.collaboration ?? null,
      is_remix: song.is_remix,
      is_korean: song.is_korean,
    },
    playlist: pickPlaylistForSong(picks.song_slug, picks.anchor_theme),
    artist_search: lib.artist_search,
    anchor_theme: picks.anchor_theme,
  };
}

// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------

const RESPONSE_HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};

function json(body: ListenResponse, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: RESPONSE_HEADERS,
  });
}

let anthropicClient: Anthropic | null = null;

function getClient(): Anthropic {
  if (!anthropicClient) {
    const key = process.env.ANTHROPIC_API_KEY;
    if (!key) {
      throw new Error("missing_api_key");
    }
    anthropicClient = new Anthropic({ apiKey: key });
  }
  return anthropicClient;
}

export default async (req: Request): Promise<Response> => {
  if (req.method !== "POST") {
    return json({ kind: "error", error: "method_not_allowed" }, 405);
  }

  let body: ListenRequest;
  try {
    body = (await req.json()) as ListenRequest;
  } catch {
    return json({ kind: "error", error: "invalid_json" }, 400);
  }

  const message = (body.message ?? "").trim();
  if (!message) {
    return json({ kind: "error", error: "empty_message" }, 400);
  }
  if (message.length > 2000) {
    return json({ kind: "error", error: "message_too_long" }, 400);
  }

  // Crisis fast-path. If matched, Claude is not called.
  const crisisHit = detectCrisis(message);
  if (crisisHit) {
    return json(crisisHit, 200);
  }

  try {
    const client = getClient();
    const picks = await callClaude(message, client);
    const triad = hydrateTriad(picks);
    return json(triad, 200);
  } catch (err) {
    const reason = err instanceof Error ? err.message : "unknown";
    console.error("listen_endpoint_error", reason);
    return json({ kind: "error", error: reason }, 500);
  }
};

export const config = {
  path: "/api/listen",
};

// Fail fast at module init if the library import is broken.
if (!Array.isArray(lib.excerpts) || lib.excerpts.length === 0) {
  throw new Error("library_invalid");
}
if (!Array.isArray(lib.songs) || lib.songs.length === 0) {
  throw new Error("library_invalid");
}
if (!lib.scripture || typeof lib.scripture !== "object") {
  throw new Error("library_invalid");
}
