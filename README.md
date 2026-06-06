# calendar_matching

`calendar_matching` is a simple calendar-matching application concept for helping authenticated users find the best meeting moments across connected agendas.

The first release should focus on:

1. User login and account management.
2. Flexible persistence that can run locally with SQLite and later in Azure with a managed SQL database.
3. Google Calendar connection for each user.
4. Meeting requests between users through shareable links.
5. Matching logic that proposes the best three meeting options based on both users' calendars and the requester's preferred days and hours.
6. Calendar option publishing, agreement tracking, and cleanup of declined options.
7. An in-app agenda view where users can inspect their own events, meeting requests, and anonymized busy blocks from the other participant.

Microsoft Calendar support is planned for a future release after the Google Calendar flow is stable.

## Documentation

Project planning is split into feature documents so development can start from clear product boundaries:

- [Product overview](docs/product-overview.md)
- [Roadmap](docs/roadmap.md)
- [Authentication](docs/features/authentication.md)
- [Storage abstraction](docs/features/storage-abstraction.md)
- [Calendar integrations](docs/features/calendar-integrations.md)
- [Meeting requests](docs/features/meeting-requests.md)
- [Availability matching](docs/features/availability-matching.md)
- [Meeting options and agreement](docs/features/meeting-options-agreement.md)
- [Agenda view](docs/features/agenda-view.md)
- [Privacy and anonymization](docs/features/privacy-anonymization.md)

## Current repository status

This repository currently contains documentation only. No application source code, dependency manifest, database migrations, or automated tests have been added yet.
