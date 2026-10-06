import { useState } from 'react'
import { authApi } from '../api'
import ErrorBanner from './ErrorBanner'
import Spinner from './Spinner'

/**
 * Registration step 1: prove the college email before an account exists.
 *
 * The order matters more than it looks. Previously signup created the account and
 * *then* mailed a code, so a mistyped code or a closed tab left a half-built
 * account behind - and that leftover address then blocked the real signup with
 * "email already registered". Nothing is created here, so abandoning this step
 * costs nothing.
 *
 * The response is identical whether or not the address is eligible, because it
 * must not be possible to find out who has an account by typing an address. The
 * duplicate is reported later, at the create step, once the mailbox has been
 * proven - at which point the requester owns that address anyway.
 */
export default function SignupEmail({ onVerified, onBack, offline }) {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [stage, setStage] = useState('email') // email | code
  const [busy, setBusy] = useState(false)
  const [resending, setResending] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  // Set once the code is right, so the next step knows the address is usable.
  const [verified, setVerified] = useState(false)

  const sendCode = async (event) => {
    event?.preventDefault()
    setError(null)
    const address = email.trim().toLowerCase()
    if (!address) {
      setError('Enter your college email address')
      return
    }
    setBusy(true)
    try {
      await authApi.startSignup(address)
      setStage('code')
      setNotice('If that address can receive mail, a code is on its way.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const resend = async () => {
    setResending(true)
    setError(null)
    try {
      await authApi.startSignup(email.trim().toLowerCase())
      setNotice('If that address can receive mail, a new code is on its way.')
    } catch (err) {
      setError(err.message)
    } finally {
      setResending(false)
    }
  }

  const checkCode = async (event) => {
    event.preventDefault()
    setError(null)
    if (code.trim().length !== 6) {
      setError('Enter the 6-digit code')
      return
    }
    setBusy(true)
    try {
      await authApi.verifySignup(email.trim().toLowerCase(), code.trim())
      setVerified(true)
      onVerified(email.trim().toLowerCase())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/logo-icon.svg" alt="Essential" className="w-16 h-16 mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-primary-500">essential</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <div className="card space-y-4">
          {offline && (
            <div className="p-3 rounded-lg border border-warning-200 bg-warning-50 text-warning-700 text-sm">
              Backend offline. Start it with: uvicorn main:app --port 8001
            </div>
          )}

          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {stage === 'email' ? 'Verify your college email' : 'Enter the code'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {stage === 'email'
                ? 'We check the address first, so a half-created account cannot block you later.'
                : `We sent a 6-digit code to ${email.trim().toLowerCase()}.`}
            </p>
          </div>

          {/* Order, so it is clear what happens next. */}
          <ol className="flex items-center gap-2 text-xs">
            <Step n={1} label="Email" done={stage === 'code'} active={stage === 'email'} />
            <span className="flex-1 h-px bg-gray-200" aria-hidden="true" />
            <Step n={2} label="Code" done={verified} active={stage === 'code' && !verified} />
            <span className="flex-1 h-px bg-gray-200" aria-hidden="true" />
            <Step n={3} label="Details" done={false} active={false} />
          </ol>

          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          {notice && (
            <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
              {notice}
            </div>
          )}

          {stage === 'email' ? (
            <form onSubmit={sendCode} className="space-y-4">
              <div>
                <label className="label" htmlFor="su-start-email">
                  College email
                </label>
                <input
                  id="su-start-email"
                  name="email"
                  type="email"
                  className="input-field"
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value)
                    setError(null)
                  }}
                  autoComplete="email"
                  placeholder="you@iiitdmj.ac.in"
                  required
                />
              </div>
              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? <Spinner size={18} className="text-white" /> : 'Send code'}
              </button>
            </form>
          ) : (
            <form onSubmit={checkCode} className="space-y-4">
              <div>
                <label className="label" htmlFor="su-start-code">
                  6-digit code
                </label>
                <input
                  id="su-start-code"
                  name="code"
                  inputMode="numeric"
                  maxLength={6}
                  className="input-field text-center font-mono text-lg tracking-[0.4em]"
                  value={code}
                  onChange={(event) => {
                    setCode(event.target.value.replace(/\D/g, '').slice(0, 6))
                    setError(null)
                  }}
                  autoComplete="one-time-code"
                  placeholder="000000"
                  required
                />
              </div>

              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? <Spinner size={18} className="text-white" /> : 'Verify email'}
              </button>

              <div className="flex items-center justify-between text-sm pt-1">
                <button
                  type="button"
                  onClick={resend}
                  disabled={resending}
                  className="font-medium text-primary-600 hover:underline disabled:text-gray-400 disabled:no-underline"
                >
                  {resending ? 'Sending…' : 'Resend code'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStage('email')
                    setCode('')
                    setNotice(null)
                    setError(null)
                  }}
                  className="text-gray-600 hover:underline"
                >
                  Change email
                </button>
              </div>
            </form>
          )}

          <div className="border-t border-gray-200 pt-3 text-center">
            <p className="text-sm text-gray-600">
              Already registered?{' '}
              <button
                type="button"
                onClick={onBack}
                className="font-medium text-primary-600 hover:underline"
              >
                Sign in
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

/** One step in the "email, then code, then details" sequence. */
function Step({ n, label, done, active }) {
  return (
    <li
      className={`flex items-center gap-1.5 ${active ? 'text-primary-600' : done ? 'text-success-600' : 'text-gray-400'}`}
    >
      <span
        className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold ${
          done ? 'bg-success-500 text-white' : active ? 'bg-primary-500 text-white' : 'bg-gray-200 text-gray-500'
        }`}
      >
        {done ? '✓' : n}
      </span>
      <span className="hidden sm:inline">{label}</span>
    </li>
  )
}
