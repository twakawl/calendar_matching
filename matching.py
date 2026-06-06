"""Pure availability matching service for meeting option suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Protocol, Sequence


@dataclass(frozen=True)
class BusyPeriodInput:
    """A UTC busy period that blocks candidate meeting slots."""

    start: str
    end: str


@dataclass(frozen=True)
class TimeWindowInput:
    """Allowed weekday and time range for candidate meeting slots."""

    day: int
    start: str
    end: str


@dataclass(frozen=True)
class MeetingOptionResult:
    """A ranked candidate meeting option."""

    start: str
    end: str
    score: int
    reason: str


@dataclass(frozen=True)
class MatchingOptionsResult:
    """The result returned by the matching service."""

    duration_minutes: int
    slot_granularity_minutes: int
    options: list[MeetingOptionResult] = field(default_factory=list)


class BusyLike(Protocol):
    start: str
    end: str


class WindowLike(Protocol):
    day: int
    start: str
    end: str


def parse_utc_datetime(value: str) -> datetime:
    """Parse an ISO-8601 datetime and normalize it to UTC."""
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_utc_datetime(value: datetime) -> str:
    """Format a UTC datetime as an RFC 3339 string with a Z suffix."""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_time(value: str) -> time:
    """Parse HH:MM time window input."""
    return datetime.strptime(value, "%H:%M").time()


def overlaps_busy(start: datetime, end: datetime, busy_periods: Sequence[BusyLike]) -> bool:
    """Return True when a candidate slot overlaps any busy period."""
    for period in busy_periods:
        busy_start = parse_utc_datetime(period.start)
        busy_end = parse_utc_datetime(period.end)
        if start < busy_end and end > busy_start:
            return True
    return False


def within_allowed_windows(
    start: datetime, end: datetime, windows: Sequence[WindowLike]
) -> bool:
    """Return True when the slot fits one allowed weekday/time window."""
    if not windows:
        return True

    weekday = start.weekday()
    slot_start = start.time().replace(second=0, microsecond=0)
    slot_end = end.time().replace(second=0, microsecond=0)

    return any(
        window.day == weekday
        and slot_start >= parse_time(window.start)
        and slot_end <= parse_time(window.end)
        for window in windows
    )


def score_candidate(start: datetime, range_start: datetime) -> int:
    """Score candidates with a deterministic MVP preference for earlier slots."""
    minutes_from_start = int((start - range_start).total_seconds() // 60)
    return max(0, 100_000 - minutes_from_start)


def find_matching_options(
    *,
    time_min: str,
    time_max: str,
    duration_minutes: int,
    busy_periods: Sequence[BusyLike],
    allowed_windows: Sequence[WindowLike] | None = None,
    max_options: int = 3,
    slot_granularity_minutes: int = 15,
) -> MatchingOptionsResult:
    """Find the best non-overlapping meeting options for two calendars."""
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    if max_options <= 0:
        raise ValueError("max_options must be positive")

    range_start = parse_utc_datetime(time_min)
    range_end = parse_utc_datetime(time_max)
    if range_end <= range_start:
        raise ValueError("time_max must be after time_min")

    duration = timedelta(minutes=duration_minutes)
    granularity = timedelta(minutes=slot_granularity_minutes)
    windows = allowed_windows or []
    options: list[MeetingOptionResult] = []
    cursor = range_start

    while cursor + duration <= range_end and len(options) < max_options:
        candidate_end = cursor + duration
        if within_allowed_windows(cursor, candidate_end, windows) and not overlaps_busy(
            cursor, candidate_end, busy_periods
        ):
            options.append(
                MeetingOptionResult(
                    start=format_utc_datetime(cursor),
                    end=format_utc_datetime(candidate_end),
                    score=score_candidate(cursor, range_start),
                    reason="earliest available slot matching the request constraints",
                )
            )
            cursor = candidate_end
        else:
            cursor += granularity

    return MatchingOptionsResult(
        duration_minutes=duration_minutes,
        slot_granularity_minutes=slot_granularity_minutes,
        options=options,
    )
