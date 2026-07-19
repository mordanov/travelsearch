# Accessibility Checklist: Accommodation Search MVP

**Baseline**: WCAG 2.1 AA
**Date**: 2026-07-19

Items marked **[TEST]** must be verified by Autotester or manual QA. Items marked **[IMPL]** are implementation-time requirements.

---

## Global (all pages)

- [IMPL] HTML `<html lang="en">` declared.
- [IMPL] Page `<title>` unique per route and descriptive (e.g. "Search results — Barcelona | TravelSearch").
- [IMPL] Visible focus ring on all interactive elements (2px outline, minimum 3:1 contrast against background).
- [IMPL] Focus never trapped outside a modal when no modal is open.
- [IMPL] `Tab` order follows DOM reading order; no `tabindex > 0`.
- [IMPL] `prefers-reduced-motion` media query: all CSS transitions/animations wrapped in `@media (prefers-reduced-motion: no-preference)`.
- [TEST] Keyboard-only navigation can reach every interactive control on every page.
- [TEST] Screen reader (VoiceOver + Chrome, NVDA + Firefox) announces page title on route change.

---

## /login

- [IMPL] `<form>` with `role="form"` and `aria-label="Sign in"` (or use `<main>` landmark appropriately).
- [IMPL] Email input: `<label for="email">` explicitly associated. `type="email"` for mobile keyboard.
- [IMPL] Password input: `<label for="password">` explicitly associated. Toggle show/hide if added: button with `aria-label="Show password"` / `aria-label="Hide password"`.
- [IMPL] Inline error: rendered in an element with `role="alert"` or tied via `aria-describedby` to the relevant input.
- [IMPL] Submit button: `<button type="submit">`, not a `<div>`.
- [TEST] Screen reader announces error message when credentials are wrong without requiring focus move.

---

## /search (SearchForm)

- [IMPL] All form fields have explicit `<label>` elements — no placeholder-as-label.
- [IMPL] Required fields marked with `aria-required="true"`.
- [IMPL] Inline validation errors: tied to fields via `aria-describedby`. Error IDs stable (not dynamic).
- [IMPL] Filter panel toggle button: `aria-expanded="true"/"false"` updated on toggle; `aria-controls` pointing to filter panel ID.
- [IMPL] Checkbox group for providers: wrapped in `<fieldset>/<legend>` ("Search on"). Same for amenities checkboxes.
- [IMPL] Date inputs: if using a custom picker, expose as `role="dialog"` with focus trap when open; Escape closes.
- [IMPL] Submit button: shows `aria-busy="true"` while request is in-flight.
- [TEST] Tab order: Destination → Check-in → Check-out → Guests → Providers → Filters → Search button.
- [TEST] Error announcements fire without moving visual focus.

---

## /search/{id}/progress (SearchProgressPage)

