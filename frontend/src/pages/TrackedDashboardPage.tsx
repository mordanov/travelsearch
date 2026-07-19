import { useTrackedSearches, useDeleteTrackedSearch, useTrackedProperties, useDeleteTrackedProperty } from '../api/tracked'

export default function TrackedDashboardPage() {
  const {
    data: searchesData,
    isLoading: searchesLoading,
    isError: searchesError,
  } = useTrackedSearches()

  const {
    data: propertiesData,
    isLoading: propertiesLoading,
    isError: propertiesError,
  } = useTrackedProperties()

  const { mutate: deleteSearch } = useDeleteTrackedSearch()
  const { mutate: deleteProperty } = useDeleteTrackedProperty()

  return (
    <main className="tracked-page">
      <h1>Tracked</h1>

      <section aria-label="Tracked searches">
        <h2>Tracked Searches</h2>
        {searchesLoading && <p>Loading…</p>}
        {searchesError && (
          <p role="alert" className="error">Failed to load tracked searches.</p>
        )}
        {!searchesLoading && !searchesError && (
          searchesData?.items.length === 0 ? (
            <p className="empty-state">No tracked searches. <a href="/search">Start a search</a> and track it.</p>
          ) : (
            <table className="tracked-table">
              <thead>
                <tr>
                  <th>Destination</th>
                  <th>Dates</th>
                  <th>Interval</th>
                  <th>Last checked</th>
                  <th>Next run</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {searchesData?.items.map(ts => (
                  <tr key={ts.id}>
                    <td>{ts.destination}</td>
                    <td>{ts.check_in} → {ts.check_out}</td>
                    <td>Every {ts.interval_hours}h</td>
                    <td>{ts.last_successful_run_at ? formatDate(ts.last_successful_run_at) : '—'}</td>
                    <td>{ts.next_run_at ? formatDate(ts.next_run_at) : '—'}</td>
                    <td>
                      <span className={`badge badge-${ts.is_active ? 'success' : 'neutral'}`}>
                        {ts.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn-danger-small"
                        onClick={() => deleteSearch(ts.id)}
                        aria-label={`Untrack search for ${ts.destination}`}
                      >
                        Untrack
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </section>

      <section aria-label="Tracked properties">
        <h2>Tracked Properties</h2>
        {propertiesLoading && <p>Loading…</p>}
        {propertiesError && (
          <p role="alert" className="error">Failed to load tracked properties.</p>
        )}
        {!propertiesLoading && !propertiesError && (
          propertiesData?.items.length === 0 ? (
            <p className="empty-state">No tracked properties.</p>
          ) : (
            <table className="tracked-table">
              <thead>
                <tr>
                  <th>Property</th>
                  <th>Dates</th>
                  <th>Interval</th>
                  <th>Min price seen</th>
                  <th>Last checked</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {propertiesData?.items.map(tp => (
                  <tr key={tp.id}>
                    <td>{tp.name ?? tp.property_id}</td>
                    <td>{tp.check_in} → {tp.check_out}</td>
                    <td>Every {tp.interval_hours}h</td>
                    <td>{tp.min_price_seen != null ? `€${tp.min_price_seen.toFixed(2)}` : '—'}</td>
                    <td>{tp.last_successful_run_at ? formatDate(tp.last_successful_run_at) : '—'}</td>
                    <td>
                      <span className={`badge badge-${tp.is_active ? 'success' : 'neutral'}`}>
                        {tp.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn-danger-small"
                        onClick={() => deleteProperty(tp.id)}
                        aria-label={`Untrack property ${tp.name ?? tp.property_id}`}
                      >
                        Untrack
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </section>
    </main>
  )
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}
