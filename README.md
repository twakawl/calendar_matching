# Calendar Matching

Calendar Matching is an early-stage FastAPI prototype for comparing two Google Calendars. It now includes first-party app registration/login, lets logged-in users connect two Google Calendar slots with OAuth 2.0, stores encrypted refresh tokens and meeting request drafts in SQLite, reads only Google Calendar free/busy data, and shows overlapping availability in a simple browser UI.

The longer-term product direction is documented separately: authenticated users should eventually send meeting requests and receive the best meeting options based on both users' availability and request preferences.

## Current repository status

This repository currently contains both planning documentation and a runnable prototype:

- `app.py` — single-file FastAPI backend, first-party auth/session handling, OAuth callback handling, SQLite persistence, encrypted token storage, meeting request and invite storage, Google Calendar free/busy calls, and API endpoints.
- `static/html/home.html`, `static/html/login.html`, `static/css/style.css`, `static/js/app.js`, and `static/js/login.js` — lightweight frontend with a standalone login page, authenticated app shell, calendar-slot authentication, availability preferences, and suggested free slots.
- `pyproject.toml` — Python package metadata and dependency list for `uv`.
- `Dockerfile`, `fly.toml`, `requirements.txt`, and `.python-version` — Fly.io deployment settings for the hosted FastAPI service.
- `.github/workflows/ci.yml` and `.github/workflows/deploy-fly.yml` — GitHub Actions CI and optional Fly.io CD workflows.
- `cloud_hosting/fly_io.md` — Fly.io account, deployment, environment, OAuth callback, and troubleshooting instructions.
- `.env.example` — environment-variable template for Google OAuth credentials, a Fernet key, database configuration, and hosted redirect settings.
- `tests/test_verify_setup.py` — setup verification script for environment variables, imports, and local database readiness.
- `test.py` — manual helper script for printing local `google_accounts` rows.
- `DEBUGGING_GUIDE.md` — manual troubleshooting notes for the current prototype.
- `docs/` — product roadmap and feature specifications for future development, including `docs/features/profile-friends-demo.md` for the latest implemented feature slice.

The setup instructions that are needed for the current prototype are included below.

## Implemented features

- First-party registration, standalone login, logout, HTTP-only session cookies, bearer-token API sessions, an inline register warning for unknown login emails, and app-style placeholder pages for future Google/Microsoft app-login.
- Dedicated registration page with email/password prefill from an unknown-email login attempt, default display name from the email local part, plus editable personal profile with display name, phone number, timezone preference, linked calendar preference, and ordered time presets.
- Friends page with email-based friend requests, acceptance, and contact-import placeholder links for Gmail, Apple, Microsoft, and Android.
- OAuth 2.0 Web Server Flow for Google Calendar tied to the logged-in user.
- Offline access with refresh token storage.
- Fernet encryption for stored refresh tokens.
- SQLite-backed `users`, `user_sessions`, `oauth_states`, user-owned `google_accounts`, `meeting_requests`, and `request_audit_events` records.
- Google Calendar free/busy reads for primary calendars only; event titles, descriptions, attendees, and locations are not fetched.
- Combined busy-block response for two connected accounts.
- MVP matching endpoint that returns the top three non-overlapping meeting options from duration, weekday, allowed-hour, and busy-block constraints.
- Bootstrap-based multi-page frontend with a public informational home page, polished login/register screens, a clear top navigation bar with personal dropdown menu, authenticated dashboard, account/calendar connection cards, profile and friends pages, SQLite-backed multi-invitee request creation/listing, secure invite preview with accept/decline actions, request-detail placeholders, responsive availability preview, a public demo request, and live top-three matching cards backed by the existing Google free/busy prototype.
- Automatic access-token refresh before Calendar API calls.

## Future implementation scope

The current app is still a prototype. Future work described in `docs/` includes:

- Full meeting-request lifecycle statuses, participant-specific calendar readiness for multiple invitees, persistent proposed options, and email invite delivery.
- A fuller storage abstraction that can support local SQLite and Azure SQL-style deployments.
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

Run the full automated regression suite when changing application behavior:

```bash
uv run python -m pytest -q
```

If you only need the documented setup verifier, run:

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

