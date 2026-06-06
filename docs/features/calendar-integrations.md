# Feature: Calendar Integrations

## Goal

Users connect external calendars so the app can read availability and write meeting options. Google Calendar is the first supported provider; Microsoft Calendar is a future release.

## MVP scope

- Google OAuth consent flow.
- Store refresh/access token metadata securely.
- Read calendar events for a relevant date range.
- Detect busy/free windows.
- Write proposed meeting option holds to calendars after user action.
- Delete app-created option holds that are no longer needed.
- Track provider event IDs in app storage.

## Future scope

- Microsoft Calendar support through the same provider interface.
- Matching between users on different calendar providers.
- Provider-specific resiliency for rate limits and revoked consent.

## User stories

- As a user, I can connect Google Calendar so the app can inspect my availability.
- As a user, I can disconnect a calendar connection.
- As a user, I can permit the app to add proposed meeting options to my calendar.
- As the app, I can delete only calendar events that I created.

## Acceptance criteria

- A user can connect exactly one primary Google Calendar connection for the MVP, unless multi-calendar support is explicitly added.
- The app can fetch busy blocks for a meeting request date range.
- Calendar details from another participant are not exposed to the request viewer.
- App-created events include enough metadata or stored mappings for later cleanup.
- Revoked or expired calendar authorization is handled with a clear reconnect path.

## Provider interface responsibilities

- Start authorization.
- Complete authorization callback.
- Refresh tokens.
- List busy intervals.
- Create tentative option events.
- Convert an option event to a final event if supported, or replace it safely.
- Delete app-created option events.
