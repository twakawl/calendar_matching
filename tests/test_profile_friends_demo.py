"""Regression tests for profile settings, friends, and demo matching."""

import unittest
import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app import app


class ProfileFriendsDemoTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.email = f"profile-{uuid.uuid4().hex}@example.com"
        self.password = "correct horse battery staple"
        self.client.post(
            "/auth/register",
            json={"email": self.email, "password": self.password, "display_name": "Profile User"},
        )

    def test_profile_can_update_ordered_presets_and_contact_fields(self):
        profile = self.client.get("/api/profile")
        self.assertEqual(profile.status_code, 200)
        self.assertGreaterEqual(len(profile.json()["time_presets"]), 5)

        payload = profile.json()
        payload["display_name"] = "Updated User"
        payload["phone_number"] = "+31612345678"
        payload["timezone_preference"] = "Europe/Amsterdam"
        payload["linked_calendar_label"] = "a"
        payload["linked_calendar_labels"] = ["a", "b"]
        payload["time_presets"] = [
            {
                "id": "custom-lunch",
                "name": "Custom lunch",
                "windows": [{"day": 0, "start": "12:00", "end": "13:00"}],
            }
        ]

        updated = self.client.put("/api/profile", json=payload)
        self.assertEqual(updated.status_code, 200)
        body = updated.json()
        self.assertEqual(body["display_name"], "Updated User")
        self.assertEqual(body["phone_number"], "+31612345678")
        self.assertEqual(body["timezone_preference"], "Europe/Amsterdam")
        self.assertEqual(body["linked_calendar_label"], "a")
        self.assertEqual(body["linked_calendar_labels"], ["a", "b"])
        self.assertEqual(body["time_presets"][0]["id"], "custom-lunch")

    def test_friend_request_can_be_sent_and_accepted_by_email(self):
        friend_email = f"friend-{uuid.uuid4().hex}@example.com"
        sent = self.client.post("/api/friends", json={"recipient_email": friend_email})
        self.assertEqual(sent.status_code, 200)
        request_id = sent.json()["id"]
        self.assertEqual(sent.json()["status"], "pending")

        friend_client = TestClient(app)
        friend_client.post(
            "/auth/register",
            json={"email": friend_email, "password": self.password},
        )
        accepted = friend_client.post(f"/api/friends/{request_id}/accept")
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "accepted")

    def test_demo_matching_uses_submitted_busy_registries(self):
        response = self.client.post(
            "/api/demo/options",
            json={
                "time_min": "2026-06-15T09:00:00Z",
                "time_max": "2026-06-15T12:00:00Z",
                "duration_minutes": 30,
                "allowed_windows": [{"day": 0, "start": "09:00", "end": "12:00"}],
                "busy_a": [{"start": "2026-06-15T09:00:00Z", "end": "2026-06-15T10:00:00Z"}],
                "busy_b": [{"start": "2026-06-15T10:00:00Z", "end": "2026-06-15T10:30:00Z"}],
                "max_options": 3,
            },
        )
        self.assertEqual(response.status_code, 200)
        options = response.json()["options"]
        self.assertTrue(options)
        self.assertGreaterEqual(
            datetime.fromisoformat(options[0]["start"].replace("Z", "+00:00")),
            datetime.fromisoformat("2026-06-15T10:30:00+00:00"),
        )


if __name__ == "__main__":
    unittest.main()
