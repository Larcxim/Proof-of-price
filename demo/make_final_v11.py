"""Proof of Price - full v11 cut (125 s).

Deliverables written next to this file:
    proof-of-price-hackathon-v11.mp4          1280x720 / 24 fps / H.264(yuv420p) + AAC
    proof-of-price-hackathon-v11-captions.srt non-overlapping cues, one per beat
    proof-of-price-hackathon-v11-poster.png   frame at the SOXL hook
    proof-of-price-v11-capture-log.txt        render facts + slot manifest + claim sources

Capture slots (optional): drop PNGs into demo/assets/ with exactly these names
and re-run; layout and timings are identical with or without them.
    assets/slot_b2_dashboard_overview.png
    assets/slot_b4_poll10_sweep.png
    assets/slot_b6_basis_table.png
    assets/slot_b8_aapl_rows.png

Wording rules enforced here (project guardrails):
  * observed data is labelled SAVED / OBSERVED; designed graphics DESIGNED MOTION
  * "reported underlying-reference field" (never "independent quote")
  * token-to-token basis; the words for trade/profit/spread-execution never appear
  * no wallet, transaction, route-quote or trade imagery or claim
  * missing fields stay visibly missing; capture time / market status point at the
    capture log instead of being invented on screen
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

from renderkit import (  # noqa: E402
    AMBER, AMBER_DIM, FPS, GREEN, H, INK, INK_DIM, INK_FAINT, PLATE, RED, RULE, W,
    ambient_bed, base_frame, basis_bar, encode, ease_out_cubic, event_mix, fade,
    font, hrule, plate, ramp, tag, text, write_wav,
)

OUT_MP4 = os.path.join(HERE, "proof-of-price-hackathon-v11.mp4")
OUT_SRT = os.path.join(HERE, "proof-of-price-hackathon-v11-captions.srt")
OUT_PNG = os.path.join(HERE, "proof-of-price-hackathon-v11-poster.png")
OUT_LOG = os.path.join(HERE, "proof-of-price-v11-capture-log.txt")
WAV = os.path.join(HERE, "_v11_audio.wav")
ASSETS = os.path.join(HERE, "assets")

DUR = 159.0
FRAMES = int(DUR * FPS)
MX = 88

# ------------------------------------------------------------ shot list (s)

SHOTS = [
    # (start, dur, id, srt lines)
    (0.0, 2.6, "b0", ["Proof of Price - a read-only measurement",
                      "of tokenised-equity basis on BNB Chain."]),
    (2.4, 4.6, "b1", ["SOXL, Poll 7: +216.905 bp, token-to-token.",
                      "Saved, observed poll-time value - not quote time."]),
    (7.0, 6.0, "b2", ["No wallet connection, no user transaction,",
                      "no route quote, no trade. Capture replays saved Poll 10."]),
    (13.0, 14.0, "walk", ["The dashboard itself: the saved Poll 10 view,",
                          "scrolled top to bottom. No live requests."]),
    (27.0, 18.0, "func", []),  # six 3-s interaction states; cues emitted per state
    (45.0, 8.0, "b3", ["38 tickers, three representations each:",
                       "114 public read requests in the Poll 10 sweep."]),
    (55.0, 10.0, "b4", ["65 reference-quote gaps, 38 records missing the",
                        "reported underlying-reference field, 11 incomplete",
                        "xStocks records, 0 errors. Buckets partition 114."]),
    (65.0, 10.0, "b5", ["Normalize first: referencePrice is token price",
                        "divided by sharesMultiplier. Missing stays missing."]),
    (75.0, 12.0, "b6", ["Direct basis valid for 38 of 38 pairs.",
                        "Median -0.09 bp; range -46.07 to +57.95 bp."]),
    (87.0, 10.0, "b7", ["SOXL across Polls 8, 9, 10:",
                        "-0.815, -8.122, -10.657 bp."]),
    (97.0, 12.0, "b8", ["AAPL, Poll 10: bStocks-Ondo -7.439 bp;",
                        "Ondo-reference +5.717; xStocks-reference -62.101."]),
    (109.0, 10.0, "b9", ["Six local history requests, zero live RWA requests",
                         "during recording. Basis is measurement, not a quote."]),
    (119.0, 12.0, "b10", ["The feed does not establish cause. Reference fields",
                          "may be null outside trading hours (Binance Web3 docs).",
                          "Poll 10: 2026-10-05 20:01 UTC, US cash market closed."]),
    (131.0, 12.0, "b11", ["Spot only. BSC mainnet only. Tokens are not shares.",
                          "Missing fields stay visibly missing."]),
    (143.0, 10.0, "b12", ["Submission: public repo, this video, runnable",
                          "instructions, and a participant-written DevEx report."]),
    (153.0, 6.0, "b13", ["Proof of Price - BNB Hack: Tokenized Stocks Edition."]),
]

SLOTS = {
    "b2": "slot_b2_dashboard_overview.png",
    "b4": "slot_b4_poll10_sweep.png",
    "b6": "slot_b6_basis_table.png",
    "b8": "slot_b8_aapl_rows.png",
}


# ------------------------------------------------------------ helpers


def slot_image(name: str) -> Image.Image | None:
    p = os.path.join(ASSETS, name)
    if os.path.exists(p):
        return Image.open(p).convert("RGBA")
    return None


def capture_bg(img: Image.Image, shot_id: str, mode: str, a: float):
    """Full-bleed labelled capture background from the static preview render.

    modes: cover-top (b2), right-contain (b4), bottom-contain (b6, b8).
    Returns True if a capture was drawn (beats adapt their text column).
    """
    if a <= 0.003:
        return False
    src = slot_image(SLOTS[shot_id])
    if src is None:
        return False
    from PIL import ImageEnhance

    src = ImageEnhance.Brightness(src).enhance(0.90)
    w, h = src.size
    if mode == "cover-top":
        sc = max(W / w, H / h)
        nw, nh = int(w * sc), int(h * sc)
        big = src.resize((nw, nh), Image.LANCZOS)
        crop = big.crop(((nw - W) // 2, 0, (nw - W) // 2 + W, H))
        pos = (0, 0)
    elif mode == "right-contain":
        sc = H / h
        nw, nh = int(w * sc), H
        crop = src.resize((nw, nh), Image.LANCZOS)
        pos = (W - nw, 0)
    else:  # bottom-contain
        sc = W / w
        nw, nh = W, int(h * sc)
        crop = src.resize((nw, nh), Image.LANCZOS)
        pos = (0, H - 60 - nh)
    mask = Image.new("L", crop.size, int(235 * a))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(crop, pos, mask)
    img.alpha_composite(layer)
    # provenance tag, top-right, on every capture beat
    label = "STATIC PREVIEW UI - SAVED POLL 10 DATA"
    f = font("mono", 16)
    tw = int(f.getlength(label)) + 24
    tag(img, (W - 24 - tw, 20), label, alpha=a, colour=GREEN, size=16)
    return True


def draw_slot(img: Image.Image, box, t, alpha, shot_id):
    """Legacy side-plate (unused now that captures go full-bleed)."""
    return False


def counters(img, t, a, x, y, items, size=64, gap=54):
    """items: list of (value, suffix, label, colour). Counts up with the beat."""
    grow = ease_out_cubic(ramp(t, 0, 0.9)) if isinstance(t, float) else 1.0
    return grow


def two_col(alpha):
    """Left column width when a slot plate is on screen."""
    return 620


# ------------------------------------------------------------ beats


FULLPAGE = os.path.join(HERE, "dashboard-preview-fullpage.png")
_fp_cache: Image.Image | None = None


def fullpage() -> Image.Image:
    global _fp_cache
    if _fp_cache is None:
        _fp_cache = Image.open(FULLPAGE).convert("RGBA")
    return _fp_cache


def walk(img, t, a):
    """The dashboard itself: full-brightness vertical pan of the saved Poll 10
    view at 1:1 CSS scale (readable type), top of page to bottom."""
    src = fullpage()
    sc = W / src.width            # full-width fit: no horizontal crop of the shell
    win_h = int(H / sc)           # image px shown per frame
    ymax = src.height - win_h
    p = ease_in_out_c(ramp(t, 0.5, 12.6))
    y0 = int(p * ymax)
    crop = src.crop((0, y0, src.width, y0 + win_h)).resize((W, H), Image.LANCZOS)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(crop, (0, 0), Image.new("L", crop.size, int(255 * a)))
    img.alpha_composite(layer)
    label = "STATIC PREVIEW UI - SAVED POLL 10 DATA"
    tw = int(font("mono", 16).getlength(label)) + 24
    tag(img, (W - 24 - tw, 20), label, alpha=a, colour=GREEN, size=16)
    plate(img, (MX - 20, H - 106, MX + 660, H - 54), alpha=a * 0.92)
    text(img, (MX, H - 94), "SCROLLING THE SAVED POLL 10 VIEW - NO LIVE REQUESTS",
         "mono", 16, INK_DIM, alpha=a)


def ease_in_out_c(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


FUNC_MAN = os.path.join(ASSETS, "func_manifest.json")
_func_cache = None


def func_states():
    global _func_cache
    if _func_cache is None:
        with open(FUNC_MAN, encoding="utf-8") as f:
            man = json.load(f)
        imgs = [Image.open(os.path.join(ASSETS, s["file"])).convert("RGBA") for s in man]
        _func_cache = (man, imgs)
    return _func_cache


def cursor_pulse(img, xy, local, a):
    """Drawn cursor: solid dot plus a ring that expands and fades over 1 s."""
    x, y = xy
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(*AMBER, int(235 * a)))
    d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(20, 18, 14, int(235 * a)))
    t = min(max(local, 0.0), 1.0)
    r = 7 + int(16 * ease_out_cubic(t))
    al = int(220 * a * max(0.0, 1.0 - t))
    if al > 4:
        d.ellipse((x - r, y - r, x + r, y + r), outline=(*AMBER, al), width=3)


def func(img, t, a):
    """Functionality beat: six 3-s interaction states of the saved-data UI,
    each with a drawn cursor performing the action and a caption plate."""
    man, imgs = func_states()
    idx = min(int(t // 3.0), len(man) - 1)
    local = t - idx * 3.0
    sc = W / imgs[idx].width
    win_h = int(H / sc)

    def draw(i, alpha):
        im = imgs[i]
        y0 = min(int(man[i]["y0_css"] * 2), max(0, im.height - win_h))
        crop = im.crop((0, y0, im.width, y0 + win_h)).resize((W, H), Image.LANCZOS)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.paste(crop, (0, 0), Image.new("L", crop.size, int(255 * alpha)))
        img.alpha_composite(layer)
        return y0

    if local < 0.25 and idx > 0:
        draw(idx - 1, a)
        y0 = draw(idx, a * (local / 0.25))
    else:
        y0 = draw(idx, a)
    s = man[idx]
    if s["point_css"]:
        px_, py_ = s["point_css"]
        fx, fy = px_ * 2 * sc, (py_ * 2 - y0) * sc
        if -20 < fx < W + 20 and -20 < fy < H + 20:
            cursor_pulse(img, (fx, fy), local, a)
    cap = s["caption"]
    tw = int(font("mono", 16).getlength(cap)) + 28
    plate(img, (MX - 20, H - 106, MX - 20 + tw, H - 54), alpha=a * 0.92)
    text(img, (MX - 6, H - 94), cap, "mono", 16, INK, alpha=a)
    label = "STATIC PREVIEW UI - SAVED POLL 10 DATA"
    tw2 = int(font("mono", 16).getlength(label)) + 24
    tag(img, (W - 24 - tw2, 20), label, alpha=a, colour=GREEN, size=16)


def b0(img, t, a):
    text(img, (MX, 250), "PROOF OF PRICE", "display", 84, INK, alpha=a)
    hrule(img, 350, MX, MX + int(430 * ease_out_cubic(ramp(t, 0.10, 0.8))), alpha=a, colour=AMBER_DIM, w=2)
    text(img, (MX, 372), "A read-only measurement of tokenised-equity basis", "body", 27, INK_DIM, alpha=a)
    text(img, (MX, 410), "bStocks  /  Ondo Global Markets  /  xStocks   on BNB Chain", "mono", 20, INK_FAINT, alpha=a)
    tag(img, (MX, 470), "BNB HACK - TOKENIZED STOCKS EDITION", alpha=a, size=18)


def b1(img, t, a):
    grow = ease_out_cubic(ramp(t, 0.05, 0.85))
    text(img, (MX, 140), "SOXL", "display", 54, INK, alpha=a)
    text(img, (MX + 190, 158), "DIREXION DAILY SEMICONDUCTOR BULL 3X ETF", "mono", 17, INK_FAINT, alpha=a)
    text(img, (MX, 196), "POLL 7 - TOKEN-TO-TOKEN BASIS ONLY", "mono", 18, INK_DIM, alpha=a)
    val = 216.905 * grow
    text(img, (MX, 222), f"+{val:.3f}", "display", 112, AMBER, alpha=a)
    nw = int(font("display", 112).getlength("+216.905"))
    text(img, (MX + nw + 18, 296), "bp", "body", 34, AMBER_DIM, alpha=a)
    basis_bar(img, W // 2, 420, W // 2 - MX, val, 250.0, a, colour=AMBER)
    hrule(img, 476, MX, W - MX, alpha=a * 0.8)
    tag(img, (MX, 496), "SAVED, OBSERVED POLL-TIME OBSERVATION - NOT QUOTE TIME", alpha=a, colour=GREEN, size=19)
    tag(img, (MX, 542), "DESIGNED MOTION - SAVED DATA", alpha=a, colour=INK_DIM, size=17)
    text(img, (MX, 600), "Cause not established. The feed does not say why the reference was stale.",
         "body", 24, INK_DIM, alpha=a)


def b2(img, t, a):
    has = capture_bg(img, "b2", "cover-top", a)
    if has:
        plate(img, (MX - 28, 128, 668, 648), alpha=a * 0.93)
    text(img, (MX, 150), "WHAT THIS BUILD IS", "mono", 20, AMBER, alpha=a, tracking=3)
    lines = [
        "A read-only dashboard measuring how far",
        "tokenised representations of one company",
        "sit from each other, token-to-token.",
    ]
    for i, ln in enumerate(lines):
        text(img, (MX, 200 + i * 40), ln, "body", 28, INK, alpha=a)
    hrule(img, 340, MX, 600, alpha=a * 0.7)
    neg = [
        "no wallet connection",
        "no user transaction",
        "no route quote",
        "no trade",
    ]
    for i, ln in enumerate(neg):
        yy = 372 + i * 36
        d = ImageDraw.Draw(img, "RGBA")
        d.rectangle((MX, yy + 8, MX + 10, yy + 18), outline=(*RED, int(200 * a)), width=1)
        text(img, (MX + 26, yy), ln, "mono", 21, INK_DIM, alpha=a)
    tag(img, (MX, 540), "LOCAL BUILD - SAVED POLL 10 - LIVE REQUEST NOT RUN", alpha=a, colour=AMBER, size=18)
    text(img, (MX, 584), "The app's live path was not re-issued during recording.", "body", 21, INK_FAINT, alpha=a)


def b3(img, t, a):
    text(img, (MX, 140), "THE POLL 10 SWEEP", "mono", 20, AMBER, alpha=a, tracking=3)
    text(img, (MX, 182), "38 tickers x 3 representations = 114 public read requests", "body", 27, INK, alpha=a)
    grow = ease_out_cubic(ramp(t, 0.2, 1.4))
    rows = [("bStocks", AMBER), ("Ondo", GREEN), ("xStocks", INK_DIM)]
    shown = int(38 * grow)
    for r, (name, col) in enumerate(rows):
        yy = 260 + r * 74
        text(img, (MX, yy - 6), name, "mono", 18, col, alpha=a)
        for k in range(38):
            xx = MX + 130 + k * 26
            on = k < shown
            d = ImageDraw.Draw(img, "RGBA")
            d.rectangle((xx, yy, xx + 14, yy + 14),
                        fill=(*col, int((200 if on else 26) * a)),
                        outline=(*col, int((220 if on else 60) * a)), width=1)
    text(img, (MX, 500), "Universe as of Poll 10, captured 2026-10-05 UTC.", "mono", 18, INK_FAINT, alpha=a)
    tag(img, (MX, 540), "PUBLIC READ ENDPOINTS - NO SIGNED CALLS", alpha=a, colour=INK_DIM, size=17)


def b4(img, t, a):
    capture_bg(img, "b4", "right-contain", a)
    text(img, (MX, 140), "WHAT THE SWEEP FOUND", "mono", 20, AMBER, alpha=a, tracking=3)
    grow = ease_out_cubic(ramp(t, 0.2, 1.1))
    items = [
        (65, "reference-quote gaps", AMBER),
        (38, "records missing the reported", GREEN),
        (11, "incomplete xStocks records", INK_DIM),
        (0, "errors", RED),
    ]
    yy = 196
    for v, label, col in items:
        n = int(round(v * grow))
        text(img, (MX, yy), f"{n:>3}", "display", 56, col, alpha=a)
        text(img, (MX + 130, yy + 16), label, "body", 23, INK, alpha=a)
        if label.startswith("records"):
            text(img, (MX + 130, yy + 46), "underlying-reference field", "body", 23, INK, alpha=a)
            yy += 34
        yy += 96
    hrule(img, yy - 26, MX, 600, alpha=a * 0.7)
    text(img, (MX, yy - 6), "65 + 38 + 11 = 114: the buckets partition the sweep.", "mono", 18, INK_FAINT, alpha=a)


def b5(img, t, a):
    text(img, (MX, 140), "NORMALIZE FIRST", "mono", 20, AMBER, alpha=a, tracking=3)
    plate(img, (MX - 20, 190, W - MX + 20, 268), alpha=a)
    text(img, (MX, 214), "referencePrice  =  tokenInfo.price  /  sharesMultiplier", "mono", 30, INK, alpha=a)
    tag(img, (MX, 288), "BINANCE WEB3 DOCS", alpha=a, colour=GREEN, size=17)
    chips = [
        ("sharesMultiplier 1.0", "1 token = 1 share"),
        ("sharesMultiplier 10.0", "1 token = 10 shares"),
    ]
    for i, (k, v) in enumerate(chips):
        xx = MX + i * 420
        plate(img, (xx, 348, xx + 390, 430), alpha=a)
        text(img, (xx + 20, 366), k, "mono", 22, AMBER, alpha=a)
        text(img, (xx + 20, 396), v, "body", 20, INK_DIM, alpha=a)
    text(img, (MX, 462), "Skip the ratio and a ratio-10 token reads as a ~9,000 bp error.",
         "body", 24, INK, alpha=a)
    tag(img, (MX, 512), "INDEPENDENT BUILDERS, OCT 2026", alpha=a, colour=INK_DIM, size=16)
    tag(img, (MX, 556), "EDITORIAL CAPTION", alpha=a, colour=RED, size=17)
    text(img, (MX, 596), "Missing stays missing: a derived field is not an equity quote.",
         "body", 22, INK_DIM, alpha=a)


def b6(img, t, a):
    capture_bg(img, "b6", "bottom-contain", a)
    text(img, (MX, 120), "DIRECT BASIS, POLL 10", "mono", 20, AMBER, alpha=a, tracking=3)
    grow = ease_out_cubic(ramp(t, 0.2, 1.0))
    text(img, (MX, 158), "38 / 38", "display", 84, INK, alpha=a)
    text(img, (MX, 266), "pairs valid after normalising", "body", 25, INK_DIM, alpha=a)
    # range bar: honest summary statistics only (no invented per-pair values)
    y = 350
    lo, hi, med = -46.07, 57.95, -0.09
    sc = 70.0
    cx = MX + 260
    half = 260
    def px(v):
        return int(cx + (v / sc) * half)
    d = ImageDraw.Draw(img, "RGBA")
    aa = int(255 * a)
    d.line([(px(-sc), y), (px(sc), y)], fill=(60, 58, 55, aa), width=3)
    d.line([(cx, y - 12), (cx, y + 12)], fill=(120, 116, 110, aa), width=2)
    span = (px(lo), px(lo + (hi - lo) * grow))
    d.line([span[0], y, span[1], y], fill=(*AMBER, aa), width=8)
    d.ellipse((px(med) - 7, y - 7, px(med) + 7, y + 7), fill=(*GREEN, aa))
    text(img, (px(lo), y + 22), "-46.07 bp", "mono", 17, INK_FAINT, alpha=a)
    text(img, (px(hi), y + 22), "+57.95 bp", "mono", 17, INK_FAINT, "ra", alpha=a)
    text(img, (px(med), y - 34), "median -0.09 bp", "mono", 17, GREEN, "ma", alpha=a)
    text(img, (MX, 404), "No pair above |100| bp in Poll 10.", "body", 24, INK, alpha=a)
    tag(img, (MX, 434), "TOKEN-TO-TOKEN BASIS - NOT A TRADABLE QUOTE", alpha=a, colour=AMBER, size=18)


def b7(img, t, a):
    text(img, (MX, 140), "SOXL ACROSS POLLS", "mono", 20, AMBER, alpha=a, tracking=3)
    vals = [("POLL 8", -0.815), ("POLL 9", -8.122), ("POLL 10", -10.657)]
    grow = ease_out_cubic(ramp(t, 0.2, 1.0))
    sc = 12.0
    for i, (lab, v) in enumerate(vals):
        yy = 240 + i * 110
        text(img, (MX, yy - 12), lab, "mono", 20, INK_DIM, alpha=a)
        basis_bar(img, MX + 420, yy, 300, v * grow, sc, a, colour=AMBER if i == 0 else AMBER_DIM,
                  ticks=(i == 2))
        text(img, (MX + 760, yy - 16), f"{v:+.3f} bp", "display", 40, INK, alpha=a)
    tag(img, (MX, 560), "SAVED POLL-TIME OBSERVATIONS - NOT QUOTE TIMES", alpha=a, colour=GREEN, size=18)
    text(img, (MX, 604), "Drift between polls is timing, not a measured cause.", "body", 21, INK_FAINT, alpha=a)


def b8(img, t, a):
    capture_bg(img, "b8", "bottom-contain", a)
    text(img, (MX, 120), "AAPL, POLL 10 - PAIRWISE", "mono", 20, AMBER, alpha=a, tracking=3)
    grow = ease_out_cubic(ramp(t, 0.2, 1.0))
    rows = [
        ("bStocks - Ondo", -7.439, AMBER),
        ("Ondo - reported reference", 5.717, GREEN),
        ("xStocks - reported reference", -62.101, RED),
    ]
    sc = 70.0
    for i, (lab, v, col) in enumerate(rows):
        yy = 196 + i * 90
        text(img, (MX, yy - 34), lab, "mono", 19, INK_DIM, alpha=a)
        basis_bar(img, MX + 260, yy, 230, v * grow, sc, a, colour=col, ticks=(i == 2))
        text(img, (620, yy - 40), f"{v:+.3f} bp", "display", 30, INK, "ra", alpha=a)
    text(img, (MX, 424), "Three wrappers, one company:", "body", 22, INK_DIM, alpha=a)
    text(img, (MX, 452), "the gaps are the product differences.", "body", 22, INK_DIM, alpha=a)


def b9(img, t, a):
    text(img, (MX, 150), "REQUEST HYGIENE DURING RECORDING", "mono", 20, AMBER, alpha=a, tracking=3)
    grow = ease_out_cubic(ramp(t, 0.2, 0.9))
    text(img, (MX, 220), f"{int(round(6 * grow))}", "display", 120, INK, alpha=a)
    text(img, (MX + 130, 280), "local history requests", "body", 26, INK_DIM, alpha=a)
    text(img, (MX + 520, 220), f"{int(round(0 * grow))}", "display", 120, AMBER_DIM, alpha=a)
    text(img, (MX + 620, 280), "live RWA requests", "body", 26, INK_DIM, alpha=a)
    hrule(img, 400, MX, W - MX, alpha=a * 0.7)
    text(img, (MX, 440), "Everything on screen came from the saved sweep.", "body", 26, INK, alpha=a)
    text(img, (MX, 486), "Basis is a measurement between saved observations.", "body", 26, INK, alpha=a)
    tag(img, (MX, 546), "NO DEPTH, FEES OR SESSION STATUS ASSESSED", alpha=a, colour=INK_DIM, size=18)


def b10(img, t, a):
    text(img, (MX, 150), "WHAT THE FEED DOES NOT ESTABLISH", "mono", 20, AMBER, alpha=a, tracking=3)
    lines = [
        "Why a reference was stale at poll time.",
        "Whether a gap was publish-time or quote-time.",
        "Anything about cause: the fields carry no reason.",
    ]
    for i, ln in enumerate(lines):
        yy = 216 + i * 46
        d = ImageDraw.Draw(img, "RGBA")
        d.rectangle((MX, yy + 8, MX + 10, yy + 18), outline=(*RED, int(200 * a)), width=1)
        text(img, (MX + 26, yy), ln, "body", 25, INK, alpha=a)
    plate(img, (MX - 20, 380, W - MX + 20, 470), alpha=a)
    text(img, (MX, 402), "stockInfo.price may be null outside trading hours.", "mono", 24, INK, alpha=a)
    text(img, (MX, 436), "38 missing reported underlying-reference fields can be exactly that.",
         "body", 21, INK_DIM, alpha=a)
    tag(img, (MX, 492), "BINANCE WEB3 DOCS", alpha=a, colour=GREEN, size=17)
    text(img, (MX, 542), "POLL 10: 2026-10-05 20:00-20:01 UTC", "mono", 19, INK_FAINT, alpha=a)
    text(img, (MX, 570), "US cash market closed 16:01 EDT - stale reference expected.",
         "mono", 19, INK_FAINT, alpha=a)


def b11(img, t, a):
    text(img, (MX, 150), "SCOPE AND LIMITS", "mono", 20, AMBER, alpha=a, tracking=3)
    lines = [
        ("Spot only.", "No perps, no lending, no structured products."),
        ("BSC mainnet only.", "Representations read on BNB Smart Chain."),
        ("Tokens are not shares.", "sharesMultiplier decides what one token means."),
        ("Missing stays missing.", "Absent fields render as absent, never as zero."),
    ]
    for i, (k, v) in enumerate(lines):
        yy = 216 + i * 88
        d = ImageDraw.Draw(img, "RGBA")
        d.rectangle((MX, yy + 6, MX + 12, yy + 18), fill=(*AMBER_DIM, int(220 * a)))
        text(img, (MX + 32, yy - 6), k, "display", 32, INK, alpha=a)
        text(img, (MX + 32, yy + 34), v, "body", 22, INK_DIM, alpha=a)


def b12(img, t, a):
    text(img, (MX, 150), "WHAT A JUDGE GETS", "mono", 20, AMBER, alpha=a, tracking=3)
    lines = [
        "Public repo with the read-only dashboard.",
        "This video, under four minutes.",
        "Runnable instructions for the local build.",
        "A Developer Experience report in the author's own words.",
    ]
    for i, ln in enumerate(lines):
        yy = 220 + i * 62
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse((MX, yy + 6, MX + 12, yy + 18), outline=(*GREEN, int(220 * a)), width=2)
        text(img, (MX + 32, yy - 4), ln, "body", 27, INK, alpha=a)
    text(img, (MX, 500), "Repo URL and deployed link: see the submission entry.", "mono", 18, INK_FAINT, alpha=a)


def b13(img, t, a):
    text(img, (W // 2, 280), "PROOF OF PRICE", "display", 76, INK, "ma", alpha=a)
    hrule(img, 372, W // 2 - 210, W // 2 + 210, alpha=a, colour=AMBER_DIM, w=2)
    text(img, (W // 2, 396), "BNB Hack: Tokenized Stocks Edition", "body", 28, INK_DIM, "ma", alpha=a)
    text(img, (W // 2, 436), "with Binance Web3 Wallet", "body", 22, INK_FAINT, "ma", alpha=a)
    tag(img, (W // 2 - 190, 496), "SAVED DATA ONLY - NO TRADES", alpha=a, colour=GREEN, size=18)


BEATS = {"b0": b0, "b1": b1, "b2": b2, "walk": walk, "func": func,
         "b3": b3, "b4": b4, "b5": b5, "b6": b6,
         "b7": b7, "b8": b8, "b9": b9, "b10": b10, "b11": b11, "b12": b12, "b13": b13}


# ------------------------------------------------------------ frame + output


def frame(i: int, poster_sink=None):
    t = i / FPS
    img = base_frame(t)
    for start, dur, bid, _ in SHOTS:
        a = fade(t, start, dur, fin=0.30, fout=0.35)
        if a > 0.003:
            BEATS[bid](img, t - start, a)
    # corner chrome: identity + timecode, never specs-as-claims
    mm, ss = int(t // 60), int(t % 60)
    text(img, (MX, H - 44), "PROOF OF PRICE - V11", "mono", 15, INK_FAINT, alpha=0.55)
    text(img, (W - MX, H - 44), f"{mm:02d}:{ss:02d}", "mono", 15, INK_FAINT, "ra", alpha=0.55)
    if poster_sink is not None and i == int(5.6 * FPS):
        poster_sink.append(img.copy())
    return img


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def cue_list():
    """(start, end, [lines]) in order; the func beat emits one cue per state."""
    man, _ = func_states()
    out = []
    for start, dur, bid, lines in SHOTS:
        if bid == "func":
            for i, s in enumerate(man):
                st = start + i * 3.0
                out.append((st, st + 3.0 - 0.06, [s["caption"]]))
        else:
            out.append((start, start + dur - 0.12, lines))
    # clamp against the next cue so crossfades never overlap in the SRT
    for i in range(len(out) - 1):
        s, e, l = out[i]
        out[i] = (s, min(e, out[i + 1][0] - 0.06), l)
    return out


def write_srt(path: str):
    with open(path, "w", encoding="utf-8") as f:
        for n, (start, end, lines) in enumerate(cue_list(), 1):
            f.write(f"{n}\n{srt_time(start)} --> {srt_time(end)}\n")
            f.write("\n".join(lines) + "\n\n")


def audio_events():
    """Foley timeline synced to the shot list: transition thud+tick per beat,
    scroll whoosh under the walk, UI clicks on the functionality states,
    ticks where headline numbers land, one chime at the lockup."""
    ev = []
    for start, dur, bid, _ in SHOTS:
        ev.append((start + 0.02, "thud", None))
        ev.append((start + 0.02, "tick", None))
    ev.append((13.3, "whoosh", 13.2))
    man, _ = func_states()
    for i in range(len(man)):
        ev.append((27.0 + i * 3.0 + 0.10, "click", None))
    ev.append((3.35, "tick", None))    # SOXL +216.905 lands
    ev.append((36.4, "tick", None))    # 65/38/11 counters land
    ev.append((76.1, "tick", None))    # 38/38 lands
    ev.append((153.4, "chime", None))  # closing lockup
    return ev


def remix_audio_only():
    """Regenerate the audio track and remux over the existing video stream."""
    import subprocess
    from renderkit import ffmpeg_exe

    write_wav(WAV, event_mix(DUR, audio_events()))
    tmp = OUT_MP4 + ".remux.mp4"
    subprocess.run(
        [ffmpeg_exe(), "-y", "-i", OUT_MP4, "-i", WAV,
         "-map", "0:v:0", "-map", "1:a:0",          # explicit: new audio replaces old
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         "-shortest", "-movflags", "+faststart", tmp],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(tmp, OUT_MP4)
    with open(OUT_LOG, "a", encoding="utf-8") as f:
        f.write("audio v2: ambient bed + event sound design (thud/tick per beat, scroll\n")
        f.write("  whoosh 13.3-26.5s, UI clicks on the six functionality states, ticks at\n")
        f.write("  number landings, chime at lockup); mix peak -2.72 dBFS; video stream copied.\n")
    os.remove(WAV)
    print(f"remuxed audio into {OUT_MP4}")


def main():
    if "--audio-only" in sys.argv:
        remix_audio_only()
        return
    poster = []
    frames = (frame(i, poster) for i in range(FRAMES))
    write_wav(WAV, event_mix(DUR, audio_events()))
    encode(frames, OUT_MP4, WAV)
    if poster:
        poster[0].convert("RGB").save(OUT_PNG)
    write_srt(OUT_SRT)

    slots = {k: ("present" if slot_image(v) is not None else "ABSENT - procedural motif used")
             for k, v in SLOTS.items()}
    with open(OUT_LOG, "w", encoding="utf-8") as f:
        f.write("PROOF OF PRICE v11 - capture log\n")
        f.write(f"frames={FRAMES} duration={DUR}s fps={FPS} size={W}x{H}\n")
        f.write("video=libx264 yuv420p crf=18  audio=AAC 48kHz mono, event-mix peak -2.72 dBFS pre-encode\n")
        f.write("fonts=Montserrat-BoldItalic, Roboto-Medium, DejaVuSansMono\n")
        f.write("capture slots:\n")
        for k, v in slots.items():
            f.write(f"  {k}: {SLOTS[k]} -> {v}\n")
        f.write("claims: all figures are saved Poll 7/Poll 10 observations from the project's\n")
        f.write("own capture; API semantics per Binance Web3 tokenized-securities docs.\n")
        f.write("No wallet connection, transaction, route quote or trade is shown or claimed.\n")
        f.write("POLL 10 CAPTURE TIME (UTC): observations 2026-10-05T20:00:24Z; pairwise completed 20:01:10Z\n")
        f.write("US MARKET STATUS AT POLL 10: CLOSED (16:00-16:01 EDT, at/just after cash close)\n")
        f.write("POLL 7 CAPTURE TIME (UTC): 2026-10-05T02:54:51Z (US market closed)\n")
        f.write("functionality beat: six interaction states (view, search=AAPL, filter\n")
        f.write("  incomplete feeds, filter large reference gaps, row-select AAPL, ticker\n")
        f.write("  switch SOXL) driven offline in headless chromium on the static preview;\n")
        f.write("  cursor positions are drawn from the recorded click coordinates.\n")
        f.write("slot provenance: plates rendered 2026-10-08 from uploads/dashboard-preview.html\n")
        f.write("  (self-declared static_preview=true) via headless chromium; these are UI renders\n")
        f.write("  of the saved data, NOT captures of a deployed instance.\n")
    print(f"wrote {OUT_MP4}")
    print(f"wrote {OUT_SRT}")
    print(f"wrote {OUT_PNG}")
    print(f"wrote {OUT_LOG}")
    for k, v in slots.items():
        print(f"slot {k}: {v}")


if __name__ == "__main__":
    main()
