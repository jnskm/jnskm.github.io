/**
 * Stay a Moment — homepage interaction (fully static).
 *
 * The visitor taps a feeling chip; we show its curated Scripture and song plus
 * one Tails of Grace passage chosen at random from every kept excerpt themed to
 * that feeling, across all nine books (assets/data/moments.json). No AI at
 * runtime, no API key — every piece was chosen locally and approved before it
 * shipped.
 *
 * Choosing a feeling pushes a history entry, so the browser Back button returns
 * to the chips (there is no on-screen "back" — Back does it).
 */

(function () {
  const DATA_URL = '/assets/data/moments.json';

  const card = document.getElementById('sam-card');
  if (!card) return;

  const chips = document.getElementById('sam-chips');
  const prompt = document.getElementById('sam-prompt');
  const loading = document.getElementById('sam-loading');
  const result = document.getElementById('sam-result');

  function esc(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function show(el) { if (el) el.hidden = false; }
  function hide(el) { if (el) el.hidden = true; }

  function scrollToTop() {
    const c = document.querySelector('.site-main .content');
    if (c) c.scrollTop = 0;
    window.scrollTo(0, 0);
  }

  const STREAMING_LABELS = {
    youtube: 'YouTube',
    youtube_music: 'YouTube Music',
    spotify: 'Spotify',
    apple_music: 'Apple Music',
    amazon_music: 'Amazon Music',
  };

  function streamingLinkHtml(platform, url) {
    if (!url) return '';
    const label = STREAMING_LABELS[platform] || platform;
    return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
  }

  // --- Data (fetched once, cached) ---

  let dataCache = null;
  async function loadData() {
    if (dataCache) return dataCache;
    const res = await fetch(DATA_URL);
    dataCache = await res.json();
    return dataCache;
  }

  function randomPassage(m, passages) {
    const ids = m.passage_ids || [];
    if (!ids.length) return null;
    const id = ids[Math.floor(Math.random() * ids.length)];
    return passages[id] || null;
  }

  // --- Rendering ---

  function renderTriad(m, passages) {
    const sc = m.scripture;
    const scriptureRef =
      `<a href="${esc(sc.full_url)}" target="_blank" rel="noopener">${esc(sc.display)}</a> · ${esc(sc.translation)}`;
    const readAll = sc.excerpted
      ? `<p class="sam-scripture-more"><a href="${esc(sc.full_url)}" target="_blank" rel="noopener">Read all of ${esc(sc.display)} →</a></p>`
      : '';

    const passage = randomPassage(m, passages);
    let passageHtml = '';
    if (passage) {
      const bookName = passage.book_amazon_url
        ? `<a href="${esc(passage.book_amazon_url)}" target="_blank" rel="noopener">${esc(passage.book_title)}</a>`
        : esc(passage.book_title);
      const sourceLine = passage.book_title
        ? `<p class="sam-excerpt-source">— from <em>${bookName}</em>, <span class="sam-series">Tails of Grace</span></p>`
        : '';
      // A passage is a list of segments: plain text, or a set-apart Scripture
      // quote with a right-aligned reference.
      const body = (passage.segments || []).map((seg) => {
        if (seg.t === 'quote') {
          return `<blockquote class="sam-quote">
            <p class="sam-quote-text">“${esc(seg.v)}”</p>
            <p class="sam-quote-ref">— ${esc(seg.ref)}</p>
          </blockquote>`;
        }
        return `<p class="sam-excerpt-text">${esc(seg.v)}</p>`;
      }).join('');
      passageHtml = `
        <p class="sam-section-label">a passage</p>
        ${body}
        ${sourceLine}`;
    }

    const song = m.song;
    const streaming = Object.entries(song.streaming || {})
      .map(([p, u]) => streamingLinkHtml(p, u))
      .filter(Boolean)
      .join('');
    const songTitle = song.url
      ? `<a href="${esc(song.url)}">${esc(song.title)}</a>` : esc(song.title);

    result.innerHTML = `
      <p class="sam-section-label">a word</p>
      <div class="sam-scripture">
        <p class="sam-scripture-text">${esc(sc.text)}</p>
        <p class="sam-scripture-ref">${scriptureRef}</p>
        ${readAll}
      </div>
      ${passageHtml}

      <p class="sam-section-label">a song</p>
      <div class="sam-song">
        <p class="sam-song-title">${songTitle}</p>
        ${song.scripture_ref ? `<p class="sam-song-scripture">inspired by ${esc(song.scripture_ref)}</p>` : ''}
        ${streaming ? `<div class="sam-streaming">${streaming}</div>` : ''}
      </div>
    `;
  }

  function renderError(messageText) {
    result.innerHTML = `<p class="sam-error">${esc(messageText)}</p>`;
  }

  // --- Views ---

  function showResult() {
    hide(prompt);
    hide(loading);
    show(result);
    scrollToTop();
  }

  function showPrompt() {
    hide(result);
    hide(loading);
    show(prompt);
    scrollToTop();
  }

  async function pick(feelingKey) {
    hide(prompt);
    hide(result);
    show(loading);
    try {
      const data = await loadData();
      const m = (data.moments || {})[feelingKey];
      if (!m) { renderError('That one isn’t ready yet. Please try another.'); }
      else { renderTriad(m, data.passages || {}); }
    } catch (err) {
      renderError('Something went wrong. Please try again in a moment.');
    } finally {
      showResult();
    }
  }

  // --- Wire events ---

  chips.addEventListener('click', (ev) => {
    const target = ev.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const key = target.dataset.key || (target.textContent || '').trim().toLowerCase();
    if (!key) return;
    // Push a history entry so the browser Back button returns to the chips.
    history.pushState({ sam: key }, '');
    pick(key);
  });

  // Back button (or gesture) → return to the chips.
  window.addEventListener('popstate', () => {
    showPrompt();
  });
})();
