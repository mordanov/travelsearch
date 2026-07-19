import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthContext } from '../src/hooks/useAuth'
import LoginPage from '../src/pages/LoginPage'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async importOriginal => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

function makeAuthCtx(loginFn: (e: string, p: string) => Promise<void>) {
  return {
    isAuthenticated: false,
    telegramLinked: false,
    user: null,
    login: loginFn,
    logout: async () => {},
    setUser: () => {},
  }
}

function renderLogin(loginFn: (e: string, p: string) => Promise<void>) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AuthContext.Provider value={makeAuthCtx(loginFn)}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>
  )
}

describe('LoginPage', () => {
  beforeEach(() => mockNavigate.mockClear())

  it('renders email and password inputs', () => {
    renderLogin(async () => {})
    expect(screen.getByLabelText('Email')).toBeTruthy()
    expect(screen.getByLabelText('Password')).toBeTruthy()
  })

  it('calls login and redirects on success', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    renderLogin(login)

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'pass' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(login).toHaveBeenCalledWith('user@test.com', 'pass'))
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/search', { replace: true }))
  })

  it('shows error on 401', async () => {
    const err = Object.assign(new Error('401'), {
      isAxiosError: true,
      response: { status: 401, data: {} },
    })
    const login = vi.fn().mockRejectedValue(err)
    renderLogin(login)

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'bad@test.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid email or password.')
    )
  })
})
