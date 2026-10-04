import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi, clearSession, getToken, isUnauthorized, setToken } from '../api'
import LoginForm from './LoginForm'
import SignupForm from './SignupForm'
import VerifyEmail from './VerifyEmail'
import Spinner from './Spinner'

/**
 * Auth provider.
 *
 * Owns the session and decides which screen to show.  On reload the token is
 * re-validated with `/auth/me`, retrying twice so a backend that is still
 * starting does not log the user out.  Only a genuine 401 clears the session;
 * network failures keep the user signed in so the header can show "offline".
 */
const AuthContext = createContext(null)

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthWrapper')
  return value
}

const PENDING_EMAIL_KEY = 'pending_verification_email'

export function readPendingEmail() {
  try {
    return localStorage.getItem(PENDING_EMAIL_KEY) || ''
  } catch {
    return ''
  }
}

export function writePendingEmail(email) {
  try {
    if (email) localStorage.setItem(PENDING_EMAIL_KEY, email)
    else localStorage.removeItem(PENDING_EMAIL_KEY)
  } catch {
    /* ignore */
  }
}

export default function AuthWrapper({ children }) {
  const [status, setStatus] = useState('checking') // checking | anonymous | authenticated
  const [user, setUser] = useState(null)
  const [screen, setScreen] = useState('login') // login | signup | verify
  const [offline, setOffline] = useState(false)

  const checkAuth = useCallback(async (retries = 2) => {
    if (!getToken()) {
      setStatus('anonymous')
      return
    }
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      try {
        const data = await authApi.me()
        setUser(data)
        setOffline(false)
        setStatus('authenticated')
        return
      } catch (error) {
        if (isUnauthorized(error)) {
          clearSession()
          setUser(null)
          setStatus('anonymous')
          return
        }
        // Backend unreachable: wait and retry rather than dropping the session.
        setOffline(true)
        if (attempt < retries) {
          await new Promise((resolve) => setTimeout(resolve, 1500))
        }
      }
    }
    // Still unreachable - keep the session, let the app render offline.
    setStatus('authenticated')
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  // A pending verification means the tab was closed mid-flow.
  useEffect(() => {
    if (status === 'anonymous' && readPendingEmail()) setScreen('verify')
  }, [status])

  const handleLogin = async (username, password) => {
    const data = await authApi.login(username, password)
    setToken(data.access_token)
    const profile = await authApi.me()
    setUser(profile)
    setOffline(false)
    setStatus('authenticated')
    return profile
  }

  const handleLogout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      /* the client-side token removal is what actually ends the session */
    }
    clearSession()
    setUser(null)
    setStatus('anonymous')
    setScreen('login')
  }, [])

  if (status === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Spinner size={32} className="text-primary-500" />
      </div>
    )
  }

  if (status === 'anonymous') {
    if (screen === 'signup') {
      return (
        <SignupForm
          onSwitchToLogin={() => setScreen('login')}
          onSwitchToVerify={(email) => {
            writePendingEmail(email)
            setScreen('verify')
          }}
        />
      )
    }
    if (screen === 'verify') {
      return <VerifyEmail onVerified={() => setScreen('login')} onStartOver={() => setScreen('signup')} />
    }
    return (
      <LoginForm
        onSwitchToSignup={() => setScreen('signup')}
        onLogin={handleLogin}
        offline={offline}
      />
    )
  }

  return (
    <AuthContext.Provider value={{ user, logout: handleLogout, refresh: checkAuth, offline }}>
      {children}
    </AuthContext.Provider>
  )
}