import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import { useCreateTrackedProperty } from '../api/tracked'
import { useAuth } from '../hooks/useAuth'
import type { PropertyListing, ProblemDetail } from '../types/api'
import type { AxiosError } from 'axios'

const INTERVAL_OPTIONS = [6, 12, 24, 48] as const
type IntervalHours = (typeof INTERVAL_OPTIONS)[number]

export default function PropertyDetailPage() {
  const { id: propertyId } = useParams<{ id: string }>()
  const { telegramLinked } = useAuth()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['property', propertyId],
    queryFn: () =>
      apiClient.get<PropertyListing>(`/property/${propertyId}`).then(r => r.data),
    enabled: !!propertyId,
  })

  const [trackOpen, setTrackOpen] = useState(false)
  const [checkIn, setCheckIn] = useState('')
  const [checkOut, setCheckOut] = useState('')
  const [interval, setInterval] = useState<IntervalHours>(24)
  const [trackError, setTrackError] = useState<string | null>(null)
  const [tracked, setTracked] = useState(false)

  const { mutate: createTracked, isPending } = useCreateTrackedProperty()

  function handleTrack() {
    if (!propertyId) return
    setTrackError(null)
    createTracked(
      { property_id: propertyId, check_in: checkIn, check_out: checkOut, interval_hours: interval },
      {
        onSuccess: () => {
          setTracked(true)
          setTrackOpen(false)
        },
        onError: err => {
          const axiosErr = err as AxiosError<ProblemDetail>
          setTrackError(axiosErr.response?.data?.detail ?? 'Failed to track property.')
        },
      }
    )
  }

  if (isLoading) return <main className="property-page"><p>Loading…</p></main>

  if (isError || !data) {
    return (
      <main className="property-page">
        <p role="alert" className="error">
          Property not found. <Link to="/search">Back to search</Link>
        </p>
      </main>
    )
  }

  return (
    <main className="property-page">
      <nav className="breadcrumb">
        <Link to="/search">Search</Link> / {data.name}
      </nav>

      <h1>{data.name}</h1>

      <dl className="property-details">
        <dt>Provider</dt>
        <dd>
          <span className={`provider-badge provider-badge--${data.provider}`}>
            {data.provider}
          </span>
        </dd>

        <dt>Price per night</dt>
        <dd>€{data.price_per_night.toFixed(2)}</dd>

        <dt>Total price</dt>
        <dd>€{data.total_price.toFixed(2)}</dd>

        {data.rating != null && (
          <>
            <dt>Rating</dt>
            <dd>{data.rating}</dd>
          </>
        )}

        {data.bedrooms != null && (
          <>
            <dt>Bedrooms</dt>
            <dd>{data.bedrooms}</dd>
          </>
        )}

        {data.bathrooms != null && (
          <>
            <dt>Bathrooms</dt>
            <dd>{data.bathrooms}</dd>
          </>
        )}

        {data.distance_km != null && (
          <>
            <dt>Distance from centre</dt>
            <dd>{data.distance_km} km</dd>
          </>
        )}

        <dt>Free cancellation</dt>
        <dd>{data.free_cancellation ? 'Yes' : 'No'}</dd>

        {data.amenities.length > 0 && (
          <>
            <dt>Amenities</dt>
            <dd>{data.amenities.join(', ')}</dd>
          </>
        )}
      </dl>

      <div className="property-actions">
        <a href={data.url} target="_blank" rel="noreferrer noopener" className="btn btn-secondary">
          View on {data.provider}
        </a>

        {tracked ? (
          <span className="badge badge-success">Tracking this property ✓</span>
        ) : (
          <button className="btn btn-primary" onClick={() => setTrackOpen(true)}>
            Track this property
          </button>
        )}
      </div>

      {trackOpen && (
        <div role="dialog" aria-modal="true" aria-label="Track property" className="modal">
          <div className="modal-content">
            <h2>Track price drops</h2>

            {!telegramLinked && (
              <p className="warning" role="status">
                Telegram not linked — alerts will be recorded in-app but not sent to Telegram.{' '}
                <Link to="/settings/telegram">Link now</Link>
              </p>
            )}

            <div className="field">
              <label htmlFor="prop-check-in">Check-in date</label>
              <input
                id="prop-check-in"
                type="date"
                value={checkIn}
                onChange={e => setCheckIn(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="prop-check-out">Check-out date</label>
              <input
                id="prop-check-out"
                type="date"
                value={checkOut}
                onChange={e => setCheckOut(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="prop-interval">Re-check interval</label>
              <select
                id="prop-interval"
                value={interval}
                onChange={e => setInterval(Number(e.target.value) as IntervalHours)}
              >
                {INTERVAL_OPTIONS.map(h => (
                  <option key={h} value={h}>Every {h}h</option>
                ))}
              </select>
            </div>

            {trackError && <p role="alert" className="error">{trackError}</p>}

            <div className="modal-actions">
              <button onClick={handleTrack} disabled={isPending || !checkIn || !checkOut}>
                {isPending ? 'Tracking…' : 'Confirm'}
              </button>
              <button onClick={() => setTrackOpen(false)} className="btn-ghost">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
