import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useSearchStatus } from '../api/search'

export default function SearchProgressPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data, isError } = useSearchStatus(id)

  useEffect(() => {
    if (data?.status === 'complete' || data?.status === 'partial') {
      navigate(`/search/${id}/results`, { replace: true })
    }
  }, [data?.status, id, navigate])

  if (isError) {
    return (
      <main className="progress-page">
        <p role="alert" className="error">
          Search failed. <a href="/search">Try again</a>
        </p>
      </main>
    )
  }

  const providerStatuses = data?.provider_statuses ?? {}

  return (
    <main className="progress-page">
      <h1>Searching…</h1>
      <p>Fetching results from providers. This can take up to 3 minutes.</p>

      <ul className="provider-status-list" aria-label="Provider status">
        {Object.entries(providerStatuses).map(([provider, ps]) => (
          <li key={provider} className={`provider-status provider-status--${ps.status}`}>
            <span className="provider-name">{capitalize(provider)}</span>
            <span className="provider-state">{ps.status}</span>
            {ps.results > 0 && (
              <span className="provider-count">{ps.results} found</span>
            )}
          </li>
        ))}
      </ul>

      {data?.results_count != null && data.results_count > 0 && (
        <p className="results-hint">{data.results_count} listings found so far…</p>
      )}

      {data?.status === 'failed' && (
        <p role="alert" className="error">
          Search failed. <a href="/search">Try again</a>
        </p>
      )}
    </main>
  )
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1)
}
