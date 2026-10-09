# Proof of Price — tokenized-equity basis monitor (BNB Hack: Tokenized Stocks Edition)

A **read-only** dashboard that measures how far tokenised representations of the
same company (bStocks, Ondo Global Markets, xStocks on BNB Smart Chain) sit from
each other, **token-to-token**, using only public read endpoints. No wallet
connection, no user transaction, no route quote, no trade. Spot only, BSC
mainnet only.

This repository also contains the reproducible render pipeline for the
submission demo video (`proof-of-price-hackathon-v11.mp4`, 2:39, 1280×720,
24 fps, H.264/AAC, with narration: a calm male voiceover mixed over a ducked
ambient bed and procedural foley; segment timings live in
`demo/vo/manifest.json`).

## Quick start (runnable instructions)

```bash
pip install pillow numpy scipy imageio-ffmpeg playwright
export PLAYWRIGHT_BROWSERS_PATH=$PWD/pw-browsers
python3 -m playwright install chromium

# 1. the saved-data preview (self-declared static_preview=true) must sit at:
#    uploads/dashboard-preview.html
# 2. render the dashboard plates and interaction states (offline, no network):
python3 demo/capture_slots.py
python3 demo/capture_functionality.py
# 3. render the video, captions, poster and capture log:
python3 demo/make_final_v11.py
```

The dashboard itself is a static page: open `uploads/dashboard-preview.html` in
any browser. It renders entirely from the embedded `#page-data` JSON snapshot
(Poll 10, captured 2026-10-05 20:00–20:01 UTC). Search, filters, row-select and
the ticker switch all work offline. The "Official RWA API check" button is
disabled in the static preview by design: live signed checks run only on the
private tool server, and this repo/video never issues them.

## What the numbers are (and are not)

| Figure in the video | Source |
|---|---|
| 38 tickers × 3 representations = 114 requests | `#page-data.tickers` (38) × issuers |
| 65 reference-quote gaps / 38 missing reported underlying-reference fields / 11 incomplete xStocks records / 0 errors | Poll-10 observation states in `#page-data.histories` (65 ok rows; 114−65 = 49 = 38+11) |
| SOXL Poll 7 +216.905 bp; Polls 8/9/10 −0.815 / −8.122 / −10.657 bp | `histories.SOXL.pairwise[].basis_bps` |
| AAPL Poll 10: −7.439 (bStocks↔Ondo), +5.717 (Ondo↔reference), −62.101 (xStocks↔reference) | `histories.AAPL.pairwise[-1]`, `histories.AAPL.observations` (Poll-10 rows) |
| Direct basis 38/38 valid, median −0.09 bp, range −46.07…+57.95 bp | Poll-10 `basis_bps` across all 38 tickers (median −0.086) |
| `referencePrice = tokenInfo.price ÷ sharesMultiplier` | Binance Web3 tokenized-securities documentation (the field is derived from token price; it is **not** an independent equity quote) |

Labelling policy enforced in the video and captions:

- observed data → `SAVED` / `OBSERVED` / `NOT QUOTE TIME`;
- designed graphics → `DESIGNED MOTION - SAVED DATA`;
- dashboard imagery → `STATIC PREVIEW UI - SAVED POLL 10 DATA` (headless-Chromium
  renders of the saved snapshot, **not** captures of a deployed instance);
- missing fields render as missing, never as zero;
- basis is a measurement between saved observations: no depth, fees, session
  status or executability is assessed, and no trade opportunity is claimed.

## Repo contents

| Path | Purpose |
|---|---|
| `demo/make_final_v11.py`, `demo/renderkit.py` | procedural video renderer (frames → libx264 → AAC mux) |
| `demo/capture_slots.py`, `demo/capture_functionality.py` | offline plate/interaction captures via headless Chromium |
| `demo/assets/` | slot plates, interaction states, `func_manifest.json` |
| `demo/proof-of-price-hackathon-v11*` | video, captions (SRT), poster |
| `demo/proof-of-price-v11-capture-log.txt` | render facts, capture timestamps, market status, provenance |
| `demo/mix_voice.py`, `demo/vo/manifest.json` | audio-only narration remix (voice offsets + ducking); the ten raw TTS segments are not committed |
| `uploads/dashboard-preview.html` | static preview of the dashboard with embedded saved data |

## Credentials

None. No API keys, no judge credentials, no deployment secrets are stored here.
The deployed judge demo (Frankfurt) is a public, read-only link with no
password; signed live-API keys live only in Render environment variables, and
the live endpoint keeps its 5-second server-side cooldown.
