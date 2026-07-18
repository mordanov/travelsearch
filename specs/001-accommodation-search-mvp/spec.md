# Feature Specification: Accommodation Search MVP

**Feature Branch**: `001-accommodation-search-mvp`
**Created**: 2026-07-18
**Status**: Draft
**Input**: User description from specification.md

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Search and compare accommodation listings (Priority: P1)

A user wants to search for accommodation across Booking and Airbnb in one place, with
common filters, and see a unified, sortable table of results — without having to visit two
different sites and manually reconcile listings.

**Why this priority**: Core value proposition. Without live search, no other feature can be
demonstrated or tested. All other stories depend on search results existing.

**Independent Test**: A user can open the app, enter a destination with dates and filters,
and receive a merged results table showing listings from both providers. This is fully
demonstrable without any tracking or Telegram features.

**Acceptance Scenarios**:

1. **Given** a logged-in user on the search form, **When** they enter a destination,
   check-in/check-out dates, guest count, and optionally filters (max price, bedrooms,
   rating, amenities), **Then** the system runs a live search and returns a merged results
   table with columns: Source, Name, Price/night, Total price, Rating, Bedrooms,
   Bathrooms, Distance, Cancellation, Amenities, Link.

2. **Given** search results are displayed, **When** the user sorts by any column or applies
   additional filters, **Then** the table updates accordingly without re-running the search.

3. **Given** search results are displayed, **When** the user clicks "Export CSV", **Then**
   a CSV file containing all visible results is downloaded.

4. **Given** the search is running, **When** the provider is slow or returns partial
   results, **Then** the UI shows a progress indicator and results appear as they arrive.

5. **Given** a provider is unavailable or blocked, **When** the search runs, **Then** the
   results from the working provider are still shown and the failure is indicated clearly.

---

### User Story 2 — Track a saved search for new or cheaper listings (Priority: P2)

A user wants a saved search to keep running in the background so they are notified on
Telegram when a new matching listing appears, or when a previously-seen listing drops below
its lowest recorded price — without manually re-checking.

**Why this priority**: Core monetization of user attention — passive monitoring. Builds
directly on US1 (search must work first).

**Independent Test**: A user can enable tracking on a search result page, configure an
interval, then verify that after a simulated background cycle a Telegram notification
arrives for a new or cheaper listing. Testable without US3 (property tracking).

**Acceptance Scenarios**:

1. **Given** a user has run a search, **When** they click "Track this search" and choose
   an interval, **Then** the search is saved and background monitoring begins.

2. **Given** a tracked search, **When** a background cycle finds a listing not present in
   the previous successful cycle, **Then** a Telegram alert is sent with the listing's
   name, price, and link.

3. **Given** a tracked search, **When** a background cycle finds a previously-seen listing
   whose current price is below its lowest ever recorded price, **Then** a Telegram alert
   is sent showing the old minimum and the new price.

4. **Given** a tracked search, **When** a background cycle finds nothing new or cheaper,
   **Then** no notification is sent.

5. **Given** a tracked search, **When** a background cycle is blocked, CAPTCHA'd, or
   returns a suspiciously small result set, **Then** the cycle is discarded without
   updating the baseline and no notification is sent.

6. **Given** a user visits the Tracked dashboard, **When** they view their tracked
   searches, **Then** they can see each search's status, last-checked time, and untrack it.

---

### User Story 3 — Follow a specific listing via the Telegram bot (Priority: P3)

A user wants to send a Booking or Airbnb link to the Telegram bot and have it monitor that
exact property for the dates encoded in the link, notifying them if the price drops —
without opening the web app.

**Why this priority**: High user convenience but depends on the tracking infrastructure
(US2) being in place. The bot command is an alternative entry point, not a prerequisite.

**Independent Test**: A user sends `/follow <link>` with a valid URL including dates. The
bot confirms tracking has started. After a simulated background cycle with a lower price,
a notification arrives. Testable without the web UI tracking form (US2 web form may
be tested separately).

**Acceptance Scenarios**:

1. **Given** a user sends `/follow <link>` with a Booking or Airbnb URL that contains
   check-in/check-out dates, **When** the bot parses the link successfully, **Then** it
   replies confirming tracking has started for that property and those dates.

2. **Given** a user sends `/follow <link>` where no dates can be parsed, **When** the bot
   processes the message, **Then** it replies asking the user to resend a link that
   includes dates.

3. **Given** a user sends `/follow <link>` with a URL that is not a recognised Booking or
   Airbnb listing, **When** the bot processes it, **Then** it replies with an error and
   nothing is created.

4. **Given** a property the user is already following with the same dates, **When** they
   send `/follow <link>` again, **Then** the bot replies that it is already tracked — no
   duplicate is created.

5. **Given** a followed property, **When** a background cycle finds today's price lower
   than the price recorded when tracking started, **Then** a Telegram alert is sent showing
   old price, new price, and the link.

6. **Given** a followed property whose check-in date has passed, **When** the scheduler
   runs, **Then** tracking is automatically deactivated.

---

### User Story 4 — Account & Telegram linking (Priority: P4)

A user needs to log in to the app and optionally link their Telegram account so they can
receive alerts and issue bot commands tied to their identity.

**Why this priority**: Authentication is a prerequisite for all features, but it is the
simplest piece. Telegram linking is needed for US2 and US3 to deliver notifications.

**Independent Test**: A user can log in with email and password. They can navigate to
account settings, generate a one-time link code, open the Telegram bot deep-link, and
complete linking. After linking, the bot responds to `/list` with their tracked items.

