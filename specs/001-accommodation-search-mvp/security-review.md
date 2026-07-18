# Security Review: Accommodation Search MVP

**Branch**: `001-accommodation-search-mvp` | **Date**: 2026-07-19
**Author**: security-architect agent
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Tasks**: [tasks.md](tasks.md)

---

## Executive Summary

The TravelSearch MVP has a reasonably security-aware design: Argon2id for passwords, HttpOnly
cookies for refresh tokens, JWT access tokens, Telegram webhook HMAC validation, and explicit
per-user data scoping. The threat model below identifies 12 actionable issues ranging from
high to low severity. Most are addressed by existing tasks (T097–T099) or are implementation
details that need explicit callouts. Three new tasks are recommended.

---

## Threat Model — STRIDE Analysis

### Trust Boundary Map

```
[Browser]  ←HTTPS→  [Nginx]  ←HTTP→  [FastAPI backend]  ←async→  [PostgreSQL]
                                    ↑                              [Redis]
[Telegram] ←HTTPS→  [Nginx]  ←HTTP→  [POST /telegram/webhook]
                                    ↓
                              [arq Worker/Scheduler]  ←Playwright→  [Booking/Airbnb]
```

Key trust boundaries:
1. Browser ↔ Nginx (TLS termination)
2. Nginx ↔ Backend (internal HTTP, trusted network)
3. Backend ↔ Telegram (webhook, HMAC validated)
4. Backend ↔ PostgreSQL/Redis (container-internal)
5. Worker ↔ External Booking/Airbnb (egress via proxy)

---

## Issues by Severity

### HIGH

#### SEC-001: Refresh Token Rotation Not Specified
**Location**: T014/T015 — `security.py`, `auth_service.py`
**Threat**: Session hijacking via stolen refresh token (long-lived).
**Description**: The plan specifies Redis-backed revocation for refresh tokens but does not
mandate token rotation (issuing a new refresh token on every `/auth/refresh` call and
invalidating the old one). Without rotation, a stolen refresh token is valid until expiry.
**Control**: On every `POST /auth/refresh`: issue a new refresh token, invalidate the old one
in Redis (add old token ID to revocation list), replace the `Set-Cookie` header. Implement
as "refresh-token rotation" in `auth_service.py`.
**Task reference**: T015 — add rotation requirement explicitly.

---

#### SEC-002: No User Ownership Check on Search-Scoped Resources
**Location**: `GET/DELETE /search/{search_id}`, `POST /tracked-searches`, `GET /tracked-properties`
**Threat**: Horizontal privilege escalation — User A reads or deletes User B's search.
**Description**: The API contract does not explicitly state that search endpoints check
`search.user_id == current_user.id`. The data model has the FK, but the route implementation
(T041) must enforce ownership or a user can enumerate UUIDs.
**Control**: All search repository queries (`get_status`, `get_results_page`, `export_csv`)
MUST filter by `user_id = current_user.id`. Return 404 (not 403) on mismatch to avoid
confirming resource existence.
**Task reference**: T042 integration tests should include cross-user access assertion.
**New task**: Add to T098 scope: assert User A cannot read/export User B's search results.

---

#### SEC-003: SSRF via `/follow <url>` Telegram Command
**Location**: T077 — `telegram_bot_service.py`, `Provider.parse_url()`
**Threat**: SSRF — attacker sends `/follow http://internal-host/secret` to the bot.
**Description**: `Provider.parse_url()` is called on attacker-controlled input. Even if no
provider matches, future code might attempt to fetch the URL. Booking/Airbnb providers
themselves could be tricked with redirect chains pointing to internal hosts.
**Control**:
- `parse_url()` MUST be a pure URL parsing function (regex/pattern matching only) — it MUST
  NOT make any network requests.
- Add an allowlist check before any network call: property URLs resolved from a Telegram
  command must match `*.booking.com/*` or `*.airbnb.com/*` (or relevant subdomains).
