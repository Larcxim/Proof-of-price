"""Render the four capture-slot plates from uploads/dashboard-preview.html.

The preview file is self-declared `static_preview = true`: it renders the local
build's UI from an embedded saved-data JSON block and makes no network calls.
We therefore label these plates "STATIC PREVIEW UI - SAVED POLL 10 DATA", never
as captures of a deployed instance.

Run: python3 demo/capture_slots.py
"""

from __future__ import annotations

import json
import os
import re

from PIL import Image
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
FULL = os.path.join(HERE, "dashboard-preview-fullpage.png")
DSF = 2  # device scale factor: capture at 2x, plates downscale crisply

REGIONS_JS = """
() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height };
  };
  const union = (rs) => {
    rs = rs.filter(Boolean);
    if (!rs.length) return null;
    const x = Math.min(...rs.map(r => r.x));
    const y = Math.min(...rs.map(r => r.y));
    const x2 = Math.max(...rs.map(r => r.x + r.w));
    const y2 = Math.max(...rs.map(r => r.y + r.h));
    return { x, y, w: x2 - x, h: y2 - y };
  };
  const q = (s) => document.querySelector(s);
  return {
    overview: union([rect(q('header')), rect(q('.hero')), rect(q('.metrics'))]),
    basis: rect(q('.basis-shell')),
    issues: rect(q('.issues') ? q('.issues').closest('.panel') || q('.issues') : null),
    table: rect(q('.map-shell')),
  };
}
"""


def main():
    os.makedirs(ASSETS, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=DSF)
        page.goto(f"file://{SRC}")
        page.wait_for_timeout(1800)  # let the inline JS hydrate from #page-data
        boxes = page.evaluate(REGIONS_JS)
        page.screenshot(path=FULL, full_page=True)

        # AAPL-filtered table for the pairwise slot
        page.fill(".search", "AAPL")
        page.wait_for_timeout(500)
        boxes["table_aapl"] = page.evaluate("() => { const e = document.querySelector('.map-shell'); const r = e.getBoundingClientRect(); return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height }; }")
        page.screenshot(path=os.path.join(ASSETS, "_aapl_view.png"), full_page=True)
        browser.close()

    full = Image.open(FULL)
    aapl = Image.open(os.path.join(ASSETS, "_aapl_view.png"))

    def crop(img, box, name, pad=6):
        if not box:
            print(f"  !! missing region for {name}")
            return
        x, y, w, h = (int(v * DSF) for v in (box["x"], box["y"], box["w"], box["h"]))
        x = max(0, x - pad); y = max(0, y - pad)
        im = img.crop((x, y, min(img.width, x + w + 2 * pad), min(img.height, y + h + 2 * pad)))
        out = os.path.join(ASSETS, name)
        im.save(out)
        print(f"  {name}: {im.size[0]}x{im.size[1]}")

    crop(full, boxes["overview"], "slot_b2_dashboard_overview.png")
    crop(full, boxes["issues"], "slot_b4_poll10_sweep.png")
    crop(full, boxes["basis"], "slot_b6_basis_table.png")
    crop(aapl, boxes["table_aapl"], "slot_b8_aapl_rows.png")
    os.remove(os.path.join(ASSETS, "_aapl_view.png"))
    print("fullpage:", full.size)


if __name__ == "__main__":
    main()