1. Open `http://127.0.0.1:8000`; unauthenticated users see the public information home page with a top-right **Log in** button.
2. Register or log in with an app account, then use the authenticated dashboard and account pages.
3. Create a request from `/requests/new`; it is persisted in local SQLite, generates a hashed expiring invite token, and appears on `/dashboard`.
4. From `/account`, connect **Google Calendar · Slot A** and **Google Calendar · Slot B** with OAuth.
5. On `/requests/new`, select a meeting duration and weekday/hour availability preferences.
6. Click **Find best options** to fetch both calendars' busy blocks and show the top three matching slots.

Direct OAuth start URLs are also available after logging in:

```text
http://127.0.0.1:8000/oauth/start?account_label=a
http://127.0.0.1:8000/oauth/start?account_label=b
```

## Prototype UI routes

The current frontend implements the first UI milestone from `docs/ui-design-plan.md` as static Bootstrap pages with placeholders where backend request persistence and participant workflows will be added later:

- `/` — public landing page with privacy-first product explanation and a top-right login button.
- `/login` — first-party email login page with prominent email login, a text register link below the login button, an inline warning/register handoff for unknown accounts, secondary Google/Microsoft app-login placeholder links, and privacy guidance.
- `/register` — first-party registration page with display name collection, default display name from the email text before `@`, email/password prefill after an unknown-account login, and an "I already have an account" text link below the submit button.
- `/profile` — authenticated personal profile with display name, phone number, timezone preference, linked calendar preference, ordered time presets, and a personal dropdown menu shared with friends/account routes.
- `/friends` — authenticated friend list with email request/accept flow and contact-import placeholder links.
- `/account` — authenticated Google Calendar connection cards for prototype slots A and B, plus a Microsoft Calendar placeholder that opens a not-implemented app page.
- `/dashboard` — authenticated list of SQLite-backed requests visible to the requester or accepted invitee, with an action to regenerate invite links.
- `/requests/new` — authenticated request creation wizard-style form with title, multiple invitee emails, friend selections, three quick preset buttons plus ordered preset dropdown, duration, date range, weekday chips, time window, SQLite save action, prominent live matching button, top-three option cards, and secondary availability preview.
- `/invite/{token}` — public secure invite preview that resolves non-sensitive request details from a hashed expiring token and lets the matching logged-in invitee accept or decline.
- `/requests/demo` — public demo request with two demo connector cards that runs the matching engine against separate demo calendar busy registries.
- `/requests/demo-request` — request detail placeholder with participant readiness, option cards, and agreement-state placeholders.
- `/requests/demo-request/availability` — anonymized availability preview placeholder.
- `/not-implemented/{feature_slug}` — app-style placeholder page for non-working planned functionality with **Back to home** and **Back to previous page** actions.

## API endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/health` | GET | JSON health check. |
| `/` | GET | Public informational frontend home page with top-right login action. |
| `/login` | GET | Standalone email login page with Google/Microsoft app-login placeholders; redirects authenticated users to `/dashboard`. |
| `/register` | GET | Standalone registration page that collects display name. |
| `/profile` | GET | Authenticated profile page for editable personal settings and ordered time presets. |
| `/friends` | GET | Authenticated friend list page. |
| `/requests/demo` | GET | Public demo request page backed by demo calendar registries. |
| `/auth/register` | POST | Create an app user and return/set a session token. |
| `/auth/login` | POST | Authenticate an app user and return/set a session token; unknown emails return a register-first response used by the frontend warning block. |
| `/auth/logout` | POST | Revoke the current session and clear the session cookie. |
| `/auth/me` | GET | Return the logged-in app user. |
| `/not-implemented/{feature_slug}` | GET | Render an app page for planned but non-working functionality with home and previous-page navigation. |
| `/auth/oauth/{provider}` | GET | Render the not-implemented app-login page for future Google/Microsoft app-login providers. |
| `/api/requests` | GET | List SQLite-backed meeting requests visible to the logged-in requester or invitee. |
| `/api/requests` | POST | Create a SQLite-backed meeting request and return a one-time-visible secure invite URL. |
| `/api/requests/{request_id}` | GET | Return one visible meeting request for the logged-in requester or invitee. |
| `/api/requests/{request_id}/invite` | POST | Regenerate a hashed, expiring invite token for a requester-owned request. |
| `/api/requests/{request_id}/audit` | GET | Return lifecycle audit events for a visible request. |
| `/api/invites/{token}` | GET | Preview non-sensitive details for an unexpired invite token. |
| `/api/invites/{token}/accept` | POST | Accept an invite as the logged-in invitee. |
| `/api/invites/{token}/decline` | POST | Decline an invite as the logged-in invitee. |
| `/oauth/start?account_label=a` | GET | Start Google OAuth for user-owned account slot `a` or `b`; requires login. |
| `/oauth/callback` | GET | OAuth callback used by Google. |
| `/freebusy/{account_label}` | GET | Free/busy response for one connected account owned by the logged-in user. Requires `time_min` and `time_max`. |
| `/pair` | GET | Combined free/busy response for both connected accounts owned by the logged-in user. Requires `time_min` and `time_max`. |
| `/matching/options` | POST | Returns up to three non-overlapping options for both connected calendars owned by the logged-in user using `time_min`, `time_max`, `duration_minutes`, and optional weekday/time windows. |
| `/api/demo/options` | POST | Runs the same matching engine against two submitted demo busy registries without using personal calendar connections. |
| `/api/profile` | GET/PUT | Returns or updates display name, phone number, timezone preference, selected linked calendar labels, and ordered time presets. |
| `/api/time-presets` | GET | Returns the current user's ordered time presets. |
| `/api/friends` | GET/POST | Lists friend requests or sends a new email-address friend request. |
| `/api/friends/{id}/accept` | POST | Accepts a pending friend request addressed to the current user. |
| `/accounts` | GET | Logged-in user's stored account metadata, without tokens. |
| `/accounts/select` | POST | Prototype endpoint for marking an account selected in the UI. |

