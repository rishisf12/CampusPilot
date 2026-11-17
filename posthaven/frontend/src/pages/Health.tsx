import { useEffect, useState } from "react"
import { health, ready } from "@/lib/api"

export default function Health() {
  const [api, setApi] = useState<string | null>(null)
  const [readyState, setReady] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      health().then((r) => { if (!cancelled) setApi(JSON.stringify(r)) }),
      ready().then((r) => { if (!cancelled) setReady(JSON.stringify(r)) }).catch((e) => { if (!cancelled) setError(e.message) }),
    ])
    return () => { cancelled = true }
  }, [])

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">PostHaven</h1>
      <div className="grid gap-2">
        <div className="p-3 border rounded bg-white">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">API /health</div>
          <div className="font-mono text-sm">{api ?? "loading…"}</div>
        </div>
        <div className="p-3 border rounded bg-white">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">DB + Redis /health/ready</div>
          <div className="font-mono text-sm">{readyState ?? (error ? "error: " + error : "loading…")}</div>
        </div>
      </div>
    </div>
  )
}
