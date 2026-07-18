# Content Guidelines: Accommodation Search MVP

**Date**: 2026-07-19

---

## Voice and Tone

**Direct and task-focused.** Users come to search and monitor prices — copy should help them do that, not explain what the product is.

- Use present-tense verbs: "Track" not "Start tracking", "Search" not "Start a search".
- Address the user as "you" — no passive constructions.
- Avoid: "Please", "successfully", "amazing", "powerful", filler adjectives.
- Be specific about what happened: "No longer tracking Barcelona Sep 1–7" not "Untracked".

---

## Navigation Labels

| Route | Label |
|---|---|
| `/search` | Search |
| `/dashboard` | Dashboard |
| `/notifications` | Notifications |
| `/settings/telegram` | Account |
| Sub-item: Telegram settings | Telegram notifications |
| Sub-item: Sign out | Sign out |

---

## Page Titles (H1)

| Page | Title |
|---|---|
| /login | (no visible H1 — logo serves as heading context) |
| /search | Find Accommodation |
| /search/{id}/progress | Searching… |
| /search/{id}/results | {destination} · {check-in}–{check-out} · {N} results |
| /property/{id} | {property name} |
| /dashboard | Tracked items |
| /notifications | Notification history |
| /settings/telegram | Telegram notifications |

---

## Form Labels and Helper Text

### SearchForm

| Field | Label | Helper text | Placeholder |
|---|---|---|---|
| Destination | Destination | — | e.g. Barcelona |
| Check-in | Check-in | — | YYYY-MM-DD |
| Check-out | Check-out | — | YYYY-MM-DD |
| Guests | Guests | — | 2 |
| Price max | Max price per night | Leave blank for no limit | e.g. 150 |
| Bedrooms min | Bedrooms (min) | — | 1 |
| Bathrooms min | Bathrooms (min) | — | 1 |
| Rating min | Rating (min) | — | e.g. 4.0 |
| Free cancellation | Free cancellation | — | — (checkbox) |
| Wifi | Wifi | — | — (checkbox) |
| Kitchen | Kitchen | — | — (checkbox) |
| AC | Air conditioning | — | — (checkbox) |
| Pool | Pool | — | — (checkbox) |
| Providers | Search on | At least one required | — (checkboxes) |

---

## Validation and Error Messages

Write errors as specific instructions, not accusations.

| Field | Error | Message |
|---|---|---|
| Destination | Empty | Enter a destination |
| Check-in | Empty | Choose a check-in date |
| Check-in | In the past | Choose a future check-in date |
| Check-out | Empty | Choose a check-out date |
| Check-out | Before/equal to check-in | Check-out must be after check-in |
| Guests | Empty | Enter the number of guests |
| Guests | Out of range | Guests must be between 1 and 16 |
| Providers | None selected | Select at least one provider |
| Login — email | Empty | Enter your email address |
| Login — email | Invalid format | Enter a valid email address |
| Login — password | Empty | Enter your password |
| Login — credentials | 401 | Incorrect email or password |

---

## Button Labels

| Action | Label | Notes |
|---|---|---|
| Submit search | Search | Primary action |
| Track a search | Track this search | On results page |
| Track a property | Track this property | On property detail page |
| Per-row track toggle — off | Track | Table row action |
| Per-row track toggle — on | Tracking ✓ | Indicates active state |
| Export CSV | Export CSV | Not "Download" — more specific |
| Confirm tracking | Start tracking | In interval modal |
| Cancel tracking modal | Cancel | Secondary |
| Untrack (table row) | Untrack | Destructive appearance |
| Confirm untrack (popover) | Untrack | Destructive, red |
| Cancel untrack (popover) | Cancel | Secondary |
| Generate link code | Generate code | In Telegram settings |
| Open Telegram | Open in Telegram | With external link icon |
| Unlink Telegram | Unlink Telegram | Destructive appearance |
| Confirm unlink | Unlink | In confirmation dialog |
| Sign out | Sign out | In account dropdown |

