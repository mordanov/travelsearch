# Component Behavior: Accommodation Search MVP

**Date**: 2026-07-19

All components follow these global rules unless overridden:
- Keyboard navigable (Tab / Shift-Tab / Enter / Space / Arrow keys per ARIA pattern).
- Visible focus ring on all interactive elements (2px outline, offset 2px, contrast ≥3:1 against background).
- No action depends on color alone — always pair color with icon, label, or pattern.

---

## SearchForm

### Fields & Validation

| Field | Type | Validation | Inline error |
|---|---|---|---|
| Destination | Text input | Required, min 2 chars | "Enter a destination" |
| Check-in | Date input | Required, not in the past | "Select a future date" |
| Check-out | Date input | Required, > check-in | "Check-out must be after check-in" |
| Guests | Number input (1–16) | Required, integer 1–16 | "Enter 1 to 16 guests" |
| Providers | Checkboxes | At least one checked | "Select at least one provider" |

**Validation timing**: on submit only — not on blur, to avoid premature interruption.
**Submit disabled state**: button shows spinner while request is in-flight; re-enabled on 4xx response.
**Filter panel**: toggle via "▾ Filters" button. Saves expansion state in session storage so returning to the page keeps it open.

---

## SearchProgressPage

### State Machine

```
pending  →  running  →  complete  →  (redirect to results)
                     →  partial   →  (redirect to results with warning)
                     →  failed    →  error panel
```

**Per-provider card states**: `running` (animated bar), `complete` (solid bar + count), `failed` (red icon + "Unavailable"), `pending` (gray bar).

**Auto-redirect**: fires when `status === "complete"` or `status === "partial"`. No manual button needed.

**Polling**: 3-second interval via `useSearchStatus()`. Polling stops on redirect or `status === "failed"`.

**Timeout**: if polling exceeds 3 minutes and status is still `running`, show: "This is taking longer than expected. Results will appear when ready." — do not stop polling.

---

## ResultsTable

### Sorting

- Click column header → sort ascending. Click again → sort descending. Click a third time → remove sort (return to default order by first provider then original position).
- Sort state shown: up/down caret icon adjacent to column label. Screen-reader text: `aria-sort="ascending"` / `aria-sort="descending"` on `<th>`.
- Sorting is client-side only (results already loaded).

### Column Filters

- Each sortable column has a compact text/number input in the header row below the label.
- Filter applies on `input` event (live), debounced 200ms.
- Multiple filters combine with AND logic.
- "Clear filters" button appears when any filter is active.

### Source Badge

| Provider | Visual | Aria label |
|---|---|---|
| Booking.com | Blue pill, "Bk" text | "Booking.com" |
| Airbnb | Orange pill, "Ab" text | "Airbnb" |

Color + text label together — never color alone.

### Track Toggle (per row)

| State | Appearance | Action |
|---|---|---|
| Not tracked | Outlined button "Track" | Opens interval modal (Phase 4+) |
| Tracked | Filled button "Tracking ✓" | Click → untrack confirmation popover |
| Loading | Spinner, disabled | — |
| Limit reached | Disabled, tooltip "Limit reached" | None |

### Empty State

```
[Icon: magnifying glass with ×]
No results found
Try adjusting your filters or search dates.
[Modify search]  ← links back to /search (pre-fills form from URL params)
```

### Provider Failure Banner

Shown at top of results when one provider failed (partial state):
```
⚠ Results from [Provider] could not be loaded. Showing [other provider] results only.
```
Dismissible via × button. Does not block the table.

---

## IntervalSelectorModal

