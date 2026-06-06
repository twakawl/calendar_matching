# Feature: Agenda View

## Goal

Users can see their own agenda inside the app, including regular calendar events, meeting requests, proposed options, and final planned meetings.

## MVP scope

- Display a user's own connected calendar events.
- Display meeting requests in the agenda timeline.
- Distinguish normal calendar events from app-created proposed options and final meetings.
- Show request details from agenda entries.
- Allow users to inspect proposed options visually before agreeing.

## User stories

- As a user, I can view my agenda in the app.
- As a user, I can see where meeting requests and proposed options fit in my schedule.
- As a user, I can open a request from the agenda view.
- As a user, I can identify which calendar entries were created by this app.

## Acceptance criteria

- The agenda view only shows the logged-in user's detailed calendar data.
- Request-related entries link back to the request details.
- App-created tentative options are visually distinct from final meetings.
- Calendar data is refreshed or clearly marked with its last sync time.
- Empty, loading, and calendar-disconnected states are handled.

## Open questions

- Whether the agenda view is day, week, or month first.
- Whether users can edit app-created meetings from the agenda view or only from request details.
- Whether external calendar events should be cached or fetched live for each view.
