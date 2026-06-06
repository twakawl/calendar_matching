# Calendar Matching

Calendar Matching is an early-stage FastAPI prototype for comparing two Google Calendars. It authenticates two Google accounts with OAuth 2.0, stores encrypted refresh tokens in SQLite, reads only Google Calendar free/busy data, and shows overlapping availability in a simple browser UI.

The longer-term product direction is documented separately: authenticated users should eventually connect calendars, send meeting requests, and receive the best meeting options based on both users' availability and request preferences.

## Current repository status

This repository currently contains both planning documentation and a runnable prototype:

- `app.py` — single-file FastAPI backend, OAuth callback handling, SQLite persistence, encrypted token storage, Google Calendar free/busy calls, and API endpoints.
- `static/html/home.html`, `static/css/style.css`, and `static/js/app.js` — lightweight frontend for authenticating two accounts, choosing availability preferences, and viewing suggested free slots.
- `pyproject.toml` — Python package metadata and dependency list for `uv`.
- `.env.example` — environment-variable template for Google OAuth credentials, a Fernet key, and the optional database URL.
- `tests/test_verify_setup.py` — setup verification script for environment variables, imports, and local database readiness.
- `test.py` — manual helper script for printing local `google_accounts` rows.
- `DEBUGGING_GUIDE.md` — manual troubleshooting notes for the current prototype.
- `docs/` — product roadmap and feature specifications for future development.

The setup instructions that are needed for the current prototype are included below.

## Implemented features

- OAuth 2.0 Web Server Flow for Google Calendar.
- Offline access with refresh token storage.
- Fernet encryption for stored refresh tokens.
- SQLite-backed `google_accounts` table.
- Google Calendar free/busy reads for primary calendars only; event titles, descriptions, attendees, and locations are not fetched.
- Combined busy-block response for two connected accounts.
- Simple frontend with two authenticate buttons, account selectors, weekday/hour availability preferences, calendar visibility toggles, and suggested free slots.
- Automatic access-token refresh before Calendar API calls.

## Future implementation scope

The current app is still a prototype. Future work described in `docs/` includes:

- Login-protected first-party user accounts rather than only two local OAuth slots.
- Storage abstraction that can support local SQLite and Azure SQL-style deployments.
- Meeting request links between users.
- Matching that returns the best three options based on request constraints and both agendas.
- Calendar writes for proposed options, final agreement tracking, and cleanup of unchosen app-created events.
- Microsoft Calendar support.
- In-app agenda views with anonymized visibility into the other participant's busy blocks.

## Prerequisites

- Python 3.10 or newer.
- `uv` for dependency management.
- A Google Cloud project with OAuth consent configured.
- A Google OAuth 2.0 Web application client.

## Google Cloud setup summary

Create or select a Google Cloud project, enable the Google Calendar API, and configure an OAuth consent screen. Then create OAuth 2.0 credentials with application type `Web application`.

Add this authorized redirect URI to the OAuth client:

```text
http://127.0.0.1:8000/oauth/callback
```

The app requests these scopes:

```text
https://www.googleapis.com/auth/calendar.freebusy
openid
email
```

The Calendar scope is used only for free/busy reads. The OpenID/email scopes identify which Google account was connected.

## Environment variables

Copy the template and fill in your Google OAuth credentials plus a Fernet key:

```bash
cp .env.example .env
```

Required values:

```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
ENCRYPTION_KEY=your_fernet_key
DATABASE_URL=sqlite:///./calendar.db
```

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`DATABASE_URL` is optional. If omitted, the app uses `sqlite:///./calendar.db`.

## Install dependencies

Install all dependencies from `pyproject.toml`:

```bash
uv sync
```

If you are not using `uv`, install the same packages listed in `pyproject.toml` with your preferred Python package manager.

## Verify local setup

Run the setup verifier:

```bash
uv run python tests/test_verify_setup.py
```

Expected successful summary:

```text
Environment............................. ✅ OK
Dependencies............................ ✅ OK
Database................................ ✅ OK
```

The environment check fails until `.env` exists and contains valid-looking values. The script does not contact Google.

## Run the app

