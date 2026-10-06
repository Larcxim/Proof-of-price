#!/usr/bin/env python3
"""Read-only BSC tokenized-stock monitor and SQLite time-series recorder.

Correct measurement:
    per_share = tokenInfo.price / tokenInfo.sharesMultiplier
    gap_bps   = (per_share / stockInfo.price - 1) * 10_000

The monitor deliberately records missing references (notably bStocks) instead
of dropping the row or pretending a gap can be computed.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_UNIVERSE = BASE_DIR / "data" / "universe.json"
DEFAULT_DATABASE = BASE_DIR / "data" / "monitor.sqlite3"

TOKEN_LIST_URL = (
    "https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/"
    "market/token/rwa/stock/detail/list/ai"
)
DYNAMIC_BASE_URL = (
    "https://www.binance.com/bapi/defi/v2/public/wallet-direct/buw/wallet/"
    "market/token/rwa/dynamic/ai"
)
REQUEST_HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "identity",
    "User-Agent": "binance-web3/1.1 (Skill)",
}
VENUE_BY_SUFFIX = {"on": "ondo", "x": "xstocks", "B": "bstocks"}
VENUES = ("ondo", "xstocks", "bstocks")
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Asset:
    ticker: str
    venue: str
    symbol: str
    contract_address: str
    chain_id: str = "56"
    list_multiplier: str | None = None


class FetchError(Exception):
    """A retryable or final HTTP/transport/JSON error, with HTTP status if known."""

    def __init__(self, message: str, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not number.is_finite():
        return None
    return number


def _to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def build_universe(records: Iterable[dict[str, Any]], generated_at_utc: str | None = None) -> dict[str, Any]:
    """Build the pinned triple-representation BSC universe from Binance's token list."""
    grouped: dict[str, dict[str, Asset]] = {}
    for row in records:
        if str(row.get("chainId")) != "56":
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        symbol = str(row.get("symbol") or "").strip()
        address = str(row.get("contractAddress") or "").strip()
        if not ticker or not symbol.startswith(ticker) or not address:
            continue
        suffix = symbol[len(ticker):]
        venue = VENUE_BY_SUFFIX.get(suffix)
        if venue is None:
            continue
        grouped.setdefault(ticker, {})[venue] = Asset(
            ticker=ticker,
            venue=venue,
            symbol=symbol,
            contract_address=address,
            chain_id="56",
            list_multiplier=(str(row.get("multiplier")) if row.get("multiplier") is not None else None),
        )

    triples = {
        ticker: venues
        for ticker, venues in grouped.items()
        if all(venue in venues for venue in VENUES)
    }
    if not triples:
        raise ValueError("No BSC tickers with all three recognized representations were found")

    return {
        "generated_at_utc": generated_at_utc or utc_now(),
        "chain_id": "56",
        "source": TOKEN_LIST_URL,
        "venue_suffixes": {"on": "ondo", "x": "xstocks", "B": "bstocks"},
        "tickers": {
            ticker: {
                venue: {
                    "symbol": triples[ticker][venue].symbol,
                    "contract_address": triples[ticker][venue].contract_address,
                    "chain_id": triples[ticker][venue].chain_id,
                    "list_multiplier": triples[ticker][venue].list_multiplier,
                }
                for venue in VENUES
            }
            for ticker in sorted(triples)
        },
    }


def _request_json(url: str, timeout: float) -> tuple[dict[str, Any], int, float]:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS, method="GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(400).decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        msg = f"HTTP {exc.code}" + (f": {detail[:240]}" if detail else "")
        raise FetchError(msg, http_status=int(exc.code)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(f"transport error: {exc}") from exc

    elapsed_ms = (time.monotonic() - started) * 1000
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"invalid JSON: {exc}", http_status=status) from exc
    if not isinstance(payload, dict):
        raise FetchError("invalid JSON: response root is not an object", http_status=status)
    return payload, status, elapsed_ms


