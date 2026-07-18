import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient from './client'
import type {
  TrackedSearchListResponse,
  TrackedPropertyListResponse,
  NotificationListResponse,
} from '../types/api'

interface CreateTrackedSearchRequest {
  search_id: string
  interval_hours: number
}

interface CreateTrackedPropertyRequest {
  property_id: string
  check_in: string
  check_out: string
  interval_hours: number
}

export function useTrackedSearches() {
  return useQuery({
    queryKey: ['tracked-searches'],
    queryFn: () =>
      apiClient.get<TrackedSearchListResponse>('/tracked-searches').then(r => r.data),
  })
}

export function useCreateTrackedSearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: CreateTrackedSearchRequest) =>
      apiClient.post('/tracked-searches', req).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tracked-searches'] })
    },
  })
}

export function useDeleteTrackedSearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete(`/tracked-searches/${id}`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tracked-searches'] })
    },
  })
}

export function useTrackedProperties() {
  return useQuery({
    queryKey: ['tracked-properties'],
    queryFn: () =>
      apiClient.get<TrackedPropertyListResponse>('/tracked-properties').then(r => r.data),
  })
}

export function useCreateTrackedProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: CreateTrackedPropertyRequest) =>
      apiClient.post('/tracked-properties', req).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tracked-properties'] })
    },
  })
}

export function useDeleteTrackedProperty() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete(`/tracked-properties/${id}`).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tracked-properties'] })
    },
  })
}

export function useNotifications(params: { page?: number; size?: number; type?: string } = {}) {
  return useQuery({
    queryKey: ['notifications', params],
    queryFn: () =>
      apiClient
        .get<NotificationListResponse>('/notifications', { params })
        .then(r => r.data),
  })
}