---

## Status Labels

### Search status (progress page)

| Status | Label |
|---|---|
| pending | Waiting to start |
| running | Searching… |
| complete | Done |
| failed | Unavailable |

### Tracked search / property status (dashboard)

| Status | Badge label | Color + icon |
|---|---|---|
| Active | Active | Green dot |
| Failed last run | Last run failed | Amber triangle |
| Auto-deactivated | Expired | Gray dash |

---

## Toast Messages

| Event | Message |
|---|---|
| Tracked search created | Search tracked — every {N}h |
| Tracked property created | Property tracked — every {N}h |
| Untracted (search or property) | No longer tracking |
| CSV download started | Downloading CSV… |
| Copy link code to clipboard | Code copied |
| Telegram unlinked | Telegram account unlinked |
| Generic error | Something went wrong. Try again. |
| Network error | Connection lost. Check your network. |

---

## Inline Warnings and Informational Messages

### Telegram not linked (inside interval modal)

> Telegram is not linked — alerts won't be sent until you link your account. Notification history is still recorded here in the app.
> [Link Telegram →]

### Provider partial failure (results page)

> Results from [Airbnb / Booking.com] could not be loaded. Showing [other provider] results only.

### Tracked search limit reached (inside interval modal)

> You've reached the 10 tracked search limit. Untrack an existing search before adding another.

### Tracked property limit reached

> You've reached the 20 tracked property limit. Untrack an existing property to add another.

### Tracking already active (idempotent)

> This search is already being tracked. Your interval has been updated.

---

## Empty States

| Screen | Heading | Subtext | Action |
|---|---|---|---|
| Search results (0 results) | No results found | Try adjusting your filters or dates. | [Modify search] |
| Dashboard — no tracked searches | Nothing tracked yet | Track a search to monitor prices in the background. | [Search now] |
| Dashboard — no tracked properties | — | (shown in same empty state as above, combined) | — |
| Notification history — empty | No alerts yet | Start tracking a search or property to receive price-drop alerts. | [Search now] |
| Property detail (unavailable) | Property unavailable | This property could not be loaded. | [Back to results] |

---

## Notification History Item Format

**Price drop**:
> ↓ Price drop — {Property name}
> €{before} → €{after} · {timestamp}
> [View listing ↗]

**New listing**:
> ★ New listing — {Property name}
> €{price}/night · {timestamp}
> [View listing ↗]

**Timestamp format**: `19 Jul 2026, 08:12` (locale-aware, 24h for European audiences).

---

## Telegram Bot Messages (for reference — bot output, not web UI)

| Command / event | Bot message |
|---|---|
| `/follow` success | ✓ Tracking {property name} for {dates}. I'll alert you if the price drops below {price}. |
| `/follow` no dates | I can't find dates in that link. Please resend with check-in and check-out dates in the URL. |
| `/follow` unrecognised URL | I don't recognise that as a Booking.com or Airbnb listing. Please send a direct property link. |
| `/follow` already tracked | Already tracking this property for those dates. |
| `/unfollow` success | Stopped tracking {property name} for {dates}. |
| `/unfollow` not tracked | I wasn't tracking that property. |
| `/list` — has items | Your tracked items: \n1. Barcelona search (Sep 1–7) · next run in 2h\n… |
| `/list` — empty | You have no tracked searches or properties yet. |
| `/list` — not linked | Send /start to link your TravelSearch account first. |
| `/start <code>` success | ✓ Your Telegram account is now linked to TravelSearch. |
| `/start <code>` expired | That code has expired or already been used. Generate a new one in the app. |
| Price drop alert | 📉 Price drop: {Property name}\n€{before} → €{after} (↓{%})\n{dates}\n{link} |
| New listing alert | 🏠 New listing: {Property name}\n€{price}/night\n{dates}\n{link} |
