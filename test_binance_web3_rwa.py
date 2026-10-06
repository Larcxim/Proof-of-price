import base64
import hashlib
import hmac
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import binance_web3_rwa as rwa


class BinanceWeb3RwaTests(unittest.TestCase):
    def setUp(self):
        rwa.clear_live_cache()

    def tearDown(self):
        rwa.clear_live_cache()

    def test_signature_includes_build_prefix_and_query(self):
        query, signed_path = rwa._request_path(
            rwa.TOKEN_PRICE_PATH,
            [("binanceChainId", "56"), ("tokenContractAddresses", "0xabc,0xdef")],
        )
        timestamp = "2026-10-06T10:00:00.000Z"
        expected_path = "/build/api/v1/dex/market/rwa/price?" + query
        expected_prehash = timestamp + "GET" + expected_path
        expected = base64.b64encode(
            hmac.new(b"test-secret", expected_prehash.encode("utf-8"), hashlib.sha256).digest()
        ).decode("ascii")
        self.assertEqual(signed_path, expected_path)
        self.assertEqual(rwa._signature("test-secret", timestamp, "GET", signed_path), expected)
        self.assertIn("%2C", query)

    def test_live_snapshot_normalizes_both_venues_and_computes_basis(self):
        tokens = {
            "code": 0,
            "timestamp": 1791280800000,
            "data": [
                {"underlyingTicker": "SOXL", "platformId": "bstock", "binanceChainId": "56",
                 "tokenContractAddress": "0xB", "tokenSymbol": "SOXLB", "tokenToShareRatio": "2",
                 "statusInfo": {"marketStatus": "regular", "openState": True}},
                {"underlyingTicker": "SOXL", "platformId": "ondo", "binanceChainId": "56",
                 "tokenContractAddress": "0xO", "tokenSymbol": "SOXLon", "tokenToShareRatio": "1",
                 "statusInfo": {"marketStatus": "regular", "openState": True}},
            ],
        }
        prices = {
            "code": 0,
            "timestamp": 1791280800100,
            "data": [
                {"tokenContractAddress": "0xb", "tokenPrice": "203.00", "tokenPriceUpdatedAt": 1791280799000},
                {"tokenContractAddress": "0xo", "tokenPrice": "101.00", "tokenPriceUpdatedAt": 1791280798000},
            ],
        }
        with patch.dict(os.environ, {"OC_API_KEY": "test-key", "OC_SECRET_KEY": "test-secret"}), \
             patch.object(rwa, "_signed_get_json", side_effect=[tokens, prices]) as signed_get:
            result = rwa.live_rwa_snapshot("soxl", use_cache=False)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["ticker"], "SOXL")
        self.assertEqual(result["chain_id"], "56")
        self.assertEqual(result["request_count"], 2)
        self.assertEqual(result["venues"]["bstocks"]["per_share_usd"], "101.5")
        self.assertEqual(result["venues"]["ondo"]["per_share_usd"], "101")
        expected_basis = (Decimal("101.5") / Decimal("101") - 1) * Decimal(10_000)
        self.assertEqual(Decimal(result["direct_basis_bps"]), expected_basis)
        self.assertEqual(signed_get.call_count, 2)
        self.assertEqual(signed_get.call_args_list[0].args[0], rwa.TOKEN_LIST_PATH)
        self.assertEqual(signed_get.call_args_list[1].args[0], rwa.TOKEN_PRICE_PATH)

    def test_live_snapshot_preserves_missing_venue_instead_of_zero(self):
        tokens = {
            "code": 0,
            "data": [{"underlyingTicker": "SOXL", "platformId": "bstock", "binanceChainId": "56",
                      "tokenContractAddress": "0xB", "tokenSymbol": "SOXLB", "tokenToShareRatio": "2"}],
        }
        prices = {"code": 0, "data": [{"tokenContractAddress": "0xb", "tokenPrice": "200"}]}
        with patch.dict(os.environ, {"OC_API_KEY": "test-key", "OC_SECRET_KEY": "test-secret"}), \
             patch.object(rwa, "_signed_get_json", side_effect=[tokens, prices]):
            result = rwa.live_rwa_snapshot("SOXL", use_cache=False)
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["direct_basis_bps"])
        self.assertEqual(result["missing_or_incomplete_venues"], ["Ondo"])

    def test_missing_share_ratio_is_preserved_not_coerced_to_zero(self):
        tokens = {
            "code": 0,
            "data": [
                {"underlyingTicker": "SOXL", "platformId": "bstock", "binanceChainId": "56",
                 "tokenContractAddress": "0xB", "tokenSymbol": "SOXLB", "tokenToShareRatio": None},
                {"underlyingTicker": "SOXL", "platformId": "ondo", "binanceChainId": "56",
                 "tokenContractAddress": "0xO", "tokenSymbol": "SOXLon", "tokenToShareRatio": "1"},
            ],
        }
        prices = {"code": 0, "data": [
            {"tokenContractAddress": "0xb", "tokenPrice": "200"},
            {"tokenContractAddress": "0xo", "tokenPrice": "100"},
        ]}
        with patch.dict(os.environ, {"OC_API_KEY": "test-key", "OC_SECRET_KEY": "test-secret"}), \
             patch.object(rwa, "_signed_get_json", side_effect=[tokens, prices]):
            result = rwa.live_rwa_snapshot("SOXL", use_cache=False)
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["venues"]["bstocks"]["per_share_usd"])
        self.assertIsNone(result["direct_basis_bps"])
        self.assertEqual(result["missing_or_incomplete_venues"], ["bStocks"])

    def test_missing_credentials_returns_safe_configuration_error(self):
        with patch.dict(os.environ, {"OC_API_KEY": "", "OC_SECRET_KEY": ""}, clear=False):
            with patch.object(rwa, "_private_dotenv_values", return_value={}):
                with self.assertRaises(rwa.RwaApiError) as context:
                    rwa.live_rwa_snapshot("SOXL", use_cache=False)
        self.assertEqual(context.exception.code, "credentials_missing")
        self.assertNotIn("test-secret", context.exception.message)

    def test_dotenv_reader_only_returns_named_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# private local file\nOC_API_KEY=abc123\nOC_SECRET_KEY='very-secret'\nOTHER=value\n",
                encoding="utf-8",
            )
            self.assertEqual(
                rwa._private_dotenv_values(path),
                {"OC_API_KEY": "abc123", "OC_SECRET_KEY": "very-secret"},
            )


if __name__ == "__main__":
    unittest.main()
