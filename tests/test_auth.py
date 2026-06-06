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


    def test_home_redirects_to_login_when_unauthenticated(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login")

        login_page = self.client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("Log in", login_page.text)
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
        self.assertEqual(login_redirect.headers["location"], "/")

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn("userMenuName", home.text)
        self.assertIn("Authenticate user A", home.text)
        self.assertNotIn("authEmail", home.text)

    def test_calendar_accounts_require_authentication(self):
        response = self.client.get("/accounts")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
