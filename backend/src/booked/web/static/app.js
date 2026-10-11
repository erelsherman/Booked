// Booked web prototype: scan photos, confirm books, see a Reader Identity.
// No framework and no build step. Everything the server returns is escaped before it reaches the DOM.
(() => {
  const app = document.getElementById('app');
  const params = new URLSearchParams(location.hash.slice(1));
  const token = params.get('token') || '';
  const modelParam = new URLSearchParams(location.search).get('model') || '';
  const authHeaders = token ? { 'X-Access-Token': token } : {};

  const COVERS = [['#2F4858', '#fff'], ['#B8704F', '#fff'], ['#E6D5B0', '#2a2a2a'], ['#3C3A6E', '#fff'],
                  ['#7FA08B', '#10261a'], ['#A8403A', '#fff'], ['#E2B93B', '#2a2a2a'], ['#CBD5DC', '#1c2a33']];
  const BARS = ['#0F5F58', '#5FA39B', '#B7D3CE', '#9AA0B4', '#D9D9D3'];

  // Premium is a demo switch kept on this device only. No payment is taken anywhere.
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage can be blocked */ } },
  };

  const state = {
    screen: 'welcome', shelves: [], config: {}, files: [], items: [], removed: [], cost: 0, unreadable: 0,
    errors: [], identity: null, error: '', focus: null,
    premium: store.get('booked.premium') === '1', plan: 'yearly', paywallFrom: 'start',
  };
  let uid = 0;

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const hash = (s) => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const langName = (code) => {
    if (!code || code === 'und') return 'Unknown';
    try { return new Intl.DisplayNames(['en'], { type: 'language' }).of(code) || code; } catch { return code; }
  };
  const money = (n) => `$${Number(n || 0).toFixed(n < 0.1 ? 3 : 2)}`;

  // ---- Standalone demo: when window.BOOKED_MOCK is set, the page answers its own API calls with sample data
  // (no server, no photos leave the device). Everything below up to api() exists only for that mode.
  const MOCK = window.BOOKED_MOCK || null;
  const fold = (s) => String(s || '').normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
    .replace(/[ךםןףץ]/g, (c) => ({ 'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ' }[c]))
    .replace(/[\u05F3\u05F4]/g, '').replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
  const NOISE_PREFIX = ['reading level', 'nyt:', 'in library', 'accessible', 'protected daisy', 'overdrive', 'internet archive', 'large type', 'open library', 'lending library'];
  const NOISE_EXACT = new Set(['fiction in english', 'english language', 'english fiction', 'books and reading']);
  const cleanSubjects = (list) => {
    const out = [];
    for (const raw of list || []) {
      const t = String(raw).trim().toLowerCase();
      if (!t || NOISE_EXACT.has(t) || NOISE_PREFIX.some((p) => t.startsWith(p)) || t.length > 40) continue;
      if (!out.includes(t)) out.push(t);
    }
    return out;
  };
  const shares = (counts, top) => {
    const total = [...counts.values()].reduce((a, b) => a + b, 0);
    return total ? [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, top).map(([name, count]) => ({ name, count, share: Math.round((count / total) * 1000) / 1000 })) : [];
  };
  function mockIdentity(books) {
    const n = books.length, langs = new Map(), subj = new Map(), auth = new Map();
    const bump = (m, k) => m.set(k, (m.get(k) || 0) + 1);
    for (const b of books) {
      bump(langs, b.language || 'und');
      cleanSubjects(b.subjects).slice(0, 6).forEach((x) => bump(subj, x));
      if ((b.authors || []).length) bump(auth, b.authors[0]);
    }
    const confidence = n < 8 ? 'low' : n < 30 ? 'medium' : 'high';
    const top = shares(subj, 3).map((x) => x.name);
    const statement = n === 0 ? 'Scan a shelf to see your Reader Identity.'
      : confidence === 'low' ? 'A first sketch of your taste. Scan a few more shelves to sharpen it.'
      : top.length >= 2 ? `Mostly ${top[0]} and ${top[1]}.` : top.length ? `Mostly ${top[0]}.` : 'A varied shelf.';
    return { books: n, confidence, statement, languages: shares(langs, 5), subjects: shares(subj, 6), authors: shares(auth, 5), note: `Based on ${n} book${n !== 1 ? 's' : ''}.` };
  }
  function mockSearch(q) {
    const terms = fold(q).split(' ').filter(Boolean);
    if (!terms.length) return [];
    return MOCK.catalog
      .map((w) => { const hay = fold([w.title, ...(w.alt_titles || []), ...(w.authors || [])].join(' ')); return { w, score: terms.filter((t) => hay.includes(t)).length / terms.length }; })
      .filter((x) => x.score >= 0.5).sort((a, b) => b.score - a.score).slice(0, 8)
      .map(({ w, score }) => ({ work_id: w.id, title: w.title, authors: w.authors, language: w.language, subjects: w.subjects, year: w.year, score }));
  }
  async function mockApi(path, options) {
    await new Promise((r) => setTimeout(r, path.startsWith('/api/scan') ? 1100 : 120));
    if (path.startsWith('/api/config')) return { ...MOCK.config };
    if (path.startsWith('/api/scan')) return JSON.parse(JSON.stringify(MOCK.scan));
    if (path.startsWith('/api/search')) return mockSearch(decodeURIComponent(path.split('q=')[1] || ''));
    if (path.startsWith('/api/identity')) return mockIdentity(JSON.parse(options.body).books);
    if (path.startsWith('/api/log')) return { saved: false };
    throw new Error('Unknown demo route');
  }


  // ---- Live-in-Claude mode: when window.BOOKED_LIVE is set, the page asks Claude (on the viewer's own
  // Claude account, through the artifact `sample` capability) to read the photos. There is no server, no
  // API key and no catalog: Claude both reads the spines and says which book each one is. Everything it
  // returns is treated as untrusted text and escaped before it reaches the DOM.
  const LIVE = window.BOOKED_LIVE === true;
  const SPINE_PROMPT = `You are reading the book spines in the attached photo of a bookshelf. Many books are in Hebrew or English; keep Hebrew as printed.
List every spine you can read, left to right (and top to bottom if there are several shelves). Never invent a book for text you cannot read: count those spines in "unreadable" instead.
Reply with only one JSON object, no other text:
{"spines":[{"title":"title exactly as printed on the spine","author":"author as printed, or empty","language":"ISO 639-1 code of the printed title","read_confidence":0.0-1.0 for how sure you are of the printed text,"identified":{"title":"the book's standard title (use the Hebrew title for a Hebrew edition)","authors":["author"],"language":"ISO 639-1 code","subjects":["up to 4 lowercase genre or topic words"],"year":null or the first publication year,"known":true only if you are confident this is a real published book matching the printed text},"alternatives":[up to 2 other books it could be, each {"title","authors","language","subjects","year"}]}],"unreadable":number of spines too small, blurry or hidden to read}`;
  const searchPrompt = (q) => `Search for books matching: ${JSON.stringify(String(q).slice(0, 120))}
Reply with only a JSON array of up to 6 real, published books that best match, most likely first. Each item: {"title","authors":[],"language":"ISO 639-1","subjects":[up to 4 lowercase words],"year":null or number}. Use only books you are confident exist. Reply [] if unsure.`;
  const str = (v) => (typeof v === 'string' ? v.trim() : '');
  const strs = (v) => (Array.isArray(v) ? v.map(str).filter(Boolean) : []);
  const FATAL = new Set(['not_granted', 'rate_limited', 'sampling_disabled', 'session_expired', 'images_unavailable', 'capability_disabled', 'not_declared']);
  const SAMPLE_COPY = {
    not_granted: 'To read photos, allow this page to use Claude when asked, then try again.',
    rate_limited: 'Claude is busy or your usage limit was reached. Try again in a little while.',
    session_expired: 'Please sign in to Claude again, then reload this page.',
    sampling_disabled: 'Claude is not available for this account.',
    image_rejected: 'That photo could not be read. Try a different one.',
    invalid_json: 'Claude’s answer could not be understood. Try again, or take a closer photo.',
    refused: 'Claude declined to read that photo. Try a different one.',
  };
  const sampleError = (e) => Object.assign(new Error(SAMPLE_COPY[e && e.code] || (e && e.message) || 'Something went wrong.'), { code: e && e.code });
  let samplePromise;
  const getSample = () => (samplePromise ||= (async () => {
    const c = window.claude && (await window.claude.use('sample'));
    if (!c) throw new Error('Reading photos needs this page to be opened on claude.ai, signed in to Claude.');
    return c;
  })());
  const liveWork = (w) => ({
    work_id: `claude:${hash(`${str(w.title)}|${strs(w.authors)[0] || ''}`.toLowerCase())}`,
    title: str(w.title), authors: strs(w.authors), language: str(w.language),
    subjects: cleanSubjects(strs(w.subjects)).slice(0, 4), year: Number.isInteger(w.year) ? w.year : null, score: null,
  });
  function liveItem(id, s) {
    const title = str(s.title), author = str(s.author);
    const conf = Math.min(1, Math.max(0, Number(s.read_confidence) || 0));
    const ident = s.identified && str(s.identified.title) ? s.identified : null;
    const candidates = [ident, ...(Array.isArray(s.alternatives) ? s.alternatives : [])]
      .filter((w) => w && typeof w === 'object' && str(w.title)).slice(0, 3).map(liveWork);
    if (!title && !candidates.length) return null;
    const oneWordNoAuthor = fold(title).split(' ').filter(Boolean).length < 2 && !author;
    const sure = ident && ident.known === true && conf >= 0.8 && !oneWordNoAuthor;
    return {
      id, read: { title: title || candidates[0].title, author, language: str(s.language), confidence: conf },
      decision: !candidates.length ? 'manual' : sure ? 'auto' : 'confirm', reasons: [], candidates,
    };
  }
  async function liveScan(form) {
    const sample = await getSample();
    const photos = [];
    for (const [pi, f] of form.getAll('files').entries()) {
      try {
        const out = await sample.json(SPINE_PROMPT, { images: f, modelTier: 'default' });
        const items = (Array.isArray(out && out.spines) ? out.spines : []).slice(0, 80)
          .map((s, i) => (s && typeof s === 'object' ? liveItem(`${pi}-${i}`, s) : null));
        const skipped = items.filter((x) => !x).length;
        photos.push({ photo: f.name, error: '', unreadable: Math.max(0, Number(out && out.unreadable) || 0) + skipped, items: items.filter(Boolean) });
      } catch (e) {
        const err = sampleError(e);
        if (FATAL.has(e && e.code) && !photos.length) throw err;
        photos.push({ photo: f.name, error: err.message, unreadable: 0, items: [] });
        if (FATAL.has(e && e.code)) break;
      }
    }
    return { model: 'Claude', photos, cost_usd: 0, spent_usd: 0 };
  }
  async function liveApi(path, options) {
    if (path.startsWith('/api/config')) {
      const sample = await getSample();
      const lim = await sample.limits().catch(() => null);
      if (!lim || !lim.images) throw new Error('This view cannot send photos to Claude. Open the page on claude.ai.');
      return { demo: false, live: true, model: 'Claude', logging: false, max_photos: Math.min(6, lim.images.maxCount || 6), spent_usd: 0, max_spend_usd: 0 };
    }
    if (path.startsWith('/api/scan')) return liveScan(options.body);
    if (path.startsWith('/api/search')) {
      const sample = await getSample();
      try {
        const list = await sample.json(searchPrompt(decodeURIComponent(path.split('q=')[1] || '')), { modelTier: 'quick' });
        return (Array.isArray(list) ? list : []).filter((w) => w && typeof w === 'object' && str(w.title)).slice(0, 6).map(liveWork);
      } catch (e) { throw sampleError(e); }
    }
    if (path.startsWith('/api/identity')) return mockIdentity(JSON.parse(options.body).books);
    if (path.startsWith('/api/log')) return { saved: false };
    throw new Error('Unknown route');
  }

  async function api(path, options = {}) {
    if (MOCK) return mockApi(path, options);
    if (LIVE) return liveApi(path, options);
    const res = await fetch(path, { ...options, headers: { ...authHeaders, ...(options.headers || {}) } });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch { /* keep status text */ }
      throw new Error(res.status === 401 ? 'This server needs an access token. Open the link you were given, including the part after #.' : detail);
    }
    return res.json();
  }

  // Phone photos are 4 to 12 MB. Shrinking them first makes the upload fast, and the server shrinks again.
  async function shrink(file, max = 2000) {
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' });
      const scale = Math.min(1, max / Math.max(bmp.width, bmp.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(bmp.width * scale);
      canvas.height = Math.round(bmp.height * scale);
      canvas.getContext('2d').drawImage(bmp, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85));
      return blob ? new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' }) : file;
    } catch { return file; }
  }

  // ---------------------------------------------------------------- views

  const cover = (title) => {
    const [bg, fg] = COVERS[hash(title) % COVERS.length];
    return `<div class="cover" style="background:${bg};color:${fg}" aria-hidden="true">${esc(String(title).slice(0, 30))}</div>`;
  };

  const svg = (d, size = 24, stroke = '#0F5F58') => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICON = {
    camera: '<path d="M4 8h3l1.5-2h7L17 8h3v11H4z"></path><circle cx="12" cy="13" r="3.5"></circle>',
    people: '<circle cx="9" cy="8" r="3.5"></circle><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"></path><circle cx="17.5" cy="9" r="2.5"></circle><path d="M17 14c2.8 0 4.5 1.9 4.5 5"></path>',
    compass: '<circle cx="12" cy="12" r="9"></circle><path d="M15.5 8.5l-2 5-5 2 2-5z"></path>',
    phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.5"></rect><path d="M11 18.5h2"></path>',
  };
  const WELCOME_ROWS = [
    ['camera', 'Scan your shelf', 'One photo adds dozens of books, in any language.'],
    ['people', 'See what your friends read', 'Follow readers you trust. You choose what to share.'],
    ['compass', 'Discover what to read next', 'Recommendations built from your own shelf.'],
  ];

  function viewWelcome() {
    return `
    <section class="screen welcome">
      <div class="stack" style="gap:12px">
        <span class="wordmark" style="color:var(--teal);font-size:22px">Booked</span>
        <h1 class="serif" style="font-size:44px;line-height:1.05;letter-spacing:-0.5px">Your world of books.</h1>
        <p class="sub" style="font-size:17px;line-height:1.45">Scan your shelf and we’ll learn your taste in a minute.</p>
      </div>
      <div class="stack" style="gap:20px">
        ${WELCOME_ROWS.map(([icon, t, d]) => `
        <div class="row" style="align-items:flex-start;gap:14px">
          <span class="ico">${svg(ICON[icon])}</span>
          <div class="stack" style="gap:2px"><b style="font-size:16px">${esc(t)}</b><span class="sub" style="font-size:14px">${esc(d)}</span></div>
        </div>`).join('')}
      </div>
      ${state.error ? `<div class="err" role="alert">${esc(state.error)}</div>` : ''}
      ${SOC.on ? `<div class="stack spacer">
        <button class="btn dark" data-action="join">${SOC.name ? `Continue as ${esc(SOC.name)}` : 'Continue'}</button>
        <p class="note" style="text-align:center">You are signed in with your Claude account, so there is nothing to sign up for. People with access to this page can see your name. Your shelf stays private until you choose to share it.</p>
      </div>` : `<div class="stack spacer">
        <button class="btn dark" data-action="enter">Continue with Apple</button>
        <button class="btn outline" data-action="enter"><span class="g" aria-hidden="true">G</span>Continue with Google</button>
        <button class="btn outline" data-action="enter">${svg(ICON.phone, 20, '#16161A')}Continue with phone number</button>
        <button class="btn text" data-action="enter">Use email instead</button>
        <p class="note" style="text-align:center">Prototype: sign-in is not connected yet, so any option continues without an account. Your shelf is private until you choose to share it.</p>
      </div>`}
    </section>`;
  }

  const SPINE_ART = [[22, 170, '#2F4858'], [30, 195, '#B8704F'], [18, 150, '#E6D5B0'], [26, 185, '#3C3A6E'], [20, 145, '#7FA08B'], [34, 205, '#A8403A'],
                     [24, 170, '#6B5F57'], [28, 190, '#E2B93B'], [18, 155, '#CBD5DC'], [30, 200, '#2F4858'], [22, 175, '#B8704F'], [26, 150, '#7FA08B'], [20, 195, '#E6D5B0'], [32, 180, '#3C3A6E']];

  function viewStart() {
    const have = state.items.length;
    const pending = state.files.length;
    const last = state.files[pending - 1];
    const thumbs = state.files.map((f, i) => `
      <div class="thumb"><img src="${f.url}" alt="Photo ${i + 1}">
        <button data-action="drop-file" data-i="${i}" aria-label="Remove photo ${i + 1}">×</button></div>`).join('');
    const shelves = state.shelves.map((sh, i) => `
      <div class="shelf-tile"><img src="${sh.url}" alt="Shelf ${i + 1}"><span class="count">${sh.count}</span></div>`).join('');
    return `
    <section class="screen hero scan">
      <div class="row">
        <button class="round" data-action="close-scan" aria-label="Close">${svg('<path d="M6 6l12 12M18 6L6 18"></path>', 22, '#16161A')}</button>
        <span class="grow"></span>${premiumChip()}
        ${have ? `<button class="btn dark small" data-action="to-check">Done · ${have} book${have > 1 ? 's' : ''}</button>` : ''}
      </div>
      <div class="stack" style="gap:6px">
        <h1 class="serif" style="font-size:32px;line-height:1.08;font-weight:600">${have ? 'Add another shelf.' : 'Let’s scan your library.'}</h1>
        <p class="sub" style="line-height:1.45">Scan a shelf, or a wall in a few passes. The more you scan, the better we know your taste. You can come back any time.</p>
      </div>
      ${state.error ? `<div class="err" role="alert">${esc(state.error)}</div>` : ''}
      <div class="viewfinder">
        ${last ? `<img src="${last.url}" alt="Your latest photo">` : SPINE_ART.map(([w, h, c]) => `<i style="flex:${w} 1 0;height:${h}px;background:${c}"></i>`).join('')}
        <div class="shelfline"></div>
        <span class="vf-chip">${pending ? `${pending} ready to read` : 'Shelf or wall'}</span>
        <span class="vf-chip warm">Spines small? Move closer</span>
      </div>
      ${have ? `<div class="stack" style="gap:8px">
        <b style="font-size:13px">Scanned so far · ${state.shelves.length} shelf${state.shelves.length === 1 ? '' : 'ves'}</b>
        <div class="row" style="gap:8px">${shelves}<div class="shelf-tile next">Next shelf</div></div>
      </div>` : ''}
      ${thumbs ? `<div class="thumbs">${thumbs}</div>` : ''}
      <div class="stack spacer" style="align-items:center;gap:14px">
        ${pending ? `<button class="btn dark" style="align-self:stretch" data-action="scan">Read ${pending} photo${pending > 1 ? 's' : ''}</button>` : ''}
        <button class="shutter" data-action="take" aria-label="Take a photo"></button>
        <button class="btn ghost small" data-action="choose">Choose photos from your gallery</button>
        <input id="cam" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden>
        <input id="pick" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden>
        <p class="note" style="color:#2a1a0e;text-align:center">${MOCK ? 'Demo: your photos stay on this device and sample books are shown, so try the whole flow.' : LIVE ? 'Your photos are read by Claude, on your own Claude account. Booked does not store them.' : 'Photos are sent to the model to read the spines and are not stored by this prototype.'}</p>
      </div>
    </section>`;
  }

  function viewReading() {
    return `
    <section class="screen hero center">
      <div class="spinner" role="status" aria-label="Reading"></div>
      <h1 class="serif mid">Reading your shelf…</h1>
      <p class="sub">${LIVE ? 'This can take up to a minute per photo.' : 'This usually takes 10 to 30 seconds per photo.'}</p>
    </section>`;
  }

  const HEBREW = /[\u0590-\u05FF]/;

  function itemRow(it) {
    const shown = { ...(it.choice || { title: it.read.title, authors: it.read.author ? [it.read.author] : [] }) };
    // Show what is printed on the spine when it is Hebrew but the catalog title is not, and use the
    // language of the copy on the shelf (the spine), not the original language of the work.
    let alsoKnownAs = '';
    if (it.choice && HEBREW.test(it.read.title) && !HEBREW.test(it.choice.title)) { alsoKnownAs = it.choice.title; shown.title = it.read.title; }
    shown.language = it.read.language || (it.choice && it.choice.language) || '';
    const sub = [(shown.authors || []).slice(0, 2).join(', '), shown.language ? langName(shown.language) : ''].filter(Boolean).join(' · ');
    const status = it.status === 'matched' ? '<span class="st ok">✓ Matched</span>' : it.status === 'check' ? '<span class="st rev">Review</span>' : '<span class="st rev">Add</span>';
    let more = '';
    if (it.status === 'check') {
      more = `<div class="cands" role="group" aria-label="Pick the right book">${it.candidates.map((c, i) => `
        <button class="cand" data-action="pick" data-id="${it.id}" data-i="${i}" dir="auto">${esc(c.title)}<small>${esc(c.authors.slice(0, 2).join(', '))}${c.year ? ' · ' + c.year : ''}</small></button>`).join('')}
        <button class="btn line small" data-action="none" data-id="${it.id}">None of these</button></div>`;
    } else if (it.status === 'missing') {
      more = `<div class="find">
        <label class="note" for="q-${it.id}">${LIVE ? 'Search by title or author' : 'Search the catalog'}</label>
        <input id="q-${it.id}" data-id="${it.id}" data-input="search" value="${esc(it.query ?? it.read.title)}" dir="auto" autocomplete="off">
        ${(it.found || []).map((c, i) => `<button class="cand" data-action="pick-found" data-id="${it.id}" data-i="${i}" dir="auto">${esc(c.title)}<small>${esc(c.authors.slice(0, 2).join(', '))}${c.year ? ' · ' + c.year : ''}</small></button>`).join('')}
        ${LIVE ? `<button class="btn dark small" data-action="run-search" data-id="${it.id}">${it.searching ? 'Searching…' : 'Search'}</button>` : ''}
        ${it.read.title ? `<button class="btn line small" data-action="add-typed" data-id="${it.id}">Add “${esc(it.read.title)}” as typed</button>` : ''}</div>`;
    }
    return `
    <div class="crow">
      <div class="row" style="gap:14px">${cover(shown.title || '?')}
        <div class="grow"><div class="title" dir="auto">${esc(shown.title || 'Couldn’t read this spine')}</div>
          <div class="author" dir="auto">${esc(sub || 'Search or add it by hand')}</div>
          ${alsoKnownAs ? `<div class="author" dir="ltr">${esc(alsoKnownAs)}</div>` : ''}</div>
        ${state.selecting ? `<button class="x" data-action="remove" data-id="${it.id}" aria-label="Set aside ${esc(shown.title)}">×</button>` : status}
      </div>${more}
    </div>`;
  }

  function viewCheck() {
    const n = state.items.length;
    const matched = state.items.filter((i) => i.status === 'matched').length;
    const toCheck = n - matched;
    return `
    <section class="screen check">
      <div class="row"><button class="round soft" data-action="scan-more" aria-label="Back">${svg('<path d="M15 5l-7 7 7 7"></path>', 22, '#16161A')}</button><span class="grow"></span>
        ${n ? `<button class="link" style="min-height:44px;padding:0 8px;font-size:15px" data-action="toggle-select">${state.selecting ? 'Done' : 'Select'}</button>` : ''}</div>
      <div class="stack" style="gap:6px">
        <h1 class="serif" style="font-size:32px;line-height:1.1;letter-spacing:-0.3px">${n ? `We found ${n} book${n > 1 ? 's' : ''}` : 'No books yet'}</h1>
        <p class="sub" style="line-height:1.4">${matched} matched.${toCheck ? ` ${toCheck} need a quick look.` : ''} Not all yours? Tap Select to set some aside.</p>
      </div>
      ${state.unreadable ? `<div class="warn">${state.unreadable} spine${state.unreadable > 1 ? 's were' : ' was'} too small or blurry to read. Try a closer photo, one shelf at a time.</div>` : ''}
      ${state.errors.map((e) => `<div class="err" role="alert">${esc(e)}</div>`).join('')}
      <div>${state.items.map(itemRow).join('')}</div>
      <div class="spacer stack" style="position:sticky;bottom:0;background:#fff;padding:12px 0 8px">
        ${LIVE || MOCK ? '' : `<p class="note">This session has cost ${money(state.cost)}${state.config.max_spend_usd ? ` of a ${money(state.config.max_spend_usd)} cap` : ''}.</p>`}
        <div class="row" style="justify-content:space-between;font-size:14px;color:var(--muted)"><span>Missing a book?</span>
          <span class="row" style="gap:16px"><button class="link" data-action="add-row">Search</button><button class="link" data-action="add-row">Add by hand</button></span></div>
        <button class="btn primary" style="min-height:54px" data-action="identity" ${matched ? '' : 'disabled'}>Show me my Reader Identity</button>
      </div>
    </section>`;
  }

  const HEB = /[֐-׿]/;
  const shelfTitle = (it) => (HEB.test(it.read.title) && !HEB.test(it.choice.title) ? it.read.title : it.choice.title);

  function premiumChip() {
    return `<button class="chip prem${state.premium ? ' on' : ''}" data-action="paywall" aria-label="${state.premium ? 'Premium is on (demo)' : 'Try Premium'}">${state.premium ? '✓ Premium (demo)' : 'Free · Try Premium'}</button>`;
  }

  const subjectBars = (list) => list.map((x) => `
    <div><span dir="auto" class="cap">${esc(x.name)}</span><span class="note">${x.count}</span></div><div class="bar"><i style="width:${Math.round(x.share * 100 * 2.5)}%"></i></div>`).join('');

  function fullIdentity(d) {
    const matched = identityPool();
    const behind = d.subjects.slice(0, 3).map((s) => ({
      name: s.name,
      titles: matched.filter((i) => (i.choice.subjects || []).some((x) => x.toLowerCase() === s.name)).slice(0, 4).map(shelfTitle),
    })).filter((g) => g.titles.length);
    return `
      ${d.subjects.length ? `<div class="metric"><strong>What you read</strong>${subjectBars(d.subjects)}</div>` : ''}
      ${d.authors.length ? `<div class="metric"><strong>Authors you return to</strong>${d.authors.map((a) => `<div><span dir="auto">${esc(a.name)}</span><span class="note">${a.count} book${a.count > 1 ? 's' : ''}</span></div>`).join('')}</div>` : ''}
      ${behind.length ? `<div class="metric"><strong>The books behind this</strong>${behind.map((g) => `
        <div style="flex-direction:column;gap:2px"><span class="cap" style="font-weight:600">${esc(g.name)}</span><span class="note" dir="auto">${g.titles.map(esc).join(' · ')}</span></div>`).join('')}</div>` : ''}`;
  }

  function lockedIdentity(d) {
    return `
      ${d.subjects[0] ? `<div class="metric"><strong>What you read</strong>${subjectBars(d.subjects.slice(0, 1))}</div>` : ''}
      <div class="lock">
        <div class="blurred" aria-hidden="true">
          <div class="bar"><i style="width:70%"></i></div><div class="bar"><i style="width:45%"></i></div><div class="bar"><i style="width:30%"></i></div>
          <div class="bar"><i style="width:55%"></i></div><div class="bar"><i style="width:20%"></i></div>
        </div>
        <div class="lock-card">
          <strong class="serif" style="font-size:22px;line-height:1.15">See the full picture of how you read</strong>
          <ul class="perks"><li>The books behind every insight</li><li>Every subject and the authors you return to</li><li>More as your library grows</li></ul>
          <button class="btn primary" data-action="paywall">Unlock with Premium</button>
          <p class="note">Your Reader Identity overview stays free.</p>
        </div>
      </div>`;
  }

  function viewIdentity() {
    const d = state.identity;
    const langs = d.languages;
    const first = langs[0];
    return `
    <section class="screen">
      <div class="row">${SOC.on ? '<button class="btn line small" data-action="tab" data-tab="home">‹ Home</button>' : '<button class="btn line small" data-action="to-check">‹ My books</button>'}<span class="grow"></span>${premiumChip()}</div>
      <div><h1 class="serif mid">Your Reader Identity</h1><p class="sub">Who you are as a reader</p></div>
      <div class="card">
        <div class="eyebrow">AT A GLANCE</div>
        <div class="statement" dir="auto">${esc(d.statement)}</div>
        <div class="tiles">
          <div class="tile"><b>${d.books}</b><span>books in your taste</span></div>
          <div class="tile"><b>${langs.length}</b><span>language${langs.length === 1 ? '' : 's'}</span></div>
          <div class="tile"><b>${first ? esc(langName(first.name)) : '–'}</b><span>most read language</span></div>
          <div class="tile"><b class="cap">${d.subjects[0] ? esc(d.subjects[0].name) : '–'}</b><span>top subject</span></div>
        </div>
        ${langs.length ? `<div class="metric"><strong>Languages</strong>
          <div class="stackbar">${langs.map((l, i) => `<div style="flex:${l.count};background:${BARS[i % BARS.length]}"></div>`).join('')}</div>
          <div class="legend">${langs.map((l, i) => `<span><i style="display:inline-block;width:10px;height:10px;border-radius:5px;background:${BARS[i % BARS.length]}"></i> ${esc(langName(l.name))} ${Math.round(l.share * 100)}%</span>`).join('')}</div></div>` : ''}
        ${state.premium ? fullIdentity(d) : lockedIdentity(d)}
        <p class="note">${esc(d.note)} Confidence: ${esc(d.confidence)}.${d.confidence === 'low' ? ' Scan more shelves to sharpen it.' : ''}</p>
      </div>
      <div class="stack spacer">
        <button class="btn primary" data-action="scan-more">Scan more books</button>
        ${MOCK || LIVE
          ? '<button class="btn line" data-action="copy-csv">Copy my books (CSV)</button>'
          : '<button class="btn line" data-action="download-json">Download my books (JSON)</button><button class="btn line" data-action="download-csv">Download my books (CSV)</button>'}
        ${state.logged ? `<p class="note">Session saved for evaluation (${esc(state.logged)}).</p>` : ''}
      </div>
    </section>`;
  }

  const PERKS = [
    ['Your full identity', 'The books behind each insight, every subject, the authors you return to.'],
    ['Smarter discovery', 'Filter by language, mood and length. Choose how far to branch out.'],
    ['Control what is shared', 'Choose by collection, genre or audience what appears in the feed.'],
    ['Reading recaps', 'Monthly and yearly recaps, made to share.'],
    ['Household shelf', 'One library for you and your partner, each with your own taste.'],
  ];

  function viewPaywall() {
    const on = state.premium;
    return `
    <section class="screen">
      <div class="row"><button class="btn line small" data-action="close-paywall">‹ Back</button><span class="grow"></span><span class="chip" style="background:var(--orange-tint);color:var(--orange-text)">Booked Premium</span></div>
      <h1 class="serif big">Go deeper into your reading.</h1>
      <div class="stack" style="gap:14px">${PERKS.map(([t, s]) => `<div><b>${esc(t)}</b><p class="note">${esc(s)}</p></div>`).join('')}</div>
      <div class="info">Always free: scanning, your Reader Identity overview, recommendations, wishlist, friends and the feed.</div>
      ${on ? `
        <div class="ok-box" role="status">Premium is on for this device (demo).</div>
        <button class="btn line" data-action="free-again">Switch back to Free (demo)</button>`
      : `
        <div class="plans" role="radiogroup" aria-label="Plan">
          <button class="plan${state.plan === 'yearly' ? ' sel' : ''}" role="radio" aria-checked="${state.plan === 'yearly'}" data-action="plan" data-plan="yearly"><span class="best">BEST VALUE</span><b>Yearly</b><span>[Annual price]</span><small>per year</small></button>
          <button class="plan${state.plan === 'monthly' ? ' sel' : ''}" role="radio" aria-checked="${state.plan === 'monthly'}" data-action="plan" data-plan="monthly"><b>Monthly</b><span>[Monthly price]</span><small>per month</small></button>
        </div>
        <button class="btn primary" data-action="go-premium">Continue</button>
        <p class="note" style="text-align:center">Demo: no payment is taken. You get Premium on this device, and can switch back any time.</p>`}
    </section>`;
  }

  function render() {
    const views = { loading: viewLoading, welcome: viewWelcome, start: viewStart, reading: viewReading, check: viewCheck, identity: viewIdentity, paywall: viewPaywall,
                    home: viewHome, library: viewLibrary, people: viewPeople, friend: viewFriend, me: viewMe, invite: viewInvite, story: viewStoryNew, storyview: viewStoryView };
    app.innerHTML = views[state.screen]() + (SOC.on && TABS.has(state.screen) ? tabBar() : '') + (SOC.on && state.drawer && state.screen === 'home' ? drawerHtml() : '');
    if (state.focus) {
      const el = document.getElementById(state.focus.id);
      if (el) { el.focus(); try { el.setSelectionRange(state.focus.pos, state.focus.pos); } catch { /* not a text input */ } }
    }
  }

  // ---------------------------------------------------------------- actions

  const byId = (id) => state.items.find((i) => i.id === id);

  async function addFiles(fileList) {
    const room = Math.max(0, (state.config.max_photos || 8) - state.files.length);
    if (fileList.length > room) state.error = `You can read up to ${state.config.max_photos || 8} photos at a time.`;
    const added = await Promise.all([...fileList].slice(0, room).map(async (f) => { const s = await shrink(f); return Object.assign(s, { url: URL.createObjectURL(s) }); }));
    state.files.push(...added);
    if (added.length === fileList.length) state.error = '';
    render();
  }

  async function scan() {
    state.screen = 'reading';
    state.error = '';
    render();
    try {
      const form = new FormData();
      state.files.forEach((f) => form.append('files', f, f.name));
      if (modelParam) form.append('model', modelParam);
      const data = await api('/api/scan', { method: 'POST', body: form });
      state.cost += data.cost_usd;
      for (const photo of data.photos) {
        if (photo.error) state.errors.push(`${photo.photo}: ${photo.error}`);
        state.unreadable += photo.unreadable || 0;
        for (const m of photo.items) {
          const base = { id: `i${++uid}`, photo: photo.photo, read: m.read, candidates: m.candidates, decision: m.decision, action: m.decision, choice: null };
          if (m.decision === 'auto') state.items.push({ ...base, status: 'matched', choice: m.candidates[0] });
          else if (m.decision === 'confirm') state.items.push({ ...base, status: 'check' });
          else state.items.push({ ...base, status: 'missing' });
        }
      }
      data.photos.forEach((photo, i) => { if (state.files[i]) state.shelves.push({ url: state.files[i].url, count: photo.items.length }); });
      state.files = [];
      state.config.spent_usd = data.spent_usd;
      state.screen = 'check';
    } catch (e) {
      state.error = e.message;
      state.screen = 'start';
    }
    render();
  }

  let searchTimer;
  function runSearch(id, q) {
    if (LIVE) return; // each search asks Claude, so it runs on the Search button, not on every keystroke
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      if (q.trim().length < 2) return;
      try { byId(id).found = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { state.errors.push(e.message); }
      render();
    }, 400);
  }

  function setChoice(it, work, action) { it.choice = work; it.status = 'matched'; it.action = action; }

  async function showIdentity() {
    if (SOC.on) await commitItems();
    const books = identityPool().map((i) => ({
      work_id: i.choice.work_id || '', title: i.choice.title, authors: i.choice.authors || [],
      language: i.read.language || i.choice.language || '', subjects: i.choice.subjects || [],
    }));
    try {
      state.identity = await api('/api/identity', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ books }) });
      state.screen = 'identity';
      if (state.config.logging) {
        const items = [...state.items.map((i, n) => ({ photo: i.photo, position: n + 1, read: i.read, action: i.status === 'matched' ? i.action : 'unmatched', final: i.choice })),
                       ...state.removed.map((i) => ({ photo: i.photo, position: 0, read: i.read, action: 'removed', final: null }))];
        const res = await api('/api/log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items }) });
        state.logged = res.saved ? res.file : '';
      }
    } catch (e) { state.errors.push(e.message); state.screen = 'check'; }
    render();
  }

  function download(name, type, text) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function toast(message) {
    const el = Object.assign(document.createElement('div'), { className: 'toast', textContent: message, role: 'status' });
    document.body.append(el);
    setTimeout(() => el.remove(), 2600);
  }
  const mine = () => (SOC.on ? SOC.library : state.items.filter((i) => i.status === 'matched').map((i) => i.choice));
  const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;

  const actions = {
    enter: () => { state.screen = 'start'; window.scrollTo(0, 0); render(); },
    'close-scan': () => { if (SOC.on) goTab('home'); else { state.screen = state.items.length ? 'check' : 'welcome'; render(); } },
    take: () => document.getElementById('cam').click(),
    choose: () => document.getElementById('pick').click(),
    'drop-file': (el) => { const [f] = state.files.splice(Number(el.dataset.i), 1); URL.revokeObjectURL(f.url); render(); },
    scan,
    'run-search': async (el) => {
      const it = byId(el.dataset.id); const q = (document.getElementById(`q-${it.id}`) || {}).value || it.read.title;
      it.query = q; it.searching = true; render();
      try { it.found = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { state.errors.push(e.message); }
      it.searching = false; render();
    },
    'scan-more': () => { state.screen = 'start'; render(); },
    'to-check': () => { state.screen = 'check'; render(); },
    pick: (el) => { const it = byId(el.dataset.id); setChoice(it, it.candidates[Number(el.dataset.i)], 'confirmed'); render(); },
    none: (el) => { byId(el.dataset.id).status = 'missing'; render(); },
    'pick-found': (el) => { const it = byId(el.dataset.id); setChoice(it, it.found[Number(el.dataset.i)], 'manual'); render(); },
    'add-typed': (el) => {
      const it = byId(el.dataset.id);
      setChoice(it, { work_id: '', title: it.read.title, authors: it.read.author ? [it.read.author] : [], language: it.read.language, subjects: [] }, 'manual');
      render();
    },
    remove: (el) => { const i = state.items.findIndex((x) => x.id === el.dataset.id); state.removed.push(...state.items.splice(i, 1)); render(); },
    identity: () => (SOC.on ? finishScan() : showIdentity()),
    'toggle-select': () => { state.selecting = !state.selecting; render(); },
    'add-row': () => { state.items.push({ id: `i${++uid}`, photo: '', read: { title: '', author: '', language: '', confidence: 0 }, candidates: [], decision: 'manual', action: 'manual', choice: null, status: 'missing', query: '' }); render(); const el = document.querySelector('.crow:last-child input'); if (el) el.focus(); },
    paywall: () => { state.paywallFrom = state.screen; state.screen = 'paywall'; window.scrollTo(0, 0); render(); },
    'close-paywall': () => { state.screen = state.paywallFrom || 'start'; render(); },
    plan: (el) => { state.plan = el.dataset.plan; render(); },
    'go-premium': () => { state.premium = true; store.set('booked.premium', '1'); state.screen = state.paywallFrom || 'start'; render(); toast('Premium is on (demo)'); },
    'free-again': () => { state.premium = false; store.set('booked.premium', '0'); state.screen = state.paywallFrom || 'start'; render(); toast('Back to Free'); },
    'copy-csv': async (el) => {
      const text = ['title,author,language,work_id', ...mine().map((b) => [b.title, (b.authors || [])[0], b.language, b.work_id].map(csvCell).join(','))].join('\n');
      try { await navigator.clipboard.writeText(text); toast('Copied your books'); } catch { toast('Copy is blocked here'); }
    },
    'download-json': () => download('my-books.json', 'application/json', JSON.stringify(mine(), null, 2)),
    'download-csv': () => download('my-books.csv', 'text/csv', ['title,author,language,work_id', ...mine().map((b) => [b.title, (b.authors || [])[0], b.language, b.work_id].map(csvCell).join(','))].join('\n')),
  };


  // ================================================================================================
  // Social layer (live-in-Claude only). Sign-in is the viewer's Claude account (`user`); the private
  // library lives in the viewer's own `data/users/<id>/` subtree (`db`); what they choose to share goes
  // to `public/<id>`, `posts/<id>/items` and `reactions/<id>`, which everyone with access to this page
  // can read and only the owner of each id can write. Recommendations come from Claude (`sample`).
  // Only ids are stored, never names; names are resolved at render time. Everything read from the
  // store is other people's input and is escaped before it reaches the DOM.
  // ================================================================================================
  const SOC = {
    on: false, db: null, user: null, uid: '', name: '', avatar: '', library: [], wishlist: [],
    prefs: { following: [], sharing: 'off', joined: false, joinedAt: 0, recs: [], recsAt: 0, circleHidden: false },
    members: {}, posts: [], given: {}, profiles: {}, readOnly: false, loading: false, loaded: false, q: null,
  };
  const BLANK_AV = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E%3Crect width='40' height='40' rx='20' fill='%23d9d9d3'/%3E%3C/svg%3E";
  const SHARING = {
    off: ['Private', 'Nobody sees your books. Your name is visible to people with access to this page.'],
    highlights: ['Highlights', 'Your 12 most recently added books and your Reader Identity overview.'],
    everything: ['Everything', 'Your whole library and your Reader Identity overview.'],
  };
  const TABS = new Set(['home', 'library', 'people', 'me', 'friend', 'identity', 'invite']);
  const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
  const bookKey = (b) => `${fold(b.title)}|${fold((b.authors || [])[0] || '')}`;
  const P = (id) => SOC.profiles[id] || { id, name: '', avatarUrl: BLANK_AV };
  const nameOf = (id) => (id === SOC.uid ? 'You' : P(id).name || 'Someone');
  const av = (id, size = 36) => `<img class="av" style="width:${size}px;height:${size}px" src="${esc(P(id).avatarUrl)}" alt="">`;
  const ago = (t) => { const m = (Date.now() - num(t)) / 60000; return m < 1 ? 'now' : m < 60 ? `${Math.floor(m)} min` : m < 1440 ? `${Math.floor(m / 60)} h` : `${Math.floor(m / 1440)} d`; };
  const libPath = () => `data/users/${SOC.uid}/library`;
  const prefsPath = () => `data/users/${SOC.uid}/prefs`;
  const cleanBook = (b) => ({
    title: str(b && b.title).slice(0, 200), authors: strs(b && b.authors).slice(0, 3), language: str(b && b.language).slice(0, 8),
    subjects: strs(b && b.subjects).slice(0, 5), year: Number.isInteger(b && b.year) ? b.year : null,
  });
  const toIdBook = (b) => ({ work_id: b.work_id || '', title: b.title, authors: b.authors || [], language: b.language || '', subjects: b.subjects || [] });
  const identityPool = () => (SOC.on ? SOC.library.map((b) => ({ choice: b, read: { title: b.title, language: b.language } })) : state.items.filter((i) => i.status === 'matched'));

  function put(ref, data) {
    SOC.q = (SOC.q || Promise.resolve()).then(() => ref.set(data)).catch((e) => {
      if (e && e.code === 'invalid_argument') SOC.readOnly = true;
      toast(e && e.code === 'quota_exceeded' ? 'Storage for this page is full.' : 'Could not save that. Try again.');
      render();
    });
    return SOC.q;
  }
  const saveLibrary = () => put(SOC.db.doc(libPath()), { books: SOC.library, wishlist: SOC.wishlist });
  const savePrefs = () => put(SOC.db.doc(prefsPath()), SOC.prefs);

  function publishPublic() {
    const mode = SOC.prefs.sharing;
    const lib = SOC.library;
    const shown = mode === 'everything' ? lib : mode === 'highlights' ? lib.slice(-12) : [];
    const id = mode === 'off' ? null : mockIdentity(lib.map(toIdBook));
    return put(SOC.db.doc(`public/${SOC.uid}`), {
      sharing: mode, joinedAt: SOC.prefs.joinedAt || Date.now(), updated: Date.now(), count: mode === 'off' ? 0 : lib.length,
      statement: id ? id.statement : '', subjects: id ? id.subjects.slice(0, 3).map((x) => x.name) : [], languages: id ? id.languages.slice(0, 3).map((x) => x.name) : [],
      books: shown.map(cleanBook),
    });
  }

  async function ensureProfiles(ids) {
    const list = [...new Set(ids.filter(Boolean))];
    if (!list.length || !SOC.user) return;
    try { Object.assign(SOC.profiles, await SOC.user.profiles(list)); } catch { /* names stay blank */ }
  }

  async function initSocial() {
    try {
      if (!window.claude) return;
      const [user, db] = await Promise.all([window.claude.use('user'), window.claude.use('db')]);
      if (!user || !db) return;
      const me = await user.me();
      if (!me.id) return;
      Object.assign(SOC, { user, db, uid: me.id, name: me.name || '', avatar: me.avatarUrl || '' });
      SOC.profiles[me.id] = { id: me.id, name: me.name, avatarUrl: me.avatarUrl, isMe: true };
      const [lib, pr] = await Promise.all([db.doc(libPath()).get(), db.doc(prefsPath()).get()]);
      const l = lib.exists ? lib.data() : {};
      SOC.library = (Array.isArray(l.books) ? l.books : []).map((b) => ({ ...b }));
      SOC.wishlist = (Array.isArray(l.wishlist) ? l.wishlist : []).map((b) => ({ ...b }));
      const p = pr.exists ? pr.data() : {};
      SOC.prefs = {
        following: strs(p.following), sharing: Object.hasOwn(SHARING, p.sharing) ? p.sharing : 'off', joined: !!p.joined, joinedAt: num(p.joinedAt),
        recs: Array.isArray(p.recs) ? p.recs.map((r) => ({ ...r })) : [], recsAt: num(p.recsAt), circleHidden: !!p.circleHidden,
      };
      SOC.on = true;
    } catch { SOC.on = false; }
  }

  async function loadSocial() {
    if (!SOC.on || SOC.loading) return;
    SOC.loading = true;
    render();
    try {
      const ids = [SOC.uid, ...SOC.prefs.following];
      const [pub, react, ...feeds] = await Promise.all([
        SOC.db.collection('public').limit(300).get(),
        SOC.db.collection('reactions').limit(300).get(),
        ...ids.map((id) => SOC.db.collection(`posts/${id}/items`).orderBy('ts', 'desc').limit(10).get()
          .then((snap) => snap.docs.map((d) => ({ id: d.id, author: id, ...d.data() }))).catch(() => [])),
      ]);
      SOC.members = {};
      pub.docs.forEach((d) => { if (d.id !== SOC.uid) SOC.members[d.id] = { id: d.id, ...d.data() }; });
      SOC.given = {};
      react.docs.forEach((d) => { const g = d.data().given; SOC.given[d.id] = Array.isArray(g) ? g : []; });
      SOC.posts = feeds.flat().filter((x) => x && typeof x.book === 'object').sort((a, b) => num(b.ts) - num(a.ts)).slice(0, 40);
      await ensureProfiles([...Object.keys(SOC.members), ...SOC.posts.map((x) => x.author), ...Object.keys(SOC.given), ...SOC.prefs.following]);
      SOC.loaded = true;
    } catch { toast('Could not load your friends. Pull to refresh.'); }
    SOC.loading = false;
    render();
  }

  const bravoers = (author, pid) => Object.entries(SOC.given).filter(([, list]) => list.some((g) => g && g.a === author && g.p === pid)).map(([id]) => id);

  // ---- views
  const tabIcon = {
    home: '<path d="M4 11l8-7 8 7v9H4z"></path>',
    library: '<path d="M5 4h4v16H5zM10 4h4v16h-4zM15.5 5l4 .8-3 14.2-4-.8z"></path>',
    start: ICON.camera, people: ICON.people,
    me: '<circle cx="12" cy="8" r="4"></circle><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"></path>',
  };
  function tabBar() {
    const t = [['home', 'Home'], ['library', 'Library'], ['start', 'Scan'], ['people', 'Friends'], ['me', 'Me']];
    const cur = state.screen === 'friend' ? 'people' : (state.screen === 'identity' || state.screen === 'invite') ? 'home' : state.screen;
    return `<nav class="tabs" aria-label="Main">${t.map(([k, l]) => `
      <button class="tab${cur === k ? ' on' : ''}" data-action="tab" data-tab="${k}" ${cur === k ? 'aria-current="page"' : ''}>${svg(tabIcon[k], 24, 'currentColor')}<span>${l}</span></button>`).join('')}</nav>`;
  }
  const readOnlyBanner = () => (SOC.readOnly ? '<div class="warn" role="alert">You can look around, but your changes are not saved. Ask the owner to share this page with you as a Contributor.</div>' : '');

  function viewLoading() {
    return `<section class="screen hero center"><div class="spinner" role="status" aria-label="Loading"></div><h1 class="serif mid">Opening your shelf…</h1></section>`;
  }

  const postCard = (x) => {
    const mineP = x.author === SOC.uid;
    const who = bravoers(x.author, x.id);
    const gaveBravo = who.includes(SOC.uid);
    const b = x.book || {};
    return `
    <article class="post">
      <div class="row">${av(x.author)}<div class="grow"><b>${esc(nameOf(x.author))}</b> <span class="note">· ${esc(ago(x.ts))}</span></div>
        ${mineP ? `<button class="x" data-action="post-del" data-id="${esc(x.id)}" aria-label="Delete this post">×</button>` : ''}</div>
      <div class="row" style="align-items:flex-start">${cover(str(b.title))}<div class="grow">
        <div class="title" dir="auto">${esc(str(b.title))}</div><div class="author" dir="auto">${esc(strs(b.authors).slice(0, 2).join(', '))}</div>
        ${x.text ? `<p dir="auto" style="margin-top:6px">${esc(str(x.text))}</p>` : ''}</div></div>
      <div class="row">
        ${mineP ? '' : `<button class="chip bravo${gaveBravo ? ' on' : ''}" data-action="bravo" data-a="${esc(x.author)}" data-p="${esc(x.id)}" aria-pressed="${gaveBravo}">${gaveBravo ? '★ Bravo given' : '☆ Bravo'}</button>`}
        <span class="note">${who.length ? `${who.length} Bravo${who.length > 1 ? 's' : ''}` : ''}</span>
        ${mineP && who.length ? (state.premium ? `<span class="note">from ${who.map((id) => esc(nameOf(id))).join(', ')}</span>` : '<button class="chip prem" data-action="paywall">See who · Premium</button>') : ''}
      </div>
    </article>`;
  };

  const recCard = (r, i) => {
    const src = r.from && r.from !== 'taste' ? `Because ${esc(nameOf(r.from))} read it` : 'From your taste';
    const wished = SOC.wishlist.some((w) => bookKey(w) === bookKey(r));
    return `<div class="rec"><div class="row" style="align-items:flex-start">${cover(str(r.title))}<div class="grow">
      <div class="title" dir="auto">${esc(str(r.title))}</div><div class="author" dir="auto">${esc(strs(r.authors).slice(0, 2).join(', '))}</div>
      <p class="note" dir="auto" style="margin-top:4px">${esc(str(r.why))}</p><p class="note"><b>${src}</b></p></div></div>
      <button class="btn line small" data-action="wish-rec" data-i="${i}" ${wished ? 'disabled' : ''}>${wished ? 'On your wishlist' : 'Add to wishlist'}</button></div>`;
  };

  const activeStories = () => SOC.posts.filter((x) => x.story && num(x.exp) > Date.now());
  const storyBy = (id) => activeStories().find((x) => x.author === id);
  const ringBtn = (kind, inner, label, action, id = '') => `
    <button class="friend" data-action="${action}" ${id ? `data-id="${esc(id)}"` : ''}><span class="ring ${kind}">${inner}</span><span class="rl">${esc(label)}</span></button>`;
  const discHtml = (bg, content, fg = '#16161A') => `<span class="disc" style="background:${bg};color:${fg}">${content}</span>`;

  function bandHtml() {
    const mine = storyBy(SOC.uid);
    const cov = '<span class="disc" style="background:#B8704F"><i style="display:block;width:38%;height:62%;background:#7B3F24;border-radius:3px 3px 0 0;margin-top:30%"></i></span>';
    const rings = [
      ringBtn('ghost', discHtml('#fff', svg('<path d="M9 8a3.5 3.5 0 1 0 7 0 3.5 3.5 0 0 0-7 0M3 20c0-3.6 2.9-6 6.5-6M18 14v6M15 17h6"></path>', 22, '#0F5F58')), 'Invite', 'invite'),
      mine ? ringBtn('new', cov, 'Your story', 'story-view', SOC.uid) : ringBtn('add', discHtml('#F3F3EF', svg('<path d="M12 5v14M5 12h14"></path>', 22, '#6B6B73')), 'Your story', 'story-new'),
      ...SOC.prefs.following.map((f) => (storyBy(f) ? ringBtn('new', `<img class="av disc" src="${esc(P(f).avatarUrl)}" alt="">`, nameOf(f).split(' ')[0], 'story-view', f)
        : ringBtn('seen', `<img class="av disc" src="${esc(P(f).avatarUrl)}" alt="">`, nameOf(f).split(' ')[0], 'open-friend', f))),
    ];
    return `<div class="strip">${rings.join('')}</div>`;
  }

  function circleArt() {
    const cx = 159, cy = 78;
    const F = [[293, 78, 'D', '#F1E7DA', '#3C3A6E'], [226, 28, 'Y', '#E6E3F2', '#B8704F'], [92, 28, 'N', '#F2E4E4', '#7FA08B'], [25, 78, 'A', '#E9EDF2', '#A8403A'], [92, 128, 'M', '#E4F0EE', '#E2B93B'], [226, 128, 'R', '#F8EAC8', '#2F4858']];
    const parts = F.map(([x, y, ch, bg, book]) => {
      const vx = cx - x, vy = cy - y, d = Math.hypot(vx, vy);
      const bx = x + (31 * vx) / d, by = y + (31 * vy) / d, tilt = x < cx ? 14 : -14;
      return `<span class="cbook" style="left:${Math.round(bx - 9)}px;top:${Math.round(by - 13)}px;background:${book};transform:rotate(${tilt}deg)"></span><span class="cav" style="left:${x - 18}px;top:${y - 18}px;background:${bg}">${ch}</span>`;
    }).join('');
    return `<div class="cart" aria-hidden="true"><div class="ring1"></div><div class="ring2"></div><span class="glow"></span>${parts}<span class="you">${esc((SOC.name || 'You').trim()[0] || 'Y')}</span></div>`;
  }

  const circleCard = () => `
    <section class="circle">
      <div class="row"><h2 class="grow" style="font-size:17px;font-weight:700">Build your circle</h2><button class="x" style="margin:-8px -12px -8px 0" data-action="hide-circle" aria-label="Hide this">${svg('<path d="M6 6l12 12M18 6L6 18"></path>', 20, '#16161A')}</button></div>
      ${circleArt()}
      <h3 class="serif" style="font-size:27px;line-height:1.1;font-weight:600">Get recommendations from people you trust</h3>
      <button class="btn dark" data-action="invite">Invite friends</button>
    </section>`;

  const bandEmpty = () => `
    <section class="bandempty">
      <div class="row" style="gap:14px;align-items:center">${bandHtml().replace('class="strip"', 'class="strip" style="overflow:visible"')}
        <div class="grow"><b>Friends’ stories</b><div class="note">Nothing yet. Write one, or bring a friend along.</div></div></div>
      <div class="row" style="gap:8px"><button class="btn primary small grow" data-action="story-new">Write a story</button><button class="btn line small grow" data-action="invite">Invite friends</button></div>
    </section>`;

  const progressCard = (n) => `
    <section class="progress"><div class="row"><b class="grow">Build your circle</b><b>${n} of 3</b></div>
      <div class="row" style="gap:6px">${[0, 1, 2].map((i) => `<span class="seg3${i < n ? ' on' : ''}"></span>`).join('')}</div>
      <div class="row" style="gap:12px"><span class="grow note" style="color:#4a4a52;font-size:14px">${3 - n} more friend${3 - n === 1 ? '' : 's'} and your recommendations get much sharper.</span><button class="btn dark small" data-action="invite">Invite</button></div>
    </section>`;

  function identityCard(id) {
    const subs = id.subjects.slice(0, 3).map((x) => `<span class="chip ok cap">${esc(x.name)}</span>`).join('');
    return `<button class="card idcard" data-action="show-identity">
      <div class="eyebrow">YOUR READER IDENTITY</div>
      <div class="statement" dir="auto" style="font-size:23px">${esc(id.statement)}</div>
      <div class="chips">${subs}</div></button>`;
  }

  function drawerHtml() {
    const id = mockIdentity(SOC.library.map(toIdBook));
    const subs = id.subjects.slice(0, 3).map((x) => `<span class="chip ok cap">${esc(x.name)}</span>`).join('');
    const sky = [16, 28, 22, 34, 20, 30, 24, 36, 18, 32, 26, 22, 34, 20, 28, 24, 30, 18].map((h, i) => `<i style="height:${h}px;background:${['#CFE3DF', '#B7D3CE', '#E4F0EE', '#9DC3BC'][i % 4]}"></i>`).join('');
    return `<div class="scrim" data-action="close-drawer"></div>
    <section class="drawer" role="dialog" aria-label="Your Reader Identity">
      <div class="grab"></div>
      <div class="row"><span class="eyebrow grow">YOUR READER IDENTITY</span><span class="note">1 of 6</span><button class="x" style="margin:-8px -12px -8px 0" data-action="close-drawer" aria-label="Close">${svg('<path d="M6 6l12 12M18 6L6 18"></path>', 20, '#16161A')}</button></div>
      <div class="statement" dir="auto" style="font-size:31px">${esc(id.statement)}</div>
      <div class="chips">${subs}</div>
      <div class="tiles"><div class="tile"><b>${id.books}</b><span>books in your taste</span></div><div class="tile"><b>${id.languages.length}</b><span>language${id.languages.length === 1 ? '' : 's'}</span></div></div>
      <div class="sky">${sky}</div>
      <button class="btn primary" style="min-height:52px" data-action="explore">Explore my identity</button>
      <button class="btn text" data-action="close-drawer">Maybe later</button>
      <p class="note" style="text-align:center">It stays on your Home, any time.</p>
    </section>`;
  }

  function viewHome() {
    const id = mockIdentity(SOC.library.map(toIdBook));
    const n = SOC.prefs.following.length;
    const feed = SOC.posts.filter((x) => !x.story);
    let top;
    if (n === 0 && !SOC.prefs.circleHidden) top = `${bandHtml()}${circleCard()}`;
    else if (n === 0) top = bandEmpty();
    else top = `${bandHtml()}${n < 3 ? progressCard(n) : ''}`;
    return `
    <section class="screen">
      <div class="row"><h1 class="grow" style="font-size:28px;letter-spacing:-0.5px">Home</h1>${premiumChip()}
        <span class="av" style="width:40px;height:40px;background:#E4F0EE;color:#0F5F58;font:700 16px var(--ui);display:flex;align-items:center;justify-content:center">${esc((SOC.name || 'E').trim()[0] || 'E')}</span></div>
      ${readOnlyBanner()}
      ${top}
      ${SOC.library.length ? identityCard(id) : `
      <div class="card"><div class="statement" style="font-size:24px">Scan your first shelf.</div><p class="sub">One photo adds dozens of books and starts your Reader Identity.</p>
        <button class="btn primary" data-action="scan-more">Scan a shelf</button></div>`}
      ${n > 0 || feed.length ? `<h2 class="h2">From your friends circle</h2>
      ${SOC.loading && !SOC.loaded ? '<p class="note">Loading…</p>' : feed.length ? feed.map(postCard).join('') : '<div class="tip">Nothing here yet. Post a book from your library to start the conversation.</div>'}` : ''}
      <h2 class="h2">Recommended for you</h2>
      ${SOC.prefs.recs.length ? SOC.prefs.recs.map(recCard).join('') : ''}
      ${SOC.library.length >= 3
        ? `<button class="btn ${SOC.prefs.recs.length ? 'line small' : 'dark'}" data-action="recs-get" ${state.recsBusy ? 'disabled' : ''}>${state.recsBusy ? 'Asking Claude…' : SOC.prefs.recs.length ? 'Get new recommendations' : 'Recommend books for me'}</button>`
        : '<div class="tip">Add at least 3 books to your library to get recommendations.</div>'}
      ${state.recsError ? `<div class="err" role="alert">${esc(state.recsError)}</div>` : ''}
    </section>`;
  }

  function viewInvite() {
    const members = Object.values(SOC.members).sort((a, b) => num(b.updated) - num(a.updated));
    return `
    <section class="screen">
      <div class="row"><button class="round soft" data-action="tab" data-tab="home" aria-label="Back">${svg('<path d="M15 5l-7 7 7 7"></path>', 22, '#16161A')}</button></div>
      <h1 class="serif" style="font-size:34px;line-height:1.08;font-weight:500;letter-spacing:-0.3px">Invite friends</h1>
      <div class="info" style="font-size:14px;line-height:1.45"><b>Bring someone new.</b> Open this page’s Share menu and add them as a Contributor. They show up below after they open Booked and continue.<br><br>Phone and email contacts arrive with the iPhone app.</div>
      <h2 class="h2">People on Booked</h2>
      ${members.length ? members.map((m) => `
        <div class="row item" style="padding:10px 0">${av(m.id, 44)}
          <button class="grow link-row" data-action="open-friend" data-id="${esc(m.id)}"><b>${esc(nameOf(m.id))}</b>
            <div class="note">${m.sharing && m.sharing !== 'off' ? `${num(m.count)} book${num(m.count) === 1 ? '' : 's'} shared` : 'Keeps their shelf private'}</div></button>
          ${followBtn(m.id)}</div>`).join('') : SOC.loading ? '<p class="note">Loading…</p>' : '<div class="tip">Nobody else has joined yet.</div>'}
    </section>`;
  }

  const STORY_KINDS = { finished: 'I JUST FINISHED', reading: 'NOW READING', quote: 'A LINE I LOVED' };
  const storyBg = (t) => ['#B8704F', '#2F4858', '#3C3A6E', '#7FA08B', '#A8403A'][hash(String(t)) % 5];

  function viewStoryNew() {
    const lib = SOC.library.slice().reverse();
    const cur = findBook(SOC.library, state.storyBook) || lib[0];
    const kind = state.storyKind || 'finished';
    return `
    <section class="screen" style="background:#F8F8F5">
      <div class="row"><button class="round soft" style="background:#fff" data-action="story-close" aria-label="Close">${svg('<path d="M6 6l12 12M18 6L6 18"></path>', 22, '#16161A')}</button><b class="grow" style="text-align:center;font-size:17px">Your story</b><span style="width:44px"></span></div>
      ${cur ? `
      <div class="row" style="gap:8px;flex-wrap:wrap">${Object.entries(STORY_KINDS).map(([k, l]) => `<button class="pill${kind === k ? ' on' : ''}" data-action="story-kind" data-k="${k}">${esc({ finished: 'Finished a book', reading: 'Now reading', quote: 'A line I loved' }[k])}</button>`).join('')}</div>
      <label class="note" for="story-book">Book</label>
      <select id="story-book" data-input="story-book">${lib.map((b) => `<option value="${esc(bookKey(b))}" ${bookKey(b) === bookKey(cur) ? 'selected' : ''}>${esc(str(b.title))}</option>`).join('')}</select>
      <label class="note" for="story-text">Say something (optional)</label>
      <input id="story-text" data-input="story-text" maxlength="100" dir="auto" value="${esc(state.storyText || '')}" autocomplete="off">
      <div class="storycard" style="background:${storyBg(cur.title)}">
        <span class="eyebrow" style="color:#fff">${STORY_KINDS[kind]}</span>
        <div>${cover(str(cur.title))}<div class="serif" id="story-preview" dir="auto" style="font-size:30px;line-height:1.1;color:#fff;margin-top:14px">${esc(state.storyText || '')}</div>
          <div style="color:#fff;font-size:14px;margin-top:8px" dir="auto">${esc(str(cur.title))}${strs(cur.authors)[0] ? ' · ' + esc(strs(cur.authors)[0]) : ''}</div></div>
        <span style="font-size:12px;color:#fff">Disappears in 24 hours</span></div>
      <button class="btn primary" data-action="story-share">Share to your story</button>` : '<div class="tip">Add a book to your library first, then write a story about it.</div>'}
    </section>`;
  }

  function viewStoryView() {
    const x = storyBy(state.storyOf);
    if (!x) return `<section class="screen"><button class="btn line small" data-action="tab" data-tab="home">‹ Home</button><div class="tip">That story has ended.</div></section>`;
    const b = x.book || {};
    const gave = bravoers(x.author, x.id).includes(SOC.uid);
    return `
    <section class="screen" style="background:${storyBg(b.title)};color:#fff">
      <div class="row">${av(x.author, 40)}<b class="grow">${esc(nameOf(x.author))} <span style="font-weight:400;opacity:.8">· ${esc(ago(x.ts))}</span></b><button class="round" data-action="tab" data-tab="home" aria-label="Close">${svg('<path d="M6 6l12 12M18 6L6 18"></path>', 22, '#16161A')}</button></div>
      <span class="eyebrow" style="color:#fff">${STORY_KINDS[x.kind] || 'ON THE SHELF'}</span>
      <div style="margin:auto 0">${cover(str(b.title))}<div class="serif" dir="auto" style="font-size:34px;line-height:1.1;margin-top:16px">${esc(str(x.text))}</div>
        <div dir="auto" style="margin-top:10px">${esc(str(b.title))}${strs(b.authors)[0] ? ' · ' + esc(strs(b.authors)[0]) : ''}</div></div>
      ${x.author === SOC.uid ? '' : `<button class="btn ${gave ? 'dark' : 'ghost'}" data-action="bravo" data-a="${esc(x.author)}" data-p="${esc(x.id)}">${gave ? '★ Bravo given' : '☆ Bravo'}</button>`}
    </section>`;
  }

  function viewLibrary() {
    const seg = state.seg || 'books';
    const list = seg === 'books' ? SOC.library : SOC.wishlist;
    const rows = list.map((b, i) => ({ b, i })).reverse().map(({ b }) => `
      <div class="item"><div class="row">${cover(str(b.title))}
        <div class="grow"><div class="title" dir="auto">${esc(str(b.title))}</div><div class="author" dir="auto">${esc(strs(b.authors).slice(0, 2).join(', '))}</div>
          <div class="chips" style="margin-top:6px">${b.language ? `<span class="chip lang">${esc(langName(b.language))}</span>` : ''}</div></div>
        ${seg === 'books' ? `<button class="x" data-action="lib-remove" data-k="${esc(bookKey(b))}" aria-label="Remove ${esc(str(b.title))}">×</button>`
          : `<button class="x" data-action="wish-remove" data-k="${esc(bookKey(b))}" aria-label="Remove ${esc(str(b.title))}">×</button>`}</div>
        <div class="row" style="padding-left:56px">${seg === 'books'
          ? `<button class="btn line small" data-action="post-open" data-k="${esc(bookKey(b))}">Post to friends</button>`
          : `<button class="btn line small" data-action="wish-got" data-k="${esc(bookKey(b))}">I have it</button>`}</div>
        ${state.composing === bookKey(b) && seg === 'books' ? `<div class="find" style="padding-left:56px"><label class="note" for="post-text">Say something (optional)</label>
          <textarea id="post-text" data-input="post" maxlength="300" rows="3" dir="auto">${esc(state.postText || '')}</textarea>
          <div class="row"><button class="btn dark small" data-action="post-send" data-k="${esc(bookKey(b))}">Post</button><button class="btn line small" data-action="post-cancel">Cancel</button></div></div>` : ''}
      </div>`).join('');
    return `
    <section class="screen">
      <h1 class="serif mid">Library</h1>
      ${readOnlyBanner()}
      <div class="seg" role="tablist"><button class="${seg === 'books' ? 'on' : ''}" data-action="seg" data-seg="books">My books · ${SOC.library.length}</button><button class="${seg === 'wish' ? 'on' : ''}" data-action="seg" data-seg="wish">Wishlist · ${SOC.wishlist.length}</button></div>
      <div class="find" style="padding:0"><label class="note" for="add-q">Add a book by title or author</label>
        <div class="row"><input id="add-q" class="grow" data-input="add" value="${esc(state.addq || '')}" dir="auto" autocomplete="off"><button class="btn dark small" data-action="run-add">Search</button></div>
        ${state.addBusy ? '<p class="note">Searching…</p>' : ''}
        ${(state.addFound || []).map((c, i) => `<button class="cand" data-action="add-book" data-i="${i}" dir="auto">${esc(c.title)}<small>${esc(c.authors.slice(0, 2).join(', '))}${c.year ? ' · ' + c.year : ''}</small></button>`).join('')}</div>
      ${list.length ? `<div>${rows}</div>` : `<div class="tip">${seg === 'books' ? 'No books yet. Scan a shelf or add one above.' : 'Your wishlist is empty. Add books from recommendations or a friend’s shelf.'}</div>`}
    </section>`;
  }

  const followBtn = (id) => (SOC.prefs.following.includes(id)
    ? `<button class="btn line small" data-action="unfollow" data-id="${esc(id)}">Following</button>`
    : `<button class="btn dark small" data-action="follow" data-id="${esc(id)}">Follow</button>`);

  function viewPeople() {
    const members = Object.values(SOC.members).sort((a, b) => num(b.updated) - num(a.updated));
    const found = (state.peopleFound || []).filter((p) => p.id !== SOC.uid);
    return `
    <section class="screen">
      <div class="row"><h1 class="serif mid grow">Friends</h1><button class="refresh" data-action="refresh" aria-label="Refresh">↻</button></div>
      ${readOnlyBanner()}
      <div class="find" style="padding:0"><label class="note" for="people-q">Find someone by name</label>
        <input id="people-q" data-input="people" value="${esc(state.peopleq || '')}" autocomplete="off">
        ${found.map((p) => `<div class="row item" style="padding:8px 0">${av(p.id)}<div class="grow"><b>${esc(p.name || 'Someone')}</b><div class="note">${SOC.members[p.id] ? 'On Booked' : 'Not on Booked yet'}</div></div>${SOC.members[p.id] ? followBtn(p.id) : ''}</div>`).join('')}</div>
      <h2 class="h2">On Booked</h2>
      ${members.length ? members.map((m) => `
        <div class="row item" style="padding:10px 0">${av(m.id, 44)}
          <button class="grow link-row" data-action="open-friend" data-id="${esc(m.id)}"><b>${esc(nameOf(m.id))}</b>
            <div class="note">${m.sharing && m.sharing !== 'off' ? `${num(m.count)} book${num(m.count) === 1 ? '' : 's'} shared` : 'Keeps their shelf private'}</div></button>
          ${followBtn(m.id)}</div>`).join('')
        : SOC.loading ? '<p class="note">Loading…</p>' : '<div class="tip">Nobody else has joined yet.</div>'}
      <div class="info">To invite someone, add them from this page’s Share menu as a Contributor. They appear here after they open Booked and continue.</div>
    </section>`;
  }

  function viewFriend() {
    const m = SOC.members[state.friendId];
    if (!m) return `<section class="screen"><button class="btn line small" data-action="tab" data-tab="people">‹ Friends</button><div class="tip">That reader has not shared anything.</div></section>`;
    const books = (Array.isArray(m.books) ? m.books : []).map(cleanBook);
    return `
    <section class="screen">
      <div class="row"><button class="btn line small" data-action="tab" data-tab="people">‹ Friends</button><span class="grow"></span>${followBtn(m.id)}</div>
      <div class="row">${av(m.id, 64)}<div><h1 class="serif mid">${esc(nameOf(m.id))}</h1><span class="note">${m.sharing === 'off' ? 'Keeps their shelf private' : `${num(m.count)} books`}</span></div></div>
      ${m.sharing !== 'off' && m.statement ? `<div class="card"><div class="eyebrow">READER IDENTITY</div><div class="statement" dir="auto" style="font-size:24px">${esc(str(m.statement))}</div>
        <div class="chips">${strs(m.subjects).map((x) => `<span class="chip">${esc(x)}</span>`).join('')}</div></div>` : ''}
      ${books.length ? `<h2 class="h2">On their shelf</h2><div>${books.map((b, i) => `<div class="item"><div class="row">${cover(b.title)}
        <div class="grow"><div class="title" dir="auto">${esc(b.title)}</div><div class="author" dir="auto">${esc(b.authors.slice(0, 2).join(', '))}</div></div>
        <button class="btn line small" data-action="wish-friend" data-i="${i}" ${SOC.wishlist.some((w) => bookKey(w) === bookKey(b)) ? 'disabled' : ''}>${SOC.wishlist.some((w) => bookKey(w) === bookKey(b)) ? 'Wishlisted' : 'Wishlist'}</button></div></div>`).join('')}</div>` : ''}
    </section>`;
  }

  function viewMe() {
    return `
    <section class="screen">
      <div class="row">${av(SOC.uid, 64)}<div class="grow"><h1 class="serif mid">${esc(SOC.name || 'You')}</h1><span class="note">Signed in with your Claude account</span></div>${premiumChip()}</div>
      ${readOnlyBanner()}
      <h2 class="h2">What friends can see</h2>
      <div class="stack">${Object.entries(SHARING).map(([k, [t, d]]) => `
        <button class="plan${SOC.prefs.sharing === k ? ' sel' : ''}" style="min-height:0" role="radio" aria-checked="${SOC.prefs.sharing === k}" data-action="set-sharing" data-mode="${k}"><b>${esc(t)}</b><small>${esc(d)}</small></button>`).join('')}</div>
      <p class="note">Anything you post is shared on purpose, whatever you pick here. Anyone who can open this page can see what you share.</p>
      <h2 class="h2">Your data</h2>
      <div class="stack">
        <button class="btn line" data-action="show-identity">See my Reader Identity</button>
        <button class="btn line" data-action="copy-csv">Copy my books (CSV)</button>
        ${state.confirmDelete
          ? `<div class="err" role="alert">This removes your library, wishlist, posts and Bravos from this page. It cannot be undone.</div>
             <button class="btn dark" data-action="delete-confirm">Yes, delete everything</button><button class="btn line" data-action="delete-cancel">Keep my data</button>`
          : '<button class="btn line" data-action="delete-data">Delete my Booked data</button>'}
      </div>
    </section>`;
  }

  // ---- recommendations (Claude, on the viewer's account)
  async function getRecs() {
    state.recsBusy = true; state.recsError = ''; render();
    try {
      const sample = await getSample();
      const mine = SOC.library.slice(-60).map((b) => `${b.title} — ${(b.authors || [])[0] || 'unknown'}`);
      const labelToId = {};
      const friendLines = SOC.prefs.following.filter((f) => SOC.members[f] && SOC.members[f].sharing !== 'off').slice(0, 6).map((f, i) => {
        labelToId[`F${i + 1}`] = f;
        return `F${i + 1}: ${(SOC.members[f].books || []).slice(0, 15).map((b) => str(b.title)).join('; ')}`;
      });
      const prompt = `You recommend books. The reader owns these books (title — author):\n${mine.join('\n')}\n\n${friendLines.length ? `Friends they follow shared these shelves:\n${friendLines.join('\n')}\n\n` : ''}Recommend 6 real, published books this reader would likely enjoy next. Never recommend a book they already own. Prefer books they can read in the languages they already read. ${friendLines.length ? 'Where a friend’s shelf is a good reason, say so and set "source" to that friend’s label (for example "F1"); otherwise set "source" to "taste". ' : 'Set "source" to "taste". '}Reply with only a JSON array of objects: {"title","authors":[],"language":"ISO 639-1","subjects":[up to 4 lowercase words],"year":null or number,"why":"one short sentence naming what on their shelf it connects to","source":"taste"}.`;
      const out = await sample.json(prompt, { modelTier: 'default' });
      const own = new Set(SOC.library.map(bookKey));
      SOC.prefs.recs = (Array.isArray(out) ? out : []).filter((r) => r && typeof r === 'object' && str(r.title))
        .map((r) => ({ ...cleanBook(r), why: str(r.why).slice(0, 240), from: labelToId[str(r.source)] || 'taste' }))
        .filter((r) => !own.has(bookKey(r))).slice(0, 6);
      SOC.prefs.recsAt = Date.now();
      await savePrefs();
      if (!SOC.prefs.recs.length) state.recsError = 'Claude had no new suggestions. Try again after adding more books.';
    } catch (e) { state.recsError = sampleError(e).message; }
    state.recsBusy = false; render();
  }

  // ---- actions
  async function commitItems() {
    const matched = state.items.filter((i) => i.status === 'matched');
    for (const it of matched) {
      const c = it.choice;
      const b = { ...cleanBook({ ...c, title: shelfTitle(it), language: it.read.language || c.language }), work_id: str(c.work_id), t: Date.now() };
      if (!SOC.library.some((x) => bookKey(x) === bookKey(b))) SOC.library.push(b);
      SOC.wishlist = SOC.wishlist.filter((w) => bookKey(w) !== bookKey(b));
    }
    state.items = state.items.filter((i) => i.status !== 'matched');
    await saveLibrary();
    await publishPublic();
  }
  const findBook = (list, k) => list.find((b) => bookKey(b) === k);

  function goTab(tab) {
    state.screen = tab; state.composing = null; window.scrollTo(0, 0); render();
    if ((tab === 'home' || tab === 'people') && SOC.on && !SOC.loaded) loadSocial();
  }

  const socialActions = {
    join: async () => {
      SOC.prefs.joined = true; SOC.prefs.joinedAt = SOC.prefs.joinedAt || Date.now();
      await savePrefs(); await publishPublic();
      if (SOC.library.length) goTab('home'); else { state.screen = 'start'; render(); }
    },
    tab: (el) => (el.dataset.tab === 'start' ? (state.screen = 'start', render()) : goTab(el.dataset.tab)),
    refresh: () => loadSocial(),
    'show-identity': async () => { await showIdentity(); },
    seg: (el) => { state.seg = el.dataset.seg; render(); },
    follow: async (el) => { const id = el.dataset.id; if (!SOC.prefs.following.includes(id)) SOC.prefs.following = [...SOC.prefs.following, id]; render(); await savePrefs(); SOC.loaded = false; loadSocial(); },
    unfollow: async (el) => { SOC.prefs.following = SOC.prefs.following.filter((x) => x !== el.dataset.id); render(); await savePrefs(); SOC.loaded = false; loadSocial(); },
    'open-friend': (el) => { state.friendId = el.dataset.id; state.screen = 'friend'; window.scrollTo(0, 0); render(); },
    bravo: async (el) => {
      const a = el.dataset.a, p = el.dataset.p;
      const mineList = (SOC.given[SOC.uid] || []).filter((g) => g && typeof g === 'object');
      const has = mineList.some((g) => g.a === a && g.p === p);
      SOC.given[SOC.uid] = has ? mineList.filter((g) => !(g.a === a && g.p === p)) : [...mineList, { a, p, t: Date.now() }].slice(-300);
      render();
      await put(SOC.db.doc(`reactions/${SOC.uid}`), { given: SOC.given[SOC.uid] });
    },
    'post-open': (el) => { state.composing = el.dataset.k; state.postText = ''; render(); },
    'post-cancel': () => { state.composing = null; render(); },
    'post-send': async (el) => {
      const b = findBook(SOC.library, el.dataset.k);
      if (!b) return;
      const text = (document.getElementById('post-text') || {}).value || '';
      state.composing = null; render();
      try {
        await SOC.db.collection(`posts/${SOC.uid}/items`).add({ ts: Date.now(), kind: 'book', book: cleanBook(b), text: text.trim().slice(0, 300) });
        toast('Posted to your friends'); SOC.loaded = false; loadSocial();
      } catch (e) { if (e && e.code === 'invalid_argument') { SOC.readOnly = true; render(); } toast('Could not post that. Try again.'); }
    },
    'post-del': async (el) => {
      try { await SOC.db.doc(`posts/${SOC.uid}/items/${el.dataset.id}`).delete(); SOC.posts = SOC.posts.filter((x) => x.id !== el.dataset.id); render(); } catch { toast('Could not delete that.'); }
    },
    'lib-remove': async (el) => { SOC.library = SOC.library.filter((b) => bookKey(b) !== el.dataset.k); render(); await saveLibrary(); publishPublic(); },
    'wish-remove': async (el) => { SOC.wishlist = SOC.wishlist.filter((b) => bookKey(b) !== el.dataset.k); render(); await saveLibrary(); },
    'wish-got': async (el) => {
      const b = findBook(SOC.wishlist, el.dataset.k);
      if (b && !findBook(SOC.library, el.dataset.k)) SOC.library.push({ ...cleanBook(b), work_id: '', t: Date.now() });
      SOC.wishlist = SOC.wishlist.filter((x) => bookKey(x) !== el.dataset.k); render(); await saveLibrary(); publishPublic();
    },
    'wish-rec': async (el) => { const r = SOC.prefs.recs[Number(el.dataset.i)]; if (r && !findBook(SOC.wishlist, bookKey(r))) { SOC.wishlist.push(cleanBook(r)); render(); toast('Added to your wishlist'); await saveLibrary(); } },
    'wish-friend': async (el) => {
      const m = SOC.members[state.friendId]; const b = m && (m.books || [])[Number(el.dataset.i)];
      if (b && !findBook(SOC.wishlist, bookKey(b))) { SOC.wishlist.push(cleanBook(b)); render(); toast('Added to your wishlist'); await saveLibrary(); }
    },
    'recs-get': getRecs,
    'set-sharing': async (el) => { SOC.prefs.sharing = el.dataset.mode; render(); await savePrefs(); publishPublic(); toast(`Sharing: ${SHARING[el.dataset.mode][0]}`); },
    'run-add': async () => {
      const q = (document.getElementById('add-q') || {}).value || '';
      if (q.trim().length < 2) return;
      state.addq = q; state.addBusy = true; state.addFound = []; render();
      try { state.addFound = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { toast(e.message); }
      state.addBusy = false; render();
    },
    'add-book': async (el) => {
      const c = (state.addFound || [])[Number(el.dataset.i)];
      if (c && !findBook(SOC.library, bookKey(c))) SOC.library.push({ ...cleanBook(c), work_id: c.work_id, t: Date.now() });
      state.addFound = []; state.addq = ''; render(); toast('Added to your library'); await saveLibrary(); publishPublic();
    },
    'delete-data': () => { state.confirmDelete = true; render(); },
    'delete-cancel': () => { state.confirmDelete = false; render(); },
    'delete-confirm': async () => {
      state.confirmDelete = false;
      try {
        const mine = await SOC.db.collection(`posts/${SOC.uid}/items`).limit(500).get();
        await Promise.all(mine.docs.map((d) => d.ref ? d.ref.delete() : SOC.db.doc(`posts/${SOC.uid}/items/${d.id}`).delete()));
        await SOC.db.doc(`public/${SOC.uid}`).delete();
        await SOC.db.doc(`reactions/${SOC.uid}`).delete();
      } catch { /* the private documents are overwritten below either way */ }
      SOC.library = []; SOC.wishlist = []; SOC.prefs = { following: [], sharing: 'off', joined: false, joinedAt: 0, recs: [], recsAt: 0, circleHidden: false };
      state.items = []; state.shelves = []; state.identity = null; SOC.posts = []; SOC.given = {};
      await saveLibrary(); await savePrefs();
      state.screen = 'welcome'; render(); toast('Your Booked data is deleted');
    },
  };
  Object.assign(actions, socialActions);
  async function finishScan() {
    await commitItems();
    state.selecting = false; state.drawer = true; state.screen = 'home'; window.scrollTo(0, 0); render();
    if (!SOC.loaded) loadSocial();
  }
  Object.assign(actions, {
    'close-drawer': () => { state.drawer = false; render(); },
    explore: async () => { state.drawer = false; await showIdentity(); },
    invite: () => { state.screen = 'invite'; window.scrollTo(0, 0); render(); if (!SOC.loaded) loadSocial(); },
    'hide-circle': async () => { SOC.prefs.circleHidden = true; render(); await savePrefs(); },
    'story-new': () => { state.screen = 'story'; state.storyText = ''; state.storyBook = ''; window.scrollTo(0, 0); render(); },
    'story-close': () => { state.screen = 'home'; render(); },
    'story-kind': (el) => { state.storyKind = el.dataset.k; render(); },
    'story-share': async () => {
      const b = findBook(SOC.library, state.storyBook) || SOC.library[SOC.library.length - 1];
      if (!b) return;
      const text = (document.getElementById('story-text') || {}).value || '';
      state.screen = 'home'; render();
      try {
        await SOC.db.collection(`posts/${SOC.uid}/items`).add({ ts: Date.now(), exp: Date.now() + 86400000, story: true, kind: state.storyKind || 'finished', book: cleanBook(b), text: text.trim().slice(0, 100) });
        toast('Added to your story'); SOC.loaded = false; loadSocial();
      } catch (e) { if (e && e.code === 'invalid_argument') { SOC.readOnly = true; render(); } toast('Could not share that. Try again.'); }
    },
    'story-view': (el) => { state.storyOf = el.dataset.id; state.screen = 'storyview'; window.scrollTo(0, 0); render(); },
  });


  app.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (el && actions[el.dataset.action]) { state.focus = null; actions[el.dataset.action](el); }
  });
  app.addEventListener('change', (e) => {
    if (e.target.dataset && e.target.dataset.input === 'story-book') { state.storyBook = e.target.value; render(); return; }
    if (e.target.id === 'cam' || e.target.id === 'pick') { addFiles(e.target.files); e.target.value = ''; }
  });
  app.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || e.isComposing) return;
    const kind = e.target.dataset && e.target.dataset.input;
    if (kind === 'add') { e.preventDefault(); actions['run-add'](); }
    if (kind === 'search') { e.preventDefault(); if (LIVE) actions['run-search']({ dataset: { id: e.target.dataset.id } }); }
  });
  let peopleTimer;
  app.addEventListener('input', (e) => {
    const kind = e.target.dataset && e.target.dataset.input;
    if (kind === 'post') { state.postText = e.target.value; return; }
    if (kind === 'story-text') { state.storyText = e.target.value; const pv = document.getElementById('story-preview'); if (pv) pv.textContent = e.target.value; return; }
    if (kind === 'add') { state.addq = e.target.value; return; }
    if (kind === 'people') {
      state.peopleq = e.target.value;
      clearTimeout(peopleTimer);
      peopleTimer = setTimeout(async () => {
        const q = state.peopleq.trim();
        state.peopleFound = q.length < 2 || !SOC.user ? [] : await SOC.user.search(q);
        await ensureProfiles((state.peopleFound || []).map((x) => x.id));
        state.focus = { id: 'people-q', pos: state.peopleq.length };
        render();
      }, 350);
      return;
    }
    if (e.target.dataset.input === 'search') {
      const it = byId(e.target.dataset.id);
      it.query = e.target.value;
      state.focus = { id: e.target.id, pos: e.target.selectionStart };
      runSearch(it.id, it.query);
    }
  });

  (async () => {
    try { state.config = await api('/api/config'); } catch (e) { state.error = e.message; }
    if (LIVE && !state.error) {
      state.screen = 'loading'; render();
      await initSocial();
      state.screen = SOC.on && SOC.prefs.joined ? 'home' : 'welcome';
      if (state.screen === 'home') loadSocial();
    }
    render();
  })();
})();
