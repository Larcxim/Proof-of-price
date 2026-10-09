# Tokenized-stock dislocation monitor (BNB Hack)

A small, **read-only** BSC monitor for the 38 tickers that have Ondo, xStocks, and bStocks representations. Its saved historical collection uses Binance's public RWA data endpoint and does not need credentials. The local dashboard now also offers an optional, separate live check through the signed Binance Web3 RWA Data API; that check uses a private API key/secret, but no wallet or trade.

**Deployed judge demo (Frankfurt, public — no password):**
https://proof-of-price-demo.onrender.com — read-only dashboard; the service sleeps on Render's free plan, so open it a minute before use.

## What it measures

For each venue, the collector uses the per-share conversion—not the API's circular `referencePrice` field:

```text
per_share = tokenInfo.price / tokenInfo.sharesMultiplier
gap_bps   = (per_share / stockInfo.price - 1) * 10,000
```

A missing `stockInfo.price` is retained as a missing reference (currently seen for bStocks); it is **not** turned into a zero or silently discarded. Rows with a valid on-chain price but no underlying quote remain useful observations, but have no `gap_bps`.

A separate direct comparison is available when both token prices are valid:

```text
pairwise_basis_bps = (bStocks_per_share / Ondo_per_share - 1) * 10,000
```

This is a **token-to-token basis**, not a reference-quote gap. It does not require bStocks `stockInfo.price`; the dashboard shows it in a distinct summary, table column, and per-ticker history. It does not account for route availability, depth, fees, or slippage.

### Optional signed live API check

The local served dashboard includes a button that makes two **read-only, signed** Binance Web3 RWA Data API requests for the selected BSC ticker: one to find its bStocks/Ondo token records and share ratios, and one to request current token prices. It normalizes each venue as `tokenPrice / tokenToShareRatio` and computes the same direct basis. The live result is not appended to the saved public-endpoint polling history, so sources and timelines are not mixed. No wallet connection, user transaction, route quote, or trade is involved. The button is disabled in the offline `dashboard-preview.html` file.

For a private local run, set `OC_API_KEY` and `OC_SECRET_KEY` in a local `.env` file based on `.env.example`, or use `Start-Proof-of-Price.command` to enter them privately for that server session. Keep the credentials out of this shared workspace, browser code, and public repo. Do not share them in chat.

The spread is a **data comparison**, not proof that a trade is executable or profitable. A quote can be stale, a token can have thin liquidity, and the unexplained xStocks outliers already found must not be presented as arbitrage.

## Demo video (submission)

`proof-of-price-hackathon-v11.mp4` — 2:39, 1280×720, 24 fps, H.264/AAC, with narration: a calm male voiceover mixed over a ducked ambient bed and procedural foley. Structure: title + SOXL Poll 7 hook; what the build is (no wallet, no transaction, no route quote, no trade); a full-brightness scroll-through of the saved Poll 10 view; a functionality beat showing search, both filters, row-select and ticker-switch driven offline; sweep maths (114 requests, 65/38/11/0); normalize-first method; direct basis 38/38 (median −0.09 bp, range −46.07…+57.95 bp); SOXL poll sequence; AAPL pairwise; request hygiene; what the feed does not establish (Poll 10 captured 2026-10-05 20:00–20:01 UTC, US cash market closed); scope and limits; submission pack.

Dashboard imagery in the video carries the tag `STATIC PREVIEW UI - SAVED POLL 10 DATA`: those plates are headless-browser renders of `dashboard-preview.html` (self-declared `static_preview=true`), not captures of the deployed instance. Observed data is labelled `SAVED / OBSERVED … NOT QUOTE TIME`; designed graphics `DESIGNED MOTION - SAVED DATA`. The render pipeline, captions (SRT), poster and capture log live in `demo/`; reproduce the picture with `python3 demo/make_final_v11.py` — the narration mix is documented by `demo/vo/manifest.json` and `demo/mix_voice.py` (raw voice segments are not committed).

## Run it

Requirements: Python 3.10+; standard library only.

From this directory:

```bash
# Fast smoke test: one ticker, three venue requests
python3 monitor.py --tickers AAPL

# One sweep of the full 38-ticker universe (114 venue requests)
python3 monitor.py

# Keep collecting every 15 minutes until Ctrl-C
python3 monitor.py --loop --interval-seconds 900

# Serve the dashboard (standard library only; bind 0.0.0.0 by default)
python3 serve.py --port 8000

# Export a self-contained HTML snapshot for the workspace file viewer/offline use
python3 export_preview.py
```

