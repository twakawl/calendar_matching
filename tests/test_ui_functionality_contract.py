"""UI contract tests for JavaScript-backed prototype functionality."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_DIR = REPO_ROOT / "static" / "html"


class UiFunctionalityContractTest(unittest.TestCase):
    def test_account_page_keeps_oauth_button_ids_used_by_javascript(self):
        """Calendar connection buttons must keep the IDs wired in app.js."""
        account_html = (HTML_DIR / "account.html").read_text()
        login_html = (HTML_DIR / "login.html").read_text()

        for html in (account_html, login_html):
            with self.subTest(page="account_or_login"):
                self.assertIn('id="authA"', html)
                self.assertIn('id="authB"', html)
                self.assertIn('id="statusA"', html)
                self.assertIn('id="statusB"', html)
                self.assertIn('id="emailA"', html)
                self.assertIn('id="emailB"', html)

    def test_request_creation_page_keeps_matching_form_contract(self):
        """The live matching flow depends on stable form, result, and grid IDs."""
        request_html = (HTML_DIR / "requests_new.html").read_text()

        required_ids = [
            "durationMinutes",
            "earliestDate",
            "latestDate",
            "windowStart",
            "windowEnd",
            "findBtn",
            "selectA",
            "selectB",
            "optionCards",
            "calendarContainer",
            "calendarGrid",
            "suggestedSlots",
            "overview",
        ]
        for element_id in required_ids:
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', request_html)

        self.assertIn("weekday-input", request_html)
        self.assertIn("Find best options", request_html)

    def test_javascript_references_existing_matching_endpoints(self):
        """The new templates should still call the existing pair and matching APIs."""
        app_js = (REPO_ROOT / "static" / "js" / "app.js").read_text()

        self.assertIn('fetch(`/pair?time_min=${encodeURIComponent(timeMin)}', app_js)
        self.assertIn('fetch("/matching/options"', app_js)
        self.assertIn('window.location = "/oauth/start?account_label=a"', app_js)
        self.assertIn('window.location = "/oauth/start?account_label=b"', app_js)

    def test_oauth_callback_returns_to_account_page_for_new_templates(self):
        """After OAuth, users should return to a page that has the account status UI."""
        app_py = (REPO_ROOT / "app.py").read_text()

        self.assertIn('redirect_url = f"/account?account_label={account_label}&email={email}"', app_py)


if __name__ == "__main__":
    unittest.main()
