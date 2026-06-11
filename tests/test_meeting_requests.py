"""Regression tests for SQLite-backed meeting requests and invite links."""

import unittest
import uuid

from fastapi.testclient import TestClient

from app import RequestAuditEvent, SessionLocal, app


class MeetingRequestApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.email = f"request-user-{uuid.uuid4().hex}@example.com"
        self.invitee_email = f"invitee-{uuid.uuid4().hex}@example.com"
        self.password = "correct horse battery staple"
        self.client.post(
            "/auth/register",
            json={"email": self.email, "password": self.password},
        )

    def request_payload(self):
        return {
            "title": "SQLite planning sync",
            "invitee_email": self.invitee_email.upper(),
            "duration_minutes": 45,
            "earliest_date": "2026-06-08",
            "latest_date": "2026-06-19",
            "timezone": "UTC",
            "window_start": "09:00",
            "window_end": "17:00",
            "allowed_weekdays": ["Mon", "Tue", "Wed"],
            "allowed_windows": [
                {"day": 0, "start": "10:00", "end": "12:00"},
                {"day": 1, "start": "10:00", "end": "12:00"},
                {"day": 2, "start": "10:00", "end": "15:00"},
            ],
            "notes": "Bring roadmap notes.",
        }

    def test_create_and_list_request_generates_secure_invite_once(self):
        created = self.client.post("/api/requests", json=self.request_payload())
        self.assertEqual(created.status_code, 200)
        body = created.json()
        self.assertEqual(body["title"], "SQLite planning sync")
        self.assertEqual(body["invitee_email"], self.invitee_email)
        self.assertEqual(body["status"], "sent")
        self.assertTrue(body["invite_url"].startswith("/invite/"))
        self.assertNotIn(body["id"], body["invite_url"])
        self.assertIsNotNone(body["invite_expires_at"])

        listed = self.client.get("/api/requests")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()], [body["id"]])
        self.assertIsNone(listed.json()[0]["invite_url"])

        fetched = self.client.get(f"/api/requests/{body['id']}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["allowed_weekdays"], ["Mon", "Tue", "Wed"])
        self.assertEqual(
            fetched.json()["allowed_windows"],
            [
                {"day": 0, "start": "10:00", "end": "12:00"},
                {"day": 1, "start": "10:00", "end": "12:00"},
                {"day": 2, "start": "10:00", "end": "15:00"},
            ],
        )

    def test_invite_preview_accept_and_audit_flow(self):
        created = self.client.post("/api/requests", json=self.request_payload()).json()
        token = created["invite_url"].rsplit("/", 1)[-1]

        preview = self.client.get(f"/api/invites/{token}")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["title"], "SQLite planning sync")
        self.assertEqual(preview.json()["requester_email"], self.email)
        self.assertEqual(preview.json()["invitee_email"], self.invitee_email)
        self.assertNotIn("notes", preview.json())

        invitee_client = TestClient(app)
        invitee_client.post(
            "/auth/register",
            json={"email": self.invitee_email, "password": self.password},
        )
        accepted = invitee_client.post(f"/api/invites/{token}/accept")
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "awaiting_calendar_connection")

        visible_to_invitee = invitee_client.get(f"/api/requests/{created['id']}")
        self.assertEqual(visible_to_invitee.status_code, 200)
        self.assertEqual(visible_to_invitee.json()["invitee_email"], self.invitee_email)

        audit = self.client.get(f"/api/requests/{created['id']}/audit")
        self.assertEqual(audit.status_code, 200)
        self.assertIn("created", [event["action"] for event in audit.json()])
        self.assertIn("accepted", [event["action"] for event in audit.json()])

        db = SessionLocal()
        try:
            details = [
                event.details
                for event in db.query(RequestAuditEvent).filter_by(request_id=created["id"]).all()
            ]
            self.assertTrue(any("expires_at" in (detail or "") for detail in details))
        finally:
            db.close()

    def test_accept_invite_rejects_wrong_email(self):
        created = self.client.post("/api/requests", json=self.request_payload()).json()
        token = created["invite_url"].rsplit("/", 1)[-1]

        wrong_client = TestClient(app)
        wrong_client.post(
            "/auth/register",
            json={
                "email": f"wrong-{uuid.uuid4().hex}@example.com",
                "password": self.password,
            },
        )
        response = wrong_client.post(f"/api/invites/{token}/accept")
        self.assertEqual(response.status_code, 403)

    def test_request_validation_rejects_bad_date_range(self):
        response = self.client.post(
            "/api/requests",
            json={
                "title": "Bad range",
                "invitee_email": "invitee@example.com",
                "duration_minutes": 30,
                "earliest_date": "2026-06-19",
                "latest_date": "2026-06-08",
                "window_start": "09:00",
                "window_end": "17:00",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Latest date must be on or after earliest date")


if __name__ == "__main__":
    unittest.main()
