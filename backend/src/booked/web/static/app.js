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
    screen: 'start', config: {}, files: [], items: [], removed: [], cost: 0, unreadable: 0,
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

  async function api(path, options = {}) {
    if (MOCK) return mockApi(path, options);
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

  function viewStart() {
    const have = state.items.length;
    const thumbs = state.files.map((f, i) => `
      <div class="thumb"><img src="${f.url}" alt="Photo ${i + 1}">
        <button data-action="drop-file" data-i="${i}" aria-label="Remove photo ${i + 1}">×</button></div>`).join('');
    return `
    <section class="screen hero">
      <div class="row"><span class="wordmark">Booked</span>${state.config.demo ? '<span class="chip" style="background:#fff">Demo</span>' : ''}<span class="grow"></span>${premiumChip()}</div>
      <h1 class="serif big">${have ? 'Add another shelf.' : 'Let’s scan your library.'}</h1>
      <p class="sub">Photograph one shelf, or a wall in a few passes. The more you scan, the better we know your taste.</p>
      ${state.error ? `<div class="err" role="alert">${esc(state.error)}</div>` : ''}
      <div class="stack">
        <button class="btn dark" data-action="take">Take a photo</button>
        <button class="btn ghost" data-action="choose">Choose photos</button>
      </div>
      <input id="cam" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden>
      <input id="pick" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden>
      ${thumbs ? `<div class="thumbs">${thumbs}</div>` : ''}
      ${state.files.length ? `<button class="btn dark" data-action="scan">Read ${state.files.length} photo${state.files.length > 1 ? 's' : ''}</button>` : ''}
      <div class="tip"><b>For the best result:</b> good light, hold steady, fill the frame with one row, and tilt the phone so spines are straight. If spines look tiny, move closer.</div>
      ${have ? '<button class="btn line" data-action="to-check">Back to my books</button>' : ''}
      <p class="note spacer" style="color:#2a1a0e">${MOCK ? 'Demo: your photos stay on this device and sample books are shown, so try the whole flow.' : 'Photos are sent to the model to read the spines and are not stored by this prototype.'}</p>
    </section>`;
  }

  function viewReading() {
    return `
    <section class="screen hero center">
      <div class="spinner" role="status" aria-label="Reading"></div>
      <h1 class="serif mid">Reading your shelf…</h1>
      <p class="sub">This usually takes 10 to 30 seconds per photo.</p>
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
    const status = it.status === 'matched' ? '<span class="chip ok">✓ Matched</span>'
      : it.status === 'check' ? '<span class="chip check">Which one?</span>' : '<span class="chip check">Not found</span>';
    let more = '';
    if (it.status === 'check') {
      more = `<div class="cands" role="group" aria-label="Pick the right book">${it.candidates.map((c, i) => `
        <button class="cand" data-action="pick" data-id="${it.id}" data-i="${i}" dir="auto">${esc(c.title)}<small>${esc(c.authors.slice(0, 2).join(', '))}${c.year ? ' · ' + c.year : ''}</small></button>`).join('')}
        <button class="btn line small" data-action="none" data-id="${it.id}">None of these</button></div>`;
    } else if (it.status === 'missing') {
      more = `<div class="find">
        <label class="note" for="q-${it.id}">Search the catalog</label>
        <input id="q-${it.id}" data-id="${it.id}" data-input="search" value="${esc(it.query ?? it.read.title)}" dir="auto" autocomplete="off">
        ${(it.found || []).map((c, i) => `<button class="cand" data-action="pick-found" data-id="${it.id}" data-i="${i}" dir="auto">${esc(c.title)}<small>${esc(c.authors.slice(0, 2).join(', '))}${c.year ? ' · ' + c.year : ''}</small></button>`).join('')}
        <button class="btn line small" data-action="add-typed" data-id="${it.id}">Add “${esc(it.read.title)}” as typed</button></div>`;
    }
    return `
    <div class="item">
      <div class="row">${cover(shown.title)}
        <div class="grow"><div class="title" dir="auto">${esc(shown.title)}</div>
          <div class="author" dir="auto">${esc((shown.authors || []).slice(0, 2).join(', '))}</div>
          ${alsoKnownAs ? `<div class="author" dir="ltr">${esc(alsoKnownAs)}</div>` : ''}
          <div class="chips" style="margin-top:6px">${shown.language ? `<span class="chip lang">${esc(langName(shown.language))}</span>` : ''}${status}</div></div>
        <button class="x" data-action="remove" data-id="${it.id}" aria-label="Remove ${esc(shown.title)} (not mine)">×</button>
      </div>${more}
    </div>`;
  }

  function viewCheck() {
    const matched = state.items.filter((i) => i.status === 'matched').length;
    const toCheck = state.items.length - matched;
    return `
    <section class="screen">
      <div class="row"><button class="btn line small" data-action="scan-more">‹ Scan more</button></div>
      <h1 class="serif mid">${state.items.length ? `We found ${state.items.length} book${state.items.length > 1 ? 's' : ''}` : 'No books yet'}</h1>
      <p class="sub">Fix anything we got wrong. Tap × on a book that is not yours. Nothing leaves this prototype except the photos you sent.</p>
      <div class="chips"><span class="chip ok">${matched} matched</span>${toCheck ? `<span class="chip check">${toCheck} to check</span>` : ''}</div>
      ${state.unreadable ? `<div class="warn">${state.unreadable} spine${state.unreadable > 1 ? 's were' : ' was'} too small or blurry to read. Try a closer photo, one shelf at a time.</div>` : ''}
      ${state.errors.map((e) => `<div class="err" role="alert">${esc(e)}</div>`).join('')}
      <div>${state.items.map(itemRow).join('')}</div>
      <div class="spacer stack" style="position:sticky;bottom:0;background:#fff;padding:12px 0">
        <p class="note">This session has cost ${money(state.cost)}${state.config.max_spend_usd ? ` of a ${money(state.config.max_spend_usd)} cap` : ''}.</p>
        <button class="btn primary" data-action="identity" ${matched ? '' : 'disabled'}>Show my Reader Identity</button>
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
    const matched = state.items.filter((i) => i.status === 'matched');
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
      <div class="row"><button class="btn line small" data-action="to-check">‹ My books</button><span class="grow"></span>${premiumChip()}</div>
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
        ${MOCK
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
    const views = { start: viewStart, reading: viewReading, check: viewCheck, identity: viewIdentity, paywall: viewPaywall };
    app.innerHTML = views[state.screen]();
    if (state.focus) {
      const el = document.getElementById(state.focus.id);
      if (el) { el.focus(); try { el.setSelectionRange(state.focus.pos, state.focus.pos); } catch { /* not a text input */ } }
    }
  }

  // ---------------------------------------------------------------- actions

  const byId = (id) => state.items.find((i) => i.id === id);

  async function addFiles(fileList) {
    const added = await Promise.all([...fileList].map(async (f) => { const s = await shrink(f); return Object.assign(s, { url: URL.createObjectURL(s) }); }));
    state.files.push(...added);
    state.error = '';
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
      state.files.forEach((f) => URL.revokeObjectURL(f.url));
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
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      if (q.trim().length < 2) return;
      try { byId(id).found = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { state.errors.push(e.message); }
      render();
    }, 400);
  }

  function setChoice(it, work, action) { it.choice = work; it.status = 'matched'; it.action = action; }

  async function showIdentity() {
    const books = state.items.filter((i) => i.status === 'matched').map((i) => ({
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
  const mine = () => state.items.filter((i) => i.status === 'matched').map((i) => i.choice);
  const csvCell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;

  const actions = {
    take: () => document.getElementById('cam').click(),
    choose: () => document.getElementById('pick').click(),
    'drop-file': (el) => { const [f] = state.files.splice(Number(el.dataset.i), 1); URL.revokeObjectURL(f.url); render(); },
    scan,
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
    identity: showIdentity,
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

  app.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (el && actions[el.dataset.action]) { state.focus = null; actions[el.dataset.action](el); }
  });
  app.addEventListener('change', (e) => {
    if (e.target.id === 'cam' || e.target.id === 'pick') { addFiles(e.target.files); e.target.value = ''; }
  });
  app.addEventListener('input', (e) => {
    if (e.target.dataset.input === 'search') {
      const it = byId(e.target.dataset.id);
      it.query = e.target.value;
      state.focus = { id: e.target.id, pos: e.target.selectionStart };
      runSearch(it.id, it.query);
    }
  });

  (async () => {
    try { state.config = await api('/api/config'); } catch (e) { state.error = e.message; }
    render();
  })();
})();
