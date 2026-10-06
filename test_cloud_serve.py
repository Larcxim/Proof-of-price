import base64
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import cloud_serve
import serve


class AuthorizationTests(unittest.TestCase):
    def test_valid_basic_auth(self):
        header = "Basic " + base64.b64encode(b"judge:private-test-passphrase").decode("ascii")
        self.assertTrue(cloud_serve.authorization_matches(header, "judge", "private-test-passphrase"))

    def test_invalid_or_malformed_auth_is_rejected(self):
        for header in (
            "",
            "Bearer token",
            "Basic !!!",
            "Basic " + base64.b64encode(b"judge:wrong").decode("ascii"),
        ):
            with self.subTest(header=header[:12]):
                self.assertFalse(cloud_serve.authorization_matches(header, "judge", "private-test-passphrase"))
        valid = "Basic " + base64.b64encode(b"judge:private-test-passphrase").decode("ascii")
        self.assertFalse(cloud_serve.authorization_matches(valid, "", "private-test-passphrase"))
        self.assertFalse(cloud_serve.authorization_matches(valid, "judge", ""))

    def test_live_request_limiter_honors_interval(self):
        limiter = cloud_serve.LiveRequestLimiter(5)
        self.assertEqual(limiter.admit(now=100), (True, 0.0))
        allowed, wait = limiter.admit(now=102)
        self.assertFalse(allowed)
        self.assertAlmostEqual(wait, 3.0)
        self.assertEqual(limiter.admit(now=105), (True, 0.0))


class ProtectedRoutesTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), cloud_serve.ProtectedDashboardHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.environment = patch.dict(os.environ, {
            "DEMO_USERNAME": "judge",
            "DEMO_PASSWORD": "private-test-passphrase-long-enough",
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_is_public_and_contains_no_data(self):
        with urllib.request.urlopen(self.base + "/health", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {"ok": True})

    def test_dashboard_requires_authentication(self):
        try:
            urllib.request.urlopen(self.base + "/", timeout=2)
            self.fail("expected HTTP 401")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 401)
            self.assertIn("Basic", exc.headers.get("WWW-Authenticate", ""))

    def test_dashboard_loads_with_valid_auth(self):
        token = base64.b64encode(b"judge:private-test-passphrase-long-enough").decode("ascii")
        request = urllib.request.Request(self.base + "/", headers={"Authorization": "Basic " + token})
        with urllib.request.urlopen(request, timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"Proof of Price", response.read())

    def test_live_api_is_not_called_without_auth(self):
        with patch.object(serve, "live_rwa_snapshot") as live_call:
            try:
                urllib.request.urlopen(self.base + "/api/live-rwa?ticker=SOXL", timeout=2)
                self.fail("expected HTTP 401")
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 401)
            live_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
