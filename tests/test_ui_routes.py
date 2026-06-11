"""Regression tests for the Bootstrap prototype UI pages."""

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import app


REPO_ROOT = Path(__file__).resolve().parents[1]


class PrototypeUiRoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_static_ui_files_include_bootstrap_and_design_placeholders(self):
        """The product-shaped pages should exist and use the shared Bootstrap shell."""
        html_dir = REPO_ROOT / "static" / "html"
        expected_files = [
            "home.html",
            "login.html",
            "account.html",
            "dashboard.html",
            "requests_new.html",
            "invite.html",
            "request_detail.html",
            "availability.html",
        ]

        for filename in expected_files:
            with self.subTest(filename=filename):
                content = (html_dir / filename).read_text()
                self.assertIn("bootstrap@5.3.3", content)
                self.assertIn("/static/css/style.css", content)

        request_page = (html_dir / "requests_new.html").read_text()
        self.assertIn("Top three option cards will appear here", request_page)
        self.assertIn("earliestDate", request_page)
        self.assertIn("latestDate", request_page)
        self.assertIn("weekday-input", request_page)

        stylesheet = (REPO_ROOT / "static" / "css" / "style.css").read_text()
        self.assertIn("overflow-x: hidden", stylesheet)
        self.assertIn("overscroll-behavior-x: contain", stylesheet)
        self.assertIn("@media (max-width: 575.98px)", stylesheet)

    def test_product_ui_routes_render_html(self):
        """FastAPI should serve each planned UI page without requiring OAuth config."""
        routes = [
            "/",
            "/login",
            "/account",
            "/dashboard",
            "/requests/new",
            "/invite/demo-token",
            "/not-implemented/google-login",
            "/not-implemented/microsoft-calendar",
            "/requests/demo-request",
            "/requests/demo-request/availability",
        ]

        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response.headers["content-type"])
                self.assertIn("Calendar Matching", response.text)


if __name__ == "__main__":
    unittest.main()
