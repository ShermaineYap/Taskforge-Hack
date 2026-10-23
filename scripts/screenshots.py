"""Capture README screenshots. Needs the app running on :5000 and Playwright.

    python scripts/screenshots.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://127.0.0.1:5000/"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
    pg.goto(URL)
    pg.wait_for_load_state("networkidle")
    pg.screenshot(path=OUT / "01-slip.png", full_page=False)

    pg.click("#demo")
    pg.wait_for_selector("#results:not([hidden])")
    pg.wait_for_timeout(900)
    pg.locator(".slip.filled").screenshot(path=OUT / "02-filled-slip.png")
    pg.locator("#asks .why-btn").first.click()
    pg.locator("#asks .item-main input").nth(1).check()
    pg.locator("section.need").screenshot(path=OUT / "03-asked-of-you.png")
    pg.click("#plain-toggle")
    pg.locator("section.need").screenshot(path=OUT / "04-plain-language.png")
    pg.click("#plain-toggle")
    pg.screenshot(path=OUT / "05-full-results.png", full_page=True)

    dark = b.new_page(viewport={"width": 1100, "height": 900}, color_scheme="dark", device_scale_factor=2)
    dark.goto(URL)
    dark.click("#demo")
    dark.wait_for_selector("#results:not([hidden])")
    dark.wait_for_timeout(900)
    dark.locator(".slip.filled").screenshot(path=OUT / "06-dark.png")

    mob = b.new_page(viewport={"width": 375, "height": 812}, device_scale_factor=2)
    mob.goto(URL)
    mob.screenshot(path=OUT / "07-mobile.png", full_page=True)
    b.close()
print("saved to", OUT)
