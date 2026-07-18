import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStartSearch } from '../api/search'
import type { AxiosError } from 'axios'
import type { ProblemDetail } from '../types/api'

const AMENITY_OPTIONS = [
  { value: 'free_cancellation', label: 'Free cancellation' },
  { value: 'kitchen', label: 'Kitchen' },
  { value: 'wifi', label: 'WiFi' },
  { value: 'ac', label: 'Air conditioning' },
  { value: 'pool', label: 'Pool' },
]

export default function SearchPage() {
  const navigate = useNavigate()
  const { mutate: startSearch, isPending, error } = useStartSearch()

  const [destination, setDestination] = useState('')
  const [checkIn, setCheckIn] = useState('')
  const [checkOut, setCheckOut] = useState('')
  const [guests, setGuests] = useState(2)
  const [providers, setProviders] = useState<Set<'booking' | 'airbnb'>>(
    new Set(['booking', 'airbnb'])
  )
  const [priceMax, setPriceMax] = useState('')
  const [bedroomsMin, setBedroomsMin] = useState('')
  const [bathroomsMin, setBathroomsMin] = useState('')
  const [ratingMin, setRatingMin] = useState('')
  const [amenities, setAmenities] = useState<Set<string>>(new Set())

  function toggleProvider(p: 'booking' | 'airbnb') {
    setProviders(prev => {
      const next = new Set(prev)
      next.has(p) ? next.delete(p) : next.add(p)
      return next
    })
  }

  function toggleAmenity(a: string) {
    setAmenities(prev => {
      const next = new Set(prev)
      next.has(a) ? next.delete(a) : next.add(a)
      return next
    })
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (providers.size === 0) return

    startSearch(
      {
        destination,
        check_in: checkIn,
        check_out: checkOut,
        guests,
        providers: Array.from(providers),
        filters: {
          ...(priceMax ? { price_max: Number(priceMax) } : {}),
          ...(bedroomsMin ? { bedrooms_min: Number(bedroomsMin) } : {}),
          ...(bathroomsMin ? { bathrooms_min: Number(bathroomsMin) } : {}),
          ...(ratingMin ? { rating_min: Number(ratingMin) } : {}),
          ...(amenities.size > 0 ? { amenities: Array.from(amenities) } : {}),
        },
      },
      {
        onSuccess: data => {
          navigate(`/search/${data.search_id}/progress`)
        },
      }
    )
  }

  const axiosErr = error as AxiosError<ProblemDetail> | null
  const errorMsg = axiosErr
    ? (axiosErr.response?.data?.detail ?? 'Search failed. Please try again.')
    : null

  return (
    <main className="search-page">
      <h1>Search accommodation</h1>
      <form onSubmit={handleSubmit} aria-label="Accommodation search form">
        <section className="form-section">
          <h2>Trip details</h2>
          <div className="field">
            <label htmlFor="destination">Destination</label>
            <input
              id="destination"
              type="text"
              value={destination}
              onChange={e => setDestination(e.target.value)}
              placeholder="e.g. Barcelona"
              required
              disabled={isPending}
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="check-in">Check-in</label>
              <input
                id="check-in"
                type="date"
                value={checkIn}
                onChange={e => setCheckIn(e.target.value)}
                required
                disabled={isPending}
              />
            </div>
            <div className="field">
              <label htmlFor="check-out">Check-out</label>
              <input
                id="check-out"
                type="date"
                value={checkOut}
                onChange={e => setCheckOut(e.target.value)}
                required
                disabled={isPending}
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="guests">Guests</label>
            <input
              id="guests"
              type="number"
              min={1}
              max={20}
              value={guests}
              onChange={e => setGuests(Number(e.target.value))}
              required
              disabled={isPending}
            />
          </div>
        </section>

        <section className="form-section">
          <h2>Providers</h2>
          <div className="checkbox-group" role="group" aria-label="Provider selection">
            <label>
              <input
                type="checkbox"
                checked={providers.has('booking')}
                onChange={() => toggleProvider('booking')}
                disabled={isPending}
              />
              Booking.com
            </label>
            <label>
              <input
                type="checkbox"
                checked={providers.has('airbnb')}
                onChange={() => toggleProvider('airbnb')}
                disabled={isPending}
              />
              Airbnb
            </label>
          </div>
          {providers.size === 0 && (
            <p role="alert" className="error">
              Select at least one provider.
            </p>
          )}
        </section>

        <section className="form-section">
          <h2>Filters</h2>
          <div className="field-row">
            <div className="field">
              <label htmlFor="price-max">Max price/night (€)</label>
              <input
                id="price-max"
                type="number"
                min={0}
                value={priceMax}
                onChange={e => setPriceMax(e.target.value)}
                placeholder="No limit"
                disabled={isPending}
              />
            </div>
            <div className="field">
              <label htmlFor="rating-min">Min rating</label>
              <input
                id="rating-min"
                type="number"
                min={0}
                max={5}
                step={0.1}
                value={ratingMin}
                onChange={e => setRatingMin(e.target.value)}
                placeholder="Any"
                disabled={isPending}
              />
            </div>
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="bedrooms-min">Min bedrooms</label>
              <input
                id="bedrooms-min"
                type="number"
                min={0}
                value={bedroomsMin}
                onChange={e => setBedroomsMin(e.target.value)}
                placeholder="Any"
                disabled={isPending}
              />
            </div>
            <div className="field">
              <label htmlFor="bathrooms-min">Min bathrooms</label>
              <input
                id="bathrooms-min"
                type="number"
                min={0}
                value={bathroomsMin}
                onChange={e => setBathroomsMin(e.target.value)}
                placeholder="Any"
                disabled={isPending}
              />
            </div>
          </div>
          <fieldset>
            <legend>Amenities</legend>
            <div className="checkbox-group">
              {AMENITY_OPTIONS.map(opt => (
                <label key={opt.value}>
                  <input
                    type="checkbox"
                    checked={amenities.has(opt.value)}
                    onChange={() => toggleAmenity(opt.value)}
                    disabled={isPending}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </fieldset>
        </section>

        {errorMsg && (
          <p role="alert" className="error">
            {errorMsg}
          </p>
        )}

        <button type="submit" disabled={isPending || providers.size === 0}>
          {isPending ? 'Starting search…' : 'Search'}
        </button>
      </form>
    </main>
  )
}