def _get_json_with_retries(url: str, timeout: float, max_retries: int) -> tuple[dict[str, Any], int, float]:
    last_error: FetchError | None = None
    for attempt in range(max_retries + 1):
        try:
            return _request_json(url, timeout)
        except FetchError as exc:
            last_error = exc
            retryable = exc.http_status is None or exc.http_status == 429 or exc.http_status >= 500
            if attempt >= max_retries or not retryable:
                break
            # Exponential backoff with small jitter; never hammer a failing endpoint.
            time.sleep(min(8.0, 0.75 * (2**attempt)) + random.uniform(0, 0.2))
    assert last_error is not None
    raise last_error


def fetch_token_list(timeout: float = 20.0, max_retries: int = 2) -> list[dict[str, Any]]:
    payload, _, _ = _get_json_with_retries(TOKEN_LIST_URL, timeout, max_retries)
    code = str(payload.get("code", ""))
    if payload.get("success") is False or code not in ("", "0", "000000"):
        raise FetchError(f"token-list API error: code={code} message={payload.get('message')}")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise FetchError("token-list response has no data array")
    return [row for row in rows if isinstance(row, dict)]


def load_universe(path: Path, refresh: bool = False, timeout: float = 20.0) -> dict[str, Any]:
    """Load the pinned 38-ticker universe, optionally refreshing it from the public list."""
    if refresh or not path.exists():
        rows = fetch_token_list(timeout=timeout)
        universe = build_universe(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(universe, indent=2) + "\n", encoding="utf-8")
        return universe
    universe = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(universe, dict) or not isinstance(universe.get("tickers"), dict):
        raise ValueError(f"Invalid universe file: {path}")
    return universe


def select_assets(universe: dict[str, Any], tickers: str | None = None) -> list[Asset]:
    requested = None
    if tickers:
        requested = {part.strip().upper() for part in tickers.split(",") if part.strip()}
        if not requested:
            raise ValueError("--tickers was provided but no ticker symbols were parsed")
    ticker_map: dict[str, Any] = universe.get("tickers", {})
    if requested:
        missing = requested - set(ticker_map)
        if missing:
            raise ValueError("Ticker(s) not in the triple-representation universe: " + ", ".join(sorted(missing)))
    selected = sorted(requested if requested else ticker_map)
    assets: list[Asset] = []
    for ticker in selected:
        reps = ticker_map[ticker]
        for venue in VENUES:
            row = reps.get(venue)
            if not isinstance(row, dict):
                raise ValueError(f"Universe entry {ticker}/{venue} is missing")
            assets.append(Asset(
                ticker=ticker,
                venue=venue,
                symbol=str(row["symbol"]),
                contract_address=str(row["contract_address"]),
                chain_id=str(row.get("chain_id", "56")),
                list_multiplier=(str(row["list_multiplier"]) if row.get("list_multiplier") is not None else None),
            ))
    return assets


def dynamic_url(asset: Asset) -> str:
    query = urllib.parse.urlencode({"chainId": asset.chain_id, "contractAddress": asset.contract_address})
    return f"{DYNAMIC_BASE_URL}?{query}"


