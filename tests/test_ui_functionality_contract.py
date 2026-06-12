"""UI contract tests for JavaScript-backed prototype functionality."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_DIR = REPO_ROOT / "static" / "html"


class UiFunctionalityContractTest(unittest.TestCase):
    def test_profile_page_keeps_calendar_connection_contract(self):
        """Calendar account management lives on Profile instead of A/B account slots."""
        profile_html = (HTML_DIR / "profile.html").read_text()
        account_html = (HTML_DIR / "account.html").read_text()

        self.assertIn('id="profileLinkedCalendarList"', profile_html)
        self.assertIn('id="profileConnectGoogle"', profile_html)
        self.assertIn('id="platformRequestForm"', profile_html)
        self.assertIn('Microsoft · not connected', profile_html)
        self.assertIn('Apple · not connected', profile_html)
        self.assertNotIn('id="authA"', account_html)
        self.assertNotIn('id="authB"', account_html)

    def test_login_page_keeps_first_party_auth_form_contract(self):
        """The login page should start with app authentication, not calendar connection controls."""
        login_html = (HTML_DIR / "login.html").read_text()

        self.assertIn('id="authEmail"', login_html)
        self.assertIn('id="authPassword"', login_html)
        self.assertIn('id="loginBtn"', login_html)
        self.assertIn('id="registerBtn"', login_html)
        self.assertIn('id="registrationPrompt"', login_html)
        self.assertIn('No account yet?', login_html)
        self.assertNotIn('id="authA"', login_html)

        register_html = (HTML_DIR / "register.html").read_text()
        self.assertIn('id="authDisplayName"', register_html)
        self.assertIn('I already have an account', register_html)

    def test_request_creation_page_keeps_matching_form_contract(self):
        """The live matching flow depends on stable form, result, and grid IDs."""
        request_html = (HTML_DIR / "requests_new.html").read_text()

        required_ids = [
            "durationMinutes",
            "earliestDate",
            "latestDate",
            "windowStart",
            "windowEnd",
            "timeWindowsContainer",
            "addTimeWindowBtn",
            "findBtn",
            "saveRequestBtn",
            "requestSaveStatus",
            "requestAccountSelect",
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
        self.assertIn("+ Add another time", request_html)
        self.assertIn("Find best options", request_html)

    def test_javascript_references_existing_matching_endpoints(self):
        """The new templates should still call the existing pair and matching APIs."""
        app_js = (REPO_ROOT / "static" / "js" / "app.js").read_text()

        self.assertIn('const pairUrl = `/pair?time_min=${encodeURIComponent(timeMin)}', app_js)
        self.assertIn('fetch(pairUrl)', app_js)
        self.assertIn('fetch("/matching/options"', app_js)
        self.assertIn('window.location = "/oauth/start"', app_js)
        self.assertIn('account_label: selectedAccountLabel', app_js)
        self.assertIn('setAvailabilityWindows(preset.windows)', app_js)
        self.assertIn("collectAvailabilityWindows('demoTimeWindowsContainer')", app_js)

    def test_not_implemented_pages_keep_navigation_contract(self):
        """Placeholder feature pages must provide home and previous-page actions."""
        app_py = (REPO_ROOT / "app.py").read_text()

        self.assertIn('/not-implemented/{feature_slug}', app_py)
        self.assertIn('Back to home', app_py)
        self.assertIn('Back to previous page', app_py)

        login_html = (HTML_DIR / "login.html").read_text()
        account_html = (HTML_DIR / "account.html").read_text()
        friends_html = (HTML_DIR / "friends.html").read_text()
        self.assertIn('/not-implemented/google-login', login_html)
        self.assertIn('/not-implemented/microsoft-login', login_html)
        self.assertIn('url=/profile', account_html)
        self.assertIn('/not-implemented/google-contact-import', friends_html)
        self.assertIn('/not-implemented/apple-contact-import', friends_html)
        self.assertIn('/not-implemented/microsoft-contact-import', friends_html)
        self.assertIn('/not-implemented/android-contact-import', friends_html)

    def test_oauth_callback_returns_to_profile_page_for_new_templates(self):
        """After OAuth, users should return to Profile where calendar accounts are managed."""
        app_py = (REPO_ROOT / "app.py").read_text()

        self.assertIn('return_path = Column(String, nullable=False, default="/account")', app_py)
        self.assertIn('request_id = Column(String, nullable=True, index=True)', app_py)
        self.assertIn('request_role = Column(String, nullable=True)', app_py)
        self.assertIn('return_to: Optional[str] = Query(', app_py)
        self.assertIn('request_id: Optional[str] = Query(', app_py)
        self.assertIn('request_id=request_id,', app_py)
        self.assertIn('request_role=request_role,', app_py)
        self.assertIn('redirect_url = f"{return_path}{separator}account_label={account_label}&email={email}"', app_py)

    def test_invite_calendar_connection_returns_to_invite_flow(self):
        """Invitee OAuth starts must preserve request context and return to the invite panel."""
        app_js = (REPO_ROOT / "static" / "js" / "app.js").read_text()

        self.assertIn('request_id=${encodeURIComponent(currentInviteRequestId)}', app_js)
        self.assertIn('return_to=${encodeURIComponent(returnTo)}', app_js)
        self.assertIn('const returnTo = `${window.location.pathname}?accepted=1`;', app_js)


if __name__ == "__main__":
    unittest.main()
