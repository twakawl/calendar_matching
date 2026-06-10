# Feature Plan: Profile, Friends, Request Presets, and Demo Request

## Purpose

This slice moves the prototype from a two-slot calendar test toward a user-centered scheduling product. The work was planned as a documentation-first feature group and then implemented in the FastAPI prototype.

## Planned features

### 1. Login flow update

- Keep email/password login on a dedicated `/login` page.
- Add visible app-login options for Google and Microsoft next to email login so the UI shape is ready for future identity providers.
- Split registration into `/register`.
- Keep `display_name` only on registration and profile editing, not on login.

### 2. Personal profile

- Add `/profile` as a private page.
- Make display name editable after registration.
- Store phone number, timezone preference, linked calendar preference, and ordered time presets.
- Seed standard presets:
  - Week-evening: weekdays 18:00–21:00.
  - Weekend: Friday 18:00 through Sunday 21:00.
  - Weekend day: Saturday/Sunday 10:00–18:00.
  - Weekend evening: Friday/Saturday 18:00–00:00.
  - Working hours: weekdays 08:00–18:00.
- Allow users to add custom presets and reorder presets.

### 3. Meeting request enhancements

- Add three quick time-preset buttons plus a dropdown containing the user's ordered presets.
- Allow multiple invitee emails in one request payload.
- Allow adding accepted friends as participants.
- Keep invite links usable by people who need to log in or register before accepting and linking a calendar.

### 4. Friends

- Add `/friends` in the same personal-menu area as profile.
- Allow users to send friend requests to email addresses.
- Allow recipients to accept requests.
- Add greyed-out placeholder buttons for Gmail, Apple, Microsoft, and Android contact imports.

### 5. Demo request

- Add `/requests/demo` as a public demo page.
- Keep two demo calendar busy registries separate from personally linked calendars.
- Reuse the same matching engine through a demo API endpoint so the flow remains testable without OAuth.

## Implemented prototype scope

- Added database fields and lightweight SQLite migrations for profile metadata, ordered presets, multi-invitee request metadata, and friend requests.
- Added private profile and friends APIs and pages.
- Added a public demo matching endpoint and page.
- Added provider-login placeholder endpoints returning `501 Not Implemented`, because true Google/Microsoft app-login requires provider client configuration separate from calendar-link OAuth.

## Follow-up work

- Replace app-login placeholders with real OAuth/OIDC identity-provider flows.
- Normalize multi-person meeting participants into a dedicated table instead of JSON columns.
- Send friend/request invitations by email.
- Add full calendar-readiness checks for every participant before matching.
