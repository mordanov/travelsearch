# Specification — Trip Finder (Flights + Accommodation)

## Vision
Find the cheapest short trip (1–2 nights) from a home airport, combining flight and accommodation cost into a single total, across flexible dates and — by default — any destination, so the user discovers cheap getaways without knowing where they're going in advance.

This is a separate feature from accommodation search (see `specification.md`); it depends on the same accommodation Provider layer and the same Telegram/Tracking infrastructure defined in `constitution.md`, but adds a flight domain and a combined-itinerary search.

## User Story — Discover a cheap short trip
As a user, I specify a home airport, a date range (e.g. "any weekend in August"), a stay length (1–2 nights), and a total budget, so the system finds the cheapest flight + accommodation combinations across any destination, and can keep watching for new cheap trips appearing.

**Acceptance Scenarios:**
1. Given origin = my home airport, date range = all of August, nights = 1–2, budget = €150 total, when I run the search, then I get a ranked list of trips (destination, dates, flight price, accommodation price, total) sorted by total price ascending, all within budget.
2. Given the same search, when I enable tracking, then the system re-runs it periodically and alerts me via Telegram when a new trip appears under budget, or an existing destination/date combo gets cheaper than previously seen.
3. Given a search with specific destinations instead of "anywhere", then results are restricted to those destinations only.
4. Given a flight-explore check that fails or is blocked, then no accommodation scraping is attempted for that cycle, and no partial/misleading results are shown or diffed.

## Functional Requirements
1. Create a trip search: origin airport, destinations (optional — empty means "anywhere"), date range, min/max nights (1–2 for this use case, but not hardcoded), max total budget.
2. Stage 1 — flight discovery: query `FlightProvider.explore()` (Google Flights Explore / Skyscanner Everywhere) for the cheapest flight candidates in the date range; cap to top N (default 15–20) candidates per run.
3. Stage 2 — accommodation matching: for each candidate (destination, dates), query the accommodation Provider (existing Booking/Airbnb layer) for the cheapest matching 1–2 night stay.
4. Combine flight price + accommodation price into a total per candidate; discard any candidate exceeding the budget.
5. Display ranked results (cheapest total first).
6. Track a trip search: background re-run at a chosen interval, reusing the same two-stage pipeline.
7. Untrack a trip search.
8. Notify via Telegram (existing Notifier) on a new or newly-cheaper trip within budget.
9. View a single trip's full itinerary (flight details + property details, both original links).

## Non-functional
- Never brute-force accommodation checks across every destination/date combination — always narrow via flight-explore first (see constitution.md, Two-stage pipeline rule).
- Flight scraping expects a higher block rate than accommodation scraping; failed cycles are skipped, not partially trusted.
- Reuses the existing Tracking Service, Telegram Notifier, and diffing pattern from the accommodation-tracking feature — no parallel implementation.

## Data Model
- Flight (id, source, origin_airport, destination_airport, destination_city, depart_date, return_date, price, currency, airline, duration_minutes, stops, link, captured_at)
- TripSearch (id, user_id, origin_airport, destinations nullable, date_range_start, date_range_end, min_nights, max_nights, max_budget_total, interval_minutes, active, last_checked_at, created_at)
- Trip (id, trip_search_id, destination_city, destination_airport, depart_date, return_date, nights, flight_price, property_id, property_price, total_price, created_at)
- TripSearchSeenTrip (trip_search_id, destination_city, depart_date, return_date, min_total_price_seen, first_seen_at) — diff baseline, same pattern as TrackedSearchSeenProperty

## REST API
```
POST   /trip-search                 { origin_airport, destinations?, date_range_start, date_range_end, min_nights, max_nights, max_budget_total }
GET    /trip-search/{id}
GET    /trip-search/{id}/results
POST   /trip-search/{id}/track      { interval_minutes }
DELETE /trip-search/{id}/track
GET    /trip/{id}
```

## Flight Provider Interface
```python
class FlightProvider:
    async def explore(origin_airport, date_range, min_nights, max_nights) -> list[FlightCandidate]: ...
    async def search(origin_airport, destination_airport, depart_date, return_date) -> list[Flight]: ...
```
Providers: google_flights, skyscanner (both scraping-based, Playwright + proxy rotation, same anti-detection approach as accommodation providers).

## UI
- Trip search form: origin airport, date range picker, nights (1–2 default), destinations (optional multi-select, empty = anywhere), max budget.
- Trip results list: destination, dates, flight price, accommodation price, total price, links to both.
- Trip details page: full itinerary.
- "Track this trip search" toggle + interval, shown in the same unified Tracked dashboard as accommodation tracking.

## Background Flow
Scheduler (per trip-search interval) →
`FlightProvider.explore(origin, date_range, nights)` → top N cheapest candidates →
for each candidate → accommodation `Provider.search(destination, dates, nights, budget_remaining)` → cheapest matching property →
`total_price = flight_price + property_price`, discard if over budget →
rank all surviving candidates → store as Trip results →
diff against `TripSearchSeenTrip` → notify on new-or-cheaper trip via existing Telegram Notifier → update baseline

## Acceptance Criteria
- A trip search with an empty destination list searches "anywhere" reachable from the origin airport within the date range.
- Accommodation scraping is only performed for flight-explore candidates that survived stage 1 — never for the full destination/date matrix.
- A tracked trip search sends a Telegram alert within one interval cycle when a new or cheaper in-budget trip appears.
- A blocked/failed flight-explore cycle produces zero accommodation calls and zero notifications for that cycle.
- New flight provider requires no changes to the accommodation Provider layer or vice versa.
