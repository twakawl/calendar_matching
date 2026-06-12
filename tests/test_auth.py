"""Regression tests for first-party user authentication."""

import uuid
import unittest

from fastapi.testclient import TestClient

from app import SESSION_COOKIE_NAME, SessionLocal, User, app


class AuthenticationApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.email = f"user-{uuid.uuid4().hex}@example.com"
        self.password = "correct horse battery staple"

    def test_register_sets_session_and_does_not_store_plaintext_password(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "display_name": "Test User",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user"]["email"], self.email)
        self.assertNotIn("password", body["user"])
        self.assertIn("session_token", body)
        self.assertIn(SESSION_COOKIE_NAME, response.cookies)

        db = SessionLocal()
        try:
            user = db.query(User).filter_by(email=self.email).one()
            self.assertNotEqual(user.password_hash, self.password)
            self.assertTrue(user.password_hash.startswith("pbkdf2_sha256$"))
        finally:
            db.close()

    def test_development_test_accounts_are_seeded_once(self):
        db = SessionLocal()
        try:
            seeded = {
                user.email: user
                for user in db.query(User).filter(
                    User.email.in_([
                        "twan.houwers92@gmail.com",
                        "twan@dutchwebshark.com",
                    ])
                ).all()
            }
            self.assertEqual(
                set(seeded),
                {"twan.houwers92@gmail.com", "twan@dutchwebshark.com"},
            )
            for user in seeded.values():
                self.assertTrue(user.password_hash.startswith("pbkdf2_sha256$"))
                self.assertNotEqual(user.password_hash, "Test123!")
        finally:
            db.close()

        for email in ["twan.houwers92@gmail.com", "twan@dutchwebshark.com"]:
            login = self.client.post(
                "/auth/login",
                json={"email": email, "password": "Test123!"},
            )
            self.assertEqual(login.status_code, 200)

    def test_login_me_and_logout_session_flow(self):
        self.client.post(
            "/auth/register",
            json={"email": self.email, "password": self.password},
        )
        login = self.client.post(
            "/auth/login",
            json={"email": self.email.upper(), "password": self.password},
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["session_token"]

        me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], self.email)

        logout = self.client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(logout.status_code, 200)

        after_logout = self.client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(after_logout.status_code, 401)

    def test_login_with_unregistered_email_prompts_registration_flow(self):
        response = self.client.post(
            "/auth/login",
            json={"email": self.email, "password": self.password},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("register first", response.json()["detail"])

    def test_home_is_public_and_app_pages_redirect_when_unauthenticated(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Find a meeting time", response.text)
        self.assertIn("/login", response.text)

        protected = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(protected.status_code, 303)
        self.assertEqual(protected.headers["location"], "/login")

        login_page = self.client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("Log in", login_page.text)
        self.assertIn("authEmail", login_page.text)
        self.assertNotIn("Authenticate user A", login_page.text)

    def test_logged_in_user_sees_app_shell_and_menu_not_login_page(self):
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "display_name": "Menu User",
            },
        )

        login_redirect = self.client.get("/login", follow_redirects=False)
        self.assertEqual(login_redirect.status_code, 303)
        self.assertEqual(login_redirect.headers["location"], "/dashboard")

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("requestList", dashboard.text)
        self.assertNotIn("authEmail", dashboard.text)

    def test_calendar_accounts_require_authentication(self):
        response = self.client.get("/accounts")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
