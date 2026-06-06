# Feature: Meeting Requests

## Goal

A logged-in user can create a meeting request and invite another user through a secure link. The invited user logs in, connects their calendar, and participates in finding a meeting time.

## MVP scope

- Create a request with:
  - title,
  - description or notes,
  - duration,
  - allowed weekdays,
  - allowed time windows,
  - date range,
  - invited user's email address or share target.
- Generate a secure link token.
- Let the invited user accept or decline participation.
- Track request status.

## Suggested request statuses

- Draft.
- Sent.
- Opened.
- Awaiting calendar connection.
- Ready to match.
- Options proposed.
- Options sent to calendars.
- Agreed.
- Disagreed.
- Cancelled.
- Expired.

## User stories

- As a requesting user, I can define when a meeting may happen.
- As a requesting user, I can send a link to another user.
- As an invited user, I can open the link and log in to continue.
- As an invited user, I can accept or decline the request.
- As both users, we can see the current request status.

## Acceptance criteria

- Request links are hard to guess and can expire.
- Only the requester and invitee can view the request after authentication.
- The request captures enough constraints for the matching engine.
- A request cannot be matched until both required calendar connections are available.
- The app records important lifecycle changes for debugging and auditability.

## Data needs

- Meeting request record.
- Participant records for requester and invitee.
- Secure link token hash and expiration.
- Request constraints.
- Request lifecycle history.
