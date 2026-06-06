# Feature: Availability Matching

## Goal

The app finds the best three meeting moments using the meeting request preferences and both users' calendar availability.

## Inputs

- Request duration.
- Allowed date range.
- Allowed weekdays.
- Allowed hours or time windows.
- Requester calendar busy blocks.
- Invitee calendar busy blocks.
- Optional scoring preferences, such as earlier dates or preferred times of day.

## MVP algorithm outline

1. Build candidate time slots from the request date range, weekdays, allowed hours, and duration.
2. Normalize all times to UTC internally while preserving each user's display timezone.
3. Remove slots that overlap either user's busy blocks.
4. Score remaining slots according to preference rules.
5. Return the best three non-overlapping options.
6. Store the matching run and selected options for traceability.

## User stories

- As a requester, I receive three good meeting options when both calendars have availability.
- As an invitee, I know the proposed options respect my linked agenda.
- As both users, we can see when no matching slots are available.

## Acceptance criteria

- The matching engine respects the requested weekdays and hours.
- Busy events from both calendars block candidate slots.
- The engine returns at most three options.
- If fewer than three slots are available, the app clearly shows the available count.
- If no slots are available, the app explains that no match was found and allows the requester to adjust constraints.
- Matching behavior is covered by unit tests once code exists.

## Open questions

- Slot granularity: 5, 10, 15, or 30 minutes.
- Whether travel or buffer time should be supported.
- Whether requester preferences should rank earlier dates, morning/afternoon, or balanced distribution.
- Whether all-day events should block the whole day by default.
