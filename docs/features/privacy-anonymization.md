# Feature: Privacy and Anonymization

## Goal

Users need enough visibility to understand why options are suggested, but they must not see private details from another user's calendar.

## MVP scope

- Show the logged-in user's own calendar event details.
- Show the other participant's unavailable periods as anonymized busy blocks.
- Hide titles, descriptions, locations, attendees, and calendar names from the other participant's events.
- Limit request access to authenticated participants.
- Store only the calendar data needed for matching and request display.

## User stories

- As a requester, I can inspect the request timeline without seeing the invitee's private meeting details.
- As an invitee, I can trust that my calendar details are not exposed to the requester.
- As both users, we can understand that unavailable periods affected the matching result.

## Acceptance criteria

- Another participant's calendar events are displayed only as busy/free information.
- Event metadata from another participant is never rendered in request views.
- Logs do not include sensitive calendar event titles or descriptions.
- Stored tokens and sensitive identifiers are protected.
- The app can delete app-created calendar events without needing to expose private event data.

## Privacy notes

- Prefer storing busy intervals over full external event payloads when possible.
- If full event payloads are temporarily needed for provider logic, avoid persisting them unless there is a clear product reason.
- Apply least-privilege calendar scopes wherever provider APIs allow it.
- Explain calendar permissions clearly during connection.
