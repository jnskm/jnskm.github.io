/**
 * Stay a Moment — homepage interaction (fully static).
 *
 * The visitor taps a feeling chip; we look the triad up in a pre-built,
 * pre-approved map (assets/data/moments.json) and render Scripture +
 * Tails of Grace snippet + song. No network call to any AI, no API key —
 * every pairing was chosen locally and approved before it shipped.
 */

(function () {
  const MOMENTS_URL = '/assets/data/moments.json';

  const card = document.getElementById('sam-card');
  if (!card) return;

  const chips = document.getElementById('sam-chips');
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

  function setLoading(isLoading) {
    if (chips) chips.querySelectorAll('button').forEach((b) => (b.disabled = isLoading));
    if (isLoading) { hide(result); show(loading); }
    else { hide(loading); }
  }

  function renderError(messageText) {
    hide(loading);
    result.innerHTML = `<p class="sam-error">${esc(messageText)}</p>`;
    show(result);
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

  let momentsCache = null;
  async function loadMoments() {
    if (momentsCache) return momentsCache;
    const res = await fetch(MOMENTS_URL);
    const data = await res.json();
    momentsCache = data.moments || {};
    return momentsCache;
  }

  // --- Rendering ---

  function renderTriad(m) {
    const sc = m.scripture;
    const scriptureRef =
      `<a href="${esc(sc.full_url)}" target="_blank" rel="noopener">${esc(sc.display)}</a> · ${esc(sc.translation)}`;
    const readAll = sc.excerpted
      ? `<p class="sam-scripture-more"><a href="${esc(sc.full_url)}" target="_blank" rel="noopener">Read all of ${esc(sc.display)} →</a></p>`
      : '';

    const ex = m.excerpt;
    const bookName = ex.book_amazon_url
      ? `<a href="${esc(ex.book_amazon_url)}" target="_blank" rel="noopener">${esc(ex.book_title)}</a>`
      : esc(ex.book_title);
    const sourceLine = ex.book_title
      ? `<p class="sam-excerpt-source">— from <em>${bookName}</em>, <span class="sam-series">Tails of Grace</span></p>`
      : '';

    const song = m.song;
    const streaming = Object.entries(song.streaming || {})
      .map(([p, u]) => streamingLinkHtml(p, u))
      .filter(Boolean)
      .join('');
    const qualifierBits = [];
    if (song.collaboration) qualifierBits.push(esc(song.collaboration));
    if (song.is_remix) qualifierBits.push('Remix');
    if (song.is_korean) qualifierBits.push('Korean');
    const qualifier = qualifierBits.length
      ? ` <span class="sam-song-qualifier">(${qualifierBits.join(' · ')})</span>` : '';
    const songTitle = song.url
      ? `<a href="${esc(song.url)}">${esc(song.title)}</a>` : esc(song.title);

    result.innerHTML = `
      <p class="sam-section-label">a word</p>
      <div class="sam-scripture">
        <p class="sam-scripture-text">${esc(sc.text)}</p>
        <p class="sam-scripture-ref">${scriptureRef}</p>
        ${readAll}
      </div>

      <p class="sam-section-label">a passage</p>
      <p class="sam-excerpt-text">${esc(ex.text)}</p>
      ${sourceLine}

      <p class="sam-section-label">a song</p>
      <div class="sam-song">
        <p class="sam-song-title">${songTitle}${qualifier}</p>
        ${song.scripture_ref ? `<p class="sam-song-scripture">inspired by ${esc(song.scripture_ref)}</p>` : ''}
        ${streaming ? `<div class="sam-streaming">${streaming}</div>` : ''}
      </div>
    `;
    show(result);
  }

  // --- Actions ---

  async function pick(feelingKey) {
    setLoading(true);
    try {
      const moments = await loadMoments();
      const item = moments[feelingKey];
      if (!item) { renderError('That one isn’t ready yet. Please try another.'); return; }
      renderTriad(item);
    } catch (err) {
      renderError('Something went wrong. Please try again in a moment.');
    } finally {
      setLoading(false);
    }
  }

  // --- Wire events ---

  chips.addEventListener('click', (ev) => {
    const target = ev.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const key = target.dataset.key || (target.textContent || '').trim().toLowerCase();
    if (!key) return;
    pick(key);
  });
})();
