# Feature Plan: Profile, Friends, Request Presets, and Demo Request

## Purpose

This slice moves the prototype from a two-slot calendar test toward a user-centered scheduling product. The work is intentionally documentation-first: describe the intended experience, then implement the matching UI/API pieces, then verify the pages and tests still match the feature contracts.

## UX priorities for this slice

- Make the most important action visually largest: on login this is **Log in with email**, and on request creation this is **Find best options**.
- Keep the top navigation predictable: primary product routes are visible in the bar, while personal actions live in a clearly labeled user dropdown.
- Use pop-up/dropdown menus for secondary personal actions only: Profile, Friends, Account, Demo request, and Log out.
- Keep privacy reassurance close to authentication and calendar-linking moments.
- Avoid overwhelming users with calendar internals; show top-three meeting options before detailed availability previews.

## Planned features

### 1. Login flow update

- Keep email/password login on a dedicated `/login` page.
- Add visible app-login options for Google and Microsoft next to email login so the UI shape is ready for future identity providers.
- Split registration into `/register`.
- Keep `display_name` only on registration and profile editing, not on login.
- Make the email login card the visual focus, with Google/Microsoft presented as secondary choices.
- Add explicit helper text when Google/Microsoft app-login is selected because true provider login is still planned.

### 2. Personal profile

- Add `/profile` as a private page.
- Make display name editable after registration.
- Store phone number, timezone preference, multiple linked calendar selections, and ordered time presets.
- Seed standard presets:
  - Week-evening: weekdays 18:00–21:00.
  - Weekend: Friday 18:00 through Sunday 21:00.
  - Weekend day: Saturday/Sunday 10:00–18:00.
  - Weekend evening: Friday/Saturday 18:00–00:00.
  - Working hours: weekdays 08:00–18:00.
- Allow users to add custom presets, reorder presets, and build a preset from multiple time blocks.
- Show preset order clearly with up/down controls, day/time block editors, add/remove block actions, and human-readable summaries.

### 3. Meeting request enhancements

- Add three quick time-preset buttons plus a dropdown containing the user's ordered presets.
- Allow multiple invitee emails in one request payload.
- Allow adding accepted friends as participants.
- Keep invite links usable by people who need to log in or register before accepting and linking a calendar.
- Give the request creator a clear step flow: basics, dates, rules, then review/match.

### 4. Friends

- Add `/friends` in the same personal-menu area as profile.
- Allow users to send friend requests to email addresses.
- Allow only the recipient to accept requests; senders see the invitation as sent.
- Let either visible side delete a friend request from the card after confirming.
- Add greyed-out placeholder buttons for Gmail, Apple, Microsoft, and Android contact imports.
- Show pending and accepted friend relationships as cards with clear status badges.

### 5. Demo request

- Add `/requests/demo` as an authenticated demo page.
- Keep two connector cards, but wire them to Google Calendar OAuth slots A and B with `return_to=/requests/demo` so users land back on the demo after consent.
- Load each connected Google agenda with the same free/busy endpoints as real requests, while keeping `/api/demo/options` available for automated/offline matching tests.
- Use the same top-three option card visual language as real requests.

## Implemented prototype scope

- Added database fields and lightweight SQLite migrations for profile metadata, ordered presets, multi-invitee request metadata, and friend requests.
- Added private profile and friends APIs and pages.
- Added a Google-calendar-backed demo page plus a public demo matching endpoint for automated/offline test data.
- Added provider-login placeholder endpoints that render safe not-implemented pages, because true Google/Microsoft app-login requires provider client configuration separate from calendar-link OAuth.
- Added a clearer top navigation pattern with visible primary links and a personal dropdown for profile/friends/account/logout.
- Improved the login/register/profile/friends/request/demo pages so the main action is prominent, secondary actions are visually quieter, and privacy/helper copy appears near risky decisions.

## Verification checklist

- `/login` shows email login plus Google and Microsoft provider-login choices, and it does not collect display name.
- `/register` is separate and does collect display name.
- `/profile` can edit display name, phone, timezone, multiple linked calendar selections, and ordered presets with day/time controls.
- `/requests/new` shows three quick preset buttons, an ordered preset dropdown, multiple invitee-email support, accepted-friend selection, and top-three matching cards.
- `/friends` supports email-based friend requests and acceptance, with disabled contact-import placeholders.
- `/requests/demo` runs matching from two connected Google Calendar agendas and displays the free/busy registries used for matching.

## Follow-up work

- Replace app-login placeholders with real OAuth/OIDC identity-provider flows.
- Normalize multi-person meeting participants into a dedicated table instead of JSON columns.
- Send friend/request invitations by email.
- Add full calendar-readiness checks for every participant before matching.


## Latest calendar account UX update

- Calendar account management now lives only on the Profile page and is removed from the top navigation and personal dropdown menus.
- New profiles start with no connected calendar accounts. Profile offers **Connect new calendar account** with Google enabled, Microsoft and Apple marked as not connected, and a request-new-platform form.
- Request creation now asks the requester to select one connected profile calendar account instead of choosing requester/invitee A and B slots.
