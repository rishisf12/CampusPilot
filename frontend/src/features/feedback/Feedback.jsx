import { useEffect, useState } from 'react'
import { feedbackApi, profileApi } from '../../api'
import { useAuth } from '../../components/AuthWrapper'
import { useProfile } from '../../hooks/useProfile.jsx'
import ErrorBanner from '../../components/ErrorBanner'
import Spinner from '../../components/Spinner'

/**
 * Feedback section: text + optional file, then submit.
 *
 * Name, phone and email are fetched automatically from the profile and the
 * account - the student only types them when they are missing or wrong. A
 * phone typed here is saved back to the profile, so next time it is already
 * filled. Submissions land in the backend `feedback` table, which the future
 * admin "feedback responses" view reads via `feedbackApi.responses()`.
 */
export default function Feedback() {
  const { user } = useAuth()
  const { profile, refresh } = useProfile()

  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [file, setFile] = useState(null)
  const [mine, setMine] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const [ingestStatus, setIngestStatus] = useState(null)
  const [checkingMail, setCheckingMail] = useState(false)

  // Auto-fill from the profile/account as soon as they arrive.
  useEffect(() => {
    const full = [profile?.first_name, profile?.last_name].filter(Boolean).join(' ').trim()
    if (!name) {
      if (full) setName(full)
      else if (user?.full_name) setName(user.full_name)
      else if (user?.username) setName(user.username)
    }
    if (!phone && profile?.phone) setPhone(profile.phone)
    if (!email && user?.email) setEmail(user.email)
    // Only run when the source data first arrives, not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.first_name, profile?.last_name, profile?.phone, user?.email, user?.full_name])

  useEffect(() => {
    feedbackApi.mine().then(setMine).catch(() => {})
    // Check mail ingestion status
    feedbackApi.ingestStatus().then(setIngestStatus).catch(() => {})
  }, [])

  const checkMail = async () => {
    setCheckingMail(true)
    try {
      // Trigger mail check by calling the ingest status endpoint which may trigger a check
      // Or we can add a dedicated endpoint for triggering mail check
      const status = await feedbackApi.ingestStatus()
      setIngestStatus(status)
    } catch (err) {
      setError(err.message)
    } finally {
      setCheckingMail(false)
    }
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!message.trim()) {
      setError('Please write your feedback first.')
      return
    }
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      // Keep the phone on the profile so it auto-fills next time.
      if (phone.trim() && phone.trim() !== (profile?.phone || '')) {
        try {
          await profileApi.update({ phone: phone.trim() })
          refresh?.()
        } catch {
          // A failed phone save must not block the feedback itself.
        }
      }
      const saved = await feedbackApi.submit({
        message: message.trim(),
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim(),
        subject: subject.trim(),
        file,
      })
      setMine((prev) => [saved, ...prev])
      setMessage('')
      setFile(null)
      event.target.reset?.()
      setDone('Thanks - your feedback is recorded.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <p className="text-sm text-gray-600 max-w-xl">
          Please give us feedback to improve this app and make more convenient for you to use
        </p>
      </div>

      {ingestStatus && (
        <div className="card p-4 border-yellow-200 bg-yellow-50">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-sm text-yellow-800">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>Mail ingestion is off. Set FEED_IMAP_USER and FEED_IMAP_PASSWORD in .env (repo root) to switch it on. Items already in the feed still show.</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={checkMail}
                disabled={checkingMail}
                className="btn-secondary text-sm disabled:opacity-60"
              >
                {checkingMail ? <Spinner size="sm" /> : 'Check mail'}
              </button>
              <button
                type="button"
                onClick={() => feedbackApi.ingestStatus().then(setIngestStatus).catch(() => {})}
                className="btn-ghost text-sm"
              >
                Refresh
              </button>
            </div>
          </div>
        </div>
      )}

      <ErrorBanner message={error} onDismiss={() => setError(null)} />
      {done && (
        <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
          {done}
        </div>
      )}

      <form onSubmit={submit} className="card p-6 space-y-4">
        <div className="grid sm:grid-cols-3 gap-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Name</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Your name"
              className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Phone number</span>
            <input
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="Your phone number"
              className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Email id</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@iiitdmj.ac.in"
              className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Subject</span>
          <input
            type="text"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="Subject / title"
            className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Feedback</span>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="What should we improve?"
            rows={4}
            maxLength={5000}
            className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
        </label>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Upload file (optional)
          </span>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.csv"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="mt-1 w-full text-sm text-gray-600"
          />
          <span className="text-xs text-gray-400">PDF, image, TXT or CSV, up to the upload limit.</span>
        </label>

        <button type="submit" disabled={busy} className="btn-primary text-sm disabled:opacity-60">
          {busy ? 'Submitting…' : 'Submit'}
        </button>
      </form>

      {mine.length > 0 && (
        <div className="card p-6 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Your feedback</h3>
          {mine.map((item) => (
            <div key={item.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-sm">
              <button
                type="button"
                onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                className="w-full flex items-center justify-between text-left"
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-800">{item.subject || 'Feedback'}</span>
                  {item.attachment_original && (
                    <span className="inline-flex items-center gap-1 text-xs text-primary-600 bg-primary-50 px-2 py-0.5 rounded">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/></svg>
                      {item.attachment_original}
                    </span>
                  )}
                </div>
                <svg
                  className={`w-4 h-4 text-gray-400 transition-transform ${expandedId === item.id ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {expandedId === item.id && (
                <div className="mt-3 space-y-2 pt-3 border-t border-gray-200 animate-slide-down">
                  <p className="text-gray-800 whitespace-pre-wrap">{item.message}</p>
                  <div className="grid sm:grid-cols-2 gap-2 text-xs text-gray-500">
                    <span>{item.name} · {item.email}</span>
                    {item.phone && <span>{item.phone}</span>}
                    {item.created_at && <span>Submitted: {new Date(item.created_at).toLocaleString()}</span>}
                  </div>
                  {(item.replies || []).map((reply) => (
                    <div
                      key={reply.id}
                      className="mt-2 rounded-lg border border-primary-100 bg-primary-50 p-2.5"
                    >
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-500">
                        Admin response
                      </p>
                      <p className="mt-0.5 text-gray-800">{reply.message}</p>
                      {reply.created_at && (
                        <p className="mt-1 text-[10px] text-gray-400">
                          {new Date(reply.created_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
