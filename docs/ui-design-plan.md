# UI Design Plan

## Purpose

This document translates the product vision into a practical UI plan for frontend and backend implementation. The app should help two people quickly find and agree on a meeting time without exposing private calendar details.

The UI should feel:

* Simple and calm.
* Trustworthy around privacy.
* Fast to understand on a laptop.
* Usable on mobile for accepting requests and choosing options.
* Structured enough for future Google and Microsoft calendar support.

## Core UI principles

### 1. Guide users through one clear task at a time

The current product journey has several steps: login, connect calendar, create request, invite another user, compare calendars, choose options, and agree. The UI should avoid putting all of these steps on one screen.

Use a step-based flow for complex actions, especially meeting request creation.

### 2. Show only the information users need

Users should not see another participant’s event titles, descriptions, attendees, locations, or calendar names. The UI should show the other person’s availability as anonymized busy blocks only.

### 3. Make status visible

Meeting requests can be draft, sent, opened, waiting for calendar connection, ready to match, options proposed, agreed, cancelled, or expired. Every request detail page should show the current status clearly.

### 4. Prioritize the top three options

The product promise is not “browse everyone’s full calendar.” The product promise is “here are the best meeting options.” Suggested options should be visually prominent.

### 5. Design mobile for decision-making, not full calendar management

Mobile users should be able to:

* Open an invite link.
* Log in.
* Connect a calendar.
* Review the request.
* See the three proposed options.
* Accept, reject, or choose an option.

Advanced calendar comparison can be more comfortable on laptop, but it should still degrade gracefully on mobile.


### 6. Keep navigation and pop-up menus obvious

The top navigation should expose the highest-frequency destinations directly: Dashboard, New request, Account, and Demo request. Personal destinations should be grouped in a single dropdown labelled with the current user's name/email where possible. The dropdown should contain Profile, Friends, Account, Demo request, and Log out. Avoid hiding the primary creation path inside the dropdown.

### 7. Make the biggest control the next best action

Authentication pages should make email login/register the largest card because that is the implemented path. Request creation should make **Find best options** larger than secondary draft-saving actions. Demo pages should make **Run demo match** the largest action so the prototype is easy to test.

***

# Main pages

## 1. Landing page

### Route suggestion

`/`

### Goal

Explain the product and move users toward login or opening an invite.

### Primary content

On one laptop screen:

* Header with product name and login button.
* Hero section:

  * Short headline: “Find a meeting time without exposing your calendar.”
  * Supporting text: “Connect calendars, invite someone, and get the best shared options.”
  * Primary button: “Create meeting request.”
  * Secondary button: “I have an invite link.”
* Small privacy note:

  * “We only use availability. Other people do not see your event details.”
* Optional simple visual:

  * Three suggested time cards beside anonymized busy blocks.

### Laptop layout

Use a two-column hero:

* Left: copy and actions.
* Right: visual explanation.

This should fit in a 1366×768 laptop viewport without scrolling if possible.

### Mobile layout

Stack vertically:

1. Product name.
2. Headline.
3. Primary action.
4. Secondary action.
5. Privacy note.
6. Optional visual below the fold.

***

## 2. Login / profile calendar accounts

### Route suggestion

`/login` and `/profile` (`/account` redirects to `/profile`)

### Goal

Let users authenticate and manage connected calendar accounts from Profile.

### Primary content

* Login form or OAuth login options.
* Profile calendar provider section with Google enabled, Microsoft/Apple marked not connected, and a request-new-platform form:

  * Google Calendar status.
  * Future Microsoft Calendar placeholder.
* Calendar connection state:

  * Not connected.
  * Connected.
  * Permission expired.
  * Needs reconnect.
* Button:

  * “Connect Google Calendar.”
  * “Reconnect Google Calendar.”
  * “Disconnect.”

### Backend needs

Frontend needs account/calendar connection state from backend:

* Current user identity.
* Connected providers.
* Provider account email.
* Token health or reconnect-required state.
* Calendar permission scope summary.

### Mobile layout

Use cards stacked vertically. Avoid tables.

***

## 3. Dashboard

### Route suggestion

`/dashboard`

### Goal

Show the user’s active meeting requests and a clear button to create a new one.

### Primary content

On one laptop screen:

* Top bar:

  * Product name.
  * User/account menu.
* Main header:

  * “Meeting requests”
  * Button: “New request”
* Request list grouped by status:

  * Needs your action.
  * Waiting for invitee.
  * Options proposed.
  * Agreed.
* Request cards:

  * Meeting title.
  * Participant name/email.
  * Status badge.
  * Date range.
  * Next action.
  * Last updated.

