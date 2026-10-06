# SOXL Poll 7–10 verification

**Result:** The SOXL figures in the video reproduce from the saved observation database through Poll 10. This is a historical data check, not a live-market check.

## Method

Read the raw public-API excerpts for SOXL in `data/monitor.sqlite3`; recompute each venue's per-share value as `tokenInfo.price / tokenInfo.sharesMultiplier`; then recompute the direct basis as `(bStocks per-share / Ondo per-share − 1) × 10,000 bp`. Recomputed per-share values match the stored values within rounding tolerance.

## Recomputed observations

| Poll | Poll completed (UTC) | bStocks per share | Ondo per share | Recomputed basis |
|---|---|---:|---:|---:|
| 7 | 2026-10-05 02:54:51.650Z | 167.620000 | 164.061429 | +216.904791 bp → **+216.9 bp** |
| 8 | 2026-10-05 18:18:30.202Z | 163.490000 | 163.503333 | −0.815457 bp → **−0.8 bp** |
| 9 | 2026-10-05 19:37:19.353Z | 164.030000 | 164.163333 | −8.121972 bp → **−8.1 bp** |
| 10 | 2026-10-05 20:01:10.650Z | 164.030000 | 164.205000 | −10.657410 bp → **−10.7 bp** |

All four polls record 114 expected observations, 114 response rows, and 0 request failures. Each also has 38/38 computable bStocks↔Ondo pairs. Both SOXL venue rows have `status=ok` in each of the four polls.

## What “Poll 7 · off-hours” means

Poll 7 was collected at 2026-10-05 02:54 UTC—Sunday 2026-10-04 at 22:54 in New York. Ondo's SOXL response reports `marketStatus="overnight"` and `openState=false`. bStocks returns no `marketStatus` (`null`) while its `openState` is `true` and `reasonCode` is `TRADING`. Therefore “off-hours” refers to the poll's timing relative to the regular U.S. equity session and is consistent with Ondo's status; it should **not** be phrased as “both APIs reported off-hours.”

## What the data does—and does not—verify

- **Verified:** The four normalized SOXL basis observations and their poll times in the saved database; the direct-basis calculation; complete 114-row polls with no request failures.
- **Not established:** Why the basis changed. Poll 7's bStocks `stockInfo.price` is null; its `marketStatus` is null and `reasonMsg` is null. Ondo reports `overnight` for Poll 7, but its `reasonMsg` is also null. None of the captured fields supplies a causal explanation.
- **Not tested:** liquidity, route depth/availability, fees, slippage, or execution. The observed basis is not evidence of executable arbitrage or profit.

## Safe presentation line

> “Our saved SOXL observations show +216.9 basis points at a Sunday off-hours poll, followed by −0.8, −8.1, and −10.7 basis points in three later polls. The requests succeeded, and we can reproduce the calculation. The captured feed does not explain the change, so we do not assign a cause or call it arbitrage.”
