import { useState } from 'react'
import { authApi, getToken } from '../api'
import { BRANCH_OPTIONS, PROGRAMMES } from '../constants'
import Spinner from './Spinner'

/**
 * Signup -> email verification -> login.
 *
 * After signup the address is pushed into the URL query string so that
 * reloading the page still shows the verification step instead of resetting
 * the flow.
 */
export default function AuthScreen({ onAuthenticated }) {
  const [step, setStep] = useState('login')
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    gender: 'Male',
    programme: 'BTech',
    semester: 1,
    branch: 'CSE A',
    username: '',
    roll_number: '',
    email: '',
    password: '',
  })
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const switchStep = (next, email) => {
    setError(null)
    setNotice(null)
    setCode('')
    setStep(next)
    if (next === 'verify') {
      const target = email || form.email
      window.history.replaceState({}, '', `?verify=${encodeURIComponent(target)}`)
    } else {
      window.history.replaceState({}, '', window.location.pathname)
    }
  }

  const handleLogin = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const data = await authApi.login(form.username.trim(), form.password)
      localStorage.setItem('campuspilot_token', data.access_token)
      onAuthenticated()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleSignup = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await authApi.signup({ ...form, semester: Number(form.semester) })
      switchStep('verify', form.email)
      setNotice(`Verification code sent to ${form.email}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleVerify = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await authApi.verifyEmail(form.email.trim(), code.trim())
      setNotice('Email verified — you can log in now.')
      switchStep('login')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleResend = async () => {
    setBusy(true)
    setError(null)
    try {
      await authApi.resendCode(form.email.trim())
      setNotice('A new verification code is on its way.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const inputClass =
    'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 outline-none'
  const labelClass = 'block text-sm font-medium text-gray-700 mb-1'
  const primaryButton =
    'w-full py-2.5 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center justify-center gap-2'

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-primary-500 rounded-2xl flex items-center justify-center mx-auto mb-3">
            <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">CampusPilot</h1>
          <p className="text-sm text-gray-500">Sign in with your IIITDMJ email address</p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-danger-50 border border-danger-200 text-danger-700 text-sm">
              {error}
            </div>
          )}
          {notice && (
            <div className="p-3 rounded-lg bg-success-50 border border-success-200 text-success-700 text-sm">
              {notice}
            </div>
          )}

          {step === 'login' && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className={labelClass} htmlFor="login-username">Username</label>
                <input id="login-username" className={inputClass} value={form.username}
                  onChange={set('username')} autoComplete="username" required />
              </div>
              <div>
                <label className={labelClass} htmlFor="login-password">Password</label>
                <input id="login-password" type="password" className={inputClass}
                  value={form.password} onChange={set('password')}
                  autoComplete="current-password" required />
              </div>
              <button type="submit" className={primaryButton} disabled={busy}>
                {busy ? <Spinner size={18} /> : 'Log in'}
              </button>
              <p className="text-sm text-gray-600 text-center">
                No account?{' '}
                <button type="button" onClick={() => switchStep('signup')}
                  className="text-primary-600 font-medium hover:underline">
                  Create one
                </button>
              </p>
            </form>
          )}

          {step === 'signup' && (
            <form onSubmit={handleSignup} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass} htmlFor="su-first">First name</label>
                  <input id="su-first" className={inputClass} value={form.first_name}
                    onChange={set('first_name')} required />
                </div>
                <div>
                  <label className={labelClass} htmlFor="su-last">Last name</label>
                  <input id="su-last" className={inputClass} value={form.last_name}
                    onChange={set('last_name')} required />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass} htmlFor="su-gender">Gender</label>
                  <select id="su-gender" className={inputClass} value={form.gender} onChange={set('gender')}>
                    <option>Male</option>
                    <option>Female</option>
                    <option>Other</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass} htmlFor="su-programme">Programme</label>
                  <select id="su-programme" className={inputClass} value={form.programme} onChange={set('programme')}>
                    {PROGRAMMES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass} htmlFor="su-semester">Semester</label>
                  <input id="su-semester" type="number" min="1" max="8" className={inputClass}
                    value={form.semester} onChange={set('semester')} required />
                </div>
                <div>
                  <label className={labelClass} htmlFor="su-branch">Branch</label>
                  <select id="su-branch" className={inputClass} value={form.branch} onChange={set('branch')}>
                    <option value="">Select branch</option>
                    {BRANCH_OPTIONS.map(b => <option key={b} value={b}>{b}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass} htmlFor="su-username">Username</label>
                  <input id="su-username" className={inputClass} value={form.username}
                    onChange={set('username')} required />
                </div>
                <div>
                  <label className={labelClass} htmlFor="su-roll">Roll number</label>
                  <input id="su-roll" className={inputClass} value={form.roll_number}
                    onChange={set('roll_number')} placeholder="23BCS125" required />
                </div>
              </div>
              <div>
                <label className={labelClass} htmlFor="su-email">College email</label>
                <input id="su-email" type="email" className={inputClass} value={form.email}
                  onChange={set('email')} placeholder="you@iiitdmj.ac.in" required />
                <p className="text-xs text-gray-500 mt-1">Must end with @iiitdmj.ac.in</p>
              </div>
              <div>
                <label className={labelClass} htmlFor="su-password">Password</label>
                <input id="su-password" type="password" className={inputClass} value={form.password}
                  onChange={set('password')} autoComplete="new-password" required />
                <p className="text-xs text-gray-500 mt-1">At least 8 characters</p>
              </div>
              <button type="submit" className={primaryButton} disabled={busy}>
                {busy ? <Spinner size={18} /> : 'Create account'}
              </button>
              <p className="text-sm text-gray-600 text-center">
                Already registered?{' '}
                <button type="button" onClick={() => switchStep('login')}
                  className="text-primary-600 font-medium hover:underline">
                  Log in
                </button>
              </p>
            </form>
          )}

          {step === 'verify' && (
            <form onSubmit={handleVerify} className="space-y-4">
              <p className="text-sm text-gray-600">
                We sent a 6-digit code to <span className="font-medium">{form.email}</span>.
                Enter it below to verify your account.
              </p>
              <div>
                <label className={labelClass} htmlFor="verify-code">Verification code</label>
                <input id="verify-code" inputMode="numeric" className={`${inputClass} text-center tracking-widest font-mono`}
                  value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} required />
              </div>
              <button type="submit" className={primaryButton} disabled={busy || code.length < 6}>
                {busy ? <Spinner size={18} /> : 'Verify email'}
              </button>
              <div className="flex justify-between text-sm">
                <button type="button" onClick={handleResend} disabled={busy}
                  className="text-primary-600 font-medium hover:underline disabled:opacity-50">
                  Resend code
                </button>
                <button type="button" onClick={() => switchStep('login')}
                  className="text-gray-600 hover:underline">
                  Back to login
                </button>
              </div>
            </form>
          )}
        </div>

        {!getToken() && (
          <p className="text-center text-xs text-gray-400 mt-6">
            CampusPilot — built for students, by students
          </p>
        )}
      </div>
    </div>
  )
}