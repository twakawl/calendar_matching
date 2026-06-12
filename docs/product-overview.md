# Product Overview

## Vision

Create a simple web app that lets users connect their calendars, request meetings with other users, and automatically find the best meeting moments without exposing private agenda details.

## Core user journey

1. A user creates an account or logs in.
2. The user opens Profile, where calendar accounts start empty, then connects one or more calendar accounts. Google is the first connected provider; Microsoft and Apple are visible as not-connected options, and the user can request another platform.
3. The user creates a meeting request, selects one of the profile's connected calendar accounts for that request, and defines:
   - invitee information,
   - meeting duration,
   - allowed weekdays,
   - allowed time windows,
   - optional priority preferences.
4. The app sends or displays a request link for the invitee.
5. The invitee opens the link, logs in or creates an account, and connects Google Calendar if needed.
6. The app compares both calendars against the request preferences.
7. The app proposes the best three meeting options.
8. Users can publish the proposed options to both calendars.
9. Users agree on one option or reject options.
10. The app keeps the chosen event and removes declined option holds from both calendars.

## Release principles

- Keep the first version small and reliable.
- Design persistence behind interfaces so local SQLite and Azure SQL can both be supported.
- Start with Google Calendar only; add Microsoft Calendar after the integration model is proven.
- Never reveal another user's meeting details. Show anonymized busy blocks where visibility is needed.
- Keep enough internal state to know which calendar events were created by the app and can safely be updated or deleted.

## Primary roles

### Requesting user

The user who creates a meeting request and defines when the meeting can happen.

### Invited user

The user who receives a link, connects their agenda, and participates in selecting a meeting option.

### System

The app that authenticates users, stores meeting-request state, reads availability, proposes options, writes tentative or final calendar events, and cleans up obsolete holds.
