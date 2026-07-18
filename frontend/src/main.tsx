import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthContext, useAuthState } from './hooks/useAuth'
import './index.css'

import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import SearchPage from './pages/SearchPage'
import SearchProgressPage from './pages/SearchProgressPage'
import SearchResultsPage from './pages/SearchResultsPage'
import PropertyDetailPage from './pages/PropertyDetailPage'
import TrackedDashboardPage from './pages/TrackedDashboardPage'
import NotificationHistoryPage from './pages/NotificationHistoryPage'
import TelegramLinkPage from './pages/TelegramLinkPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

function App() {
  const auth = useAuthState()

  return (
    <AuthContext.Provider value={auth}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/search" element={<SearchPage />} />
            <Route path="/search/:id/progress" element={<SearchProgressPage />} />
            <Route path="/search/:id/results" element={<SearchResultsPage />} />
            <Route path="/property/:id" element={<PropertyDetailPage />} />
            <Route path="/tracked" element={<TrackedDashboardPage />} />
            <Route path="/notifications" element={<NotificationHistoryPage />} />
            <Route path="/settings/telegram" element={<TelegramLinkPage />} />
            <Route path="/" element={<Navigate to="/search" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  )
}

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
)
