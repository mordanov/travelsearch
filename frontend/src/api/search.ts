import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import apiClient from './client'
import type {
  SearchRequest,
  SearchStatusResponse,
  SearchResultsPage,
} from '../types/api'

interface StartSearchResponse {
  search_id: string
  status: string
}

interface ResultsQueryParams {
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  provider?: string
  price_max?: number
  rating_min?: number
  free_cancellation?: boolean
  page?: number
  size?: number
}

export function useStartSearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: SearchRequest) =>
      apiClient.post<StartSearchResponse>('/search', req).then(r => r.data),
    onSuccess: data => {
      qc.invalidateQueries({ queryKey: ['search-status', data.search_id] })
    },
  })
}

export function useSearchStatus(searchId: string | undefined) {
  return useQuery({
    queryKey: ['search-status', searchId],
    queryFn: () =>
      apiClient
        .get<SearchStatusResponse>(`/search/${searchId}/status`)
        .then(r => r.data),
    enabled: !!searchId,
    refetchInterval: query => {
      const status = query.state.data?.status
      return status === 'complete' || status === 'failed' ? false : 3000
    },
  })
}

export function useSearchResults(searchId: string | undefined, params: ResultsQueryParams = {}) {
  return useQuery({
    queryKey: ['search-results', searchId, params],
    queryFn: () =>
      apiClient
        .get<SearchResultsPage>(`/search/${searchId}/results`, { params })
        .then(r => r.data),
    enabled: !!searchId,
  })
}

export function useExportCsvUrl(searchId: string | undefined): string {
  return searchId ? `/api/v1/search/${searchId}/export.csv` : ''
}

export function useExportCsv(searchId: string | undefined) {
  return useCallback(() => {
    if (!searchId) return
    const a = document.createElement('a')
    a.href = `/api/v1/search/${searchId}/export.csv`
    a.download = `search-${searchId}.csv`
    a.click()
  }, [searchId])
}
