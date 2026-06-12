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
  - one or more invited user email addresses or friend-list targets,
  - one selected linked requester calendar for availability checks.
- an optional ordered profile time preset.
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
- As a requesting user, I can send a link to one or more users.
- As a requesting user, I can add accepted friends or email invitees to a request.
- As an invited user, I can open the link and log in to continue.
- As an invited user, I can accept or decline the request.
- As an invited user, I can select an already linked calendar or connect Google Calendar while staying in the received request flow.
- As both users, we can see the current request status.

## Acceptance criteria

- Request links are hard to guess and can expire.
- Only the requester and invitee can view the request after authentication.
- The request captures enough constraints for the matching engine.
- A request cannot be matched until the requester has selected one linked calendar and the invitee has selected or connected one linked calendar.
- The app records important lifecycle changes for debugging and auditability.

## Data needs

- Meeting request record.
- Participant records for requester and invitees.
- Secure link token hash and expiration.
- Request constraints.
- Request lifecycle history.

## Current prototype slice

- The FastAPI prototype now persists requester-owned request records in local SQLite through `/api/requests`.
- New requests generate hard-to-guess invite tokens, store only token hashes plus expirations, and return the raw invite URL only at creation/regeneration time.
- The authenticated `/requests/new` page can save a request with title, multiple invitee emails, accepted friend selections, one selected linked requester calendar, duration, date range, selected weekdays, one time window, timezone, ordered time-preset choice, and notes.
- The authenticated `/dashboard` page loads requests visible to the requester or accepted invitee from SQLite and can regenerate invite links.
- The public `/invite/{token}` page resolves only non-sensitive request details, then lets the matching logged-in invitee accept or decline and choose an existing linked calendar or start Google OAuth for the same request.
- Request access checks now allow only the requester, invitee email, or accepted invitee user to fetch request details after authentication.
- Request lifecycle audit events are recorded for creation, invite generation, opening, acceptance, decline, calendar selection, and request-scoped calendar connection.
- Remaining future work: normalized participant rows, participant-specific calendar readiness for every invitee, secure email delivery, richer lifecycle transitions, and persistent proposed options.

## Current UX additions for request creation

- The request creation page uses a step-based card so basics, participants, dates, and rules are easier to scan.
- The three highest-priority time presets are exposed as quick buttons, while every ordered profile preset remains available in a dropdown.
- The primary action is visually emphasized as **Find best options**; saving the SQLite draft remains available as a secondary action.
- Multiple typed invitee emails and accepted friend selections are combined into the request payload.
- Top-three option cards appear before the detailed availability grid so users first see the product's main recommendation.
