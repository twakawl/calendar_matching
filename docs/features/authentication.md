# Feature: Authentication

## Goal

Users must log in before connecting calendars, creating meeting requests, accepting requests, or viewing agenda data.

## MVP scope

- Account registration or external identity-provider login.
- Separate login and registration pages.
- Login and logout.
- Session management.
- Basic user profile fields:
  - user ID,
  - display name,
  - email address,
  - phone number,
  - timezone preference,
  - linked calendar preference,
  - ordered time presets,
  - created timestamp.
- Authorization checks for every meeting request and agenda view.

## Current prototype status

- Implemented application-managed email/password registration and login, split across `/register` and `/login`.
- Passwords are stored as salted PBKDF2 hashes.
- Login creates a session token that is returned for bearer-token API use and also set as an HTTP-only browser cookie.
- Logout revokes the current session token.
- Calendar account listing, Google OAuth start, free/busy reads, paired availability, and matching now require an authenticated app user.
- Unauthenticated browser users are redirected to `/login`; registration lives separately at `/register`, and display name is not collected on login.
- The authenticated app shell shows primary navigation links plus a clear top-right personal dropdown for Profile, Friends, Account, Demo request, and logout.
- Connected Google calendar slots are owned by the logged-in user while still exposing prototype slot names `a` and `b` in the UI.
- Local SQLite startup seeds two disposable testing users when missing: `twan.houwers92@gmail.com` and `twan@dutchwebshark.com`, both with password `Test123!`.

Still deferred:

- Real Google/Microsoft app-login implementation. The current buttons are visible next to email login and route to explicit placeholder endpoints while calendar-link OAuth remains separate.
- Password reset and email verification.
- CSRF hardening and broader production session controls.
- Returning invitees to the exact invite/request context after login is still basic and should be hardened.
- Broader production authorization/audit coverage for future agenda views and calendar-write objects is still deferred.

## User stories

- As a new user, I can create an account so I can connect my calendar.
- As an existing user, I can log in so I can view my requests and agenda.
- As an invited user, I can open a request link and log in before sharing my availability.
- As a user, I can log out so other people cannot access my account from the same browser.

## Key decisions to make

- Whether the MVP uses email/password, OAuth-only login, or a managed identity service.
- Whether Azure deployment should use Microsoft Entra External ID, Azure App Service Authentication, or application-managed auth.
- Password reset and email verification requirements.

## Acceptance criteria

- Unauthenticated users cannot view private agenda data.
- Unauthenticated users who open request links are redirected to login and returned to the request after authentication.
- Authenticated users can only access their own agenda data and requests they created or were invited to.
- Session cookies or tokens are protected with secure settings in production.

## Data needs

- User account record.
- Authentication identity mapping if an external identity provider is used.
- Session or refresh-token storage if required by the chosen stack.
