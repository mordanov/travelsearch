# ADR 004: Authentication — JWT + Argon2id

## Status
Accepted

## Context

TravelSearch is a multi-user application with no public registration. Each user has
access only to their own tracked items, notifications, and Telegram link. The auth
system must protect the API, support a React SPA frontend, and be hardened against
common web attacks (XSS token theft, CSRF, brute-force).

The constitution mandates: email + password login, Argon2id password hashing, JWT
sessions. The specific token storage strategy, refresh mechanism, and revocation
approach are architectural decisions.

## Decision Drivers

- SPA frontend (React 19) — token must be accessible to Axios for `Authorization`
  header injection but must not be accessible to injected scripts (XSS risk).
- Refresh tokens must survive browser tab close (UX requirement for a personal tool).
- No third-party identity provider is in scope — self-hosted auth only.
- Brute-force protection is required on the login endpoint (FR, T097).
- The system is personal/family scale — no distributed session store needed.

## Options Considered

### Option A — In-memory access token + HttpOnly refresh cookie (chosen)

- **Access token**: Short-lived (15 min), stored in React state / React Query context.
  Never written to localStorage, sessionStorage, or a cookie. Injected into each
  request via Axios interceptor.
- **Refresh token**: Long-lived (30 days), stored as `HttpOnly; Secure; SameSite=Strict`
  cookie. Not accessible to JavaScript.
- **Pros**: Access token XSS-safe (not persistent); refresh token CSRF-safe (SameSite=Strict);
  standard hardened SPA auth pattern; automatic silent refresh on 401.
- **Cons**: In-memory access token is lost on page reload — Axios interceptor must
  transparently trigger a refresh before the first API call after reload.
- **Risks**: Refresh token is vulnerable if cookies are compromised (unlikely with
  Secure + SameSite). Mitigation: Redis-backed revocation on logout.

### Option B — localStorage for both tokens

- **Pros**: Persists across page reloads without a refresh call.
- **Cons**: localStorage is accessible to any JavaScript on the page — XSS steals both
  tokens. Rejected on security grounds.
- **Risks**: Unacceptable credential exposure.

### Option C — Server-side sessions (session ID in cookie)

- **Pros**: Token never leaves the server; revocation is trivial.
- **Cons**: Requires server-side session store (Redis or DB); adds statefulness to the
  API; contradicts JWT preference in constitution.
- **Risks**: Operational complexity without meaningful benefit at this scale.

### Option D — Short-lived access token only (no refresh)

- **Pros**: Simpler — no refresh token management.
- **Cons**: 15-minute expiry forces frequent re-login for a tool users keep open all day.
  Poor UX for a personal utility.
- **Risks**: Users work around it by setting very long access token TTLs, eliminating
  the security benefit.

## Decision

**Option A**: Argon2id for password hashing (via `argon2-cffi`); HS256 JWT for access
tokens (15 min TTL); HS256 JWT for refresh tokens (30 days TTL, stored HttpOnly cookie);
Redis-backed revocation list for refresh tokens on logout; Axios 401 interceptor
triggers silent refresh-and-retry before surfacing auth errors to the user.

Brute-force protection: Redis counter per IP, max 10 attempts per 10 minutes on
`POST /auth/login`, returning HTTP 429 on breach.

## Consequences

- **Positive**: XSS cannot steal the access token (in-memory). CSRF cannot use the
  refresh token (SameSite=Strict). Logout immediately invalidates the refresh token.
- **Negative**: Page reload requires one background refresh call before the first
  authenticated API call. The Axios interceptor handles this transparently.
- **Operational/security**: `JWT_SECRET` must be at least 32 random bytes; stored
  in `.env` only, never in code or logs. Rotation requires all active sessions to
  re-authenticate (acceptable for personal use). Argon2id parameters (time=2, memory=64MB)
  are sufficient for a low-traffic personal tool — increase for higher-threat deployments.

## Validation and Fitness Functions

- `mypy --strict`: `hashed_password` never appears in any Pydantic response schema
  (T094 verification gate).
- Integration test (T098): two users cannot read each other's data — verify at API level.
- Integration test: logout → revoked token → `POST /auth/refresh` returns 401.
- Integration test: 11th login attempt from same IP within 10 min → 429.
- Security review gate (T097): brute-force rate limit implemented and tested before
  Phase 7 sign-off.

## Reversal or Migration Strategy

If a third-party identity provider is added later (e.g., Google OAuth): add an OAuth
callback route that creates/links a User row, then issues the same JWT pair. The token
handling and Axios interceptor are unchanged. Argon2id passwords coexist with OAuth
users — users with passwords can still log in directly.
