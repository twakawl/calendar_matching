# Feature: Storage Abstraction

## Goal

The backend must support local development with SQLite and production-style deployment on Azure with a managed SQL database without rewriting business logic.

## MVP scope

- Define repository or service interfaces for persistence.
- Provide a local SQLite implementation.
- Keep schema compatible with a future Azure SQL implementation where practical.
- Centralize database configuration through environment variables.
- Store all app-created calendar event IDs so the app can update or delete only its own events.

## Candidate entities

- Users.
- Calendar connections.
- Meeting requests.
- Request participants.
- Availability snapshots or matching runs.
- Proposed meeting options.
- Calendar event mappings for app-created holds and final events.
- Agreement decisions.
- Audit events for important state transitions.

## Current prototype status

- SQLite remains the concrete local store configured through `DATABASE_URL`.
- `users`, `user_sessions`, and `oauth_states` support the first authenticated slice.
- `google_accounts` now includes an `owner_user_id` and stores user-owned prototype slots internally while preserving the visible `a`/`b` labels.
- A small `SQLiteIdentityRepository` boundary centralizes user and session persistence for the authentication flow.
- Existing SQLite databases receive an additive `owner_user_id` column migration at startup.

Still deferred:

- Full repository interfaces for all domain entities.
- Versioned migration tooling beyond the lightweight additive SQLite migration.
- Meeting requests, participants, matching-run persistence, proposed options, calendar event mappings, agreement decisions, and audit events.

## User stories

- As a developer, I can run the app locally with SQLite.
- As an operator, I can deploy the app to Azure with a managed SQL database.
- As the app, I can track which calendar events I created so cleanup is safe.

## Acceptance criteria

- Business logic depends on storage interfaces instead of SQLite-specific code.
- Local configuration can create or migrate a SQLite database.
- Production configuration can point to Azure SQL or an equivalent managed SQL connection.
- Meeting option cleanup can identify external calendar events that belong to a specific request and user.

## Implementation notes

- Avoid database-specific SQL in domain services.
- Prefer migrations from the start, even for SQLite.
- Store timestamps in UTC.
- Encrypt or otherwise protect sensitive tokens before storing them.
