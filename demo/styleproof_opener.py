"""Style proof — 8 s opener rendered at the delivery specs (1280x720 / 24 fps /
H.264 + AAC, no voiceover), using the corrected provenance wording from the
factualisation audit:

  * "SAVED, OBSERVED POLL-TIME OBSERVATION - NOT QUOTE TIME"  (the "SIMULATED"
    collision is removed: observed data is never labelled simulated)
  * "DESIGNED MOTION - SAVED DATA"                            (for graphics)
  * "LOCAL BUILD - SAVED POLL 10 - LIVE REQUEST NOT RUN" plus the one
    clarifying cue that says the live path was deliberately not re-issued

Run:  python3 demo/styleproof_opener.py
"""

from __future__ import annotations

import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from renderkit import (  # noqa: E402
    AMBER, AMBER_DIM, FPS, GREEN, H, INK, INK_DIM, INK_FAINT, RED, W,
    ambient_bed, base_frame, basis_bar, encode, fade, font, hrule, plate, ramp,
    ease_out_cubic, tag, text, write_wav,
)
from PIL import ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "proof-of-price-v11-opener-styleproof.mp4")
WAV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_styleproof_audio.wav")
DUR = 8.0
FRAMES = int(DUR * FPS)
MX = 88  # side margin


def frame(i: int):
    t = i / FPS
    img = base_frame(t)

    # ---------------------------------------------------------------- beat 1
    # title card  0.0 - 2.6
    a1 = fade(t, 0.15, 2.45, fin=0.35, fout=0.35)
    if a1 > 0:
        text(img, (MX, 250), "PROOF OF PRICE", "display", 84, INK, alpha=a1)
        hrule(img, 350, MX, MX + int(430 * ease_out_cubic(ramp(t, 0.25, 0.8))), alpha=a1, colour=AMBER_DIM, w=2)
        text(img, (MX, 372), "A read-only measurement of tokenised-equity basis",
             "body", 27, INK_DIM, alpha=a1)
        text(img, (MX, 410), "bStocks  /  Ondo Global Markets  /  xStocks   on BNB Chain",
             "mono", 20, INK_FAINT, alpha=a1)
        tag(img, (MX, 470), "BNB HACK - TOKENIZED STOCKS EDITION", alpha=a1, size=18)

    # ---------------------------------------------------------------- beat 2
    # SOXL saved observation  2.3 - 5.4
    a2 = fade(t, 2.30, 3.10, fin=0.30, fout=0.35)
    if a2 > 0:
        grow = ease_out_cubic(ramp(t, 2.35, 0.85))
        text(img, (MX, 150), "SOXL", "display", 54, INK, alpha=a2)
        text(img, (MX + 190, 168), "DIREXION DAILY SEMICONDUCTOR BULL 3X ETF",
             "mono", 17, INK_FAINT, alpha=a2)
        text(img, (MX, 205), "POLL 7 - TOKEN-TO-TOKEN BASIS, TOKEN-TO-TOKEN BASIS ONLY",
             "mono", 18, INK_DIM, alpha=a2)

        val = 216.905 * grow
        text(img, (MX, 222), f"+{val:.3f}", "display", 112, AMBER, alpha=a2)
        num_w = int(font("display", 112).getlength("+216.905"))
        text(img, (MX + num_w + 18, 296), "bp", "body", 34, AMBER_DIM, alpha=a2)

        basis_bar(img, W // 2, 420, W // 2 - MX, val, 250.0, a2, colour=AMBER)

        hrule(img, 476, MX, W - MX, alpha=a2 * 0.8)
        tag(img, (MX, 496), "SAVED, OBSERVED POLL-TIME OBSERVATION - NOT QUOTE TIME",
            alpha=a2, colour=GREEN, size=19)
        tag(img, (MX, 542), "DESIGNED MOTION - SAVED DATA", alpha=a2, colour=INK_DIM, size=17)
        text(img, (MX, 600),
             "Cause not established. The feed does not say why the reference was stale.",
             "body", 24, INK_DIM, alpha=a2)

    # ---------------------------------------------------------------- beat 3
    # capture-honesty + editorial cue  5.2 - 8.0
    a3 = fade(t, 5.20, 2.80, fin=0.30, fout=0.30)
    if a3 > 0:
        plate(img, (MX - 24, 168, W - MX + 24, 400), alpha=a3)
        tag(img, (MX, 190), "LOCAL BUILD - SAVED POLL 10 - LIVE REQUEST NOT RUN",
            alpha=a3, colour=AMBER, size=20)
        text(img, (MX, 246),
             "This capture replays saved Poll 10.", "body", 30, INK, alpha=a3)
        text(img, (MX, 288),
             "The app's live path was not re-issued during recording.", "body", 30, INK, alpha=a3)
        text(img, (MX, 344),
             "No wallet connection, no user transaction, no route quote, no trade.",
             "mono", 19, INK_FAINT, alpha=a3)

        plate(img, (MX - 24, 440, W - MX + 24, 606), alpha=a3)
        tag(img, (MX, 462), "EDITORIAL CAPTION", alpha=a3, colour=RED, size=19)
        text(img, (MX, 506), "Normalize first.", "display", 34, INK, alpha=a3)
        text(img, (MX, 556),
             "referencePrice is derived from token price / sharesMultiplier (Binance Web3 docs).",
             "body", 21, INK_DIM, alpha=a3)

    # ---------------------------------------------------------------- corner chrome
    ac = 0.55
    text(img, (W - MX, H - 44), "PROOF OF PRICE - V11 STYLE PROOF", "mono", 15, INK_FAINT, "ra", alpha=ac)
    text(img, (MX, H - 44), "1280x720 - 24 FPS - H.264 / AAC", "mono", 15, INK_FAINT, alpha=ac)
    return img


def main():
    frames = (frame(i) for i in range(FRAMES))
    write_wav(WAV, ambient_bed(DUR))
    encode(frames, OUT, WAV)
    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.0f} KiB)")
    print(f"frames={FRAMES} dur={DUR}s fps={FPS} size={W}x{H}")


if __name__ == "__main__":
    main()