Example login request:

```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"correct horse battery staple"}'
```

Use the returned `session_token` as a bearer token for API calls, or rely on the browser cookie set by the frontend.

Example one-account request:

```bash
curl -H "Authorization: Bearer $SESSION_TOKEN" \
  "http://127.0.0.1:8000/freebusy/a?time_min=2026-02-28T00:00:00Z&time_max=2026-03-10T00:00:00Z"
```

Example paired request:

```bash
curl -H "Authorization: Bearer $SESSION_TOKEN" \
  "http://127.0.0.1:8000/pair?time_min=2026-02-28T00:00:00Z&time_max=2026-03-10T00:00:00Z"
```

Example matching request:

```bash
curl -X POST "http://127.0.0.1:8000/matching/options" \
  -H "Authorization: Bearer $SESSION_TOKEN" \
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

The prototype creates a local SQLite database by default. Authentication and profile data lives in `users` and `user_sessions`; session tokens are stored only as SHA-256 hashes, passwords are stored as PBKDF2 hashes, and selected profile calendar labels are stored in `linked_calendar_labels` for later request flows. OAuth callbacks are protected with short-lived one-time `oauth_states`. Meeting requests live in `meeting_requests` with title, invitee email, duration, date range, time window, selected weekdays, notes, status, hashed invite token, invite expiration/open/accept/decline timestamps, invitee user linkage, and timestamps. Lifecycle events live in `request_audit_events`. The `google_accounts` table contains:

| Column | Purpose |
| --- | --- |
| `account_label` | Primary key using an internal user-owned slot key. |
| `owner_user_id` | App user that owns the connected calendar slot. |
| `google_sub` | Unique Google account identifier. |
| `email` | Connected Google account email address. |
| `refresh_token` | Encrypted refresh token. |
| `cached_busy` | JSON cache of recently fetched busy periods. |
| `created_at` | Storage timestamp. |
| `selected_as` | Prototype selection marker. |

Local database files such as `calendar.db` are ignored by Git.

## Security notes

- Passwords are stored as salted PBKDF2 hashes, and session tokens are stored only as SHA-256 hashes.
- Refresh tokens are encrypted with Fernet before storage.
- Secrets are loaded from environment variables and should not be committed.
- The Google Calendar scope is limited to `calendar.freebusy`.
- The API returns busy time ranges only, not event details.
- This is a local prototype and does not yet include production-grade CSRF/session hardening, secret rotation, rate limiting, email verification, or password reset flows.

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
    ├── test_auth.py
    ├── test_deployment_config.py
    ├── test_matching_options.py
    └── test_verify_setup.py
```

## Development notes

- Keep business logic independent from concrete persistence implementations as the app evolves.
- Keep calendar-provider logic behind interfaces when adding Microsoft Calendar support.
- Update this README and the relevant `docs/features/*.md` file when changing product behavior.
- Add automated tests when adding application behavior; the current test file is a setup verifier, not a full test suite.
