import { useState, useEffect } from 'react'
import { useGenerateLinkCode, useUnlinkTelegram, useCurrentUser } from '../api/telegram'
import { useAuth } from '../hooks/useAuth'
import type { AxiosError } from 'axios'
import type { ProblemDetail } from '../types/api'

const CODE_TTL_SECONDS = 900

export default function TelegramLinkPage() {
  const { setUser } = useAuth()
  const { data: user, isLoading } = useCurrentUser()

  const { mutate: generateCode, data: linkCode, isPending: generating } = useGenerateLinkCode()
  const { mutate: unlink, isPending: unlinking } = useUnlinkTelegram()

  const [codeError, setCodeError] = useState<string | null>(null)
  const [unlinkError, setUnlinkError] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null)

  useEffect(() => {
    if (!linkCode) return
    setSecondsLeft(CODE_TTL_SECONDS)
    const timer = setInterval(() => {
      setSecondsLeft(prev => {
        if (prev == null || prev <= 1) {
          clearInterval(timer)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [linkCode])

  function handleGenerate() {
    setCodeError(null)
    generateCode(undefined, {
      onError: err => {
        const axiosErr = err as AxiosError<ProblemDetail>
        setCodeError(axiosErr.response?.data?.detail ?? 'Failed to generate code.')
      },
    })
  }

  function handleUnlink() {
    setUnlinkError(null)
    unlink(undefined, {
      onSuccess: () => {
        if (user) setUser({ ...user, telegram_is_linked: false })
      },
      onError: err => {
        const axiosErr = err as AxiosError<ProblemDetail>
        setUnlinkError(axiosErr.response?.data?.detail ?? 'Failed to unlink Telegram.')
      },
    })
  }

  if (isLoading) return <main className="telegram-page"><p>Loading…</p></main>

  const linked = user?.telegram_is_linked ?? false

  return (
    <main className="telegram-page">
      <h1>Telegram linking</h1>

      {linked ? (
        <section aria-label="Linked status">
          <p className="badge badge-success">Telegram account linked ✓</p>
          {unlinkError && <p role="alert" className="error">{unlinkError}</p>}
          <button
            className="btn btn-danger"
            onClick={handleUnlink}
            disabled={unlinking}
          >
            {unlinking ? 'Unlinking…' : 'Unlink Telegram'}
          </button>
        </section>
      ) : (
        <section aria-label="Link Telegram account">
          <p>
            Link your Telegram account to receive price-drop alerts and new listing notifications.
          </p>

          {!linkCode ? (
            <>
              {codeError && <p role="alert" className="error">{codeError}</p>}
              <button onClick={handleGenerate} disabled={generating}>
                {generating ? 'Generating…' : 'Generate linking code'}
              </button>
            </>
          ) : (
            <div className="link-code-box">
              <p>
                Open the bot using the link below and confirm the code:{' '}
                <strong>{linkCode.code}</strong>
              </p>

              <a
                href={linkCode.deep_link}
                target="_blank"
                rel="noreferrer noopener"
                className="btn btn-primary"
              >
                Open Telegram bot
              </a>

              {secondsLeft != null && secondsLeft > 0 ? (
                <p className="countdown" aria-live="polite">
                  Code expires in {Math.floor(secondsLeft / 60)}m {secondsLeft % 60}s
                </p>
              ) : (
                <p role="alert" className="error">
                  Code expired.{' '}
                  <button className="link-btn" onClick={handleGenerate} disabled={generating}>
                    Generate new code
                  </button>
                </p>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  )
}
