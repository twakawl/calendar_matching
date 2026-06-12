# Development Plan

## Purpose

This plan translates the documented product direction into a recommended build order for the Calendar Matching app. The goal is to reach a small, reliable MVP before expanding into calendar writes, advanced agenda views, Azure hardening, or Microsoft Calendar support.

## Current repository assessment

The repository now contains a runnable FastAPI prototype alongside the product planning docs. The prototype can connect multiple Google accounts from Profile, store encrypted refresh tokens in SQLite, read Google Calendar free/busy data, merge busy blocks, and display availability in a browser UI.

The first implemented product slice beyond raw free/busy comparison is an MVP matching endpoint and UI path that accepts duration plus weekday/hour windows, combines both connected calendars, and returns the top three non-overlapping options with deterministic earliest-slot scoring.

## Where we are after the first feature set

- **Done:** runnable FastAPI app, first-party registration/login/session foundation, Google OAuth connection for multiple profile-owned calendar accounts, encrypted refresh-token storage, SQLite persistence, free/busy reads, merged busy blocks, health endpoint, static UI, Fly.io deployment notes, and setup/deployment checks.
- **Done in this slice:** backend matching service and `/matching/options` endpoint that returns up to three candidate meeting options for the two connected calendars using duration, weekday, and allowed-hour constraints.
- **Partially done:** the frontend can collect duration and weekday/hour preferences and display the three options, and calendar selection has moved to Profile and request creation selects one connected profile account.
- **Done in latest slice:** SQLite-backed meeting request records, hashed expiring invite links, public invite preview, invitee accept/decline actions, request visibility checks, and request lifecycle audit events for the MVP invite flow.
- **Not started:** persistent proposed options, calendar writes, final agreement tracking, advanced anonymized participant agenda views, Azure SQL implementation, and Microsoft Calendar.
- **Next recommended task:** continue Phase 4 by storing matching runs/proposed options against meeting requests, then build request detail and privacy-preserving agenda views from Phase 5. Longer-term foundation cleanup should still extract the single-file prototype into a clearer package structure with repository interfaces and migrations.

## Feature priority

### 0. Align repository documentation and actual state — done

The repository and README agree that this is a runnable FastAPI prototype with planning docs. Current source includes the single-file backend, static frontend, setup verification script, Docker/Fly.io deployment files, and feature documentation.

Remaining follow-up:

- Keep README API examples synchronized as the prototype gains endpoints.
- Continue replacing same-user prototype comparison with true requester/invitee participant calendar selection before exposing private data beyond local development.

### 1. Build the application foundation

Start with the smallest durable backend foundation. This should include the app skeleton, configuration, persistence boundaries, initial database schema, migrations, and authentication.

Primary specs:

- `docs/features/authentication.md`
- `docs/features/storage-abstraction.md`
- `docs/product-overview.md`
- `docs/roadmap.md`

Actions:

- Choose and document the first implementation stack, preferably Python/FastAPI unless a new decision is made.
- Create a clear Python package structure.
- Add configuration loading for local development and future deployment.
- Define domain models for users, calendar connections, meeting requests, participants, matching runs, proposed options, calendar event mappings, agreement decisions, and audit events.
- Define repository or service interfaces so business logic does not depend on SQLite-specific code.
- Add a local SQLite implementation.
- Add migrations from the start.
- Implement user registration/login/logout or the chosen external identity-provider flow.
- Add authorization checks for agenda and meeting request access.

Why now:

- Authentication and storage are prerequisites for every private calendar, request, matching, and agreement workflow.
- Provider and matching code will be easier to test if it is not coupled directly to a temporary database implementation.

### 2. Implement Google Calendar read-only availability

After users and storage exist, connect Google Calendar as the first calendar provider. Keep provider behavior behind an interface so Microsoft Calendar can be added later.

Primary specs:

- `docs/features/calendar-integrations.md`
- `docs/features/privacy-anonymization.md`

Actions:

