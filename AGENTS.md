# Repository Guide for Agents

## Repository Overview

This repository is named `calendar_matching`. The project is planned as a simple calendar-matching app where authenticated users connect calendars, send meeting requests, and receive the best meeting options based on both users' availability and request preferences.

The original Dutch README description was: "App om 2 kalenders met elkaar te vergelijken en uit te testen." The current planning expands that into a login-based application with Google Calendar support first, Microsoft Calendar later, and flexible storage for local SQLite and Azure SQL-style deployments.

## Current Contents

The repository is currently documentation-first:

- `README.md` — product summary and documentation index.
- `.gitignore` — Python-focused ignore rules for bytecode, virtual environments, build outputs, test caches, coverage reports, local environment files, and common editor/tool caches.
- `docs/product-overview.md` — high-level product vision and user journey.
- `docs/roadmap.md` — phased implementation roadmap.
- `docs/features/*.md` — feature specifications for authentication, storage, calendar integrations, meeting requests, matching, agreement, agenda viewing, and privacy.
- `AGENTS.md` — this guide.

No application source files, dependency manifests, database migrations, or automated tests are present yet.

## Product Direction

Build toward these major capabilities:

1. Login-protected user accounts.
2. Backend persistence abstracted so local SQLite and Azure managed SQL can both be supported.
3. Google Calendar connection in the MVP.
4. Microsoft Calendar support in a future release.
5. Meeting request links between users.
6. Matching that returns the best three options based on request constraints and both agendas.
7. Calendar writes for proposed options, final agreement tracking, and cleanup of unchosen app-created events.
8. In-app agenda views with anonymized visibility into the other participant's busy blocks.

## Development Notes

- Treat this as an early-stage Python-oriented project unless future files indicate otherwise.
- Keep generated artifacts, virtual environments, local environment files, caches, build outputs, and coverage output out of version control, following `.gitignore`.
- Read `docs/product-overview.md` and the relevant `docs/features/*.md` file before implementing a feature.
- If adding Python code, prefer a clear project structure and include dependency, formatting, linting, migration, and test configuration files.
- Keep business logic independent from concrete persistence implementations so SQLite and Azure SQL support remain practical.
- Keep calendar-provider logic behind interfaces so Google and Microsoft providers can share app workflows.
- Update `README.md` and relevant feature docs when adding runnable functionality or changing product behavior.

## Testing

There is currently no automated test command configured. When adding behavior, also add tests and document the test command in `README.md`.
