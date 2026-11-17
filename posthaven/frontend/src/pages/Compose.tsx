import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { accountsApi, type MailAccount } from "@/lib/accounts"
import { messagesApi } from "@/lib/messages"

export default function Compose() {
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [accountId, setAccountId] = useState<string>("")
  const [to, setTo] = useState("")
  const [cc, setCc] = useState("")
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [showCc, setShowCc] = useState(false)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState("")
  const [sent, setSent] = useState(false)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // load accounts and preselect
  useEffect(() => {
    let cancelled = false
    accountsApi
      .list()
      .then((list) => {
        if (cancelled) return
        setAccounts(list)
        setAccountId((cur) => cur || list[0]?.id || "")
        setLoading(false)
      })
      .catch(() => setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  // prefill when replying
  useEffect(() => {
    const replyTo = searchParams.get("reply_to")
    if (!replyTo) return
    let cancelled = false
    messagesApi
      .get(replyTo)
      .then((msg) => {
        if (cancelled) return
        if (msg.from_json?.address) setTo(msg.from_json.address)
        setShowCc(Boolean(msg.to_json?.length))
        setSubject((s) => s || (msg.subject?.startsWith("Re:") ? msg.subject : `Re: ${msg.subject ?? ""}`))
      })
      .catch(() => {
        /* prefill is best-effort */
      })
    return () => {
      cancelled = true
    }
  }, [searchParams])

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!accountId) {
      setError("Select a sending account")
      return
    }
    setSending(true)
    setError("")
    const toList = to.split(",").map((s) => s.trim()).filter(Boolean)
    const ccList = cc.split(",").map((s) => s.trim()).filter(Boolean)
    try {
      await messagesApi.send({
        account_id: accountId,
        to: toList,
        cc: ccList,
        subject,
        body_text: body,
      })
      setSent(true)
      setTimeout(() => navigate("/mail"), 800)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Send failed")
    } finally {
      setSending(false)
    }
  }

  if (loading) {
    return <div className="p-4 text-slate-500">Loading…</div>
  }

  if (accounts.length === 0) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="text-slate-600">Add a mail account before composing.</p>
        <button
          onClick={() => navigate("/add-account")}
          className="px-4 py-2 rounded-md bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
        >
          Add mail account
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 p-4">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/mail")}
              className="p-2 rounded-md hover:bg-slate-200 text-slate-600"
              aria-label="Back to inbox"
            >
              <span className="material-symbols-rounded">arrow_back</span>
            </button>
            <h1 className="text-2xl font-bold text-slate-900">Compose</h1>
          </div>
          <button
            form="compose-form"
            type="submit"
            disabled={sending || sent || !accountId || !to.trim()}
            className="flex items-center gap-2 px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50"
          >
            <span className="material-symbols-rounded text-base">send</span>
            {sending ? "Sending…" : sent ? "Sent" : "Send"}
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <form id="compose-form" onSubmit={handleSend} className="space-y-4 bg-white p-6 rounded-xl border border-slate-200">
          <div>
            <label htmlFor="compose-account" className="block text-sm font-medium text-slate-700">Account</label>
            <select
              id="compose-account"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 outline-none"
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.username} ({a.provider})
                </option>
              ))}
            </select>
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="compose-to" className="block text-sm font-medium text-slate-700">To</label>
              {!showCc && (
                <button type="button" onClick={() => setShowCc(true)} className="text-xs text-blue-600 hover:text-blue-800">
                  Cc…
                </button>
              )}
            </div>
            <input
              id="compose-to"
              type="text"
              required
              placeholder="name@example.com, other@example.com"
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
          {showCc && (
            <div>
              <label htmlFor="compose-cc" className="block text-sm font-medium text-slate-700">Cc</label>
              <input
                id="compose-cc"
                type="text"
                placeholder="name@example.com"
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                value={cc}
                onChange={(e) => setCc(e.target.value)}
              />
            </div>
          )}
          <div>
            <label htmlFor="compose-subject" className="block text-sm font-medium text-slate-700">Subject</label>
            <input
              id="compose-subject"
              type="text"
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="compose-body" className="block text-sm font-medium text-slate-700">Body</label>
            <textarea
              id="compose-body"
              required
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none h-64"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
        </form>
      </div>
    </div>
  )
}
