# Calendar Matching

Calendar Matching is an early-stage FastAPI prototype for comparing two Google Calendars. It authenticates two Google accounts with OAuth 2.0, stores encrypted refresh tokens in SQLite, reads only Google Calendar free/busy data, and shows overlapping availability in a simple browser UI.

The longer-term product direction is documented separately: authenticated users should eventually connect calendars, send meeting requests, and receive the best meeting options based on both users' availability and request preferences.

## Current repository status

This repository currently contains both planning documentation and a runnable prototype:

- `app.py` — single-file FastAPI backend, OAuth callback handling, SQLite persistence, encrypted token storage, Google Calendar free/busy calls, and API endpoints.
- `static/html/*.html`, `static/css/style.css`, and `static/js/app.js` — Bootstrap-based prototype frontend pages for the landing page, login/account calendar connections, dashboard, request creation, invite landing, request detail, and privacy-safe availability preview.
- `pyproject.toml` — Python package metadata and dependency list for `uv`.
- `Dockerfile`, `fly.toml`, `requirements.txt`, and `.python-version` — Fly.io deployment settings for the hosted FastAPI service.
- `.github/workflows/ci.yml` and `.github/workflows/deploy-fly.yml` — GitHub Actions CI and optional Fly.io CD workflows.
- `cloud_hosting/fly_io.md` — Fly.io account, deployment, environment, OAuth callback, and troubleshooting instructions.
- `.env.example` — environment-variable template for Google OAuth credentials, a Fernet key, database configuration, and hosted redirect settings.
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
- MVP matching endpoint that returns the top three non-overlapping meeting options from duration, weekday, allowed-hour, and busy-block constraints.
- Bootstrap-based multi-page frontend with product-shaped landing, account/calendar connection cards, dashboard placeholders, request creation wizard placeholders, invite and request-detail placeholders, responsive availability preview, and live top-three matching cards backed by the existing Google free/busy prototype.
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

Create or select a Google Cloud project, enable the Google Calendar API, and configure an OAuth consent screen. Then create OAuth 2.0 credentials with application type `Web application`. For this project, the Google app credentials can be edited in Google Cloud Console at <https://console.cloud.google.com/apis/credentials?project=calendar-matching>.

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

Required local values:

```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
ENCRYPTION_KEY=your_fernet_key
DATABASE_URL=sqlite:///./calendar.db
```

Hosted deployments can also set:

```env
PUBLIC_BASE_URL=https://your-fly-app.fly.dev
GOOGLE_REDIRECT_URI=https://your-fly-app.fly.dev/oauth/callback
PORT=8000

# Fly.io configuration (if deploying there)
FLY_APP_NAME=
FLY_REGION=
FLY_SECRET_KEY=
```

`GOOGLE_REDIRECT_URI` is read directly from the environment when set. If it is empty and `PUBLIC_BASE_URL` is set, the app derives `${PUBLIC_BASE_URL}/oauth/callback`; otherwise it falls back to `http://127.0.0.1:8000/oauth/callback`.

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`DATABASE_URL` is optional for local development. If omitted, the app uses `sqlite:///./calendar.db`; hosted deployments should point it at durable managed storage.

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

Run the deployment, matching, and prototype UI regression tests when changing application behavior:

```bash
uv run python -m unittest tests.test_matching_options tests.test_deployment_config tests.test_ui_routes
```

Expected successful summary:

```text
Environment............................. ✅ OK
Dependencies............................ ✅ OK
Database................................ ✅ OK
```

The environment check fails until `.env` exists and contains valid-looking values. The script does not contact Google.

## Run the app

Start the FastAPI application locally:

```bash
uv run python app.py
```

The hosted Docker command used by Fly.io is:

```bash
uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
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

1. Open `http://127.0.0.1:8000` for the landing page.
2. Open `/account` or `/login`, connect **Google Calendar · Slot A**, and complete the Google OAuth consent flow.
3. Connect **Google Calendar · Slot B** and complete the second OAuth flow.
4. Open `/requests/new`, fill or adjust the request placeholders for title, invitee, duration, date range, weekdays, and time window.
5. Click **Find best options** to retrieve both calendars, compute the top three options, and render the privacy-safe availability preview.

