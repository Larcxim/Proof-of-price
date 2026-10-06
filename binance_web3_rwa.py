"""Read-only, signed Binance Web3 RWA API client for Proof of Price.

Credentials are read only by the local server from process environment or a private
`.env` file beside this module. They are never returned in API responses or logged.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://web3.binance.com/build"
CHAIN_ID = "56"
TOKEN_LIST_PATH = "/api/v1/dex/market/rwa/tokens"
TOKEN_PRICE_PATH = "/api/v1/dex/market/rwa/price"
TIMEOUT_SECONDS = 15
CACHE_SECONDS = 15


class RwaApiError(Exception):
    """Safe-to-display API error; never contains credentials or signed headers."""

    def __init__(self, code: str, message: str, http_status: int = 502):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.message = message


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _private_dotenv_values(path: Path | None = None) -> dict[str, str]:
    """Read the two supported key names from a private local .env; do not print values."""
    env_path = path or Path(__file__).resolve().parent / ".env"
    values: dict[str, str] = {}
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key in ("OC_API_KEY", "OC_SECRET_KEY") and value:
            values[key] = value
    return values


def _credentials() -> tuple[str, str]:
    file_values = _private_dotenv_values()
    api_key = os.environ.get("OC_API_KEY", "").strip() or file_values.get("OC_API_KEY", "").strip()
    secret = os.environ.get("OC_SECRET_KEY", "").strip() or file_values.get("OC_SECRET_KEY", "").strip()
    placeholders = ("replace_with_web3_api_key", "replace_with_web3_secret_key")
    if not api_key or not secret or api_key in placeholders or secret in placeholders:
        raise RwaApiError(
            "credentials_missing",
            "Live API credentials are not configured on this server. Add them only to a private local .env file.",
            503,
        )
    return api_key, secret


def _request_path(path: str, params: list[tuple[str, str]]) -> tuple[str, str]:
    """Return the exact wire query and signed path, including Binance's /build prefix."""
    query = urlencode(params)
    suffix = f"?{query}" if query else ""
    return query, f"/build{path}{suffix}"