### Laptop layout

Use a two-column layout if there is enough space:

* Left/main: request list.
* Right/sidebar: calendar connection status, quick privacy reminder, maybe recent agreed meetings.

### Mobile layout

Single-column cards. Each request card should show only:

* Title.
* Other participant.
* Status.
* Primary action.

Details can appear after tapping.

***

## 4. Create meeting request flow

### Route suggestion

`/requests/new`

### Goal

Let a requester define enough constraints for the matching engine.

### Recommended structure

Use a multi-step form instead of one large table.

#### Step 1: Meeting basics

Fields:

* Title.
* Description or notes.
* Invitee email.
* Duration.
* Optional location or video-call preference.

Primary action: “Next: choose dates.”

#### Step 2: Date range

Fields:

* Earliest possible date.
* Latest possible date.
* Optional timezone selector.

Helpful defaults:

* Start: today or next business day.
* End: two weeks from now.
* Timezone: browser/user account timezone.

#### Step 3: Availability rules

Fields:

* Allowed weekdays.
* Allowed time windows.
* Optional preference:

  * Morning preferred.
  * Afternoon preferred.
  * Earliest possible.
  * Latest possible.
  * Spread options across days.

Recommended UI:

* Use weekday chips instead of a large table:

  * Mon, Tue, Wed, Thu, Fri selected by default.
* Use a compact time-window editor:

  * “Between 09:00 and 17:00.”
* Add “Add another time window” for advanced use.

Avoid showing all seven rows by default on mobile.

#### Step 4: Review and send

Show summary:

* Title.
* Invitee.
* Duration.
* Date range.
* Allowed days.
* Allowed hours.
* Privacy message.
* Button: “Create invite link” or “Send request.”

### Laptop layout

Use a wizard card centered in the page, max width around 720–860px. Keep each step short enough to fit mostly within one laptop screen.

### Mobile layout

Full-width form, one step per screen. Use large tap targets and native date/time inputs.

### Backend needs

Backend should support draft creation or final creation with:

* Title.
* Notes.
* Invitee email.
* Duration in minutes.
* Date range.
* Timezone.
* Allowed weekdays.
* One or more time windows.
* Preference weights or ranking hints.
* Request status.

***

## 5. Invite landing page

### Route suggestion

`/invite/{token}`

### Goal

Let the invited user understand the request and continue safely.

### Primary content

* Request title.
* Requester name/email.
* Duration.
* Date range.
* Short explanation:

  * “To find shared times, connect your calendar. The requester will only see busy/free blocks, not event details.”
* Actions:

  * “Accept and continue.”
  * “Decline.”
* If not logged in:

  * Login/create account prompt.
* If calendar not connected:

  * “Connect Google Calendar.”

### Laptop layout

Centered card, max width around 640px.

### Mobile layout

Same card, full width with comfortable spacing.

### Backend needs

Frontend needs a safe invite preview endpoint that returns non-sensitive request info before full authenticated access where appropriate.

***

## 6. Request detail page

### Route suggestion

`/requests/{request_id}`

### Goal

Show request status, participant readiness, matched options, and next actions.

### Primary content

Header:

* Meeting title.
* Status badge.
* Other participant.
* Duration.
* Date range.

Status section:

* Requester: calendar connected / waiting / action needed.
* Invitee: calendar connected / waiting / action needed.

Main action area:

* If not ready:

  * Show missing steps.
* If ready:

  * Button: “Find best options.”
* If options exist:

  * Show top three option cards.
* If calendar holds were sent:

  * Show hold status.
* If agreed:

  * Show final selected meeting.

### Option cards

Each option card should show:

* Rank label: “Best option”, “Option 2”, “Option 3”.
* Date.
* Start and end time.
* Timezone.
* Reason text:

  * “Both calendars are free.”
  * “Within your preferred hours.”
* Actions:

  * “Choose this option.”
  * “Reject.”
  * Later phase: “Add options to calendars.”

### Laptop layout

Use two columns:

* Left/main:

  * Status.
  * Options.
  * Timeline/agenda preview.
* Right/sidebar:

  * Request summary.
  * Participants.
  * Privacy explanation.
  * Activity history.

The top status and the three options should fit in the first laptop screen.

### Mobile layout

Use stacked sections:

1. Status.
2. Best option cards.
3. Request summary.
4. Calendar preview.

On mobile, the three option cards should appear before detailed agenda visualization.

### Backend needs

Frontend needs:

* Request detail.
* Participant states.
* Available actions for current user.
* Proposed options.
* Matching explanation metadata.
* Calendar hold state.
* Agreement state.
* Activity history.

***

## 7. Availability comparison / agenda preview

