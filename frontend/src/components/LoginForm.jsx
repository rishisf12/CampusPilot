import { useEffect, useState } from 'react'
import { clearEmailJustVerified, readEmailJustVerified } from '../lib/storage'
import ErrorBanner from './ErrorBanner'
import Spinner from './Spinner'

/**
 * Sign in. Username and password only - email is not accepted.
 *
 * "Forgot password?" opens the passkey recovery screen rather than a reset:
 * a reset would change the password, and the point is to get back in without
 * doing that.
 */
export default function LoginForm({
  onSwitchToSignup,
  onLogin,
  onForgotPassword,
  onChangeRole,
  resetNotice,
  onDismissResetNotice,
  offline,
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  // Acknowledge a just-completed verification once, then clear the flag.
  useEffect(() => {
    if (readEmailJustVerified()) {
      setNotice('Email verified. Sign in to continue.')
      clearEmailJustVerified()
    }
  }, [])

  const submit = async (event) => {
    event.preventDefault()
    setError(null)
    if (!username.trim()) {
      setError('Username is required')
      return
    }
    if (!password) {
      setError('Password is required')
      return
    }
    setLoading(true)
    try {
      await onLogin(username.trim(), password)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/logo-icon.svg" alt="Essential" className="w-16 h-16 mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-primary-500">essential</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">YOUR CAMPUS ASSISTANT</p>
        </div>

        <div className="card space-y-4">
          {offline && (
            <div className="p-3 rounded-lg border border-warning-200 bg-warning-50 text-warning-700 text-sm">
              Backend offline. Start it with: uvicorn main:app --port 8001
            </div>
          )}
          {notice && (
            <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
              {notice}
            </div>
          )}
          {resetNotice && (
            <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm flex items-start justify-between gap-2">
              <span>{resetNotice}</span>
              <button
                type="button"
                onClick={onDismissResetNotice}
                className="text-success-600 hover:text-success-700 shrink-0"
                aria-label="Dismiss"
              >
                x
              </button>
            </div>
          )}
          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label" htmlFor="login-username">
                Username
              </label>
              <input
                id="login-username"
                name="username"
                className="input-field"
                value={username}
                onChange={(event) => {
                  setUsername(event.target.value)
                  setError(null)
                }}
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label className="label" htmlFor="login-password">
                Password
              </label>
              <input
                id="login-password"
                name="password"
                type="password"
                className="input-field"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value)
                  setError(null)
                }}
                autoComplete="current-password"
                required
              />
            </div>

            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? <Spinner size={18} className="text-white" /> : 'Sign In'}
            </button>
          </form>

          {/* Below the button, as a secondary route rather than competing with it. */}
          <div className="text-center">
            <button
              type="button"
              onClick={onForgotPassword}
              className="text-sm text-primary-600 hover:text-primary-500"
            >
              Forgot password?
            </button>
          </div>

          <p className="text-sm text-gray-600 text-center pt-1">
            No account?{' '}
            <button
              type="button"
              onClick={onSwitchToSignup}
              className="font-medium text-primary-600 hover:text-primary-500"
            >
              Create one
            </button>
          </p>

          {/* Back to the role choice, for anyone in the wrong place. */}
          {onChangeRole && (
            <p className="text-center">
              <button
                type="button"
                onClick={onChangeRole}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                Not a student? Change role
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}