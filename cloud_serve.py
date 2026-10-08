#!/usr/bin/env python3
"""Hosted entry point for the Proof of Price demo.

The existing dashboard/API handlers remain in serve.py. This wrapper adds
optional HTTP Basic authentication (public by default when DEMO_PUBLIC is set
or DEMO_PASSWORD is absent), reads Render's PORT, and throttles signed live
API requests. It never prints credentials or authorization headers. Startup
messages are flushed so they appear in host logs immediately.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

from serve import DashboardHandler, DEFAULT_DB, DEFAULT_UNIVERSE

LIVE_REQUEST_INTERVAL_SECONDS = 5.0


def public_mode() -> bool:
    """True when the demo should serve without the Basic Auth gate.

    Public mode is explicit (DEMO_PUBLIC set to 1/true/yes/on) or implied by
    the absence of DEMO_PASSWORD, so a judge-facing link can be shared with no
    prompt. The dashboard is read-only either way, and the live-request
    cooldown below still applies.
    """
    flag = os.environ.get("DEMO_PUBLIC", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return not os.environ.get("DEMO_PASSWORD", "").strip()


class LiveRequestLimiter:
    """Process-wide cooldown; the Binance client also caches per ticker."""

    def __init__(self, interval_seconds: float = LIVE_REQUEST_INTERVAL_SECONDS) -> None:
        self.interval_seconds = max(0.0, float(interval_seconds))
        self._next_allowed_at = 0.0
        self._lock = threading.Lock()

    def admit(self, now: float | None = None) -> tuple[bool, float]:
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            wait = self._next_allowed_at - current
            if wait > 0:
                return False, wait
            self._next_allowed_at = current + self.interval_seconds
            return True, 0.0


_live_limiter = LiveRequestLimiter()


def authorization_matches(header: str, username: str, password: str) -> bool:
    """Validate a Basic Authorization header without reflecting credential data."""
    if not header or not username or not password:
        return False
    scheme, separator, encoded = header.partition(" ")
    if not separator or scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    expected = f"{username}:{password}"
    return hmac.compare_digest(decoded.encode("utf-8"), expected.encode("utf-8"))


class ProtectedDashboardHandler(DashboardHandler):
    """Require a judge password for dashboard data and API routes,
    unless the host explicitly runs the demo in public mode."""

    def _send_auth_required(self) -> None:
        body = b"Proof of Price demo access requires a username and password."
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Proof of Price demo", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_rate_limited(self, retry_after: float) -> None:
        body = json.dumps({
            "error": "Please wait a few seconds before making another live check.",
            "code": "rate_limited",
        }).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Retry-After", str(max(1, int(retry_after + 0.999))))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        # Render's health probe reveals no dashboard data or API state.
        if path == "/health":
            super().do_GET()
            return

        if not public_mode():
            username = os.environ.get("DEMO_USERNAME", "judge")
            password = os.environ.get("DEMO_PASSWORD", "")
            if not authorization_matches(self.headers.get("Authorization", ""), username, password):
                self._send_auth_required()
                return

        if path == "/api/live-rwa":
            allowed, retry_after = _live_limiter.admit()
            if not allowed:
                self._send_rate_limited(retry_after)
                return

        super().do_GET()

    def _send_method_not_allowed(self) -> None:
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        # The product is read-only; no POST endpoint exists.
        self._send_method_not_allowed()

    def do_PUT(self) -> None:  # noqa: N802
        self._send_method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802
        self._send_method_not_allowed()


def main() -> int:
    if public_mode():
        print("PUBLIC MODE: serving without password protection "
              "(DEMO_PUBLIC is set or DEMO_PASSWORD is absent).", flush=True)
    else:
        username = os.environ.get("DEMO_USERNAME", "judge").strip()
        password = os.environ.get("DEMO_PASSWORD", "")
        if not username or not password:
            raise SystemExit("Set DEMO_USERNAME and DEMO_PASSWORD as private host environment "
                             "variables, or set DEMO_PUBLIC=true to serve without the gate.")
        if len(password) < 16:
            raise SystemExit("DEMO_PASSWORD must be at least 16 characters; use a private, unique "
                             "passphrase, or set DEMO_PUBLIC=true to serve without the gate.")

    missing_api = [name for name in ("OC_API_KEY", "OC_SECRET_KEY") if not os.environ.get(name, "").strip()]
    if missing_api:
        # Keep the dashboard available, but make the live-key gap explicit in host logs.
        print("WARNING: Binance Web3 live API is not configured; missing server environment variable(s): "
              + ", ".join(missing_api), flush=True)

    try:
        port = int(os.environ.get("PORT", "10000"))
    except ValueError as exc:
        raise SystemExit("PORT must be a valid integer supplied by the hosting platform.") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535.")

    DashboardHandler.db_path = DEFAULT_DB
    DashboardHandler.universe_path = DEFAULT_UNIVERSE
    server = ThreadingHTTPServer(("0.0.0.0", port), ProtectedDashboardHandler)
    server.daemon_threads = True
    mode_text = "public (no password)" if public_mode() else "password-protected (Basic Auth)"
    print(f"Proof of Price demo listening on port {port} in {mode_text} mode; /health is always public.",
          flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nHosted dashboard server stopped.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
