# ADR 002: Provider and Notifier Isolation Pattern

## Status
Accepted

## Context

TravelSearch scrapes accommodation data from Booking and Airbnb. It delivers notifications
via Telegram. Each provider and notification channel:

- Has its own anti-bot stack (proxy rotation, fingerprint randomization, CAPTCHA detection).
- Changes its DOM/API structure independently and unpredictably.
- May be unavailable or blocked without affecting the rest of the system.
- Could be replaced or extended without disrupting business logic.

Without an explicit interface boundary, business logic (TrackingService, diff workers)
would directly import provider implementations, creating tight coupling that makes
testing, provider replacement, and failure isolation difficult.

## Decision Drivers

- Constitution I: "Backend MUST NOT communicate directly with provider or notifier
  implementations."
- FR-013: Blocked/CAPTCHA/incomplete scrape cycles must be discarded without side
  effects — this requires status to be a first-class return value, not an exception.
- SC-007: "Adding a new accommodation provider requires no changes to backend API
  contracts or routes."
- FR-009: TrackingService must be the single authority for tracking logic regardless
  of whether the trigger is the REST API or the Telegram bot — both must call through
  the same interface layer.
- Testability: provider contract tests must run against recorded fixtures without any
  live network calls.

## Options Considered

### Option A — Abstract Base Classes with structured result types (chosen)

- **Pros**: `Provider` ABC enforces `search()`, `details()`, `parse_url()`, `normalize()`.
  `ScrapeStatus` enum in the return value forces every caller to handle the blocked/CAPTCHA
  case explicitly. `Notifier` ABC enforces `send() -> bool` (no raises). Mypy strict
  confirms all implementations satisfy the interface at CI time.
- **Cons**: Python ABCs don't prevent direct imports at runtime — requires code review
  and linter enforcement (ruff rule: no imports of `BookingProvider` outside
  `app/providers/`).
- **Risks**: Developer accidentally imports implementation directly. Mitigation: ruff
  custom rule or import boundary check in CI.

### Option B — Plugin registry with dynamic loading

- **Pros**: Providers discovered at runtime from a registry; no static imports anywhere.
- **Cons**: Significant added complexity for a two-provider MVP; harder to type-check;
  registry management is non-obvious.
- **Risks**: Over-engineering for current scale.

### Option C — No formal interface; duck typing

- **Pros**: Less boilerplate.
- **Cons**: No static guarantee that a new provider implements all required methods;
  `ScrapeStatus` discard logic can be silently skipped; no contract tests possible.
- **Risks**: Silent bugs when new providers miss `parse_url()` or return wrong types.

## Decision

**Option A**: `Provider` and `Notifier` ABCs defined in `app/providers/base.py` and
`app/notifiers/base.py`. All scraping failures encoded in `ScrapeStatus` — never raised
as exceptions. `Notifier.send()` returns `bool` — never raises. No code outside
`app/providers/` may import `BookingProvider` or `AirbnbProvider`; no code outside
`app/notifiers/` may import `TelegramNotifier`.

The exact interface is frozen in `specs/001-accommodation-search-mvp/contracts/provider-interface.md`
and must not be changed without a spec amendment.

### Enforcement: Provider Registry DI Pattern

To prevent routes and services from importing implementations directly, provider
instances are registered at application startup and injected via FastAPI dependency:

```python
# app/core/providers.py — ONLY file that may import concrete providers
from app.providers.booking import BookingProvider
from app.providers.airbnb import AirbnbProvider
from app.providers.base import Provider

def get_provider_registry() -> dict[str, Provider]:
    return {"booking": BookingProvider(), "airbnb": AirbnbProvider()}

# app/main.py
app.state.providers = get_provider_registry()

# app/api/v1/deps.py
def get_providers(request: Request) -> dict[str, Provider]:
    return request.app.state.providers

# routes/search.py — only sees Provider ABC
async def start_search(..., providers: dict[str, Provider] = Depends(get_providers)):
    ...
```

Adding a new provider requires only a change to `app/core/providers.py` — zero changes
to routes or services (SC-007).

## Consequences

- **Positive**: Workers, TrackingService, and API routes are fully decoupled from
  provider implementations. Contract tests can run against recorded HTML fixtures
  without any live provider calls. Adding a new provider is a file addition with zero
  changes to the API surface.
- **Negative**: Each provider must implement all four methods, including `normalize()`
  which is an internal helper — this is intentional to keep normalization co-located
  with the provider's domain knowledge.
- **Operational/security**: Provider failures (blocked, CAPTCHA) are observable through
  structured log entries emitted by workers on discard. No alert is triggered by a
  discarded cycle — the baseline is unchanged.

## Validation and Fitness Functions

- `mypy --strict` on `app/` confirms all provider implementations satisfy `Provider` ABC.
- `tests/contract/test_booking_provider.py` and `test_airbnb_provider.py` run against
  recorded fixtures and assert `ScrapeStatus.OK` on clean fixtures and
  `ScrapeStatus.BLOCKED` on challenge-page fixtures.
- `tests/contract/test_telegram_notifier.py` asserts `send()` returns `False` (not
  raises) on Telegram API error.
- CI grep rule: `grep -r "from app.providers.booking import\|from app.providers.airbnb import" backend/app/` fails if any match outside `app/providers/`.

## Reversal or Migration Strategy

If a provider moves from scraping to an official API, implement the same `Provider` ABC
using the API client. No other code changes. The contract tests switch from HTML fixtures
to API response fixtures.
