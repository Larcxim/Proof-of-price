"""Capture the dashboard's FUNCTIONALITY states from the static preview.

Drives the real UI offline (embedded saved data, no network): search typing,
filter chips, row-select, ticker switch. Each state is saved as a full-page
render plus a manifest entry carrying the action point (CSS coords) and the
window offset the video should show, so the cut can draw a cursor performing
the action and then reveal the result.

Run: python3 demo/capture_functionality.py
"""

from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
def _find_preview() -> str:
    """Repo layout: dashboard-preview.html at repo root; workspace layout: ../uploads/."""
    base = os.path.dirname(HERE)
    for cand in (os.path.join(base, "uploads", "dashboard-preview.html"),
                 os.path.join(base, "dashboard-preview.html")):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError("dashboard-preview.html not found at repo root or ../uploads/")


SRC = _find_preview()
ASSETS = os.path.join(HERE, "assets")
MANIFEST = os.path.join(ASSETS, "func_manifest.json")

STATES = []


def record(page, name, caption, point_sel=None, window_sel=None, y0_css=0):
    point = None
    if point_sel:
        point = page.evaluate(
            """(sel) => { const e = document.querySelector(sel); if (!e) return null;
                 const r = e.getBoundingClientRect();
                 return [r.x + scrollX + r.width / 2, r.y + scrollY + r.height / 2]; }""",
            point_sel,
        )
    y0 = y0_css
    if window_sel:
        got = page.evaluate(
            """(sel) => { const e = document.querySelector(sel); if (!e) return null;
                 const r = e.getBoundingClientRect(); return r.y + scrollY; }""",
            window_sel,
        )
        if got is not None:
            y0 = max(0, got - 70)
    page.wait_for_timeout(350)
    path = os.path.join(ASSETS, f"func_{name}.png")
    page.screenshot(path=path, full_page=True)
    STATES.append({"file": f"func_{name}.png", "y0_css": y0, "point_css": point, "caption": caption})
    print(f"  func_{name}.png  y0={y0}  point={point}")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page.goto(f"file://{SRC}")
        page.wait_for_timeout(1800)

        record(page, "0_view",
               "Saved Poll 10 view - search, filters and row detail all run offline.",
               None, None, 0)

        search = page.locator(".search")
        search.fill("AAPL")
        record(page, "1_search",
               "Search narrows 38 tickers to one - here, AAPL.",
               ".search", ".map-shell")

        search.fill("")
        page.locator(".filter", has_text="Incomplete feeds").click()
        record(page, "2_incomplete",
               "Filter: incomplete feeds - the 11 xStocks records.",
               None, ".map-shell")
        # re-find the clicked button for the point (list order may differ)
        STATES[-1]["point_css"] = page.evaluate(
            """() => { const bs = [...document.querySelectorAll('.filter')];
                 const e = bs.find(b => /Incomplete feeds/i.test(b.textContent));
                 const r = e.getBoundingClientRect();
                 return [r.x + scrollX + r.width / 2, r.y + scrollY + r.height / 2]; }""")

        page.locator(".filter", has_text="Large reference gaps").click()
        record(page, "3_gaps",
               "Filter: large reference gaps - stale-reference rows first.",
               None, ".map-shell")
        STATES[-1]["point_css"] = page.evaluate(
            """() => { const bs = [...document.querySelectorAll('.filter')];
                 const e = bs.find(b => /Large reference gaps/i.test(b.textContent));
                 const r = e.getBoundingClientRect();
                 return [r.x + scrollX + r.width / 2, r.y + scrollY + r.height / 2]; }""")

        page.locator(".filter", has_text="All tickers").click()
        row = page.locator(".data-row", has_text="AAPL").first
        row.scroll_into_view_if_needed()
        row.click()
        record(page, "4_row",
               "Row select: AAPL detail - history and pairwise charts below.",
               None, ".lower-grid")

        opts = page.eval_on_selector_all(".select option", "els => els.map(e => e.textContent)")
        soxl = next((o for o in opts if "SOXL" in o), None)
        if soxl:
            page.select_option(".select", label=soxl)
        record(page, "5_switch",
               "Ticker switch: SOXL - the Poll 7 outlier in context.",
               ".select", ".lower-grid")
        b.close()

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(STATES, f, indent=1)
    print(f"wrote {MANIFEST} with {len(STATES)} states")


if __name__ == "__main__":
    main()