### Route suggestion

Embedded inside `/requests/{request_id}` or separate `/requests/{request_id}/availability`.

### Goal

Help users understand why options were suggested without revealing private data.

### Recommended desktop UI

Use a timeline grid for selected days:

* Horizontal or vertical day view.
* User’s own events may show more detail if allowed.
* Other participant’s events appear as “Busy.”
* Suggested slots appear highlighted.
* Legend:

  * You.
  * Other participant busy.
  * Both busy.
  * Suggested option.

### Recommended mobile UI

Avoid a dense full calendar grid by default.

Use:

* Day selector carousel.
* List of busy/free blocks.
* Suggested options at top.
* Expandable “Why this option?” section.

### Privacy behavior

* Never render other participant event titles.
* Never render other participant event descriptions.
* Never render attendees or locations.
* Label other-user blocks only as “Busy.”
* If a block overlaps both users, show “Unavailable.”

### Backend needs

Availability endpoint should return normalized intervals:

* Start.
* End.
* Owner category:

  * current\_user\_busy.
  * other\_user\_busy.
  * both\_busy.
  * suggested\_option.
* Optional current-user-only event display fields.
* No private metadata for the other participant.

***

## 8. Agreement flow

### Route suggestion

Part of `/requests/{request_id}`.

### Goal

Let both users pick a final option or reject options.

### States to design

* Options proposed, no decisions yet.
* One participant selected an option.
* Both selected the same option.
* Participants selected different options.
* One participant rejected all options.
* Final meeting agreed.
* Request cancelled or expired.

### UI behavior

When both users agree on the same option:

* Show confirmation state.
* Highlight final selected meeting.
* Show calendar event write/cleanup status if calendar writes are enabled.

When users disagree:

* Show clear message:

  * “You selected different options.”
* Actions:

  * “Choose another option.”
  * “Find new options.”
  * “Cancel request.”

### Backend needs

Frontend needs participant-level decision state and final agreement state.

***

# Navigation model

## Primary navigation

For authenticated users:

* Dashboard.
* New request.
* Profile calendar accounts.
* Help/privacy.

For invite users:

* Invite page should focus only on the request.
* Avoid sending invitees into a complex dashboard before they complete the required action.

## Breadcrumbs

Use breadcrumbs or back links on deeper pages:

* Dashboard → Request detail.
* Request detail → Availability view.

***

# Visual design direction

## Style

Use a clean productivity-app style:

* White or very light gray background.
* Card-based surfaces.
* One strong primary color for actions.
* Calm supporting colors for status and availability.
* Avoid overly bright red/green combinations as the only signal.

## Suggested color roles

* Primary action: blue or green.
* Success/agreed: green.
* Warning/action needed: amber.
* Error/expired/revoked: red.
* Current user busy: muted blue.
* Other participant busy: muted purple or gray.
* Both unavailable: neutral dark gray.
* Suggested option: green highlight.

Ensure color is not the only indicator. Use labels, icons, and patterns where helpful.

## Typography

Use a system font stack first:

`Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`

Recommended hierarchy:

* Page title: 28–32px desktop, 24px mobile.
* Section title: 18–22px.
* Body: 14–16px.
* Metadata: 12–14px.

## Spacing

Use consistent spacing tokens:

* 4px.
* 8px.
* 12px.
* 16px.
* 24px.
* 32px.
* 48px.

## Components

Frontend should define reusable components for:

* App shell.
* Page header.
* Status badge.
* Request card.
* Participant readiness card.
* Option card.
* Calendar connection card.
* Privacy notice.
* Empty state.
* Loading state.
* Error state.
* Stepper/wizard.
* Time-window picker.
* Weekday selector.
* Availability timeline.

***

# Responsive breakpoints

Use mobile-first CSS.

Recommended breakpoints:

* Small mobile: below 480px.
* Large mobile: 480px and up.
* Tablet: 768px and up.
* Laptop/desktop: 1024px and up.
* Wide desktop: 1280px and up.

## Laptop target

The app should work well on a common laptop viewport around 1366×768.

For key pages, the first screen should contain:

* Dashboard:

  * Header.
  * New request button.
  * Most important request cards.
* Request detail:

  * Status.
  * Top three options.
  * Primary next action.
* Create request:

  * One wizard step.
  * Navigation buttons.
* Invite page:

  * Full invite explanation and primary action.

## Mobile target

The app should work well around 390×844 and 375×667.

Mobile rules:

* One column only.
* No wide tables for core flows.
* Use cards and stacked form controls.
* Keep option cards above detailed calendar views.
* Use sticky bottom action buttons only when they do not cover important content.
* Minimum tap target around 44px high.

