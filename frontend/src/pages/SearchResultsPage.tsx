import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useSearchResults, useSearchStatus, useExportCsv } from '../api/search'
import {
  useCreateTrackedSearch,
  useCreateTrackedProperty,
  useTrackedProperties,
} from '../api/tracked'
import { useAuth } from '../hooks/useAuth'
import type { PropertyListing } from '../types/api'
import type { AxiosError } from 'axios'
import type { ProblemDetail } from '../types/api'

type SortDir = 'asc' | 'desc'

const INTERVAL_OPTIONS = [6, 12, 24, 48] as const
type IntervalHours = (typeof INTERVAL_OPTIONS)[number]

export default function SearchResultsPage() {
  const { id: searchId } = useParams<{ id: string }>()
  const { telegramLinked } = useAuth()

  const [sortBy, setSortBy] = useState<string>('price_per_night')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [page, setPage] = useState(1)
  const [filterProvider, setFilterProvider] = useState('')
  const [filterPriceMax, setFilterPriceMax] = useState('')
  const [filterRatingMin, setFilterRatingMin] = useState('')
  const [filterFreeCancellation, setFilterFreeCancellation] = useState(false)

  const [trackSearchOpen, setTrackSearchOpen] = useState(false)
  const [trackSearchInterval, setTrackSearchInterval] = useState<IntervalHours>(24)
  const [trackSearchError, setTrackSearchError] = useState<string | null>(null)
  const [trackSearchSuccess, setTrackSearchSuccess] = useState(false)

  const [trackPropertyId, setTrackPropertyId] = useState<string | null>(null)
  const [trackPropertyInterval, setTrackPropertyInterval] = useState<IntervalHours>(24)
  const [trackPropertyError, setTrackPropertyError] = useState<string | null>(null)
  const [trackPropertySuccess, setTrackPropertySuccess] = useState<string | null>(null)

  const params = {
    sort_by: sortBy,
    sort_dir: sortDir,
    ...(filterProvider ? { provider: filterProvider } : {}),
    ...(filterPriceMax ? { price_max: Number(filterPriceMax) } : {}),
    ...(filterRatingMin ? { rating_min: Number(filterRatingMin) } : {}),
    ...(filterFreeCancellation ? { free_cancellation: true } : {}),
    page,
    size: 50,
  }

  const { data: statusData } = useSearchStatus(searchId)
  const { data, isLoading, isError } = useSearchResults(searchId, params)
  const { data: trackedProps } = useTrackedProperties()
  const exportCsv = useExportCsv(searchId)

  const searchCheckIn = statusData?.check_in ?? ''
  const searchCheckOut = statusData?.check_out ?? ''

  const { mutate: createTrackedSearch, isPending: trackingSearch } = useCreateTrackedSearch()
  const { mutate: createTrackedProperty, isPending: trackingProperty } = useCreateTrackedProperty()

  function handleSort(col: string) {
    if (col === sortBy) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(col)
      setSortDir('asc')
    }
    setPage(1)
  }

  function handleTrackSearch() {
    if (!searchId) return
    setTrackSearchError(null)
    createTrackedSearch(
      { search_id: searchId, interval_hours: trackSearchInterval },
      {
        onSuccess: () => {
          setTrackSearchSuccess(true)
          setTrackSearchOpen(false)
        },
        onError: err => {
          const axiosErr = err as AxiosError<ProblemDetail>
          setTrackSearchError(
            axiosErr.response?.data?.detail ?? 'Failed to track search.'
          )
        },
      }
    )
  }

  function handleTrackProperty(listing: PropertyListing) {
    setTrackPropertyId(listing.property_id)
    setTrackPropertyError(null)
    setTrackPropertySuccess(null)
  }

  function confirmTrackProperty(listing: PropertyListing) {
    setTrackPropertyError(null)
    createTrackedProperty(
      {
        property_id: listing.property_id,
        check_in: searchCheckIn,
        check_out: searchCheckOut,
        interval_hours: trackPropertyInterval,
      },
      {
        onSuccess: () => {
          setTrackPropertySuccess(listing.property_id)
          setTrackPropertyId(null)
        },
        onError: err => {
          const axiosErr = err as AxiosError<ProblemDetail>
          setTrackPropertyError(
            axiosErr.response?.data?.detail ?? 'Failed to track property.'
          )
        },
      }
    )
  }

  const trackedPropertyIds = new Set(
    trackedProps?.items.map(tp => tp.property_id) ?? []
  )

  if (isLoading) {
    return (
      <main className="results-page">
        <p>Loading results…</p>
      </main>
    )
  }

  if (isError || !data) {
    return (
      <main className="results-page">
        <p role="alert" className="error">
          Failed to load results. <Link to="/search">New search</Link>
        </p>
      </main>
    )
  }

  return (
    <main className="results-page">
      <header className="results-header">
        <h1>Results ({data.total} listings)</h1>
        <nav className="results-actions">
          <button
            onClick={() => exportCsv()}
            className="btn btn-secondary"
          >
            Export CSV
          </button>
          {trackSearchSuccess ? (
            <span className="badge badge-success">Search tracked ✓</span>
          ) : (
            <button
              onClick={() => setTrackSearchOpen(true)}
              className="btn btn-primary"
            >
              Track this search
            </button>
          )}
        </nav>
      </header>

      {/* Track search modal */}
      {trackSearchOpen && (
        <div role="dialog" aria-modal="true" aria-label="Track search" className="modal">
          <div className="modal-content">
            <h2>Track this search</h2>
            {!telegramLinked && (
              <p className="warning" role="status">
                Telegram not linked — alerts will be recorded in-app but not sent to Telegram.{' '}
                <Link to="/settings/telegram">Link now</Link>
              </p>
            )}
            <div className="field">
              <label htmlFor="track-interval">Re-run interval</label>
              <select
                id="track-interval"
                value={trackSearchInterval}
                onChange={e => setTrackSearchInterval(Number(e.target.value) as IntervalHours)}
              >
                {INTERVAL_OPTIONS.map(h => (
                  <option key={h} value={h}>
                    Every {h}h
                  </option>
                ))}
              </select>
            </div>
            {trackSearchError && (
              <p role="alert" className="error">{trackSearchError}</p>
            )}
            <div className="modal-actions">
              <button onClick={handleTrackSearch} disabled={trackingSearch}>
                {trackingSearch ? 'Tracking…' : 'Confirm'}
              </button>
              <button onClick={() => setTrackSearchOpen(false)} className="btn-ghost">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Track property modal */}
      {trackPropertyId && (
        <div role="dialog" aria-modal="true" aria-label="Track property" className="modal">
          <div className="modal-content">
            <h2>Track property</h2>
            {!telegramLinked && (
              <p className="warning" role="status">
                Telegram not linked — alerts will be recorded in-app but not sent to Telegram.
              </p>
            )}
            <div className="field">
              <label htmlFor="prop-interval">Re-check interval</label>
              <select
                id="prop-interval"
                value={trackPropertyInterval}
                onChange={e => setTrackPropertyInterval(Number(e.target.value) as IntervalHours)}
              >
                {INTERVAL_OPTIONS.map(h => (
                  <option key={h} value={h}>
                    Every {h}h
                  </option>
                ))}
              </select>
            </div>
            {trackPropertyError && (
              <p role="alert" className="error">{trackPropertyError}</p>
            )}
            <div className="modal-actions">
              {(() => {
                const listing = data.items.find(i => i.property_id === trackPropertyId)
                return listing ? (
                  <button onClick={() => confirmTrackProperty(listing)} disabled={trackingProperty}>
                    {trackingProperty ? 'Tracking…' : 'Confirm'}
                  </button>
                ) : null
              })()}
              <button onClick={() => setTrackPropertyId(null)} className="btn-ghost">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <section className="results-filters" aria-label="Filter results">
        <div className="field-row">
          <div className="field">
            <label htmlFor="filter-provider">Provider</label>
            <select
              id="filter-provider"
              value={filterProvider}
              onChange={e => { setFilterProvider(e.target.value); setPage(1) }}
            >
              <option value="">All</option>
              <option value="booking">Booking</option>
              <option value="airbnb">Airbnb</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="filter-price">Max price/night</label>
            <input
              id="filter-price"
              type="number"
              min={0}
              value={filterPriceMax}
              onChange={e => { setFilterPriceMax(e.target.value); setPage(1) }}
              placeholder="No limit"
            />
          </div>
          <div className="field">
            <label htmlFor="filter-rating">Min rating</label>
            <input
              id="filter-rating"
              type="number"
              min={0}
              max={5}
              step={0.1}
              value={filterRatingMin}
              onChange={e => { setFilterRatingMin(e.target.value); setPage(1) }}
              placeholder="Any"
            />
          </div>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={filterFreeCancellation}
              onChange={e => { setFilterFreeCancellation(e.target.checked); setPage(1) }}
            />
            Free cancellation only
          </label>
        </div>
      </section>

      {data.items.length === 0 ? (
        <div className="empty-state" role="status">
          <p>No listings match the current filters.</p>
          <button onClick={() => {
            setFilterProvider('')
            setFilterPriceMax('')
            setFilterRatingMin('')
            setFilterFreeCancellation(false)
          }}>
            Clear filters
          </button>
        </div>
      ) : (
        <>
          <div className="table-wrapper">
            <table className="results-table">
              <thead>
                <tr>
                  <SortHeader label="Source" col="provider" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Name" col="name" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Price/night" col="price_per_night" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Total price" col="total_price" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Rating" col="rating" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Bedrooms" col="bedrooms" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Bathrooms" col="bathrooms" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <SortHeader label="Distance" col="distance_km" current={sortBy} dir={sortDir} onSort={handleSort} />
                  <th>Cancellation</th>
                  <th>Amenities</th>
                  <th>Link</th>
                  <th>Track</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map(listing => (
                  <tr key={listing.property_id}>
                    <td>
                      <span className={`provider-badge provider-badge--${listing.provider}`}>
                        {listing.provider}
                      </span>
                    </td>
                    <td>
                      <Link to={`/property/${listing.property_id}`}>{listing.name}</Link>
                    </td>
                    <td>€{listing.price_per_night.toFixed(2)}</td>
                    <td>€{listing.total_price.toFixed(2)}</td>
                    <td>{listing.rating ?? '—'}</td>
                    <td>{listing.bedrooms ?? '—'}</td>
                    <td>{listing.bathrooms ?? '—'}</td>
                    <td>{listing.distance_km != null ? `${listing.distance_km} km` : '—'}</td>
                    <td>{listing.free_cancellation ? 'Yes' : 'No'}</td>
                    <td>
                      <span title={listing.amenities.join(', ')}>
                        {listing.amenities.slice(0, 3).join(', ')}
                        {listing.amenities.length > 3 && ` +${listing.amenities.length - 3}`}
                      </span>
                    </td>
                    <td>
                      <a href={listing.url} target="_blank" rel="noreferrer noopener">
                        View
                      </a>
                    </td>
                    <td>
                      {trackPropertySuccess === listing.property_id ||
                      trackedPropertyIds.has(listing.property_id) ? (
                        <span className="badge badge-success">Tracking</span>
                      ) : (
                        <button
                          className="btn-track"
                          onClick={() => handleTrackProperty(listing)}
                          aria-label={`Track ${listing.name}`}
                        >
                          Track
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.pages > 1 && (
            <nav className="pagination" aria-label="Results pagination">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </button>
              <span>
                Page {page} of {data.pages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
              >
                Next
              </button>
            </nav>
          )}
        </>
      )}
    </main>
  )
}

interface SortHeaderProps {
  label: string
  col: string
  current: string
  dir: SortDir
  onSort: (col: string) => void
}

function SortHeader({ label, col, current, dir, onSort }: SortHeaderProps) {
  const active = col === current
  const arrow = active ? (dir === 'asc' ? ' ↑' : ' ↓') : ''
  return (
    <th>
      <button
        className="sort-btn"
        onClick={() => onSort(col)}
        aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}
      >
        {label}{arrow}
      </button>
    </th>
  )
}
