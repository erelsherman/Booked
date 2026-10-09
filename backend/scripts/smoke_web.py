"""Browser walkthrough of the web prototype in demo mode (not part of pytest: needs Playwright and Chromium).

    BOOKED_DEMO=1 uvicorn booked.web.app:create_app --factory --port 8765 &
    pip install playwright && python scripts/smoke_web.py OUT_DIR [CHROMIUM_PATH]

Drives a phone-sized browser through: choose a photo, read, resolve a candidate, search for a missing
book, remove one, show the Reader Identity. Saves screenshots to OUT_DIR and prints key facts.
"""

import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1])
chromium = sys.argv[2] if len(sys.argv) > 2 else None
out.mkdir(parents=True, exist_ok=True)
buf = io.BytesIO()
Image.new("RGB", (1600, 1200), (190, 120, 70)).save(buf, "JPEG")
(out / "shelf.jpg").write_bytes(buf.getvalue())

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chromium, args=["--no-sandbox"]) if chromium else p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page.goto("http://127.0.0.1:8765/")
    page.wait_for_selector("text=scan your library")
    page.screenshot(path=str(out / "1-start.png"))
    page.set_input_files("#pick", str(out / "shelf.jpg"))
    page.wait_for_selector(".thumb")
    page.click("text=Read 1 photo")
    page.wait_for_selector("text=We found")
    page.screenshot(path=str(out / "2-check.png"), full_page=True)
    page.click("[data-action=pick] >> nth=0")
    page.fill("[data-input=search]", "Tale of Love and Darkness")
    page.wait_for_selector("[data-action=pick-found]")
    page.click("[data-action=pick-found] >> nth=0")
    page.click("[data-action=remove] >> nth=0")
    page.click("text=Show my Reader Identity")
    page.wait_for_selector("text=Who you are as a reader")
    page.screenshot(path=str(out / "3-identity.png"), full_page=True)
    print("statement:", page.locator(".statement").inner_text())
    print("languages:", page.locator(".legend").inner_text().replace("\n", " | "))
    browser.close()