- [IMPL] Page heading announces destination and dates.
- [IMPL] Per-provider cards: `role="status"` or `aria-live="polite"` region to announce count updates.
- [IMPL] Progress bars: use `<progress>` or `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, `aria-label="Booking.com search progress"`.
- [IMPL] Auto-redirect to results: announce departure with `role="alert"` ("Search complete — loading results").
- [TEST] Screen reader announces provider completion without focus movement.
- [TEST] If search fails: error message announced and focus moved to error panel.

---

## /search/{id}/results (ResultsTable)

- [IMPL] Table: `<table>` element (not CSS grid or div-based) with proper `<thead>`, `<tbody>`, `<th scope="col">`.
- [IMPL] Sortable columns: `aria-sort="ascending"/"descending"/"none"` on `<th>`. Updated on click.
- [IMPL] Column filter inputs in header row: `aria-label="Filter by {column name}"`. Not inside the `<th>` click target for sorting — separate `<div>` below.
- [IMPL] Source badge: `aria-label="Booking.com"` / `aria-label="Airbnb"` on badge element.
- [IMPL] External link ("View on Booking.com"): `aria-label="View {property name} on Booking.com (opens in new tab)"`. Icon has `aria-hidden="true"`.
- [IMPL] Track toggle button: `aria-label="Track {property name}"` / `aria-label="Untrack {property name}"` (dynamic). `aria-pressed="true"/"false"` for toggle state.
- [IMPL] Provider failure banner: `role="alert"` so it's announced immediately on render.
- [IMPL] Empty state: `role="status"` or live region.
- [IMPL] "Export CSV" button: announces file download with `aria-live` toast or `role="status"` area.
- [IMPL] Pagination: Previous/Next buttons with `aria-label="Previous page"` / `aria-label="Next page"`. Current page announced: `aria-current="page"` or `aria-label="Page 1 of 3"`.
- [TEST] Keyboard: Tab enters table, arrow keys navigate rows (or Tab navigates between rows depending on pattern used), Enter activates Track/Untrack.
- [TEST] Sort state read by screen reader when header is activated.
- [TEST] Track toggle state change announced.

---

## IntervalSelectorModal

- [IMPL] Modal: `role="dialog"` with `aria-modal="true"`, `aria-labelledby` pointing to modal title.
- [IMPL] Focus: on open, focus moves to first radio or modal title. On close, focus returns to trigger.
- [IMPL] Focus trap: Tab/Shift-Tab cycles within modal.
- [IMPL] Escape key: closes modal, no action taken.
- [IMPL] Radio group: `<fieldset>/<legend>` or `role="radiogroup"` with `aria-labelledby`.
- [IMPL] Telegram warning: `aria-live="polite"` if shown conditionally.
- [IMPL] Error message: `role="alert"` inline inside modal.
- [TEST] Screen reader announces modal open with title.
- [TEST] Escape closes modal and restores focus to trigger.

---

## /dashboard (TrackedDashboardPage)

- [IMPL] Two sections: each with `<section>` and `aria-labelledby` pointing to its heading.
- [IMPL] Limit counter (e.g. "3 / 10 active"): descriptive `aria-label` on containing element, e.g. `aria-label="3 of 10 tracked searches active"`.
- [IMPL] Status badges: text label included (never color alone). Screen reader reads "Active", "Last run failed", etc.
- [IMPL] Untrack button per row: `aria-label="Untrack {destination} search"` / `aria-label="Untrack {property name}"`.
- [IMPL] Untrack confirmation popover: `role="dialog"` or `role="alertdialog"` with focus trap.
- [IMPL] Row removal animation: after untrack, announce removal via `aria-live="polite"` region: "{destination} search removed".
- [TEST] Untrack flow navigable and completable by keyboard only.

---

## /notifications (NotificationHistoryList)

- [IMPL] Filter dropdown: `<select>` or `role="listbox"` with proper `aria-label="Filter by notification type"`.
- [IMPL] Each notification item: structured with `<article>` or `<li>` with descriptive `aria-label`, e.g. "Price drop — Apt in Gothic Quarter — €110 to €87 — 19 July 2026".
- [IMPL] Type badges: text label visible, not icon only. If icon used, icon has `aria-hidden="true"` and adjacent text provides the label.
- [IMPL] External link "View listing": `aria-label="View {property name} (opens in new tab)"`.
- [IMPL] Pagination: same pattern as results table.
- [TEST] Filter change updates list and announces result count.

---

## /settings/telegram (TelegramLinkPage)

- [IMPL] Code display: `<code>` element or `role="region"` with `aria-label="Link code"`. Content selectable and readable by screen reader.
- [IMPL] Countdown timer: `aria-live="polite"` region updates at meaningful intervals (every 60s, not every second — to avoid noise). At expiry: `role="alert"` announces "Code expired".
- [IMPL] "Open in Telegram" button: `aria-label="Open Telegram to link your account (opens in new tab)"`.
- [IMPL] Link completion detection: when polling detects link complete, `role="alert"` announces "Telegram linked successfully".
- [IMPL] Unlink button: `aria-label="Unlink Telegram account"`.
- [IMPL] Unlink confirmation dialog: `role="alertdialog"`, focus trap, Escape cancels.
- [TEST] Countdown readable without seeing color change (audio announcement on expiry is sufficient).

---

## Color Contrast

| Element | Foreground | Background | Ratio required |
|---|---|---|---|
| Body text | — | — | ≥ 4.5:1 |
| Large text (≥18pt / ≥14pt bold) | — | — | ≥ 3:1 |
| Table cell text | — | — | ≥ 4.5:1 |
| Status badge text on colored background | — | — | ≥ 4.5:1 |
| Placeholder text | — | — | ≥ 4.5:1 |
| Disabled controls | — | — | No ratio required (disabled state) |
| Focus ring against page background | — | — | ≥ 3:1 |
| Error icon against white | #C0392B | #FFFFFF | ≥ 4.5:1 — verify |
| Success text against white | #27AE60 | #FFFFFF | ≥ 4.5:1 — verify |

**Implementation note**: Run all semantic colors through a contrast checker before finalizing. The values above are guidelines; the final implementation must be validated with a tool (e.g., axe, Colour Contrast Analyser).

---

## Non-Color Indicators (mandatory)

These states MUST be communicated without color as the sole differentiator:

| State | Color | Additional indicator |
|---|---|---|
| Error (form field) | Red | Error icon + error message text below field |
| Success (toast) | Green | Checkmark icon + text label |
| Warning | Amber | Warning triangle icon + text |
| Provider failed (progress) | Red | "×" icon + "Unavailable" text |
| Active tracked item | Green dot | "Active" text in badge |
| Failed last run | Amber dot | "Last run failed" text in badge |
| Sorted column (ascending) | — | ↑ caret icon + `aria-sort` |
| Sorted column (descending) | — | ↓ caret icon + `aria-sort` |
| Track toggle: tracked | Green fill | "Tracking ✓" text |
| Price drop notification type | Green | "↓ Price drop" text + icon |
| New listing notification type | Blue | "★ New listing" text + icon |

---

## Screen Reader Landmark Structure (per page)

All pages:
```
<header> — site nav + logo
<main> — page-specific content
<footer> — minimal (version / copyright, optional for MVP)
```

Modals and dialogs are rendered at the end of `<body>` (portal pattern) so they don't disrupt document flow.

---

## Automated Testing Gates

The following axe / Lighthouse checks must pass before any page ships:

- No `aria-*` attribute misuse.
- No `id` duplicates.
- All images have `alt` text (or `alt=""` if decorative).
- All form inputs have associated labels.
- Color contrast ratio passes for all text.
- Page has exactly one `<h1>`.
- Document has a `<title>`.
- No positive `tabindex`.
- Skip-to-main-content link present at top of page (keyboard-only visible).
