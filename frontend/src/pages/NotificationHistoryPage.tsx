import { useState } from 'react'
import { useNotifications } from '../api/tracked'

export default function NotificationHistoryPage() {
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState<string>('')

  const { data, isLoading, isError } = useNotifications({
    page,
    size: 50,
    ...(typeFilter ? { type: typeFilter } : {}),
  })

  return (
    <main className="notifications-page">
      <h1>Notification history</h1>

      <div className="filter-row">
        <label htmlFor="notif-type">Type</label>
        <select
          id="notif-type"
          value={typeFilter}
          onChange={e => { setTypeFilter(e.target.value); setPage(1) }}
        >
          <option value="">All</option>
          <option value="new_listing">New listing</option>
          <option value="price_drop">Price drop</option>
        </select>
      </div>

      {isLoading && <p>Loading…</p>}

      {isError && (
        <p role="alert" className="error">Failed to load notifications.</p>
      )}

      {!isLoading && !isError && (
        data?.items.length === 0 ? (
          <div className="empty-state" role="status">
            <p>No notifications yet.</p>
            <p>Alerts for tracked searches and properties will appear here.</p>
          </div>
        ) : (
          <>
            <table className="notifications-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Property</th>
                  <th>Price before</th>
                  <th>Price after</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map(n => (
                  <tr key={n.id}>
                    <td>
                      <span className={`badge badge-${n.type === 'price_drop' ? 'price-drop' : 'new-listing'}`}>
                        {n.type === 'price_drop' ? 'Price drop' : 'New listing'}
                      </span>
                    </td>
                    <td>
                      <a href={n.property_url} target="_blank" rel="noreferrer noopener">
                        {n.property_name}
                      </a>
                    </td>
                    <td>{n.price_before != null ? `€${n.price_before.toFixed(2)}` : '—'}</td>
                    <td>€{n.price_after.toFixed(2)}</td>
                    <td>
                      <time dateTime={n.sent_at}>{new Date(n.sent_at).toLocaleString()}</time>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {data && data.pages > 1 && (
              <nav className="pagination" aria-label="Notification history pagination">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                  Previous
                </button>
                <span>Page {page} of {data.pages}</span>
                <button
                  onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                  disabled={page === data.pages}
                >
                  Next
                </button>
              </nav>
            )}
          </>
        )
      )}
    </main>
  )
}
