# PM Scope, Priorities & Milestone Order: Accommodation Search MVP

**Feature**: `001-accommodation-search-mvp`  
**Date**: 2026-07-19  
**Owner**: product-manager agent  
**Input**: spec.md, plan.md, tasks.md

---

## Scope Statement

Build a multi-user web application that:
1. Aggregates live accommodation listings from Booking.com and Airbnb via Playwright scraping
2. Tracks saved searches and specific properties for price drops
3. Delivers alerts through a Telegram bot
4. Provides a full in-app notification history independent of Telegram

**Out of scope (explicit)**:
- Flight search (FlightProvider is out of scope for this MVP — spec.md Assumptions)
- Self-registration (admin provisions accounts manually)
- Email or push notification channels (Telegram only)
- Caching of search results
- Mobile native app

---

## Priority Order

| Priority | User Story | Rationale |
|----------|-----------|-----------|
| P1 | US1 — Search & compare listings | Core value prop. Nothing else is testable without search results. |
| P2 | US2 — Track a saved search | Core monetization of user attention. Builds directly on US1. |
| P3 | US3 — Follow via Telegram bot | High convenience but requires US2 tracking infrastructure first. |
| P4 | US4 — Account & Telegram linking | Auth is a prerequisite already in Foundational; linking UI is the final piece. |

---

## Milestone Order & Phase Gates

### Phase 1: Setup — Target: `docker compose build` completes without errors
Tasks: T001–T008  
Unblocks: Phase 2 (all work blocked until setup is done)  
Owners: backend (T001, T002), devops (T004–T007), backend (T008), frontend (T003)

### Phase 2: Foundational — Target: `POST /auth/login` returns JWT; frontend redirects to `/login`
Tasks: T009–T029  
Unblocks: ALL user story phases  
Critical path: T009→T012→T013→T014→T015→T017 (auth chain)  
Review gate: code-reviewer reviews auth chain before Phase 3 begins

### Phase 3: US1 Search — Target (MVP gate): login → search → merged results table → export CSV
Tasks: T030–T047  
**MVP STOP GATE**: After this phase passes, US1 can be deployed and demonstrated independently.  
SC-001: each provider ≤2 min, total ≤3 min  
SC-002: unified table, no manual cross-site reconciliation  
Review gate: code-reviewer reviews Provider implementations (safe-discard contract)

### Phase 4: US2 Tracking — Target: TrackedSearch CRUD + background diff worker + NotificationLog
Tasks: T048–T069  
Depends on: Phase 2 + Phase 3 (TrackedSearch references search_id)  
Key invariant: discarded scrape cycles MUST NOT update baseline or trigger notifications (FR-013)

### Phase 5: US3 Telegram Follow — Target: `/follow <url>` creates TrackedProperty, price-drop fires alert
Tasks: T070–T085  
Depends on: Phase 2 + Phase 4 (TrackingService, TelegramNotifier, webhook endpoint)  
Key: auto-deactivation when check_in date passes (FR-014)

### Phase 6: US4 Account & Linking — Target: full Telegram linking flow end-to-end; `/list` works
Tasks: T086–T093  
Depends on: Phase 2 + Phase 5 (webhook endpoint already exists)  
One-time code must be single-use (deleted from Redis after first use)

### Phase 7: Polish — Target: mypy strict + ruff + tsc --noEmit all pass; docker compose up smoke-test passes
Tasks: T094–T101  
Depends on: all story phases complete  
SC-006 release blocker: `docker compose up` with zero manual steps

---

## Acceptance Criteria Summary (per story)

### US1 — Search & Compare (P1)
- AC1: Logged-in user submits destination + dates + filters → merged results table from both providers
- AC2: Sort by any column, apply column filters → table updates without re-search
- AC3: "Export CSV" → CSV file downloaded with all visible results
- AC4: While running → progress indicator shown, results appear as they arrive
- AC5: One provider fails → other provider results still shown, failure indicated

### US2 — Track Saved Search (P2)
- AC1: "Track this search" + interval → search saved, background monitoring begins
- AC2: Background cycle finds new listing → Telegram alert with name, price, link
- AC3: Background cycle finds price below min_price_seen → Telegram alert with old/new price
- AC4: Nothing new or cheaper → no notification sent
- AC5: Cycle is blocked/CAPTCHA'd/incomplete → discarded, no baseline update, no notification
- AC6: Tracked dashboard shows all tracked searches with status, last-checked, untrack button

### US3 — Follow Listing via Bot (P3)
- AC1: `/follow <url>` with dates → bot confirms tracking started
- AC2: `/follow <url>` without dates → bot asks to resend with dates
- AC3: `/follow <url>` unrecognized URL → error reply, nothing created
- AC4: Already tracking same property+dates → bot says already tracked, no duplicate
- AC5: Price drops below min_price_seen → Telegram alert with before/after and link
- AC6: check_in date passes → tracking auto-deactivated

### US4 — Account & Telegram Linking (P4)
- AC1: Email + password → logged in, see search form
- AC2: Wrong credentials → error shown, no session
- AC3: Deep-link + one-time code → accounts linked
- AC4: `/list` → bot replies with active tracked items
- AC5: Unlink → link removed, bot no longer responds

---

## Non-Negotiable Cross-Cutting Requirements

| Requirement | Enforced by |
|-------------|-------------|
| hashed_password never in any API response | mypy review (T094), data-isolation test (T098) |
| All tracking logic in TrackingService only — no duplication | code-reviewer gate (Phase 4) |
| All scraping via Provider interface only — no direct imports | code-reviewer gate (Phase 3) |
| Discarded cycles: no DB writes, no notifications | autotester (T063, T081) |
| Per-user data isolation | autotester (T098) |
| Per-user limits: 10 tracked searches, 20 tracked properties | backend (FR-016), autotester |
| JWT access token in React state only — never localStorage | frontend, code-reviewer |
| No live provider/Telegram calls in CI | autotester (recorded fixtures + httpx mock) |

---

## Success Criteria Status Tracking

| ID | Criterion | Owner | Phase |
|----|-----------|-------|-------|
| SC-001 | Search ≤2 min/provider, ≤3 min total | backend | Phase 3 |
| SC-002 | Unified table, no manual reconciliation | frontend | Phase 3 |
| SC-003 | Tracked search detects change within one cycle | backend + autotester | Phase 4 |
| SC-004 | `/follow` set up in one bot exchange | backend | Phase 5 |
| SC-005 | In-app notification history complete | frontend + backend | Phase 4 |
| SC-006 | `docker compose up` with zero manual steps | devops | Phase 7 |
| SC-007 | Adding provider requires no API contract changes | software-architect + backend | Phase 3 |
