import { createContext, useContext, useState, useCallback } from 'react'
import apiClient, { setAccessToken } from '../api/client'
import type { User } from '../types/api'

interface AuthState {
  isAuthenticated: boolean
  telegramLinked: boolean
  user: User | null
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setUser: (user: User | null) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuthState() {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    telegramLinked: false,
    user: null,
  })

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post<{ access_token: string }>('/auth/login', {
      email,
      password,
    })
    setAccessToken(data.access_token)
    setState(prev => ({ ...prev, isAuthenticated: true }))
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiClient.post('/auth/logout')
    } finally {
      setAccessToken(null)
      setState({ isAuthenticated: false, telegramLinked: false, user: null })
    }
  }, [])

  const setUser = useCallback((user: User | null) => {
    setState(prev => ({
      ...prev,
      user,
      telegramLinked: user?.telegram_is_linked ?? false,
    }))
  }, [])

  return { ...state, login, logout, setUser }
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