- Add this allowlist in `telegram_bot_service.py` before calling `Provider.parse_url()`.
**Task reference**: T077 — add allowlist requirement to implementation.

---

#### SEC-004: Telegram Webhook Secret Leakage via Error Response
**Location**: T076 — `routes/telegram.py`
**Threat**: Information disclosure — error responses on webhook endpoint reveal internals.
**Description**: The webhook handler returns 200 always (required by Telegram). But error
handling must not include stack traces or internal error details that could leak secrets or
help an attacker craft valid requests.
**Control**:
- Webhook handler MUST catch all exceptions internally and log them (via structlog) without
  surfacing details to the response body.
- The 403 on invalid secret header should return an empty body (not an error message).
- Ensure `TELEGRAM_WEBHOOK_SECRET` is never logged, even at DEBUG level.
**Task reference**: T076 — add empty-body 403 and exception swallowing explicitly.

---

### MEDIUM

#### SEC-005: Access Token Expiry Not Specified
**Location**: T014 — `security.py`
**Threat**: Stolen access token valid for too long.
**Description**: JWT access tokens are in-memory only (not stored), but their expiry window
is unspecified. A long expiry (e.g., 24h) combined with the lack of mid-session revocation
means a stolen token is valid until expiry even after logout.
**Control**: Access token expiry MUST be short: 15 minutes maximum. Refresh token expiry:
7–30 days (configurable via `.env` as `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` and
`JWT_REFRESH_TOKEN_EXPIRE_DAYS`). Log these as required `.env` vars in `.env.example` (T008).
**Task reference**: T014, T008 — add expiry config to `.env.example`.

---

#### SEC-006: Redis Revocation List Key Format Collision
**Location**: T015 — `auth_service.py`, T020 — `redis.py`
**Threat**: Key namespace collision between refresh token revocation and Telegram link codes.
**Description**: Both the refresh token revocation list and Telegram link codes use Redis.
Without explicit key namespacing, there is a risk of collision if key generation is similar.
**Control**: Enforce explicit Redis key prefixes in `redis.py`:
- Refresh token revocation: `revoked_rt:<jti>` (where `jti` is the JWT ID claim)
- Telegram link codes: `telegram_link:<code>` (already specified in data-model.md)
- Search status: `search_status:<search_id>`
Document these prefixes in `core/redis.py` as constants. Use `jti` (JWT ID claim) rather
than the full token as the revocation key.
**Task reference**: T015, T020 — add prefix constants.

---

#### SEC-007: `raw_snapshot` JSONB May Contain PII
**Location**: data-model.md — `SearchResult.raw_snapshot`
**Threat**: Privacy — raw scraped data may include reviewer names, location data, or other PII.
**Description**: `raw_snapshot` is described as "full scraped data for debugging." In
production, raw scraped data from Booking/Airbnb may include guest reviews, host personal
details, or location-derived PII.
**Control**: Either:
- (Preferred) Disable `raw_snapshot` in production (`ENABLE_RAW_SNAPSHOT=false` env flag,
  default false). Enable only in local dev.
- Or: explicitly document what fields are allowed in `raw_snapshot` and sanitize before
  storing.
**Task reference**: New task — add `ENABLE_RAW_SNAPSHOT` env flag to T008 and SearchService
(T040).

---

#### SEC-008: Telegram `telegram_chat_id` is a Long-Term Identifier
**Location**: data-model.md — `User.telegram_chat_id`
**Threat**: Privacy — Telegram chat IDs are permanent user identifiers.
**Description**: Storing `telegram_chat_id` directly links a platform identity to the user
account. If the database is compromised, this creates a permanent cross-platform identifier.
**Control**: For MVP scope this is acceptable (no alternative for bot messaging). However:
- `telegram_chat_id` MUST NOT appear in any API response except `GET /me` (if that endpoint
  exists). It must not appear in `TrackedSearch`, `TrackedProperty`, or `NotificationLog`
  responses.
