# Feature: Meeting Options and Agreement

## Goal

After the app finds meeting options, users can place those options on both calendars, agree on one, disagree with options, and let the app remove obsolete holds.

## MVP scope

- Show up to three matched options.
- Provide a button to send proposed options to both calendars.
- Track which external calendar event belongs to which option and participant.
- Let each participant mark agreement or disagreement per option set.
- Let both users choose one final option.
- Delete unchosen app-created option events from both calendars.
- Keep or create the final agreed calendar event.

## User stories

- As a requester, I can send proposed options to both calendars.
- As an invitee, I can review the proposed options before agreeing.
- As both users, we can agree on one option.
- As both users, we can disagree and ask for different options.
- As the app, I can remove only the temporary option events I created.

## Acceptance criteria

- Proposed options are not written to calendars until a user intentionally triggers that action.
- App-created option events are traceable in app storage.
- Final agreement requires the necessary participant confirmations defined by product rules.
- When one option is finalized, unchosen app-created option events are deleted.
- If a calendar write or delete fails, the app shows a recoverable state and does not lose tracking data.

## State to track

- Proposed option ID.
- Option start and end time.
- Participant decisions.
- Calendar event IDs for each participant and option.
- Final selected option.
- Cleanup status.
