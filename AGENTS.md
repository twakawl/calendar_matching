# Repository Guide for Agents

## Repository Overview

This repository is named `calendar_matching`. The project is planned as a calendar-matching app where authenticated users connect calendars, send meeting requests, and receive the best meeting options based on both users' availability and request preferences.

The original Dutch README description was: "App om 2 kalenders met elkaar te vergelijken en uit te testen." The current planning expands that into a login-based application with Google Calendar support first, Microsoft Calendar later, and flexible storage for local SQLite and Azure SQL-style deployments.

## Current Contents

The repository currently contains planning documentation plus a runnable FastAPI prototype:

- `README.md` — current prototype setup, usage, API summary, and documentation index.
- `.gitignore` — Python-focused ignore rules for bytecode, virtual environments, build outputs, test caches, coverage reports, local environment files, local database files, and common editor/tool caches.
- `.env.example` — local environment template for Google OAuth credentials, Fernet encryption key, and optional database URL.
- `app.py` — single-file FastAPI prototype with Google OAuth flow, encrypted token storage, SQLite persistence, Google Calendar free/busy reads, and account/free-busy endpoints.
- `pyproject.toml` — Python metadata and dependencies for the prototype.
- `static/` — simple HTML/CSS/JavaScript frontend for profile-owned calendar connections, request creation, and shared free-slot matching.
- `tests/test_verify_setup.py` — setup verification script for environment variables, dependencies, and database readiness.
- `DEBUGGING_GUIDE.md` — manual debugging notes for OAuth, free/busy calls, and frontend behavior.
- `planning.md` — current development plan, repository assessment, feature priority, recommended milestones, and implementation guardrails. Check this file before starting feature work to understand the next recommended task and current product state.
- `docs/product-overview.md` — high-level product vision and user journey.
- `docs/roadmap.md` — phased implementation roadmap.
- `docs/features/*.md` — feature specifications for authentication, storage, calendar integrations, meeting requests, matching, agreement, agenda viewing, and privacy.

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

- Treat this as an early-stage Python-oriented project.
- Keep generated artifacts, virtual environments, local environment files, caches, build outputs, coverage output, and local SQLite databases out of version control, following `.gitignore`.
- Read `planning.md` first when implementing a feature; it records the current feature set, build priority, milestones, next recommended task, and guardrails. Then read `docs/product-overview.md` and the relevant `docs/features/*.md` file before changing behavior.
- If adding Python code, prefer a clear project structure and include dependency, formatting, linting, migration, and test configuration files.
- Keep business logic independent from concrete persistence implementations so SQLite and Azure SQL support remain practical.
- Keep calendar-provider logic behind interfaces so Google and Microsoft providers can share app workflows.
- Always update `README.md`, relevant feature docs, and any other affected `.md` documentation on every update, even for small UI or behavior changes.
- Always write user-facing instructions in human-centered language. Avoid implementation jargon such as prototype, SQLite, JSON, debug data, or not-implemented labels unless the text is for developer-only documentation.

## Testing

The currently documented setup check is:

```bash
uv run python tests/test_verify_setup.py
```

When adding behavior, add automated tests and document the test command in `README.md`.