- The data-model.md rule "hashed_password MUST never appear in any Pydantic response schema"
  should explicitly include `telegram_chat_id` as well.
**Task reference**: T094 mypy pass — add `telegram_chat_id` to the prohibited-in-response
schema list in plan.md notes.

---

#### SEC-009: Worker Runs with Full Database Write Privileges
**Location**: T058, T073 — workers
**Threat**: Privilege escalation — a compromised worker can write to all tables.
**Description**: The arq workers run search and property cycles. If a scraped response
contains a crafted injection payload and a bug in the parser allows arbitrary SQL construction
(unlikely with SQLAlchemy ORM but worth noting), the worker has full write access.
**Control**: For MVP scope, a dedicated read-mostly DB role for workers is impractical.
Minimum viable control:
- Ensure all worker DB writes go through the repository layer (no raw SQL in workers).
- Scraper output is always type-validated through `PropertyListing` Pydantic model before
  any DB write.
- No `text()` or `execute()` with string interpolation in any repository.
**Task reference**: T057, T058, T073 — add explicit requirement: all worker DB writes through
typed repository layer only.

---

### LOW

#### SEC-010: Missing `Strict-Transport-Security` in Nginx Headers
**Location**: T099 — `nginx.conf`
**Threat**: Protocol downgrade, MITM on first connection.
**Description**: T099 lists HSTS is missing from the security headers to add.
**Control**: Add `Strict-Transport-Security: max-age=31536000; includeSubDomains` to Nginx
TLS-serving location block. Do NOT add `preload` for MVP (requires domain submission).
**Task reference**: T099 — add HSTS to the header list.

---

#### SEC-011: One-Time Link Code Entropy
**Location**: T087 — `POST /telegram/link-code`
**Threat**: Brute force of the 8-char one-time code.
**Description**: An 8-character alphanumeric code has ~36^8 ≈ 2.8 trillion combinations,
which is sufficient for a 15-minute TTL if Redis rate-limiting is in place. However, the
code generator must use `secrets.token_urlsafe()` or `secrets.choice()` (not `random`).
**Control**: Use `secrets.token_urlsafe(6)[:8]` or similar cryptographically secure source.
Never use `random.choice()` or `uuid4()[:8]` for security-sensitive codes.
**Task reference**: T087 — add explicit note to use `secrets` module.

---

#### SEC-012: CSV Export Contains Provider URLs
**Location**: T041 — `GET /search/{id}/export.csv`
**Threat**: URL confusion — exported URLs may contain tracking parameters or session tokens
from the scraping session.
**Description**: Property URLs scraped from Booking/Airbnb may contain affiliate IDs,
session tokens, or tracking parameters embedded by the scraper's browser session. These
should not be exported to users.
**Control**: `normalize()` in each provider MUST strip known tracking/session query params
before storing the URL in `Property.url`. At minimum, strip: `aid`, `label`, `sid`,
`checkin`, `checkout` tracking params from Booking; `_set_bev`, `source_impression_id` from
Airbnb. Keep only the canonical listing path with check-in/out dates if needed.
**Task reference**: T035 (BookingProvider), T036 (AirbnbProvider) — add URL normalization.

---

## Existing Tasks — Security Coverage Assessment

| Task | Security Aspect | Assessment |
|------|-----------------|------------|
| T014 | Password hashing (Argon2id), JWT | ✅ Correct algorithm |
| T015 | Refresh token Redis revocation | ⚠️ Needs rotation (SEC-001) |
| T017 | HttpOnly Secure SameSite=Strict cookie | ✅ Correct |
| T018 | Rate-limit stub for login | ⚠️ Stub only — T097 implements it |
| T023 | Axios interceptor, 401 refresh | ✅ Correct pattern |
| T024 | In-memory access token (never localStorage) | ✅ Critical — correct |
| T076 | Telegram webhook X-Token validation | ⚠️ Needs empty-body 403 (SEC-004) |
| T097 | Login brute-force rate limiting | ✅ Correct: Redis counter, 10/IP/10min |
| T098 | Per-user data isolation integration test | ✅ Required — add search scope (SEC-002) |
| T099 | Security headers: X-Frame-Options, CSP, nosniff, Referrer | ⚠️ Add HSTS (SEC-010) |

