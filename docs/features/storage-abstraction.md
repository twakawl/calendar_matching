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
