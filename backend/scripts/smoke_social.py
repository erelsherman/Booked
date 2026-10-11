"""Two-reader browser walkthrough of the social layer, with fakes for Claude's `user`, `db` and `sample`.

    python -m booked.web.standalone --live live.html
    python scripts/smoke_social.py live.html OUT_DIR [CHROMIUM_PATH]

Both pages share one in-memory store (Python side), so Anna's posts and shelf are really read by Ben. This
checks the page's own logic and what it writes where. It does not check the real platform's access rules.
"""

import io
import json
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

page_file, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
chromium = sys.argv[3] if len(sys.argv) > 3 else None
out.mkdir(parents=True, exist_ok=True)
buf = io.BytesIO()
Image.new("RGB", (1600, 1200), (190, 120, 70)).save(buf, "JPEG")
(out / "shelf.jpg").write_bytes(buf.getvalue())

STORE: dict[str, dict] = {}


def db_get(path):
    return json.loads(json.dumps(STORE[path])) if path in STORE else None


def db_set(path, data):
    STORE[path] = json.loads(json.dumps(data))


def db_del(path):
    STORE.pop(path, None)


def db_list(prefix):
    n = prefix.count("/") + 1
    return [{"id": p.split("/")[-1], "data": json.loads(json.dumps(d))} for p, d in STORE.items() if p.startswith(prefix + "/") and p.count("/") == n]


FAKE = """
const ME = %(me)s;
const DIR = {u_anna: {name: 'Anna Cohen'}, u_ben: {name: 'Ben Levi'}};
const av = (id) => 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="#0f5f58"/></svg>');
const prof = (id) => ({id, name: (DIR[id] || {}).name || '', avatarUrl: av(id), color: '#0f5f58', email: null, isMe: id === ME, guest: false});
const user = {
  me: async () => ({...prof(ME), isOwner: false, canEdit: false}),
  profiles: async (ids) => Object.fromEntries([].concat(ids).map((i) => [i, prof(i)])),
  search: async (q) => Object.keys(DIR).filter((i) => DIR[i].name.toLowerCase().includes(q.toLowerCase())).map(prof),
  id: async () => ME, isOwner: async () => false, canEdit: async () => false, can: async () => true,
};
const snap = (id, data) => ({id, exists: data !== null && data !== undefined, data: () => data, metadata: {}});
const docRef = (path) => ({id: path.split('/').pop(), path,
  get: async () => snap(path.split('/').pop(), await window.__get(path)),
  set: async (d) => window.__set(path, d), update: async (d) => window.__set(path, d),
  delete: async () => window.__del(path), collection: (c) => colRef(path + '/' + c)});
const colRef = (path) => { let order = null, lim = 1000; const q = {path,
  orderBy(f, d = 'asc') { order = [f, d]; return q; }, limit(n) { lim = n; return q; },
  async get() { let docs = await window.__list(path); if (order) docs.sort((a, b) => (order[1] === 'desc' ? -1 : 1) * ((a.data[order[0]] || 0) - (b.data[order[0]] || 0)));
    docs = docs.slice(0, lim); return {docs: docs.map((d) => snap(d.id, d.data)), size: docs.length, empty: !docs.length}; },
  doc: (id) => docRef(path + '/' + (id || 'p' + Math.random().toString(36).slice(2, 9))),
  async add(d) { const r = q.doc(); await r.set(d); return r; }}; return q; };
const db = {doc: docRef, collection: colRef};
window.__calls = [];
const sample = async () => ({text: '', truncated: false});
sample.json = async (input, opts) => {
  window.__calls.push(String(input).slice(0, 40));
  if (opts && opts.images) return {spines: [
    {title: 'Norwegian Wood', author: 'Murakami', language: 'en', read_confidence: 0.95, identified: {title: 'Norwegian Wood', authors: ['Haruki Murakami'], language: 'en', subjects: ['literary fiction', 'japan'], year: 1987, known: true}, alternatives: []},
    {title: 'בדנהיים עיר נופש', author: 'אפלפלד', language: 'he', read_confidence: 0.9, identified: {title: 'בדנהיים עיר נופש', authors: ['אהרן אפלפלד'], language: 'he', subjects: ['literary fiction'], year: 1975, known: true}, alternatives: []}], unreadable: 0};
  if (String(input).startsWith('You recommend books')) return [
    {title: 'Norwegian Wood', authors: ['Haruki Murakami'], language: 'en', subjects: [], year: 1987, why: 'You already own it.', source: 'taste'},
    {title: 'Kafka on the Shore', authors: ['Haruki Murakami'], language: 'en', subjects: ['fantasy'], year: 2002, why: 'Same author as Norwegian Wood.', source: 'F1'}];
  const q = (String(input).match(/matching: "(.*)"/) || [])[1] || 'x';
  return [{title: q, authors: ['A. Writer'], language: 'en', subjects: ['literary fiction'], year: 2001}];
};
sample.limits = async () => ({maxPromptBytes: 262144, images: {maxCount: 4, maxInputBytes: 2e7, mediaTypes: ['image/jpeg']}});
window.claude = {use: async (n) => ({sample, user, db}[n] || null)};
"""


def reader(ctx, me):
    page = ctx.new_page()
    page.set_viewport_size({"width": 390, "height": 844})
    page.add_init_script(FAKE % {"me": json.dumps(me)})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(page_file.as_uri())
    return page, errors


