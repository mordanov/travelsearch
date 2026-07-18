import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from './client'
import type { LinkCodeResponse, User } from '../types/api'

export function useCurrentUser() {
  return useQuery({
    queryKey: ['current-user'],
    queryFn: () => apiClient.get<User>('/auth/me').then(r => r.data),
  })
}

export function useGenerateLinkCode() {
  return useMutation({
    mutationFn: () =>
      apiClient.post<LinkCodeResponse>('/telegram/link-code').then(r => r.data),
  })
}

export function useUnlinkTelegram() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.delete('/telegram/link'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['current-user'] })
    },
  })
}