The default is a **single sweep**; continuous polling is opt-in. The full universe has a 250 ms pause between requests and retries transient transport/429/5xx failures with backoff. The endpoint's formal rate limit is not established here, so adjust cadence cautiously. `--quiet` suppresses per-observation lines. `--database path/to/file.sqlite3` and `--universe path/to/universe.json` override locations.

The dashboard is served locally from the same SQLite file, with inline CSS/JS and no external assets. It includes a plain-language “How to read this comparison” guide for first-time visitors, including a basis-point glossary, a searchable integrity table, missing-data states, reference-quote gap comparisons, a separately labeled bStocks↔Ondo token basis, and per-ticker history charts for both measures. The gap charts use a logarithmic scale. It refreshes the snapshot every 60 seconds. JSON endpoints: `/api/snapshot`, `/api/history?ticker=AAPL`, `/api/live-rwa?ticker=SOXL` (signed Web3 API; local credentials required), and `/health`. If the live preview is unavailable, `python3 export_preview.py` creates `dashboard-preview.html` with its history embedded; it works in the workspace's network-isolated file viewer.

To refresh the pinned universe from the public RWA token list:

```bash
python3 monitor.py --refresh-universe --tickers AAPL
```

This updates `data/universe.json` before polling. The checked-in snapshot is derived from the token list already fetched on 2026-10-04; it contains the 38 triple-representation BSC tickers, their 114 contract addresses, and each token-list multiplier.

## First live baseline (2026-10-04)

The first full sweep completed in 45.8 seconds: 114/114 successful responses, 65 computable gaps, 38 bStocks rows with `stockInfo.price=null`, and 11 xStocks rows with `tokenInfo.price=null` (the multiplier was present). No transport or API errors. The 11 affected tickers were ADBE, ASML, ASTS, BMNR, CRM, EWY, GS, HIMS, IREN, PYPL, and SOXL. The saved public observations are in `data/monitor.sqlite3`; this is a historical snapshot through Poll 10, not a live feed.

The latest verified full public poll is Poll 10, completed `2026-10-05T20:01:10Z`, just after the scheduled U.S. close: 114/114 responses, 65 reference gaps, 38 missing references, 11 incomplete xStocks token prices, and 0 request/API errors. The separate bStocks↔Ondo comparison was available for 38/38 tickers; its median signed basis was −0.09 bp, observed range −46.07 to +57.95 bp, with no pair above |100| bp. SOXL's basis was −10.66 bp; AAPL's was −7.44 bp. The earlier off-hours SOXL reading of +216.9 bp from Poll 7 did not recur in Polls 8–10, but the public API fields do not establish why; its audit trail is in [soxl-poll-verification.md](soxl-poll-verification.md). These are API observations, not verified execution opportunities.

AAPL's Ondo response also exposed an API status-field ambiguity: `marketStatus="offhours"` while `openState=true` on Sunday. Keep the source fields separate; don't use `openState` alone to decide whether U.S. equity trading is open.

## Data model

- `polls`: sweep start/end, expected observation count, response/error counts.
- `observations`: one row per ticker/venue/request, including request/fetch times, latency, token price, shares multiplier, underlying quote, computed per-share price and gap, API-reported status fields, and a compact raw excerpt for audit.
- HTTP/API/shape errors are stored as rows rather than aborting the whole sweep. A killed sweep remains visibly incomplete in `polls`.
- `reference_state` is `available`, `missing`, `invalid`, or `not_checked`; `status` separately describes API/transport/metric validity.
- The source's `statusInfo.openState` is stored as `api_open_state`, **not** treated as authoritative U.S.-market status. In the first Sunday AAPL smoke test it was `true` while the same Ondo response said `marketStatus=offhours`; the dashboard calls out this mismatch and does not infer market hours from `openState`.

Example query (if the `sqlite3` CLI is installed):

```sql
SELECT ticker, venue, fetched_at_utc, token_price, shares_multiplier,
       stock_price, per_share_price, spread_bps, market_status, status
FROM observations
ORDER BY fetched_at_utc DESC
LIMIT 20;
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests cover the universe filter, the reference-gap and bStocks↔Ondo basis formulas, null/malformed prices, pairwise history, and database schema setup without making network calls.
