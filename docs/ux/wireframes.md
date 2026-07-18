# Wireframes: Accommodation Search MVP

**Format**: ASCII low-fidelity layout notes. All widths target desktop (≥1280px) with responsive behavior down to 960px.
**Date**: 2026-07-19

---

## Page: /login

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                        TravelSearch                                 │
│                  ─────────────────────                              │
│                                                                     │
│                    ┌─────────────────────┐                         │
│              Email │                     │                         │
│                    └─────────────────────┘                         │
│                    ┌─────────────────────┐                         │
│           Password │                     │                         │
│                    └─────────────────────┘                         │
│                                                                     │
│                    [  ●  Sign In  ]                                 │
│                                                                     │
│          [error message if 401 — tied to fields above]             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Notes**:
- Single-column, centered card (max-width 400px).
- Error message appears below the password field, not as a toast.
- No registration link — admin-provisioned accounts only.

---

## Page: /search

```
┌─────────── Nav ─────────────────────────────────────────────────────┐
│ TravelSearch      [Search]  [Dashboard]  [Notifications]  [Account] │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Find Accommodation                                                 │
│  ─────────────────                                                  │
│  ┌──────────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────┐ │
│  │  Destination     │  │ Check-in   │  │ Check-out  │  │ Guests  │ │
│  └──────────────────┘  └────────────┘  └────────────┘  └─────────┘ │
│                                                                     │
│  ▾ Filters (collapsible)                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ Price max: [_____]  Bedrooms min: [_]  Bathrooms min: [_]      │ │
│  │ Rating min: [___]   Free cancellation: [✓]                     │ │
│  │ Amenities: [✓ Wifi]  [✓ Kitchen]  [ ] AC  [ ] Pool             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Providers:  [✓ Booking.com]  [✓ Airbnb]                           │
│                                                                     │
│                               [  Search  ]                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Notes**:
- Destination is a plain text input (no autocomplete for MVP).
- Date pickers: native `<input type="date">` or a lightweight headless picker.
- Filters collapsed by default; expand on click. Filter state persists during session.
- Providers: at least one must be checked; validation prevents empty submit.

---

## Page: /search/{id}/progress

```
┌─────────── Nav ─────────────────────────────────────────────────────┐
│ TravelSearch      [Search]  [Dashboard]  [Notifications]  [Account] │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Searching for "Barcelona"  ·  1 Sep – 7 Sep  ·  2 guests          │
│  ─────────────────────────────────────────────                      │
│                                                                     │
│  ┌────────────────────────┐  ┌────────────────────────┐            │
│  │ Booking.com            │  │ Airbnb                 │            │
│  │ ████████░░░░  Running  │  │ ██████████  Complete   │            │
│  │ 10 results so far      │  │ 14 results             │            │
│  └────────────────────────┘  └────────────────────────┘            │
│                                                                     │
│  24 results found so far...                                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**States**:
- `running`: progress bar animated, partial count shown.
- `partial`: one provider failed — card shows "Failed — results unavailable from this provider".
- `complete`: auto-redirect to results (no manual action needed).
- `failed` (both): error panel with "Try again" button linking back to /search.

---

## Page: /search/{id}/results

```
┌─────────── Nav ─────────────────────────────────────────────────────┐
│ TravelSearch      [Search]  [Dashboard]  [Notifications]  [Account] │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Barcelona  ·  1 Sep – 7 Sep  ·  2 guests        24 results        │
│                                                                     │
│  [⚠ Airbnb unavailable — showing Booking.com results only]  ← cond. │
│                                                                     │
│  ┌─ Filters ──────────────────────────────────────────────────────┐ │
│  │ Source: [All ▾]  Price: [0–200]  Rating: [4.0+]               │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  [ Track this search ▾ ]                      [ Export CSV ]       │
│                                                                     │
│ ┌──────┬─────────────────────┬──────────┬───────┬──────┬──────────┐ │
│ │Source│ Name              ↕ │Price/ngt↕│Rating↕│Beds ↕│ Track    │ │
│ ├──────┼─────────────────────┼──────────┼───────┼──────┼──────────┤ │
│ │ [Bk] │ Apt Gothic Quarter  │  €95     │  4.7  │  2   │ [Track]  │ │
│ │ [Ab] │ Cozy Studio Eixample│  €72     │  4.5  │  1   │ [Track]  │ │
│ │ [Bk] │ Bright Flat Gràcia  │ €110     │  4.8  │  2   │ [Track]  │ │
│ └──────┴─────────────────────┴──────────┴───────┴──────┴──────────┘ │
│                                                                     │
│  [< Prev]  Page 1 of 1  [Next >]                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Table columns** (all sortable via column header click):
Source, Name, Price/night, Total price, Rating, Bedrooms, Bathrooms, Distance (km), Cancellation, Amenities (icon row), Link (external icon), Track (toggle).

**Source badge**: "Bk" = blue pill for Booking.com, "Ab" = orange pill for Airbnb. Both include `aria-label="Booking.com"` / `aria-label="Airbnb"`.

**Track toggle**: disabled with tooltip "Track requires login" if somehow unauthenticated; once tracked shows "Tracking ✓" in success green.

**Empty state** (zero results): centered illustration area + "No results found. Try adjusting your filters or dates."

---

## Page: /property/{id}

```
┌─────────── Nav ─────────────────────────────────────────────────────┐
│ ← Back to results                                                   │
└─────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────┬─────────────────────────────┐
│                                       │  Apt in Gothic Quarter      │
│   [image placeholder]                 │  Booking.com                │
│                                       │  ─────────────────          │
│                                       │  €95 / night                │
│                                       │  Total: €570  (6 nights)    │
│                                       │  Rating: ★ 4.7              │
│                                       │  Bedrooms: 2  Bathrooms: 1  │
│                                       │  Free cancellation: Yes     │
│                                       │  ─────────────────          │
│                                       │  Amenities:                 │
│                                       │  [Wifi] [Kitchen] [AC]      │
│                                       │  ─────────────────          │
│                                       │  [  View on Booking.com  ]  │
│                                       │  [  Track this property  ]  │
└───────────────────────────────────────┴─────────────────────────────┘
│  Map placeholder (static)                                           │
└─────────────────────────────────────────────────────────────────────┘
```

**Notes**:
- "Track this property" opens the interval selector modal (6h/12h/24h/48h).
- "View on Booking.com" / "View on Airbnb" opens in a new tab.
- Map placeholder is a static div for MVP (no interactive map required).

---

## Page: /dashboard

```
┌─────────── Nav ─────────────────────────────────────────────────────┐
│ TravelSearch      [Search]  [Dashboard]  [Notifications]  [Account] │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Tracked Searches                            3 / 10 active          │
│  ─────────────────                                                  │
│ ┌──────────────┬──────────────┬──────────┬───────────┬────────────┐ │
│ │ Destination  │ Dates        │ Interval │ Last run  │            │ │
│ ├──────────────┼──────────────┼──────────┼───────────┼────────────┤ │
│ │ Barcelona    │ Sep 1–7      │ 24h      │ 2h ago    │ [Untrack]  │ │
│ │ Rome         │ Oct 10–15    │ 12h      │ 45m ago   │ [Untrack]  │ │
│ └──────────────┴──────────────┴──────────┴───────────┴────────────┘ │
│                                                                     │
│  Tracked Properties                          5 / 20 active          │
│  ─────────────────────                                              │
│ ┌──────────────────────┬──────────────┬──────────┬────────────────┐ │
│ │ Property             │ Dates        │ Min seen │                │ │
│ ├──────────────────────┼──────────────┼──────────┼────────────────┤ │
│ │ Apt Gothic Quarter   │ Sep 1–7      │ €85      │ [Untrack]      │ │
│ └──────────────────────┴──────────────┴──────────┴────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Status badge** on each row: `● Active`, `○ Paused` (future), `✕ Failed` (last run error).
**Limit counter** (e.g. "3 / 10 active") turns amber at 80% and red at 100%.
**[Untrack]** shows a small inline confirmation popover before firing DELETE.

