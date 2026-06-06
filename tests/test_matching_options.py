"""Unit tests for the MVP availability matching engine."""

import unittest

from matching import BusyPeriodInput, TimeWindowInput, find_matching_options


class MatchingOptionsTest(unittest.TestCase):
    def test_returns_best_three_non_overlapping_options(self):
        response = find_matching_options(
            time_min="2026-06-08T09:00:00Z",
            time_max="2026-06-08T13:00:00Z",
            duration_minutes=30,
            busy_periods=[
                BusyPeriodInput(
                    start="2026-06-08T09:30:00Z",
                    end="2026-06-08T10:00:00Z",
                ),
                BusyPeriodInput(
                    start="2026-06-08T11:00:00Z",
                    end="2026-06-08T11:30:00Z",
                ),
            ],
            allowed_windows=[TimeWindowInput(day=0, start="09:00", end="13:00")],
        )

        self.assertEqual(response.duration_minutes, 30)
        self.assertEqual(response.slot_granularity_minutes, 15)
        self.assertEqual(
            [(option.start, option.end) for option in response.options],
            [
                ("2026-06-08T09:00:00Z", "2026-06-08T09:30:00Z"),
                ("2026-06-08T10:00:00Z", "2026-06-08T10:30:00Z"),
                ("2026-06-08T10:30:00Z", "2026-06-08T11:00:00Z"),
            ],
        )

    def test_respects_duration_and_allowed_windows(self):
        response = find_matching_options(
            time_min="2026-06-08T08:00:00Z",
            time_max="2026-06-08T12:00:00Z",
            duration_minutes=60,
            busy_periods=[],
            allowed_windows=[TimeWindowInput(day=0, start="09:30", end="11:00")],
        )

        self.assertEqual(len(response.options), 1)
        self.assertEqual(response.options[0].start, "2026-06-08T09:30:00Z")
        self.assertEqual(response.options[0].end, "2026-06-08T10:30:00Z")

    def test_validates_date_range(self):
        with self.assertRaisesRegex(ValueError, "time_max must be after time_min"):
            find_matching_options(
                time_min="2026-06-08T12:00:00Z",
                time_max="2026-06-08T09:00:00Z",
                duration_minutes=30,
                busy_periods=[],
            )


if __name__ == "__main__":
    unittest.main()