***

# Information architecture

## Request object UI fields

Pages will likely need these request fields:

* Request ID.
* Title.
* Notes.
* Requester.
* Invitee.
* Duration.
* Date range.
* Timezone.
* Allowed weekdays.
* Allowed time windows.
* Status.
* Created date.
* Updated date.
* Expiration date.
* Current user role.
* Available current-user actions.

## Participant UI fields

* User ID.
* Display name or email.
* Role.
* Calendar connected state.
* Response state.
* Last activity time.

## Proposed option UI fields

* Option ID.
* Start.
* End.
* Timezone.
* Rank.
* Score or ranking reason.
* Current user decision.
* Other participant decision if shareable.
* Calendar hold/write state.
* Final selected flag.

***

# Empty, loading, and error states

## Empty states

Dashboard:

* “No meeting requests yet.”
* Button: “Create your first request.”

No calendar connected:

* “Connect your calendar to find shared availability.”
* Button: “Connect Google Calendar.”

No options found:

* Explain why:

  * “No shared free time was found in this date range.”
* Actions:

  * “Edit request constraints.”
  * “Extend date range.”
  * “Try different hours.”

## Loading states

Use clear loading messages:

* “Checking calendars…”
* “Finding the best options…”
* “Creating invite link…”
* “Saving your decision…”

Avoid showing raw JSON or raw API responses in production UI.

## Error states

Common errors to design:

* Calendar permission revoked.
* Invite link expired.
* Request already cancelled.
* User is not a participant.
* Calendar provider unavailable.
* No matching slots found.
* Calendar write failed.
* Cleanup of unchosen holds failed.

Each error should include:

* Plain-language message.
* Recovery action.
* Support/debug reference if available.

***

# Accessibility requirements

* All interactive controls must be keyboard-accessible.
* Form fields need visible labels.
* Status must not rely on color alone.
* Calendar grid should have text labels or an accessible list alternative.
* Use sufficient color contrast.
* Error messages should be associated with the relevant field.
* Avoid tiny controls in the time-window picker.
* Support browser zoom up to at least 200%.

***

# Implementation guidance for frontend developers

## Replace prototype table-heavy UI

The current prototype now uses Profile-owned calendar accounts plus request-level calendar selection, but still has a dense request form, calendar grid, and raw overview. Future UI should split this further into product pages and reusable components.

Focus first on:

1. Dashboard.
2. Create request wizard.
3. Invite page.
4. Request detail with top three option cards.
5. Responsive availability preview.

## Suggested frontend structure

If the app moves beyond static files, consider a component structure like:

* `AppShell`
* `DashboardPage`
* `CreateRequestPage`
* `InvitePage`
* `RequestDetailPage`
* `AccountPage`
* `RequestCard`
* `OptionCard`
* `StatusBadge`
* `CalendarConnectionCard`
* `AvailabilityTimeline`
* `WeekdaySelector`
* `TimeWindowPicker`
* `PrivacyNotice`

## Data loading

Each page should have explicit loading and error states. Do not assume calendar or matching data is immediately available.

## Progressive enhancement

Initial frontend can be server-rendered or simple static JavaScript, but components should be designed so they can later move to a richer frontend framework if needed.

***

# Implementation guidance for backend developers

The backend should provide UI-friendly endpoints that avoid leaking provider-specific details.

Recommended API capabilities:

* Get current user/profile calendar account state.
* Get calendar connection state.
* Create/update meeting request draft.
* Finalize/send meeting request.
* Resolve invite token.
* Accept/decline invite.
* Get request detail.
* Compute proposed options.
* Get availability intervals for display.
* Record participant decision.
* Write proposed options to calendars.
* Finalize agreed option.
* Cleanup unchosen calendar holds.

Backend responses should include:

* Current user’s available actions.
* Human-friendly status codes/messages.
* Privacy-safe availability intervals.
* Stable IDs for requests, participants, and options.
* Provider reconnect requirements when applicable.

***

# Recommended first UI milestone

For the next practical UI iteration, build a polished version of the existing prototype around the future product shape:

1. Keep Google Calendar connection.
2. Keep account/calendar connection cards only in Profile and avoid A/B slot language.
3. Add a request creation card with:

   * Duration.
   * Date range.
   * Weekday chips.
   * Time window picker.
4. Show the top three matching slots as option cards.
5. Keep the calendar grid as a secondary “availability preview.”
6. Add responsive mobile styling.
7. Remove raw debug output from the primary UI, or hide it behind a developer/debug section.

This gives frontend developers a clear target while backend developers continue building proper user accounts, request persistence, and participant flows.