---

## Page: /notifications

```
┌─────────── Nav ─────────────────────────────────────────────────────┐
│ TravelSearch      [Search]  [Dashboard]  [Notifications]  [Account] │
└─────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Notification History           Filter: [All ▾]                     │
│  ────────────────────                                               │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │ [↓ Price drop]  Apt in Gothic Quarter          Jul 19 · 08:12  │  │
│ │   €110 → €87  · ↓ 21% · [View listing ↗]                      │  │
│ ├────────────────────────────────────────────────────────────────┤  │
│ │ [★ New listing]  Cozy Room Poblenou              Jul 18 · 22:40 │  │
│ │   €58 / night · [View listing ↗]                               │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  [< Prev]  Page 1 of 1  [Next >]                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Empty state**: "No alerts yet. Track a search or property to start monitoring prices."

---

## Page: /settings/telegram

```
┌─────────────────────────────────────────────────────────────────────┐
│  Telegram Notifications                                             │
│  ──────────────────────                                             │
│                                                                     │
│  [NOT LINKED state]                                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Link your Telegram account to receive price-drop alerts.      │ │
│  │                                                                │ │
│  │  1. Click "Generate code" below.                               │ │
│  │  2. Open the Telegram link and confirm.                        │ │
│  │  3. This page will update when linking is complete.            │ │
│  │                                                                │ │
│  │  [  Generate code  ]                                           │ │
│  │                                                                │ │
│  │  ← after clicking →                                            │ │
│  │  Your code: ABC123XY        Expires in 14:32                   │ │
│  │  [  Open in Telegram  ]                                        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  [LINKED state]                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  ✓ Telegram account linked                                     │ │
│  │                                                                │ │
│  │  [  Unlink Telegram  ]                                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**Notes**:
- Countdown timer runs client-side from `expires_in_seconds: 900`.
- When timer reaches 0, code display collapses and "Generate code" button reappears.
- "Open in Telegram" uses the `deep_link` from API response; opens in new tab on desktop.

---

## Modals

### Interval Selector Modal (Track Search / Track Property)

```
┌─────────────────────────────────────────┐
│  Track this search                   ✕  │
│  ─────────────────                      │
│  Re-run interval:                       │
│  ○ Every 6 hours                        │
│  ● Every 24 hours          (default)    │
│  ○ Every 12 hours                       │
│  ○ Every 48 hours                       │
│                                         │
│  ┌─ Warning (if Telegram not linked) ─┐ │
│  │ ⚠ Telegram not linked — in-app     │ │
│  │ history only until you link.        │ │
│  │ [Link Telegram]                     │ │
│  └────────────────────────────────────┘ │
│                                         │
│                [Cancel]  [Start tracking]│
└─────────────────────────────────────────┘
```

### Untrack Confirmation Popover

```
  ┌──────────────────────────────────┐
  │ Stop tracking this search?       │
  │ This cannot be undone.           │
  │             [Cancel]  [Untrack]  │
  └──────────────────────────────────┘
```

---

## Navigation Structure

```
Nav (authenticated):
  TravelSearch (logo → /search)
  [Search] → /search
  [Dashboard] → /dashboard
  [Notifications] → /notifications
  [Account ▾]
    → /settings/telegram
    → Sign out

Nav (unauthenticated): hidden — redirect to /login
```
