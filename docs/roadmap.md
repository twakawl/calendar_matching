# Roadmap

## Phase 0: Documentation and architecture

- Define features and product boundaries.
- Choose the first implementation stack.
- Define persistence interfaces for local SQLite and Azure SQL.
- Define calendar provider interfaces for Google first and Microsoft later.

## Phase 1: Foundation

- Add application skeleton.
- Add user authentication.
- Add local SQLite persistence.
- Add database models for users, calendar connections, meeting requests, proposed options, and agreement status.
- Add configuration patterns for local development and Azure deployment.

## Phase 2: Google Calendar MVP

- Implement Google OAuth connection.
- Store calendar tokens securely.
- Read availability from Google Calendar.
- Show a user's own agenda in the app.

## Phase 3: Meeting request MVP

- Let a logged-in user create a request with duration, weekdays, and allowed hours.
- Generate a secure request link.
- Let the invited user open the link, log in, connect Google Calendar, and accept participation.
- Compute and display the best three meeting options.

## Phase 4: Calendar writes and agreement flow

- Add a button to place proposed options on both users' calendars.
- Track app-created calendar event IDs.
- Let both users agree, disagree, or choose a final option.
- Keep the chosen calendar event and remove unchosen app-created option events.

## Phase 5: Privacy, polish, and reliability

- Show anonymized busy blocks in request views.
- Improve error handling for revoked calendar permissions and stale calendar data.
- Add audit history for request state changes.
- Add automated tests for matching, request lifecycle, and provider abstractions.

## Future release: Microsoft Calendar

- Add Microsoft account connection using the same calendar-provider interface.
- Support matching between Google and Microsoft users.
- Support calendar writes and cleanup for Microsoft events.