**Acceptance Scenarios**:

1. **Given** a pre-created account, **When** the user enters their email and password,
   **Then** they are logged in and see the search form.

2. **Given** incorrect credentials, **When** the user submits the login form, **Then**
   an error is shown and no session is created.

3. **Given** a logged-in user who has not linked Telegram, **When** they visit the Telegram
   linking screen and click the deep-link, **Then** the bot presents a one-time code
   prompt, they confirm, and the accounts are linked.

4. **Given** a linked Telegram account, **When** the user issues `/list` in the bot,
   **Then** the bot replies with their active tracked searches and tracked properties.

5. **Given** a linked Telegram account, **When** the user chooses to unlink from the app,
   **Then** the link is removed and the bot no longer responds to their commands.

---

### Edge Cases

- Search with zero results from both providers → show empty state, no error.
- Search where one provider returns no results but the other does → show partial results
  with provider attribution.
- User attempts to track a search that is already tracked → the existing tracked search
  is updated with the new interval (no duplicate).
- User attempts to track a property that is already tracked with the same dates → the
  existing tracked property is updated with the new interval (no duplicate).
- Notification history is visible in-app; the web app is fully self-sufficient and never
  requires the user to have checked Telegram to see past alerts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST require authentication (email + password) before any feature
  is accessible. No public registration endpoint.
- **FR-002**: The system MUST allow a user to search accommodation across Booking, Airbnb,
  or both simultaneously, with a unified filter set: destination, check-in, check-out,
  guests, bedrooms, bathrooms, price range, rating, free cancellation, kitchen, wifi, air
  conditioning, pool.
- **FR-003**: Search results MUST be fetched live (no caching) and displayed in a merged,
  sortable, filterable table.
- **FR-004**: The user MUST be able to export search results to CSV.
- **FR-005**: The user MUST be able to track a saved search with a configurable re-run
  interval; the system re-runs the search in the background and alerts on new or
  price-dropped listings.
- **FR-006**: The user MUST be able to untrack a saved search.
- **FR-007**: The user MUST be able to track a specific property from the results table,
  the property detail page, or via the Telegram bot's `/follow` command.
- **FR-008**: The user MUST be able to untrack a specific property via `/unfollow` in
  Telegram or from the web dashboard.
- **FR-009**: Tracking logic (create/remove tracked search, create/remove tracked property,
  dedup, interval validation) MUST be the same whether triggered from the web UI or the
  Telegram bot — no duplicated business logic.
- **FR-010**: The system MUST expose a Tracked dashboard showing all active tracked
  searches and tracked properties with current status.
- **FR-011**: The system MUST expose a Notification history view showing every alert ever
  sent, including price before/after and timestamp, accessible in-app without Telegram.
- **FR-012**: A user MUST be able to link their Telegram account via a bot deep-link and
  one-time code, and unlink it from the app.
- **FR-013**: Scrape cycles that are blocked, CAPTCHA'd, or return suspiciously incomplete
  results MUST be discarded without updating any baseline or triggering any notification.
- **FR-014**: Tracked properties MUST auto-deactivate after their check-in date passes.
- **FR-015**: The system MUST support multiple users; each user's tracked items, alerts,
  and Telegram link are private to them.

### Key Entities

- **User**: Represents a logged-in account; has an optional linked Telegram chat.
- **Search**: A one-time search execution with criteria and provider selection.
- **Property**: A normalized accommodation listing from any provider, with price, rating,
  location, and amenity data.
- **TrackedSearch**: A saved search that re-runs periodically; owns a per-property baseline
  (seen-property set with minimum prices).
- **TrackedProperty**: A specific property being watched for a price drop on given dates.
- **PriceSnapshot**: A historical price record for a property at a point in time.
- **NotificationLog**: A record of every alert sent (type, before/after price, channel,
  timestamp).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete a multi-provider accommodation search (destination +
  dates + filters → merged results) in a single session, with results appearing within
  a reasonable wait time showing a progress indicator.
- **SC-002**: All results from both providers appear in a single unified table; the user
  never needs to visit Booking or Airbnb to see the same data.
- **SC-003**: A tracked search detects and notifies the user of a new or cheaper matching
  listing within one scheduled interval cycle after the change becomes available.
- **SC-004**: A property followed via `/follow <link>` is set up and confirmed in a single
  bot exchange (one message in, one confirmation out) for a well-formed URL with dates.
- **SC-005**: A user can review all past alerts (price before/after, timestamp) without
  opening Telegram — the in-app notification history is complete.
- **SC-006**: Deploying the entire stack requires only `docker compose up` — no manual
  setup steps beyond providing `.env` values.
- **SC-007**: Adding a new accommodation provider requires no changes to backend API
  contracts or routes — only a new provider implementation.

## Assumptions

- Users have a Telegram account and have started the bot at least once before attempting
  to link it.
- The admin provisions accounts manually via CLI or admin endpoint; no self-registration
  flow is needed.
- Search results are always live; caching accommodation search results is explicitly
  out of scope.
- "Suspiciously incomplete" for the safe-scraping discard rule is defined per-provider
  (e.g., fewer results than a known minimum threshold); the exact threshold is a provider
  implementation detail.
- The notification channel for all alerts is Telegram only (email/push are out of scope
  for MVP).
- The bot deep-link flow assumes the VPS is publicly reachable over HTTPS before Telegram
  linking is used; local development may use a tunnel.
- Property tracking check-in date auto-deactivation applies only to TrackedProperty;
  TrackedSearch has no inherent expiry and runs until the user untracks it.