def parse_dynamic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize the public dynamic-endpoint response and compute the per-share gap."""
    api_code = payload.get("code")
    api_success = payload.get("success")
    result: dict[str, Any] = {
        "status": "ok",
        "api_code": str(api_code) if api_code is not None else None,
        "symbol": None,
        "token_price": None,
        "shares_multiplier": None,
        "stock_price": None,
        "per_share_price": None,
        "spread_bps": None,
        "reference_state": "not_checked",
        "market_status": None,
        "api_open_state": None,
        "next_open_ms": None,
        "next_close_ms": None,
        "error": None,
        "raw_excerpt": None,
    }

    if api_success is False or (api_code is not None and str(api_code) not in ("0", "000000")):
        result["status"] = "api_error"
        result["error"] = str(payload.get("message") or payload.get("msg") or f"API code {api_code}")[:500]
        result["raw_excerpt"] = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)[:4000]
        return result

    data = payload.get("data")
    if not isinstance(data, dict):
        result["status"] = "invalid_payload"
        result["error"] = "response data is not an object"
        result["raw_excerpt"] = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)[:4000]
        return result

    token_info = data.get("tokenInfo") if isinstance(data.get("tokenInfo"), dict) else {}
    stock_info = data.get("stockInfo") if isinstance(data.get("stockInfo"), dict) else {}
    status_info = data.get("statusInfo") if isinstance(data.get("statusInfo"), dict) else {}

    token_price = _decimal(token_info.get("price"))
    shares_multiplier = _decimal(token_info.get("sharesMultiplier"))
    stock_price = _decimal(stock_info.get("price"))
    result["symbol"] = data.get("symbol")
    result["token_price"] = _to_float(token_price)
    result["shares_multiplier"] = _to_float(shares_multiplier)
    result["stock_price"] = _to_float(stock_price) if stock_price is not None and stock_price > 0 else None

    metric_issues = []
    if token_price is None or token_price <= 0:
        metric_issues.append("tokenInfo.price")
    if shares_multiplier is None or shares_multiplier <= 0:
        metric_issues.append("tokenInfo.sharesMultiplier")
    if metric_issues:
        result["status"] = "incomplete_metrics"
        result["error"] = "missing or non-positive " + ", ".join(metric_issues)
    else:
        per_share = token_price / shares_multiplier
        result["per_share_price"] = _to_float(per_share)
        if stock_price is not None and stock_price > 0:
            spread = (per_share / stock_price - Decimal(1)) * Decimal(10_000)
            # Token-list multipliers are rounded decimals; suppress insignificant division residue.
            if abs(spread) < Decimal("0.000001"):
                spread = Decimal(0)
            result["spread_bps"] = _to_float(spread)
            result["reference_state"] = "available"
        elif stock_info.get("price") is None:
            # Expected for bStocks in the live probe: preserve it as a valid response.
            result["reference_state"] = "missing"
        else:
            result["reference_state"] = "invalid"

    result["market_status"] = status_info.get("marketStatus")
    # Preserve the API's openState verbatim as an integer flag; do not infer that it
    # means the underlying US equity market is open (live responses can disagree).
    open_state = status_info.get("openState")
    result["api_open_state"] = int(open_state) if isinstance(open_state, bool) else None
    for field in ("next_open_ms", "next_close_ms"):
        source_key = "nextOpenTime" if field == "next_open_ms" else "nextCloseTime"
        val = status_info.get(source_key)
        try:
            result[field] = int(val) if val is not None else None
        except (ValueError, TypeError, OverflowError):
            result[field] = None

    excerpt = {
        "code": api_code,
        "success": api_success,
        "data": {
            "symbol": data.get("symbol"),
            "tokenInfo": {"price": token_info.get("price"), "sharesMultiplier": token_info.get("sharesMultiplier")},
            "stockInfo": {"price": stock_info.get("price")},
            "statusInfo": status_info,
        },
    }
    result["raw_excerpt"] = json.dumps(excerpt, separators=(",", ":"), ensure_ascii=False)[:4000]
    return result


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at_utc TEXT NOT NULL,
            completed_at_utc TEXT,
            expected_observations INTEGER NOT NULL,
            response_rows INTEGER NOT NULL DEFAULT 0,
            spreads_computed INTEGER NOT NULL DEFAULT 0,
            missing_references INTEGER NOT NULL DEFAULT 0,
            incomplete_metrics INTEGER NOT NULL DEFAULT 0,
            request_failures INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL REFERENCES polls(id),
            ticker TEXT NOT NULL,
            venue TEXT NOT NULL,
            symbol TEXT NOT NULL,
            contract_address TEXT NOT NULL,
            requested_at_utc TEXT NOT NULL,
            fetched_at_utc TEXT NOT NULL,
            latency_ms REAL,
            http_status INTEGER,
            status TEXT NOT NULL,
            api_code TEXT,
            reference_state TEXT NOT NULL,
            token_price REAL,
            shares_multiplier REAL,
            stock_price REAL,
            per_share_price REAL,
            spread_bps REAL,
            market_status TEXT,
            api_open_state INTEGER,
            next_open_ms INTEGER,
            next_close_ms INTEGER,
            error TEXT,
            raw_excerpt TEXT,
            UNIQUE(poll_id, ticker, venue)
        );

        CREATE INDEX IF NOT EXISTS observations_ticker_venue_time
            ON observations(ticker, venue, fetched_at_utc);
        CREATE INDEX IF NOT EXISTS observations_poll_id
            ON observations(poll_id);
        """
    )
    # Lightweight migration for the first smoke-test database, where this raw API
    # field briefly had the misleading name `market_open`.
    columns = {row[1] for row in connection.execute("PRAGMA table_info(observations)")}
    if "market_open" in columns and "api_open_state" not in columns:
        connection.execute("ALTER TABLE observations RENAME COLUMN market_open TO api_open_state")
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def open_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=30)
    connection.row_factory = sqlite3.Row
    ensure_schema(connection)
    return connection