- Define a calendar-provider interface with responsibilities for authorization, callback completion, token refresh, busy interval reads, event creation, event finalization or replacement, and event deletion.
- Implement the Google OAuth connection flow.
- Store refresh-token metadata securely, with encryption or equivalent protection.
- Fetch busy intervals for a relevant date range.
- Normalize busy intervals to UTC internally.
- Add disconnect and reconnect behavior.
- Handle revoked or expired authorization with a clear reconnect path.
- Ensure logs and responses do not expose another participant's calendar event details.

Why now:

- Read-only availability is lower risk than calendar writes.
- It provides the real availability input needed by meeting requests and matching.

### 3. Implement meeting request creation and invite links

The meeting request is the core product object. Build it once users can connect calendars.

Primary spec:

- `docs/features/meeting-requests.md`

Actions:

- Add meeting request creation with title, notes, duration, date range, allowed weekdays, allowed time windows, and invited user email or share target.
- Generate secure, hard-to-guess invite links.
- Store only a token hash and expiration time for invite links.
- Let invited users open links, authenticate, and accept or decline participation.
- Track request statuses such as draft, sent, opened, awaiting calendar connection, ready to match, options proposed, agreed, disagreed, cancelled, and expired.
- Add request lifecycle audit events.
- Enforce that only the requester and invitee can view the request after authentication.

Why now:

- Matching needs request constraints and participant state.
- Secure invite links are central to the user journey.

### 4. Build the availability matching engine

Implement matching as a pure, testable service. Inputs should be request constraints and busy intervals; outputs should be ranked proposed options.

Primary spec:

- `docs/features/availability-matching.md`

Recommended MVP decisions:

- Use 15-minute slot granularity unless product testing suggests otherwise.
- Normalize matching calculations to UTC.
- Preserve user timezones for display.
- Treat all-day busy events as blocking the full day by default.
- Use simple scoring first, such as earliest acceptable options.

Actions:

- Generate candidate slots from date range, allowed weekdays, allowed time windows, and duration.
- Remove slots that overlap either participant's busy intervals.
- Score remaining slots with simple MVP rules.
- Return at most three non-overlapping options.
- Clearly handle fewer-than-three and no-match outcomes.
- Store matching runs and selected proposed options for traceability.
- Add unit tests for weekdays, time windows, busy-overlap removal, fewer-than-three results, no-result behavior, all-day blocks, and timezone boundaries.

Why now:

- This is the app's core value proposition.
- A pure matching engine can be tested without live calendar APIs.

### 5. Add request detail and privacy-preserving agenda views

Users need to review proposed options and understand availability constraints without seeing private details from another participant's calendar.

Primary specs:

- `docs/features/privacy-anonymization.md`
- `docs/features/agenda-view.md`

Actions:

- Create a request detail view showing constraints, participant readiness, status, and proposed options.
- Show the logged-in user's own calendar event details where needed.
- Show the other participant only as anonymized busy blocks.
- Hide titles, descriptions, locations, attendees, and calendar names from the other participant's events.
- Visually distinguish normal calendar events, app-created proposed options, and final meetings.
- Handle empty, loading, disconnected, and last-refreshed states.

Why now:

- Users should be able to evaluate matching results before the app writes anything to calendars.
- This reinforces the privacy model before adding higher-risk write operations.

### 6. Add calendar writes, agreement, and cleanup

Only add writes after read-only availability, requests, matching, and review are stable. Calendar writes need careful tracking so the app deletes only events it created.

Primary specs:

- `docs/features/meeting-options-agreement.md`
- write-related scope in `docs/features/calendar-integrations.md`

Actions:

- Add a deliberate user action to write proposed option holds to both users' calendars.
- Track provider event IDs per request, participant, and proposed option.
- Let participants agree, disagree, or choose a final option according to defined product rules.
- Keep or create the final agreed calendar event.
- Delete unchosen app-created option events from both calendars.
- Preserve tracking data if a provider write or delete fails.
- Expose recoverable states for partial cleanup failures.

Why later:

- Calendar writes can affect real user calendars.
- Safe cleanup depends on storage, provider interfaces, request state, and option tracking already being correct.

### 7. Harden the MVP and prepare for deployment

