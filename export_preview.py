#!/usr/bin/env python3
"""Export a self-contained HTML snapshot for the workspace file viewer/offline use."""
from __future__ import annotations

import argparse
from pathlib import Path

from serve import DEFAULT_DB, DEFAULT_UNIVERSE, history_for_ticker, latest_snapshot, render_dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Export an offline Proof of Price dashboard snapshot")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "dashboard-preview.html")
    args = parser.parse_args()

    snapshot = latest_snapshot(args.database, args.universe)
    histories = {
        row["ticker"]: history_for_ticker(args.database, row["ticker"])
        for row in snapshot["tickers"]
    }
    content = render_dashboard(snapshot, embedded_histories=histories, static_preview=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(
        f"Exported {args.output} · poll {snapshot['poll']['id']} · "
        f"{len(snapshot['tickers'])} tickers · embedded history for offline preview"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