def _insert_observation(connection: sqlite3.Connection, poll_id: int, asset: Asset,
                        requested_at: str, fetched_at: str, latency_ms: float | None,
                        http_status: int | None, fields: dict[str, Any]) -> None:
    connection.execute(
        """INSERT INTO observations (
            poll_id, ticker, venue, symbol, contract_address, requested_at_utc,
            fetched_at_utc, latency_ms, http_status, status, api_code, reference_state,
            token_price, shares_multiplier, stock_price, per_share_price, spread_bps,
            market_status, api_open_state, next_open_ms, next_close_ms, error, raw_excerpt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            poll_id, asset.ticker, asset.venue, asset.symbol, asset.contract_address,
            requested_at, fetched_at, latency_ms, http_status,
            fields.get("status", "request_error"), fields.get("api_code"),
            fields.get("reference_state", "not_checked"), fields.get("token_price"),
            fields.get("shares_multiplier"), fields.get("stock_price"),
            fields.get("per_share_price"), fields.get("spread_bps"),
            fields.get("market_status"), fields.get("api_open_state"),
            fields.get("next_open_ms"), fields.get("next_close_ms"),
            fields.get("error"), fields.get("raw_excerpt"),
        ),
    )
    # Commit each row so a Ctrl-C does not discard a partly completed sweep.
    connection.commit()


def _count_status(fields: dict[str, Any], totals: dict[str, int]) -> None:
    status = fields.get("status")
    if status not in ("request_error", "api_error", "invalid_payload"):
        totals["response_rows"] += 1
    if fields.get("spread_bps") is not None:
        totals["spreads_computed"] += 1
    if status == "ok" and fields.get("reference_state") == "missing":
        totals["missing_references"] += 1
    if status == "incomplete_metrics":
        totals["incomplete_metrics"] += 1
    if status in ("request_error", "api_error", "invalid_payload"):
        totals["request_failures"] += 1


def run_poll(connection: sqlite3.Connection, assets: list[Asset], timeout: float = 15.0,
             max_retries: int = 2, delay_seconds: float = 0.25,
             output=sys.stdout, quiet: bool = False) -> tuple[int, dict[str, int]]:
    started = utc_now()
    cursor = connection.execute(
        "INSERT INTO polls (started_at_utc, expected_observations) VALUES (?, ?)",
        (started, len(assets)),
    )
    poll_id = int(cursor.lastrowid)
    connection.commit()
    totals = {
        "response_rows": 0,
        "spreads_computed": 0,
        "missing_references": 0,
        "incomplete_metrics": 0,
        "request_failures": 0,
    }

    for index, asset in enumerate(assets):
        requested_at = utc_now()
        try:
            payload, http_status, latency_ms = _get_json_with_retries(
                dynamic_url(asset), timeout=timeout, max_retries=max_retries
            )
            fields = parse_dynamic_payload(payload)
        except FetchError as exc:
            http_status = exc.http_status
            latency_ms = None
            fields = {
                "status": "request_error",
                "api_code": None,
                "reference_state": "not_checked",
                "error": str(exc)[:500],
                "raw_excerpt": None,
            }
        fetched_at = utc_now()
        _insert_observation(connection, poll_id, asset, requested_at, fetched_at,
                            latency_ms, http_status, fields)
        _count_status(fields, totals)
        spread = fields.get("spread_bps")
        if output is not None and not quiet:
            if spread is None:
                detail = fields.get("error") or fields.get("reference_state") or fields.get("status")
                print(f"[{index + 1:03}/{len(assets):03}] {asset.ticker:6} {asset.venue:7} {fields.get('status'):18} {detail}", file=output)
            else:
                print(f"[{index + 1:03}/{len(assets):03}] {asset.ticker:6} {asset.venue:7} {spread:+9.1f} bps  market={fields.get('market_status') or 'unknown'}", file=output)
        if delay_seconds > 0 and index + 1 < len(assets):
            time.sleep(delay_seconds)

    completed = utc_now()
    connection.execute(
        """UPDATE polls SET completed_at_utc = ?, response_rows = ?, spreads_computed = ?,
           missing_references = ?, incomplete_metrics = ?, request_failures = ? WHERE id = ?""",
        (completed, totals["response_rows"], totals["spreads_computed"], totals["missing_references"],
         totals["incomplete_metrics"], totals["request_failures"], poll_id),
    )
    connection.commit()
    elapsed = ""
    try:
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        elapsed = f" elapsed={(end_dt - start_dt).total_seconds():.1f}s"
    except ValueError:
        pass
    if output is not None:
        print(
            f"Poll {poll_id} complete: {len(assets)} requested, "
            f"{totals['response_rows']} responses, {totals['spreads_computed']} gaps computed, "
            f"{totals['missing_references']} missing references, "
            f"{totals['request_failures']} request/API errors{elapsed}",
            file=output,
        )
    return poll_id, totals


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record read-only BSC tokenized-stock price observations.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE,
                        help=f"SQLite database (default: {DEFAULT_DATABASE})")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE,
                        help=f"Pinned universe JSON (default: {DEFAULT_UNIVERSE})")
    parser.add_argument("--refresh-universe", action="store_true",
                        help="Refresh the BSC triple-representation universe from Binance's public token list")
    parser.add_argument("--tickers", help="Comma-separated subset, e.g. AAPL,TSLA (default: all 38)")
    parser.add_argument("--loop", action="store_true", help="Keep polling until Ctrl-C")
    parser.add_argument("--interval-seconds", type=float, default=900,
                        help="Delay between full sweeps when --loop is set (default: 900 / 15 minutes)")
    parser.add_argument("--delay-seconds", type=float, default=0.25,
                        help="Polite pause between individual requests (default: 0.25 seconds)")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Retries for transient errors (default: 2)")
    parser.add_argument("--quiet", action="store_true", help="Print only each sweep's summary")
    args = parser.parse_args(argv)
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be greater than zero")
    if args.delay_seconds < 0:
        parser.error("--delay-seconds cannot be negative")
    if args.timeout <= 0 or args.retries < 0:
        parser.error("--timeout must be positive and --retries cannot be negative")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        universe = load_universe(args.universe, refresh=args.refresh_universe, timeout=args.timeout)
        assets = select_assets(universe, tickers=args.tickers)
    except (OSError, ValueError, FetchError, json.JSONDecodeError) as exc:
        print(f"Setup error: {exc}", file=sys.stderr)
        return 2

    print(
        f"Read-only monitor | BSC chain 56 | {len(assets) // 3} ticker(s) / {len(assets)} venue requests | "
        f"universe snapshot {universe.get('generated_at_utc', 'unknown')}",
        file=sys.stdout,
    )
    if not args.loop:
        # One sweep is the safe default. Use --loop explicitly for ongoing collection.
        with open_database(args.database) as connection:
            _, totals = run_poll(
                connection, assets, timeout=args.timeout, max_retries=args.retries,
                delay_seconds=args.delay_seconds, output=sys.stdout, quiet=args.quiet,
            )
            return 0 if totals["request_failures"] == 0 else 1

    try:
        with open_database(args.database) as connection:
            while True:
                sweep_started = time.monotonic()
                run_poll(
                    connection, assets, timeout=args.timeout, max_retries=args.retries,
                    delay_seconds=args.delay_seconds, output=sys.stdout, quiet=args.quiet,
                )
                remaining = max(0.0, args.interval_seconds - (time.monotonic() - sweep_started))
                if not args.quiet:
                    print(f"Next sweep in {remaining:.0f}s (Ctrl-C to stop)")
                time.sleep(remaining)
    except KeyboardInterrupt:
        print("\nStopped cleanly. Completed observations remain in SQLite; an interrupted sweep is visibly incomplete.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