- Radios: 6h, 12h, 24h (default), 48h.
- Focus trapping: Tab cycles within modal. Escape closes modal.
- Telegram warning: shown if `telegramLinked === false`. Non-blocking — user can still proceed.
- "Start tracking" button: disabled until a radio is selected (24h pre-selected on open, so it's always enabled).
- On error (422 limit): inline error message inside modal, modal stays open.
- On success: modal closes, toast appears.

---

## UntrackConfirmationPopover

- Triggered by [Untrack] button.
- Popover positions above/below the trigger depending on viewport space.
- Keyboard: Escape cancels, Enter/Space confirms.
- After confirm: row fades out, count decrements.
- On API error: popover stays open with error message "Failed to untrack. Try again."

---

## Toast Notifications

| Event | Message | Duration |
|---|---|---|
| Track search success | "Search tracked every X hours" | 4s auto-dismiss |
| Track property success | "Property tracked every X hours" | 4s auto-dismiss |
| Untrack success | "No longer tracking" | 3s auto-dismiss |
| CSV export started | "Downloading CSV…" | 2s auto-dismiss |
| Generic API error | "Something went wrong. Please try again." | 6s, manual dismiss |

**Position**: bottom-right, stacked if multiple.
**Accessibility**: `role="status"` with `aria-live="polite"` for success; `role="alert"` with `aria-live="assertive"` for errors.
**Animation**: slide-in from right, fade-out. Respects `prefers-reduced-motion` (no animation if set).

---

## TelegramLinkPage

### Code display state

- Code shown in `<code>` monospace block, large font, selectable.
- "Open in Telegram" button uses `deep_link` from API, opens in new tab.
- Countdown: MM:SS format, color shifts amber below 5 minutes, red below 1 minute.
- On expiry: code hides, countdown hides, "Generate code" button reappears.
- Polling: `useCurrentUser()` polls every 5 seconds while code is displayed to detect when linking completes. On detecting `telegram_is_linked === true`: show success state without page refresh.

---

## NotificationHistoryList

### Item layout

```
[type badge]  [property name — linked]           [timestamp]
              [price before] → [price after]  ↓ [% drop]
              [View listing ↗]
```

**Type badges**: "↓ Price drop" (green) / "★ New listing" (blue). Both use icon + text — not color alone.

**Pagination**: 50 items per page. "Load more" button or numbered pagination — either acceptable for MVP.

**Filter dropdown**: "All" / "Price drops" / "New listings". Fires a new API request with `type` param.

---

## NavigationBar

- Active route highlighted with underline (not color alone).
- "Notifications" link shows unread badge count if `total > 0` from GET /notifications (cached, refreshes every 60s).
- Account dropdown: keyboard-accessible, closes on outside click and Escape.
- On screens < 960px: nav collapses to hamburger menu (mobile-responsive, not a separate design).

---

## Loading & Skeleton States

| Component | Loading behavior |
|---|---|
| SearchProgressPage | Per-provider progress cards with animated bars |
| ResultsTable | Full-table skeleton rows (5 rows of gray bars) while first page loads |
| TrackedDashboardPage | Table skeleton for each section |
| NotificationHistoryList | List skeleton (3 rows) |
| TelegramLinkPage after code request | Button spinner, code display appears when response returns |

---

## Form Error Recovery Pattern

1. Inline error appears below the relevant field.
2. Error disappears when the user begins correcting the field (on `input` event).
3. On re-submit: all validations re-run fresh.
4. API-level errors (4xx) shown as inline field errors if field-specific (e.g., email taken), or as a form-level alert if generic.

---

## Design Token Rules

| Token | Value | Notes |
|---|---|---|
| Border radius (inputs, buttons) | 6px | |
| Border radius (modals, cards) | 8px | |
| Focus ring | 2px solid #0066CC, offset 2px | Meets 3:1 contrast |
| Error color | #C0392B text + icon | Always paired with text |
| Success color | #27AE60 text + icon | Always paired with text |
| Warning color | #E67E22 text + icon | Always paired with text |
| Disabled opacity | 0.45 | Applied to button/input |
| Transition duration | 150ms ease | For hover/focus states |
| Table row hover | 4% dark overlay | |