Direct OAuth start URLs are also available:

```text
http://127.0.0.1:8000/oauth/start?account_label=a
http://127.0.0.1:8000/oauth/start?account_label=b
```

## Prototype UI routes

The current frontend implements the first UI milestone from `docs/ui-design-plan.md` as static Bootstrap pages with placeholders where backend request persistence and participant workflows will be added later:

- `/` — landing page with privacy-first product explanation and primary actions.
- `/login` and `/account` — Google Calendar connection cards for prototype slots A and B, plus a Microsoft Calendar placeholder.
- `/dashboard` — grouped meeting request cards for needs-action, waiting, proposed, and agreed states.
- `/requests/new` — request creation wizard-style form with title, invitee, duration, date range, weekday chips, time window, live matching button, top-three option cards, and secondary availability preview.
- `/invite/demo-token` — invite landing page placeholder that explains the request and privacy behavior before connection.
- `/requests/demo-request` — request detail placeholder with participant readiness, option cards, and agreement-state placeholders.
- `/requests/demo-request/availability` — anonymized availability preview placeholder.

## API endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/health` | GET | JSON health check. |
| `/` | GET | Frontend home page. |
| `/oauth/start?account_label=a` | GET | Start Google OAuth for account slot `a` or `b`. |
| `/oauth/callback` | GET | OAuth callback used by Google. |
| `/freebusy/{account_label}` | GET | Free/busy response for one connected account. Requires `time_min` and `time_max`. |
| `/pair` | GET | Combined free/busy response for both connected accounts. Requires `time_min` and `time_max`. |
| `/matching/options` | POST | Returns up to three non-overlapping options for both connected calendars using `time_min`, `time_max`, `duration_minutes`, and optional weekday/time windows. |
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

Example matching request:

```bash
curl -X POST "http://127.0.0.1:8000/matching/options" \
  -H "Content-Type: application/json" \
  -d '{
    "time_min": "2026-06-08T09:00:00Z",
    "time_max": "2026-06-12T17:00:00Z",
    "duration_minutes": 30,
    "allowed_windows": [
      {"day": 0, "start": "09:00", "end": "17:00"},
      {"day": 1, "start": "09:00", "end": "17:00"}
    ],
    "max_options": 3
  }'
```

`allowed_windows[].day` uses Python weekday numbering: Monday is `0` and Sunday is `6`.

## CI/CD and cloud hosting

Fly.io is the first documented hosting target for this prototype. The deployment support includes:

- `Dockerfile` with the hosted `uvicorn` command.
- `fly.toml` with Fly.io app, build, and service settings.
- `requirements.txt` for Docker image dependency installation.
- `.python-version` to pin Python `3.12.13` for CI/local tooling.
- `.github/workflows/ci.yml` to run the setup verifier on pushes and pull requests.
- `.github/workflows/deploy-fly.yml` for optional GitHub Actions-controlled deployment to Fly.io.
- `cloud_hosting/fly_io.md` with the complete Fly.io setup checklist.

For the first hosted deployment, follow `cloud_hosting/fly_io.md` and add the Fly.io callback URL to Google Cloud OAuth before testing authentication.

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
├── .github/workflows/
│   ├── ci.yml
│   └── deploy-fly.yml
├── .python-version
├── DEBUGGING_GUIDE.md
├── Dockerfile
├── README.md
├── app.py
├── cloud_hosting/
│   └── fly_io.md
├── fly.toml
├── docs/
│   ├── product-overview.md
│   ├── roadmap.md
│   └── features/
├── pyproject.toml
├── requirements.txt
├── static/
│   ├── css/style.css
│   ├── html/home.html
│   └── js/app.js
├── test.py
└── tests/
    ├── __init__.py
    ├── test_deployment_config.py
    └── test_verify_setup.py
```

## Development notes

- Keep business logic independent from concrete persistence implementations as the app evolves.
- Keep calendar-provider logic behind interfaces when adding Microsoft Calendar support.
- Update this README and the relevant `docs/features/*.md` file when changing product behavior.
- Add automated tests when adding application behavior; the current test file is a setup verifier, not a full test suite.
