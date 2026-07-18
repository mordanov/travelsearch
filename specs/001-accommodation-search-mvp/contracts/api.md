# REST API Contract: Accommodation Search MVP

**Base path**: `/api/v1`
**Auth**: Bearer JWT (access token) on all endpoints except `POST /auth/login` and
`POST /telegram/webhook`.
**Error format**: RFC 7807 Problem Details (`application/problem+json`):
```json
{"type": "...", "title": "...", "status": 422, "detail": "...", "instance": "..."}
```

---

## Auth

### POST /auth/login

Authenticate with email + password.

**Request**
```json
{"email": "user@example.com", "password": "secret"}
```

**Response 200**
```json
{"access_token": "<jwt>", "token_type": "bearer"}
```
Refresh token set as `HttpOnly; Secure; SameSite=Strict` cookie (`refresh_token`).

**Response 401** — invalid credentials.
**Rate limit**: applies to brute-force protection.

---

### POST /auth/refresh

Exchange refresh token cookie for a new access token.

**Response 200** — same shape as login 200.
**Response 401** — refresh token missing, expired, or revoked.

---

### POST /auth/logout

Revoke the refresh token.

**Response 204**.

---

## Search

### POST /search

Start a new live search.

**Request**
```json
{
  "destination": "Barcelona",
  "check_in": "2026-09-01",
  "check_out": "2026-09-07",
  "guests": 2,
  "providers": ["booking", "airbnb"],
  "filters": {
    "price_max": 200,
    "bedrooms_min": 1,
    "rating_min": 4.0,
    "free_cancellation": true,
    "amenities": ["wifi", "kitchen"]
  }
}
```

**Response 202**
```json
{"search_id": "<uuid>", "status": "pending"}
```

---

### GET /search/{search_id}/status

Poll for search progress.

**Response 200**
```json
{
  "search_id": "<uuid>",
  "status": "running",
  "results_count": 14,
  "provider_statuses": {
    "booking": {"status": "complete", "results": 10},
    "airbnb": {"status": "running", "results": 4}
  }
}
```
`status` values: `pending | running | partial | complete | failed`

---

### GET /search/{search_id}/results

Fetch merged results for a completed search.

**Query params**: `sort_by`, `sort_dir` (asc/desc), `provider`, `price_max`, `rating_min`,
`free_cancellation`, `page` (default 1), `size` (default 50, max 200).

**Response 200**
```json
{
  "items": [
    {
      "property_id": "<uuid>",
      "provider": "booking",
      "name": "Apt in Gothic Quarter",
      "price_per_night": 95.00,
      "total_price": 570.00,
      "rating": 4.7,
      "bedrooms": 2,
      "bathrooms": 1,
      "distance_km": 0.4,
      "free_cancellation": true,
      "amenities": ["wifi", "kitchen", "ac"],
      "url": "https://booking.com/..."
    }
  ],
  "total": 24,
  "page": 1,
  "size": 50,
  "pages": 1
}
```

---

### GET /search/{search_id}/export.csv

Download all results as CSV. Returns streaming `text/csv`.

---

## Property

### GET /property/{property_id}

Fetch property details.

**Response 200** — full property fields including amenities, description, images URLs.

---

## Tracked Searches

### POST /tracked-searches

Create a tracked search. Calls `TrackingService.create_tracked_search()`.

**Request**
```json
{"search_id": "<uuid>", "interval_hours": 24}
```
`interval_hours` MUST be one of: 6, 12, 24, 48.

**Response 201**
```json
{"id": "<uuid>", "search_id": "<uuid>", "interval_hours": 24, "next_run_at": "...", "is_active": true}
```
**Response 422** — limit exceeded (max 10 active tracked searches) or invalid interval.

---

### GET /tracked-searches

List active tracked searches for the authenticated user.

**Response 200**
```json
{
  "items": [
    {
      "id": "<uuid>",
      "search_id": "<uuid>",
      "destination": "Barcelona",
      "check_in": "2026-09-01",
      "check_out": "2026-09-07",
      "interval_hours": 24,
      "is_active": true,
      "last_successful_run_at": "2026-07-19T06:00:00Z",
      "next_run_at": "2026-07-20T06:00:00Z"
    }
  ],
  "total": 3
}
```

---

### DELETE /tracked-searches/{id}

Untrack a saved search. Sets `is_active = false`.

**Response 204**.
**Response 404** — not found or not owned by authenticated user.

---

## Tracked Properties

### POST /tracked-properties

Track a specific property. Calls `TrackingService.create_tracked_property()`.

**Request**
```json
{
  "property_id": "<uuid>",
  "check_in": "2026-09-01",
  "check_out": "2026-09-07",
  "interval_hours": 12
}
```

**Response 201**
```json
{"id": "<uuid>", "property_id": "<uuid>", "check_in": "...", "check_out": "...", "interval_hours": 12, "is_active": true}
```
**Response 422** — limit exceeded (max 20 active), invalid interval, or already tracked
(idempotent: returns existing record).

---

### GET /tracked-properties

List active tracked properties for the authenticated user.

**Response 200** — paginated list with `property_id`, `name`, `url`, `check_in`,
`check_out`, `interval_hours`, `min_price_seen`, `last_successful_run_at`, `next_run_at`.

---

### DELETE /tracked-properties/{id}

Untrack a property.

**Response 204**.

---

## Notifications

### GET /notifications

Notification history for the authenticated user. Always accessible regardless of Telegram
link status.

**Query params**: `page` (default 1), `size` (default 50, max 100), `type`
(`new_listing | price_drop`).

**Response 200**
```json
{
  "items": [
    {
      "id": "<uuid>",
      "type": "price_drop",
      "property_name": "Apt in Gothic Quarter",
      "property_url": "https://booking.com/...",
      "price_before": 110.00,
      "price_after": 87.00,
      "sent_at": "2026-07-19T08:12:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "size": 50,
  "pages": 1
}
```

---

## Telegram

### POST /telegram/webhook

Receive updates from Telegram. No Bearer auth — validated via
`X-Telegram-Bot-Api-Secret-Token` header.

**Response 200** — always (Telegram requires 200 even on handling errors).

---

### POST /telegram/link-code

Generate a one-time linking code for the authenticated user.

**Response 200**
```json
{"code": "abc123xy", "expires_in_seconds": 900, "deep_link": "https://t.me/<bot>?start=abc123xy"}
```

---

### DELETE /telegram/link

Unlink the authenticated user's Telegram account.

**Response 204**.
