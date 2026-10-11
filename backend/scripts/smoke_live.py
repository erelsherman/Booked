"""Browser walkthrough of the live-in-Claude page with a stand-in for Claude (needs Playwright and Chromium).

    python -m booked.web.standalone --live live.html
    python scripts/smoke_live.py live.html OUT_DIR [CHROMIUM_PATH]

The page normally gets `window.claude` from the claude.ai viewer. Here a fake `claude.use("sample")` returns
a fixed answer, so this checks the page's own logic: sending images, turning the answer into auto / confirm /
manual rows, searching, and the Reader Identity. It does NOT check how well the real Claude reads Hebrew spines.
"""

import io
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

FAKE = """
window.__calls = [];
const spines = {spines: [
  {title: 'Norwegian Wood', author: 'Murakami', language: 'en', read_confidence: 0.95,
   identified: {title: 'Norwegian Wood', authors: ['Haruki Murakami'], language: 'en', subjects: ['literary fiction', 'japan'], year: 1987, known: true}, alternatives: []},
  {title: 'בדנהיים עיר נופש', author: 'אפלפלד', language: 'he', read_confidence: 0.9,
   identified: {title: 'בדנהיים עיר נופש', authors: ['אהרן אפלפלד'], language: 'he', subjects: ['literary fiction', 'holocaust'], year: 1975, known: true}, alternatives: []},
  {title: 'Sapiens', author: '', language: 'en', read_confidence: 0.95,
   identified: {title: 'Sapiens', authors: ['Yuval Noah Harari'], language: 'en', subjects: ['history'], year: 2011, known: true}, alternatives: []},
  {title: 'The Trial', author: 'Kafka', language: 'en', read_confidence: 0.6,
   identified: {title: 'The Trial', authors: ['Franz Kafka'], language: 'en', subjects: ['classics'], year: 1925, known: true},
   alternatives: [{title: 'The Castle', authors: ['Franz Kafka'], language: 'en', subjects: ['classics'], year: 1926}]},
  {title: '<img src=x onerror=window.__xss=1>', author: '', language: 'en', read_confidence: 0.3, identified: null, alternatives: []},
  {title: '', author: '', language: '', read_confidence: 0, identified: null, alternatives: []}
], unreadable: 2};
const sample = async () => ({text: '', truncated: false});
sample.json = async (input, opts) => {
  window.__calls.push({chars: String(input).length, images: opts && opts.images ? 1 : 0, tier: opts && opts.modelTier});
  if (opts && opts.images) return spines;
  return [{title: 'Unknown Quiet Novel', authors: ['A. Writer'], language: 'en', subjects: ['literary fiction'], year: 2001}];
};
sample.limits = async () => ({maxPromptBytes: 262144, images: {maxCount: 4, maxInputBytes: 20000000, mediaTypes: ['image/jpeg', 'image/png']}});
window.claude = {use: async (n) => (n === 'sample' ? sample : null)};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chromium, args=["--no-sandbox"]) if chromium else p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(FAKE)
    page.goto(page_file.as_uri())
    page.wait_for_selector("text=scan your library")
    page.set_input_files("#pick", str(out / "shelf.jpg"))
    page.click("text=Read 1 photo")
    page.wait_for_selector("text=We found")
    print("found:", page.inner_text("h1"))
    print("chips:", page.inner_text(".chips").replace("\n", " | "))
    print("unreadable warning:", page.locator(".warn").inner_text())
    page.screenshot(path=str(out / "live-check.png"), full_page=True)
    page.click("text=The Castle")  # resolve the confirm row
    page.fill("input[data-input=search]", "quiet novel")
    page.wait_for_selector("text=Unknown Quiet Novel")
    page.click(".cand:has-text('Unknown Quiet Novel')")
    page.click("text=Show my Reader Identity")
    page.wait_for_selector("text=Languages")
    print("identity:", page.inner_text(".statement"))
    page.screenshot(path=str(out / "live-identity.png"), full_page=True)
    print("calls:", page.evaluate("window.__calls"))
    print("xss ran:", page.evaluate("window.__xss === 1"))
    print("page errors:", errors)
    browser.close()
