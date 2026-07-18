export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface ProblemDetail {
  type: string
  title: string
  status: number
  detail: string
  instance?: string
}

export interface SearchRequest {
  destination: string
  check_in: string
  check_out: string
  guests: number
  providers: Array<'booking' | 'airbnb'>
  filters?: {
    price_max?: number
    bedrooms_min?: number
    bathrooms_min?: number
    rating_min?: number
    free_cancellation?: boolean
    amenities?: string[]
  }
}

export interface SearchStatusResponse {
  search_id: string
  status: 'pending' | 'running' | 'partial' | 'complete' | 'failed'
  results_count: number
  provider_statuses: Record<string, { status: string; results: number }>
  destination?: string
  check_in?: string
  check_out?: string
  guests?: number
}

export interface PropertyListing {
  property_id: string
  provider: string
  name: string
  price_per_night: number
  total_price: number
  rating: number | null
  bedrooms: number | null
  bathrooms: number | null
  distance_km: number | null
  free_cancellation: boolean
  amenities: string[]
  url: string
}

export interface SearchResultsPage {
  items: PropertyListing[]
  total: number
  page: number
  size: number
  pages: number
}

export interface TrackedSearch {
  id: string
  search_id: string
  destination: string
  check_in: string
  check_out: string
  interval_hours: number
  is_active: boolean
  last_successful_run_at: string | null
  next_run_at: string | null
}

export interface TrackedSearchListResponse {
  items: TrackedSearch[]
  total: number
}

export interface TrackedProperty {
  id: string
  property_id: string
  name?: string
  url?: string
  check_in: string
  check_out: string
  interval_hours: number
  is_active: boolean
  min_price_seen: number | null
  last_successful_run_at: string | null
  next_run_at: string | null
}

export interface TrackedPropertyListResponse {
  items: TrackedProperty[]
  total: number
}

export interface NotificationItem {
  id: string
  type: 'new_listing' | 'price_drop'
  property_name: string
  property_url: string
  price_before: number | null
  price_after: number
  sent_at: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  total: number
  page: number
  size: number
  pages: number
}

export interface LinkCodeResponse {
  code: string
  expires_in_seconds: number
  deep_link: string
}

export interface User {
  id: string
  email: string
  telegram_is_linked: boolean
}