def tab(page, label):
    page.click(f".tab:has(span:text-is('{label}'))")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chromium, args=["--no-sandbox"]) if chromium else p.chromium.launch()
    ctx = browser.new_context()
    for name, fn in (("__get", db_get), ("__set", db_set), ("__del", db_del), ("__list", db_list)):
        ctx.expose_function(name, fn)

    # ---- Anna joins, scans, shares, posts
    a, a_err = reader(ctx, "u_anna")
    a.wait_for_selector("text=Continue as Anna Cohen")
    a.click("text=Continue as Anna Cohen")
    a.set_input_files("#pick", str(out / "shelf.jpg"))
    a.click("text=Read 1 photo")
    a.wait_for_selector("text=We found")
    a.screenshot(path=str(out / "s0-check.png"), full_page=True)
    a.click("text=Show me my Reader Identity")
    a.wait_for_selector(".drawer")
    a.wait_for_timeout(600)
    a.screenshot(path=str(out / "s1-drawer.png"))
    print("drawer after scan:", a.inner_text(".drawer .statement")[:50], "| circle card behind:", a.locator(".circle").count())
    a.click(".drawer >> text=Maybe later")
    a.wait_for_selector(".circle")
    a.screenshot(path=str(out / "s1-home.png"), full_page=True)
    tab(a, "Me")
    a.click("[data-mode=everything]")
    tab(a, "Library")
    a.click("button:has-text('Post to friends') >> nth=0")
    a.fill("#post-text", "Could not put it down.")
    a.click("text=Post >> nth=-1") if False else a.click("button.dark:has-text('Post')")
    a.wait_for_timeout(300)
    print("anna library:", len(STORE["data/users/u_anna/library"]["books"]), "| public:", STORE["public/u_anna"]["sharing"], len(STORE["public/u_anna"]["books"]), "books")

    # ---- Ben joins, adds books, follows Anna, sees the post, gives Bravo, asks for recommendations
    b, b_err = reader(ctx, "u_ben")
    b.click("text=Continue as Ben Levi")
    b.click("text=Close") if False else b.click("button[data-action=close-scan]")
    print("ben home:", b.inner_text(".circle h3"))
    b.click("[data-action=hide-circle]")
    b.wait_for_selector(".bandempty")
    b.screenshot(path=str(out / "s2-ben-empty.png"))
    tab(b, "Library")
    for title in ("Quiet Book One", "Quiet Book Two", "Quiet Book Three"):
        b.fill("#add-q", title)
        b.press("#add-q", "Enter")
        b.click(f".cand:has-text('{title}')")
    print("ben public sharing:", STORE["public/u_ben"]["sharing"], "| ben shared books:", len(STORE["public/u_ben"]["books"]), "| statement exposed:", bool(STORE["public/u_ben"]["statement"]))
    tab(b, "Friends")
    b.wait_for_selector("text=Anna Cohen")
    print("people row:", b.inner_text(".screen .item").replace("\n", " | "))
    b.click("button.dark:has-text('Follow')")
    tab(b, "Home")
    b.wait_for_selector("text=Could not put it down.")
    print("section label:", b.locator(".h2").first.inner_text(), "|", b.locator(".h2").nth(0).inner_text())
    b.click("button.bravo")
    b.click("text=Recommend books for me")
    b.wait_for_selector(".nextread")
    print("next read:", b.inner_text(".nextread .serif"), "|", b.inner_text(".nextread .nbadge"), "| more recs:", b.locator(".rec").count(), "| attribution:", b.locator(".rec .note b").first.inner_text())
    print("progress card:", b.inner_text(".progress").replace("\n", " | ")[:110])
    b.click(".nextread button:has-text('Add to wishlist')")
    b.screenshot(path=str(out / "s2-ben-home.png"), full_page=True)
    print("ben wishlist:", [w["title"] for w in STORE["data/users/u_ben/library"]["wishlist"]])
    print("reactions:", STORE["reactions/u_ben"]["given"][0]["a"])

    # ---- Anna sees the Bravo count; the names are Premium
    tab(a, "Friends")
    a.click("[data-action=refresh]")
    a.wait_for_timeout(500)
    tab(a, "Home")
    a.wait_for_selector("text=1 Bravo")
    print("anna sees:", a.inner_text(".post").replace("\n", " | ")[-70:])
    assert a.locator("text=from beyond your circle · Premium").count() == 1  # Ben is outside Anna's circle
    assert a.locator("text=Ben Levi").count() == 0
    tab(a, "Friends")
    a.click("button.dark:has-text('Follow')")  # Anna follows Ben: now he is inside her circle
    tab(a, "Home")
    a.wait_for_selector("text=from Ben Levi")
    print("inside the circle, names are free:", a.locator("text=beyond your circle").count() == 0)
    a.screenshot(path=str(out / "s3-anna-home.png"), full_page=True)

    # ---- Ben deletes his data
    tab(b, "Me")
    b.click("text=Delete my Booked data")
    b.click("text=Yes, delete everything")
    b.wait_for_selector("text=Continue as Ben Levi")
    print("after delete: public/u_ben" in STORE and "still there" or "ben public gone:", "public/u_ben" not in STORE, "| reactions gone:", "reactions/u_ben" not in STORE, "| library:", STORE["data/users/u_ben/library"]["books"])
    print("private paths never in public docs:", all("data/users" not in k for k in STORE if k.startswith(("public", "posts", "reactions"))))
    print("page errors:", a_err + b_err)
    browser.close()