---

## New Tasks Recommended

### T-SEC-01: Add refresh token rotation to `auth_service.py`
- On `POST /auth/refresh`: issue new refresh token, revoke old token's JTI in Redis.
- Add to revocation check: verify incoming refresh token JTI not in `revoked_rt:*` set.
- Relate to T015 (can be done as an explicit sub-requirement).

### T-SEC-02: Add URL allowlist in `telegram_bot_service.py`
- Before any `Provider.parse_url()` call on bot-received URLs, assert the URL host matches
  `booking.com` or `airbnb.com` (or configured subdomains).
- Reject and reply with error for any other host.
- Relate to T077.

### T-SEC-03: Add `ENABLE_RAW_SNAPSHOT` env flag
- Default to `false` in production.
- `SearchService` only writes `raw_snapshot` if flag is true.
- Add `ENABLE_RAW_SNAPSHOT=false` to `.env.example` (T008).

---

## Secrets Inventory

All secrets must be in `.env` (never hardcoded). Confirm each is in `.env.example` (T008):

| Secret | Env Var | Notes |
|--------|---------|-------|
| Database password | `DATABASE_URL` | Contains password in DSN |
| JWT signing key | `JWT_SECRET` | Minimum 32 bytes, random |
| Telegram bot token | `TELEGRAM_BOT_TOKEN` | Never log |
| Telegram webhook secret | `TELEGRAM_WEBHOOK_SECRET` | HMAC validation |
| Proxy credentials | `PROXY_PROVIDER_HOST/USER/PASS` | Scraper egress |
| Access token expiry | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | **New — add to T008** |
| Refresh token expiry | `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | **New — add to T008** |

---

## Security Requirements Traceability

| FR/Spec Requirement | Security Control | Implemented In |
|--------------------|-----------------|----------------|
| FR-001: Auth required | JWT + ProtectedRoute | T014–T018, T024–T025 |
| FR-015: Per-user isolation | `user_id` scoping on all queries | T040–T041, T052–T060, T098 |
| FR-013: Discard bad cycles | Worker safe-discard logic | T057–T058, T073 |
| No public registration | Admin-only provisioning | T013 (no POST /users/register route) |
| HttpOnly refresh cookie | Cookie flags | T017 |
| Telegram webhook HMAC | X-Token header check | T076 |
| Brute-force protection | Redis rate limiter | T097 |
| Security headers | Nginx config | T099 + HSTS (SEC-010) |

---

## Summary of Recommendations

| ID | Severity | Action | Effort |
|----|----------|--------|--------|
| SEC-001 | High | Add refresh token rotation in T015 | Low |
| SEC-002 | High | Add user_id ownership check on search endpoints | Low |
| SEC-003 | High | Add URL host allowlist before parse_url() in T077 | Low |
| SEC-004 | High | Empty-body 403 + swallow exceptions in T076 | Low |
| SEC-005 | Medium | Add JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15 to T008/T014 | Low |
| SEC-006 | Medium | Add Redis key prefix constants in T015/T020 | Low |
| SEC-007 | Medium | Add ENABLE_RAW_SNAPSHOT flag (default false) | Low |
| SEC-008 | Medium | Exclude telegram_chat_id from all response schemas | Low |
| SEC-009 | Medium | All worker writes via typed repository layer only | Low |
| SEC-010 | Low | Add HSTS header to T099 Nginx config | Trivial |
| SEC-011 | Low | Use secrets module in T087 link code generation | Trivial |
| SEC-012 | Low | URL normalization in T035/T036 provider normalize() | Low |
