import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { composeApi, type Draft } from "@/lib/compose"
import { accountsApi, type MailAccount } from "@/lib/accounts"

export default function Compose() {
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null)
  const [to, setTo] = useState("")
  const [subject, setSubject] = useState("")
  const [body, setBody] = useState("")
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const saveDraft = async () => {
    if (!selectedAccount) return
    await composeApi.upsertDraft({
      account_id: selectedAccount,
      to_json: JSON.stringify([{ address: to }]),
      subject,
      body_text: body,
      body_html: body,
    })
  }

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveDraft()
    navigate("/health")
  }

  useEffect(() => {
    let cancelled = false
    Promise.all([
      accountsApi.list().then((a: any[]) => { if (!cancelled) setAccounts(a) }),
      composeApi.listDrafts().then((d: any[]) => { if (!cancelled) setDrafts(d) }),
    ]).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="p-4 text-slate-500">Loading…</div>

  return (
    <div className="min-h-screen bg-slate-50 p-4">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Compose</h1>
          <button
            onClick={handleSend}
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-slate-900 hover:bg-slate-800"
          >
            Send
          </button>
        </div>

        <form onSubmit={handleSend} className="space-y-4 bg-white p-6 rounded-xl border border-slate-200">
          <div>
            <label className="block text-sm font-medium text-slate-700">Account</label>
            <select
              value={selectedAccount ?? ""}
              onChange={(e) => setSelectedAccount(e.target.value || null)}
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
            >
              <option value="">Select sending account</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.username} ({a.provider})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">To</label>
            <input
              type="email"
              required
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Subject</label>
            <input
              type="text"
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Body</label>
            <textarea
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none h-64"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <p className="text-xs text-slate-500">Drafts autosave on change.</p>
        </form>

        {drafts.length > 0 && (
          <div className="mt-6 bg-white p-4 rounded-xl border border-slate-200">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Recent drafts</h2>
            <div className="space-y-2">
              {drafts.map((d) => (
                <div key={d.id} className="text-sm text-slate-600">
                  {d.subject} — {new Date(d.updated_at).toLocaleString()}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
