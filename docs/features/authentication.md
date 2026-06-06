# Feature: Authentication

## Goal

Users must log in before connecting calendars, creating meeting requests, accepting requests, or viewing agenda data.

## MVP scope

- Account registration or external identity-provider login.
- Login and logout.
- Session management.
- Basic user profile fields:
  - user ID,
  - display name,
  - email address,
  - created timestamp.
- Authorization checks for every meeting request and agenda view.

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
