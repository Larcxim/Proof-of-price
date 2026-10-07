import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from binance_web3_rwa import RwaApiError
from monitor import ensure_schema
import serve
from serve import history_for_ticker, latest_snapshot, normalized_pair_basis_bps


class PairwiseBasisTests(unittest.TestCase):
    def test_basis_compares_normalized_token_prices(self):
        self.assertAlmostEqual(
            normalized_pair_basis_bps(26.78, 26.2518),
            (26.78 / 26.2518 - 1) * 10_000,
        )
        self.assertEqual(normalized_pair_basis_bps(100, 100), 0.0)
        self.assertAlmostEqual(normalized_pair_basis_bps(99, 100), -100.0)

    def test_missing_nonpositive_and_nonfinite_prices_are_not_comparable(self):
        for bstocks, ondo in ((None, 100), (100, None), (0, 100), (100, 0), (-1, 100), (float("nan"), 100)):
            with self.subTest(bstocks=bstocks, ondo=ondo):
                self.assertIsNone(normalized_pair_basis_bps(bstocks, ondo))

    def test_snapshot_and_history_compare_bstocks_without_stock_quote(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "monitor.sqlite3"
            universe_path = root / "universe.json"
            universe_path.write_text(json.dumps({"tickers": {"TEST": {}}}), encoding="utf-8")

            connection = sqlite3.connect(db_path)
            ensure_schema(connection)
            cursor = connection.execute(
                """INSERT INTO polls (
                       started_at_utc, completed_at_utc, expected_observations,
                       response_rows, spreads_computed, missing_references,
                       incomplete_metrics, request_failures
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("2026-10-05T01:00:00Z", "2026-10-05T01:00:05Z", 3, 2, 1, 1, 0, 0),
            )
            poll_id = cursor.lastrowid
            shared = (poll_id, "TEST", "2026-10-05T01:00:01Z", "2026-10-05T01:00:02Z")
            connection.execute(
                """INSERT INTO observations (
                       poll_id, ticker, venue, symbol, contract_address,
                       requested_at_utc, fetched_at_utc, status, reference_state,
                       token_price, shares_multiplier, stock_price, per_share_price,
                       spread_bps
                   ) VALUES (?, ?, 'ondo', 'TESTon', '0x1', ?, ?, 'ok', 'available',
                             100, 1, 99, 100, ?)
                """,
                (*shared, (100 / 99 - 1) * 10_000),
            )
            connection.execute(
                """INSERT INTO observations (
                       poll_id, ticker, venue, symbol, contract_address,
                       requested_at_utc, fetched_at_utc, status, reference_state,
                       token_price, shares_multiplier, stock_price, per_share_price,
                       spread_bps
                   ) VALUES (?, ?, 'bstocks', 'TESTB', '0x2', ?, ?, 'ok', 'missing',
                             101, 1, NULL, 101, NULL)
                """,
                shared,
            )
            connection.commit()
            connection.close()

            snapshot = latest_snapshot(db_path, universe_path)
            row = next(item for item in snapshot["tickers"] if item["ticker"] == "TEST")
            self.assertAlmostEqual(row["pairwise_basis_bps"], 100.0)
            self.assertIsNone(row["venues"]["bstocks"]["stock_price"])
            self.assertEqual(snapshot["pairwise_basis"]["pair_count"], 1)
            self.assertEqual(snapshot["pairwise_basis"]["over_100_bps"], 0)

            history = history_for_ticker(db_path, "TEST")
            self.assertEqual(len(history["pairwise"]), 1)
            self.assertAlmostEqual(history["pairwise"][0]["basis_bps"], 100.0)


class OnboardingGuideTests(unittest.TestCase):
    def test_plain_language_read_only_guide_is_present(self):
        self.assertIn('id="how-to-read"', serve.HTML_TEMPLATE)
        self.assertIn("no wallet needed to view", serve.HTML_TEMPLATE.lower())
        self.assertIn("positive means bStocks is higher", serve.HTML_TEMPLATE)
        self.assertIn("1 bp = 0.01%; 100 bp = 1%", serve.HTML_TEMPLATE)
        self.assertIn("Missing is not zero", serve.HTML_TEMPLATE)
        self.assertIn("does not connect a wallet or place transactions", serve.HTML_TEMPLATE)


class DashboardPaletteTests(unittest.TestCase):
    def test_charcoal_yellow_palette_is_applied_to_primary_surfaces(self):
        self.assertIn("header{background:#181a20!important", serve.HTML_TEMPLATE)
        self.assertIn("linear-gradient(145deg,#181a20,#2a2d33)", serve.HTML_TEMPLATE)
        self.assertIn("bstocks:'#7b8088'", serve.HTML_TEMPLATE)


class LiveApiRouteTests(unittest.TestCase):
    def test_live_route_returns_safe_error_without_credentials(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), serve.DashboardHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/live-rwa?ticker=SOXL"
            with patch.object(
                serve,
                "live_rwa_snapshot",
                side_effect=RwaApiError("credentials_missing", "Configure credentials locally.", 503),
            ):
                try:
                    urllib.request.urlopen(url, timeout=2)
                    self.fail("expected HTTP 503")
                except urllib.error.HTTPError as exc:
                    self.assertEqual(exc.code, 503)
                    payload = json.loads(exc.read().decode("utf-8"))
            self.assertEqual(payload["code"], "credentials_missing")
            self.assertEqual(payload["error"], "Configure credentials locally.")
            self.assertNotIn("secret", json.dumps(payload).lower())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