After the core Google-based MVP works, improve reliability, test coverage, and deployment readiness.

Primary specs:

- `docs/roadmap.md`
- `docs/features/storage-abstraction.md`
- `docs/features/agenda-view.md`

Actions:

- Add automated tests for matching, authorization boundaries, request lifecycle transitions, provider abstractions, and calendar cleanup.
- Add error handling for revoked permissions, stale data, expired links, and provider failures.
- Add audit history for important state transitions.
- Add CI for formatting, linting, migrations, and tests.
- Document local SQLite setup and production-style SQL configuration.
- Prepare configuration patterns for Azure deployment.

Why now:

- The app should be stable and observable before expanding provider support.

### 8. Defer Microsoft Calendar until the Google MVP is proven

Microsoft Calendar should be a future release after the provider interface has supported the full Google lifecycle.

Actions:

- Implement Microsoft authorization and callbacks behind the same provider interface.
- Map Microsoft busy reads to the common busy-interval model.
- Map Microsoft event writes and deletes to the common event lifecycle model.
- Add cross-provider tests for Google-to-Microsoft and Microsoft-to-Google participants.

Why last:

- Multi-provider support is valuable, but it should not delay proving the product workflow.
- A stable provider interface will reduce rework.

## Recommended milestones

### Milestone A: Repository alignment and foundation

Deliverables:

- Accurate README and setup documentation.
- App skeleton.
- Configuration loading.
- Domain models.
- Storage interfaces.
- SQLite implementation.
- Migration setup.

### Milestone B: Authenticated local app

Deliverables:

- User registration or chosen login flow.
- Login and logout.
- Session management.
- Authorization checks.
- Basic user profile records.

### Milestone C: Google read-only availability

Deliverables:

- Google OAuth connection.
- Secure token storage.
- Token refresh.
- Busy interval fetches.
- Disconnect and reconnect flows.
- Privacy-safe availability responses.

### Milestone D: Meeting request MVP

Deliverables:

- Request creation.
- Secure expiring invite links.
- Invitee login and participation flow.
- Request status tracking.
- Lifecycle audit events.

### Milestone E: Matching MVP

Deliverables:

- Pure matching service.
- Best-three option generation.
- No-match handling.
- Persisted matching runs.
- Unit tests.

### Milestone F: Review UI

Deliverables:

- Request detail view.
- Proposed options display.
- Own event details.
- Other-user anonymized busy blocks.
- Disconnected, loading, empty, and last-refreshed states.

### Milestone G: Calendar writes and agreement

Deliverables:

- Send proposed options to calendars.
- Store external event mappings.
- Participant agreement flow.
- Final option selection.
- Cleanup of unchosen app-created events.
- Recoverable partial-failure states.

### Milestone H: Hardening and Azure readiness

Deliverables:

- Broader automated test coverage.
- CI checks.
- Audit improvements.
- Robust provider error handling.
- Local SQLite and Azure SQL-style configuration documentation.

## Implementation guardrails

- Keep business logic independent from concrete persistence implementations.
- Keep calendar-provider logic behind interfaces.
- Store timestamps in UTC.
- Preserve display timezone information separately from matching calculations.
- Store only the calendar data needed for matching and request display.
- Never render another participant's event titles, descriptions, locations, attendees, or calendar names.
- Encrypt or otherwise protect calendar tokens.
- Track every app-created calendar event before attempting cleanup.
- Do not write proposed options to calendars until a user intentionally triggers that action.
- Add tests with every behavior-producing feature.

## Planned and executed feature slice: login, profile, requests, friends, and demo

This slice was planned in `docs/features/profile-friends-demo.md` before implementation and then executed in the prototype. It adds a separated `/register` page, provider-login placeholders on `/login`, editable personal profiles, ordered standard/custom time presets, multi-invitee request inputs, friend-list request/accept flows, disabled contact-import placeholders, and a public demo request that reuses the matching engine against two demo calendar registries.

Next recommended task after this slice: normalize multi-participant requests into first-class participant rows and add per-participant calendar-readiness state before matching real multi-person requests.