def _signature(secret: str, timestamp: str, method: str, signed_path: str, body: str = "") -> str:
    prehash = timestamp + method.upper() + signed_path + body
    digest = hmac.new(secret.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _signed_get_json(path: str, params: list[tuple[str, str]], api_key: str, secret: str) -> dict[str, Any]:
    query, signed_path = _request_path(path, params)
    timestamp = _utc_now()
    signature = _signature(secret, timestamp, "GET", signed_path)
    url = BASE_URL + path + (f"?{query}" if query else "")
    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "X-OC-APIKEY": api_key,
            "X-OC-TIMESTAMP": timestamp,
            "X-OC-SIGN": signature,
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except HTTPError as exc:
        raise RwaApiError("upstream_http_error", f"Binance Web3 API returned HTTP {exc.code}.", 502) from None
    except (URLError, TimeoutError, OSError):
        raise RwaApiError("upstream_unavailable", "Could not reach the Binance Web3 API. Try again shortly.", 502) from None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RwaApiError("invalid_json", "The Binance Web3 API returned an unreadable response.", 502) from None
    if not isinstance(payload, dict):
        raise RwaApiError("invalid_response", "The Binance Web3 API returned an unexpected response shape.", 502)
    code = payload.get("code")
    if code not in (None, 0, "0") or payload.get("success") is False:
        # Do not reflect arbitrary upstream messages; they can contain request details.
        raise RwaApiError("api_rejected", "The Binance Web3 API did not accept the request. Check key access and try again.", 502)
    return payload


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not number.is_finite():
        return None
    return number


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _millis_to_iso(value: Any) -> str | None:
    try:
        number = int(value)
        if number <= 0:
            return None
        return datetime.fromtimestamp(number / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _api_data(payload: dict[str, Any], label: str) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise RwaApiError("invalid_response", f"The {label} endpoint did not return a list of assets.", 502)
    return [row for row in data if isinstance(row, dict)]


_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def clear_live_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def live_rwa_snapshot(ticker: str, *, use_cache: bool = True) -> dict[str, Any]:
    """Fetch read-only BSC RWA data and compute a direct bStocks/Ondo per-share basis."""
    clean_ticker = (ticker or "").strip().upper()
    if not clean_ticker or len(clean_ticker) > 12 or not clean_ticker.isalnum():
        raise RwaApiError("invalid_ticker", "Enter a valid ticker using letters and numbers.", 400)
    now_mono = time.monotonic()
    if use_cache:
        with _CACHE_LOCK:
            cached = _CACHE.get(clean_ticker)
            if cached and now_mono - cached[0] < CACHE_SECONDS:
                result = dict(cached[1])
                result["cache_hit"] = True
                return result

    api_key, secret = _credentials()
    requested_at = _utc_now()
    tokens_payload = _signed_get_json(
        TOKEN_LIST_PATH,
        [("binanceChainId", CHAIN_ID)],
        api_key,
        secret,
    )
    token_rows = _api_data(tokens_payload, "RWA token list")
    matches: dict[str, list[dict[str, Any]]] = {"bstock": [], "ondo": []}
    for row in token_rows:
        row_ticker = str(row.get("underlyingTicker") or "").strip().upper()
        platform = str(row.get("platformId") or "").strip().lower()
        chain_id = str(row.get("binanceChainId") or "")
        if row_ticker == clean_ticker and chain_id == CHAIN_ID and platform in matches:
            address = str(row.get("tokenContractAddress") or "").strip()
            if address:
                matches[platform].append(row)

    # Deduplicate repeated rows for the same contract without selecting among distinct assets.
    for platform, rows in matches.items():
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            unique[str(row["tokenContractAddress"]).lower()] = row
        matches[platform] = list(unique.values())
        if len(matches[platform]) > 1:
            raise RwaApiError(
                "ambiguous_asset",
                f"More than one BSC {platform} token matched {clean_ticker}; no basis was calculated.",
                409,
            )

    selected = {platform: rows[0] for platform, rows in matches.items() if rows}
    if not selected:
        raise RwaApiError("ticker_not_found", f"No bStocks or Ondo BSC token was found for {clean_ticker}.", 404)

    addresses = [str(row["tokenContractAddress"]) for row in selected.values()]
    prices_payload = _signed_get_json(
        TOKEN_PRICE_PATH,
        [("binanceChainId", CHAIN_ID), ("tokenContractAddresses", ",".join(addresses))],
        api_key,
        secret,
    )
    price_rows = _api_data(prices_payload, "RWA token price")
    prices_by_address = {
        str(row.get("tokenContractAddress") or "").lower(): row
        for row in price_rows
        if row.get("tokenContractAddress")
    }

    venues: dict[str, Any] = {}
    share_values: dict[str, Decimal] = {}
    label_for = {"bstock": "bStocks", "ondo": "Ondo"}
    for platform, row in selected.items():
        address = str(row["tokenContractAddress"])
        price_row = prices_by_address.get(address.lower())
        token_price = _decimal(price_row.get("tokenPrice")) if price_row else None
        ratio = _decimal(row.get("tokenToShareRatio"))
        per_share = token_price / ratio if token_price is not None and ratio is not None and ratio > 0 else None
        if per_share is not None and per_share > 0:
            share_values[platform] = per_share
        status_info = row.get("statusInfo") if isinstance(row.get("statusInfo"), dict) else {}
        venues[platform] = {
            "venue": label_for[platform],
            "symbol": row.get("tokenSymbol"),
            "contract_address": address,
            "token_price_usd": _decimal_text(token_price),
            "token_to_share_ratio": _decimal_text(ratio),
            "per_share_usd": _decimal_text(per_share),
            "token_price_updated_at_utc": _millis_to_iso(price_row.get("tokenPriceUpdatedAt")) if price_row else None,
            "market_status": status_info.get("marketStatus"),
            "open_state": status_info.get("openState"),
            "price_available": token_price is not None,
        }

    basis: Decimal | None = None
    if "bstock" in share_values and "ondo" in share_values:
        basis = (share_values["bstock"] / share_values["ondo"] - Decimal(1)) * Decimal(10_000)
    completed_at = _utc_now()
    missing = [label_for[key] for key in ("bstock", "ondo") if key not in share_values]
    result = {
        "status": "ok" if basis is not None else "partial",
        "ticker": clean_ticker,
        "chain_id": CHAIN_ID,
        "source": "Binance Web3 API · signed RWA Data endpoints",
        "requested_at_utc": requested_at,
        "completed_at_utc": completed_at,
        "api_server_timestamp_ms": prices_payload.get("timestamp"),
        "request_count": 2,
        "cache_hit": False,
        "venues": {
            "bstocks": venues.get("bstock"),
            "ondo": venues.get("ondo"),
        },
        "direct_basis_bps": _decimal_text(basis),
        "missing_or_incomplete_venues": missing,
        "basis_formula": "(bStocks per-share price / Ondo per-share price - 1) × 10,000",
        "per_share_formula": "tokenPrice / tokenToShareRatio",
        "reference_note": "The API's referencePrice is derived from token price; it is not an independent stock-market quote.",
        "limits": "Read-only API observations. No wallet, trade, route, liquidity, fees, or slippage check.",
    }
    if use_cache:
        with _CACHE_LOCK:
            _CACHE[clean_ticker] = (time.monotonic(), dict(result))
    return result
