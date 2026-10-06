import { useState } from 'react'
import ErrorBanner from '../../components/ErrorBanner'
import Spinner from '../../components/Spinner'

/**
 * Developer sign-in. Same username + password as students - the *role* on the
 * account is what opens the admin panel, and that role is granted with
 * `tools/make_admin.py`, never by signup.
 */
export default function AdminLogin({ onLogin, onBack, offline }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <div>
            <h2 className="text-lg font-semibold text-gray-900">Admin sign in</h2>
            <p className="text-sm text-gray-600 mt-1">Developer access - feedback responses live here.</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label" htmlFor="admin-username">
                Username
              </label>
              <input
                id="admin-username"
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
              <label className="label" htmlFor="admin-password">
                Password
              </label>
              <input
                id="admin-password"
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
              {loading ? <Spinner size={18} className="text-white" /> : 'Sign in as admin'}
            </button>
          </form>

          <p className="text-center">
            <button
              type="button"
              onClick={onBack}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Back to role choice
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
