import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { accountsApi, type MailAccount } from "@/lib/accounts"

const STATUS_COLORS: Record<string, string> = {
  connected: "bg-green-100 text-green-700",
  error: "bg-red-100 text-red-700",
  pending: "bg-amber-100 text-amber-700",
  disabled: "bg-slate-100 text-slate-700",
}

export default function Accounts() {
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [syncing, setSyncing] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    accountsApi.list().then((list) => {
      if (!cancelled) {
        setAccounts(list)
        setLoading(false)
      }
    }).catch((err) => {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Failed to load accounts")
        setLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [])

  const handleSync = async (id: string) => {
    setSyncing(id)
    setError("")
    try {
      const stats = await accountsApi.sync(id)
      if (stats.errors?.length) setError(`Sync finished with errors: ${stats.errors.join("; ")}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed")
    } finally {
      setSyncing(null)
    }
  }

  const handleRemove = async (id: string) => {
    if (!window.confirm("Remove this account? Its mail data will be deleted.")) return
    try {
      await accountsApi.remove(id)
      setAccounts(accounts.filter((a) => a.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Remove failed")
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-600">Loading accounts…</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Mail accounts</h1>
            <p className="text-slate-600">Connect and manage your IMAP/SMTP accounts</p>
          </div>
          <button
            onClick={() => navigate("/add-account")}
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-slate-900 hover:bg-slate-800"
          >
            Add account
          </button>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 mb-6">{error}</div>
        )}

        {accounts.length === 0 && (
          <div className="bg-white p-8 rounded-xl border border-slate-200 text-center">
            <h2 className="text-lg font-medium text-slate-900 mb-2">No accounts yet</h2>
            <p className="text-slate-600 mb-4">Connect your first mail account to start syncing.</p>
            <button
              onClick={() => navigate("/add-account")}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-slate-900 hover:bg-slate-800"
            >
              Add account
            </button>
          </div>
        )}

        {accounts.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-6 py-3 text-sm font-semibold text-slate-600">Provider</th>
                  <th className="px-6 py-3 text-sm font-semibold text-slate-600">Username</th>
                  <th className="px-6 py-3 text-sm font-semibold text-slate-600">Host</th>
                  <th className="px-6 py-3 text-sm font-semibold text-slate-600">Status</th>
                  <th className="px-6 py-3 text-sm font-semibold text-slate-600">Sync</th>
                  <th className="px-6 py-3 text-sm font-semibold text-slate-600 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {accounts.map((acc) => (
                  <tr key={acc.id}>
                    <td className="px-6 py-4">
                      <span className="text-sm font-medium text-slate-900">{acc.provider}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-900">{acc.username}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-500">{acc.host}:{acc.imap_port}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[acc.status] || "bg-slate-100 text-slate-600"}`}>
                        {acc.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`text-sm ${acc.sync_enabled ? "text-green-600" : "text-slate-500"}`}>
                        {acc.sync_enabled ? "On" : "Off"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          onClick={() => handleSync(acc.id)}
                          disabled={syncing === acc.id}
                          className="text-xs text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
                        >
                          {syncing === acc.id ? "Syncing…" : "Sync now"}
                        </button>
                        <button
                          onClick={() => handleRemove(acc.id)}
                          className="text-xs text-red-600 hover:text-red-800 underline"
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-6 text-xs text-slate-500">
          First registered user is the admin. Account credentials are encrypted at rest.
        </p>
      </div>
    </div>
  )
}
