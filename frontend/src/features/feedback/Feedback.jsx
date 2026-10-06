import { useEffect, useState } from 'react'
import { feedbackApi, profileApi } from '../../api'
import { useAuth } from '../../components/AuthWrapper'
import { useProfile } from '../../hooks/useProfile.jsx'
import ErrorBanner from '../../components/ErrorBanner'

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
  const [message, setMessage] = useState('')
  const [file, setFile] = useState(null)
  const [mine, setMine] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)

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
  }, [])

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
              <p className="text-gray-800">{item.message}</p>
              <p className="mt-1 text-xs text-gray-500">
                {item.name} · {item.email}
                {item.phone ? ` · ${item.phone}` : ''}
                {item.attachment_original ? ` · 📎 ${item.attachment_original}` : ''}
              </p>
              {(item.replies || []).map((reply) => (
                <div
                  key={reply.id}
                  className="mt-2 rounded-lg border border-primary-100 bg-primary-50 p-2.5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-500">
                    Admin response
                  </p>
                  <p className="mt-0.5 text-gray-800">{reply.message}</p>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
