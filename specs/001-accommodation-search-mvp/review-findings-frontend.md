# Code Review: Frontend Implementation
**Reviewer**: code-reviewer agent
**Date**: 2026-07-19
**Scope**: frontend/src/ — all tasks T003, T023–T027, T043–T047, T066–T069, T082, T092–T093
**Decision**: APPROVED — all blockers resolved; re-reviewed 2026-07-19

---

## Code Review Result

### Decision
CHANGES REQUESTED

### Scope Reviewed
- `frontend/src/api/client.ts` (T023)
- `frontend/src/hooks/useAuth.ts` (T024)
- `frontend/src/components/ProtectedRoute.tsx` (T025)
- `frontend/src/pages/LoginPage.tsx` (T026)
- `frontend/src/main.tsx` (T027)
- `frontend/src/pages/SearchResultsPage.tsx` (T046, T067, T084)
- `frontend/src/pages/TelegramLinkPage.tsx` (T093)
- `frontend/src/api/telegram.ts` (T092)
- `frontend/src/types/api.ts`

---

## Blockers

### Blocker 1: Wrong API endpoint in `useCurrentUser`

**Location**: `frontend/src/api/telegram.ts:7`
**Issue**: `useCurrentUser` fetches `/users/me` but the API contract (updated by software-architect on 2026-07-19) defines `GET /auth/me`. No `/users/me` endpoint exists.
**Impact**: `TelegramLinkPage` will always show a 404 error. `telegramLinked` state never populates. Telegram linking flow is completely broken.
**Required action**: Change to `/auth/me`.
```ts
// Before
queryFn: () => apiClient.get<User>('/users/me').then(r => r.data),
// After
queryFn: () => apiClient.get<User>('/auth/me').then(r => r.data),
```
**Evidence**: `contracts/api.md` — `GET /api/v1/auth/me` (added by software-architect, GAP-001).

---

### Blocker 2: `telegramLinked` always `undefined` — wrong field name

**Location**: `frontend/src/hooks/useAuth.ts:48`
**Issue**: `telegramLinked: user?.telegram_chat_id != null` references `telegram_chat_id`, which does not exist on the `User` type. Per SEC-008 and the updated API contract, the server returns `telegram_is_linked: boolean` — not the raw chat ID. TypeScript strict mode should flag this as a type error.
**Impact**: `telegramLinked` is always `undefined` (falsy). The "Telegram not linked" warning in both the track-search and track-property modals always shows, even for linked users. FR-005 warning behavior is inverted.
**Required action**: Change to `telegram_is_linked`:
```ts
telegramLinked: user?.telegram_is_linked === true,
```
**Evidence**: `frontend/src/types/api.ts:121-124` — `User` has `telegram_is_linked: boolean`, not `telegram_chat_id`.

---

### Blocker 3: Track-property sends empty `check_in` / `check_out`

**Location**: `frontend/src/pages/SearchResultsPage.tsx:101–108`
**Issue**: `confirmTrackProperty()` passes `check_in: ''` and `check_out: ''` to the API. The comment acknowledges this: *"populated from search context — see note below"*. The fix (passing dates via React Router `location.state`) is not implemented.
**Impact**: Every attempt to track a property from the results page will fail with a backend 422 (Pydantic validation error on required date fields). The feature is non-functional.
**Required action**: Read `check_in`/`check_out` from `useSearchStatus()` response — **do NOT use `location.state`** (lost on direct navigation / bookmark / refresh). The API contract has been updated (2026-07-19): `GET /search/{id}/status` now returns `destination`, `check_in`, `check_out`, `guests` fields. `SearchResultsPage` already has `searchId` from the URL; read the status via `useSearchStatus(searchId)` and pass dates to `confirmTrackProperty` from there. Guard the Confirm button if dates are absent.
**Evidence**: `SearchResultsPage.tsx:101–108`, `CreateTrackedPropertyRequest` in `api.ts` requires `check_in` and `check_out`.

---

## Major Findings

