/**
 * Stay a Moment — homepage interaction.
 *
 * Sends the visitor's message to /api/listen, renders the returned
 * triad (Scripture + book excerpt + song) or the crisis card. Escapes
 * all user-derived text before insertion into the DOM.
 */

(function () {
  const API_ENDPOINT = '/api/listen';

  const card = document.getElementById('sam-card');
  if (!card) return;

  const form = document.getElementById('sam-form');
  const input = document.getElementById('sam-input');
  const submit = document.getElementById('sam-submit');
  const chips = document.getElementById('sam-chips');
  const prompt = document.getElementById('sam-prompt');
  const loading = document.getElementById('sam-loading');
  const result = document.getElementById('sam-result');
  const crisis = document.getElementById('sam-crisis');

  /** Escape HTML special characters. */
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
    submit.disabled = isLoading;
    input.disabled = isLoading;
    chips.querySelectorAll('button').forEach((b) => (b.disabled = isLoading));
    if (isLoading) {
      hide(result);
      hide(crisis);
      show(loading);
    } else {
      hide(loading);
    }
  }

  function renderError(messageText) {
    hide(loading);
    hide(crisis);
    result.innerHTML = `<p class="sam-error">${esc(messageText)}</p>`;
    show(result);
  }

  function streamingLinkHtml(platform, url) {
    if (!url) return '';
    const labels = {
      youtube: 'YouTube',
      youtube_music: 'YouTube Music',
      spotify: 'Spotify',
      apple_music: 'Apple Music',
      amazon_music: 'Amazon Music',
    };
    const label = labels[platform] || platform;
    return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
  }

  function renderTriad(data) {
    const { scripture, excerpt, song, artist_search, playlist } = data;

    // Scripture
    const scriptureRef = scripture.ltb_url
      ? `<a href="${esc(scripture.ltb_url)}" target="_blank" rel="noopener">${esc(scripture.display)}</a> · ${esc(scripture.translation)}`
      : `${esc(scripture.display)} · ${esc(scripture.translation)}`;

    // Excerpt source line
    const bookAmazon = excerpt.book_amazon_url
      ? `<a href="${esc(excerpt.book_amazon_url)}" target="_blank" rel="noopener">${esc(excerpt.book_title)}</a>`
      : esc(excerpt.book_title);
    const lessonBits = [];
    if (excerpt.lesson_number != null) {
      const t = excerpt.lesson_title ? `: ${excerpt.lesson_title}` : '';
      lessonBits.push(`Lesson ${excerpt.lesson_number}${t}`);
    } else if (excerpt.section) {
      // Title-case the section: "introduction" → "Introduction"
      const sec = excerpt.section.replace(/\b\w/g, (c) => c.toUpperCase());
      lessonBits.push(sec);
    }
    const sourceLine = `— from ${bookAmazon}${lessonBits.length ? ', ' + esc(lessonBits.join(', ')) : ''}`;

    // Song streaming links — per-song first, then artist-search fallbacks
    const perSong = Object.entries(song.streaming || {})
      .map(([p, u]) => streamingLinkHtml(p, u))
      .filter(Boolean)
      .join('');
    const artistLinks = Object.entries(artist_search || {})
      .map(([p, u]) => streamingLinkHtml(p, u))
      .filter(Boolean)
      .join('');

    const songQualifier = [];
    if (song.collaboration) songQualifier.push(esc(song.collaboration));
    if (song.is_remix) songQualifier.push('Remix');
    if (song.is_korean) songQualifier.push('Korean');
    const qualifier = songQualifier.length ? ` <span class="sam-song-qualifier">(${songQualifier.join(' · ')})</span>` : '';

    result.innerHTML = `
      <div class="sam-scripture">
        <p class="sam-scripture-text">${esc(scripture.text)}</p>
        <p class="sam-scripture-ref">${scriptureRef}</p>
      </div>

      <p class="sam-section-label">a passage</p>
      <p class="sam-excerpt-text">${esc(excerpt.text)}</p>
      <p class="sam-excerpt-source">${sourceLine}</p>

      <p class="sam-section-label">a song</p>
      <div class="sam-song">
        <p class="sam-song-title">${esc(song.title)}${qualifier}</p>
        <p class="sam-song-scripture">inspired by ${esc(song.scripture_ref)}</p>
        ${perSong ? `<div class="sam-streaming">${perSong}</div>` : ''}
        ${!perSong && artistLinks ? `<div class="sam-streaming">${artistLinks}</div>
          <p class="sam-artist-note">Not all songs are on every platform yet. Search JNSKM on your preferred service.</p>` : ''}
        ${playlist ? `<p class="sam-playlist-link">More songs <a href="${esc(playlist.url)}">${esc(playlist.title.toLowerCase())}</a></p>` : ''}
      </div>
    `;
    show(result);
  }

  function renderCrisis(data) {
    const resourcesHtml = (data.resources || [])
      .map((r) => {
        const phone = r.phone
          ? `<span class="sam-crisis-phone">${esc(r.phone)}</span>`
          : '';
        const note = r.note ? `<span class="sam-crisis-note">${esc(r.note)}</span>` : '';
        return `<p class="sam-crisis-resource">
          <a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.label)}</a>
          ${phone}
          ${note}
        </p>`;
      })
      .join('');
    crisis.innerHTML = `
      <p class="sam-crisis-message">${esc(data.message)}</p>
      ${resourcesHtml}
      <p class="sam-crisis-closing">${esc(data.closing)}</p>
    `;
    show(crisis);
  }

  async function send(message) {
    setLoading(true);
    try {
      const res = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      const data = await res.json().catch(() => null);

      if (!data) {
        renderError('Something went wrong. Please try again in a moment.');
        return;
      }

      if (data.kind === 'crisis') {
        hide(result);
        renderCrisis(data);
      } else if (data.kind === 'triad') {
        hide(crisis);
        renderTriad(data);
      } else if (data.kind === 'error') {
        renderError('Something went wrong. Please try again in a moment.');
      }
    } catch (err) {
      renderError('Connection issue. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  // --- Wire events ---

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const msg = input.value.trim();
    if (!msg) return;
    send(msg);
  });

  // Submit on Enter (without Shift)
  input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      form.requestSubmit();
    }
  });

  chips.addEventListener('click', (ev) => {
    const target = ev.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const feeling = target.dataset.feeling;
    if (!feeling) return;
    input.value = feeling;
    send(feeling);
  });
})();
