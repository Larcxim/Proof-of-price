import json
import sqlite3
import unittest
from pathlib import Path

from monitor import build_universe, ensure_schema, parse_dynamic_payload, select_assets


class UniverseTests(unittest.TestCase):
    def test_pinned_snapshot_has_38_triples_and_114_contracts(self):
        root = Path(__file__).resolve().parents[1]
        universe = json.loads((root / "data" / "universe.json").read_text(encoding="utf-8"))
        self.assertEqual(len(universe["tickers"]), 38)
        self.assertEqual(len(select_assets(universe)), 114)
        self.assertEqual(len(select_assets(universe, "AAPL,TSLA")), 6)

    def test_build_universe_ignores_other_chains_and_partial_tickers(self):
        records = [
            {"chainId": "56", "ticker": "ABC", "symbol": "ABCon", "contractAddress": "0x1", "multiplier": "1"},
            {"chainId": "56", "ticker": "ABC", "symbol": "ABCx", "contractAddress": "0x2", "multiplier": "1"},
            {"chainId": "56", "ticker": "ABC", "symbol": "ABCB", "contractAddress": "0x3", "multiplier": "1"},
            {"chainId": "1", "ticker": "DEF", "symbol": "DEFon", "contractAddress": "0x4", "multiplier": "1"},
            {"chainId": "56", "ticker": "XYZ", "symbol": "XYZon", "contractAddress": "0x5", "multiplier": "1"},
        ]
        universe = build_universe(records, generated_at_utc="2026-10-04T00:00:00Z")
        self.assertEqual(list(universe["tickers"]), ["ABC"])
        self.assertEqual(universe["tickers"]["ABC"]["bstocks"]["symbol"], "ABCB")

    def test_unknown_ticker_is_rejected(self):
        universe = {"tickers": {"AAPL": {"ondo": {}, "xstocks": {}, "bstocks": {}}}}
        with self.assertRaisesRegex(ValueError, "NOTREAL"):
            select_assets(universe, "NOTREAL")


class MeasurementTests(unittest.TestCase):
    def test_formula_uses_per_share_price_and_basis_points(self):
        payload = {
            "code": "000000",
            "success": True,
            "data": {
                "symbol": "TESTon",
                "tokenInfo": {"price": "100", "sharesMultiplier": "2"},
                "stockInfo": {"price": "48"},
                "statusInfo": {"marketStatus": "closed", "openState": False},
            },
        }
        result = parse_dynamic_payload(payload)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["per_share_price"], 50.0)
        self.assertAlmostEqual(result["spread_bps"], (50 / 48 - 1) * 10_000)
        self.assertEqual(result["reference_state"], "available")
        self.assertEqual(result["market_status"], "closed")
        self.assertEqual(result["api_open_state"], 0)

    def test_null_underlying_is_valid_observation_without_a_spread(self):
        payload = {
            "code": "000000",
            "success": True,
            "data": {
                "symbol": "TESTB",
                "tokenInfo": {"price": "25", "sharesMultiplier": "1.25"},
                "stockInfo": {"price": None},
                "statusInfo": {"marketStatus": "closed"},
            },
        }
        result = parse_dynamic_payload(payload)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["reference_state"], "missing")
        self.assertEqual(result["per_share_price"], 20.0)
        self.assertIsNone(result["spread_bps"])

    def test_incomplete_token_metrics_are_not_misreported_as_zero(self):
        payload = {
            "code": "000000", "success": True,
            "data": {"tokenInfo": {"price": "10", "sharesMultiplier": None}, "stockInfo": {"price": "10"}},
        }
        result = parse_dynamic_payload(payload)
        self.assertEqual(result["status"], "incomplete_metrics")
        self.assertEqual(result["reference_state"], "not_checked")
        self.assertIsNone(result["spread_bps"])

    def test_api_error_is_preserved(self):
        result = parse_dynamic_payload({"code": "123", "success": False, "message": "sample failure"})
        self.assertEqual(result["status"], "api_error")
        self.assertEqual(result["reference_state"], "not_checked")
        self.assertIn("sample failure", result["error"])


class DatabaseTests(unittest.TestCase):
    def test_schema_creates_poll_and_observation_tables(self):
        connection = sqlite3.connect(":memory:")
        ensure_schema(connection)
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"polls", "observations"}.issubset(names))
        connection.close()


if __name__ == "__main__":
    unittest.main()