### Major 1: `TelegramLinkPage` uses `telegram_chat_id` to determine linked state

**Location**: `frontend/src/pages/TelegramLinkPage.tsx:49, 60`
**Issue**: Two additional references to the non-existent `telegram_chat_id` field:
- Line 49: `setUser({ ...user, telegram_chat_id: null })` — wrong field name, and redundant (cache invalidation re-fetches user anyway)
- Line 60: `const linked = user?.telegram_chat_id != null` — same wrong field; should use `telegram_is_linked`
**Impact**: Linked/unlinked display state on the page is always wrong. The "Link Telegram account" section always shows even after linking. TypeScript strict should catch both.
**Required action**:
- Line 49: Remove the `setUser` call entirely (the `qc.invalidateQueries` in `useUnlinkTelegram.onSuccess` already handles cache refresh).
- Line 60: `const linked = user?.telegram_is_linked === true`
**Evidence**: `types/api.ts:121–124`.

---

## Minor / Nits

### Minor 1: `isRefreshing` module-level flag is not reset on `onTokenRefreshed`

**Location**: `frontend/src/api/client.ts:60–73`
**Issue**: `isRefreshing = false` is set in the `catch` block (line 68) but not at the top of the happy path before `onTokenRefreshed` fires on line 63. If `onTokenRefreshed` (which triggers queued subscriber retries) throws, `isRefreshing` stays `true` permanently — all future 401s will queue forever.
**Impact**: Low probability edge case, but would freeze the app after any subscriber error.
**Required action**: Set `isRefreshing = false` before calling `onTokenRefreshed`:
```ts
isRefreshing = false
onTokenRefreshed(data.access_token)
```
The current code sets it after (line 63 then 64 — correct order), actually wait: line 63 calls `onTokenRefreshed` then line 64 sets `isRefreshing = false`. Swap those two lines.

### Nit 1: `useCurrentUser` is in `api/telegram.ts` but is a generic auth concern

**Location**: `frontend/src/api/telegram.ts:5–9`
**Issue**: `useCurrentUser` belongs conceptually alongside `useAuth` or in `api/auth.ts`, not `api/telegram.ts`. Not a functional issue — organisational only.
**Required action**: Consider moving to `api/auth.ts` in a future cleanup. Not a blocker.

---

## Tests and Evidence Reviewed

- `frontend/tests/LoginPage.test.tsx`: 3 tests passing. Covers submit, 401 error display, and loading state. Good coverage for the login flow.
- TypeScript strict is correctly configured (`tsconfig.json` with `strict: true`). The Blocker 2 and Major 1 issues should be caught by `tsc --noEmit`. If they are not surfaced, that indicates the User type was recently updated (from `telegram_chat_id` to `telegram_is_linked`) but not all consumers were updated — confirm with `tsc --noEmit` after fixes.

---

## Untested or Unverified Areas

- No tests for `SearchResultsPage` (sort, filter, track-search, track-property flows)
- No tests for `TelegramLinkPage` (linking, countdown, unlink)
- No tests for `SearchProgressPage` polling / auto-redirect
- No test for the Axios 401-refresh-retry interceptor logic
- These gaps are acceptable pre-backend (no real API to mock), but autotester should prioritise the interceptor and the track-property date-passing flow once backend is ready.

---

## Required Follow-Up

| # | Owner | Action |
|---|-------|--------|
| B1 | frontend | Fix `/users/me` → `/auth/me` in `api/telegram.ts` |
| B2 | frontend | Fix `telegram_chat_id` → `telegram_is_linked` in `useAuth.ts` |
| B3 | frontend | Pass `check_in`/`check_out` via Router state; fix `confirmTrackProperty` |
| M1 | frontend | Fix `telegram_chat_id` → `telegram_is_linked` in `TelegramLinkPage.tsx`; remove redundant `setUser` after unlink |
| m1 | frontend | Swap `isRefreshing = false` before `onTokenRefreshed` in `client.ts` |
| verify | code-reviewer | Re-review after fixes; run `tsc --noEmit` evidence |