Start the FastAPI application:

```bash
uv run python app.py
```

Then open:

```text
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/redoc
```

## Basic usage

1. Open `http://127.0.0.1:8000`.
2. Click **Authenticate user A** and complete the Google OAuth consent flow.
3. Click **Authenticate user B** and complete the flow for a second account.
4. Select weekday/hour availability preferences.
5. Click **Find matching times** to fetch both calendars' busy blocks and show suggested free slots.

Direct OAuth start URLs are also available:

```text
http://127.0.0.1:8000/oauth/start?account_label=a
http://127.0.0.1:8000/oauth/start?account_label=b
```

## API endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/health` | GET | JSON health check. |
| `/` | GET | Frontend home page. |
| `/oauth/start?account_label=a` | GET | Start Google OAuth for account slot `a` or `b`. |
| `/oauth/callback` | GET | OAuth callback used by Google. |
| `/freebusy/{account_label}` | GET | Free/busy response for one connected account. Requires `time_min` and `time_max`. |
| `/pair` | GET | Combined free/busy response for both connected accounts. Requires `time_min` and `time_max`. |
| `/accounts` | GET | Stored account metadata, without tokens. |
| `/accounts/select` | POST | Prototype endpoint for marking an account selected in the UI. |

Example one-account request:

```bash
curl "http://127.0.0.1:8000/freebusy/a?time_min=2026-02-28T00:00:00Z&time_max=2026-03-10T00:00:00Z"
```

Example paired request:

```bash
curl "http://127.0.0.1:8000/pair?time_min=2026-02-28T00:00:00Z&time_max=2026-03-10T00:00:00Z"
```

## Database schema

The prototype creates a local SQLite database by default. The `google_accounts` table contains:

| Column | Purpose |
| --- | --- |
| `account_label` | Primary key, currently `a` or `b`. |
| `google_sub` | Unique Google account identifier. |
| `email` | Connected Google account email address. |
| `refresh_token` | Encrypted refresh token. |
| `cached_busy` | JSON cache of recently fetched busy periods. |
| `created_at` | Storage timestamp. |
| `selected_as` | Prototype selection marker. |

Local database files such as `calendar.db` are ignored by Git.

## Security notes

- Refresh tokens are encrypted with Fernet before storage.
- Secrets are loaded from environment variables and should not be committed.
- The Google Calendar scope is limited to `calendar.freebusy`.
- The API returns busy time ranges only, not event details.
- This is a local prototype and does not yet include production-grade user login, CSRF/session hardening, secret rotation, or multi-user tenancy controls.

## Troubleshooting

### `GOOGLE_CLIENT_ID environment variable not set`

Create `.env` from `.env.example` and fill in `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `ENCRYPTION_KEY`.

### `Invalid ENCRYPTION_KEY format`

Generate a new Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### `Refresh token not received`

Google may not return a refresh token if the account has already approved the app. Revoke the app grant in the Google Account security settings, then authenticate again. Make sure the authorization request uses offline access and prompt consent; `app.py` is configured to request both.

### `Database is locked`

Stop duplicate local app processes, then start one instance again:

```bash
uv run python app.py
```

### `UNIQUE constraint failed on google_sub`

This usually means an old local database row conflicts with a newly connected Google account. For local development, stop the app and remove `calendar.db`, then authenticate both accounts again.

## Repository structure

```text
calendar_matching/
├── .env.example
├── .gitignore
├── AGENTS.md
├── DEBUGGING_GUIDE.md
├── README.md
├── app.py
├── docs/
│   ├── product-overview.md
│   ├── roadmap.md
│   └── features/
├── pyproject.toml
├── static/
│   ├── css/style.css
│   ├── html/home.html
│   └── js/app.js
├── test.py
└── tests/
    ├── __init__.py
    └── test_verify_setup.py
```

## Development notes

- Keep business logic independent from concrete persistence implementations as the app evolves.
- Keep calendar-provider logic behind interfaces when adding Microsoft Calendar support.
- Update this README and the relevant `docs/features/*.md` file when changing product behavior.
- Add automated tests when adding application behavior; the current test file is a setup verifier, not a full test suite.
