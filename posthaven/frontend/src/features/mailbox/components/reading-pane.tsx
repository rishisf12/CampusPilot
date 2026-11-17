import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { messagesApi, type Message } from "@/lib/messages"
import { useTheme } from "@/components/theme-provider"
import { sanitizeHtml } from "@/lib/sanitize"

export function ReadingPane({
  messageId,
  onDismiss,
  onChanged,
}: {
  messageId: string
  onDismiss: () => void
  onChanged?: () => void
}) {
  const { resolvedTheme } = useTheme()
  const navigate = useNavigate()
  const [msg, setMsg] = useState<Message | null>(null)
  const [error, setError] = useState("")
  const [acting, setActing] = useState(false)

  useEffect(() => {
    let cancelled = false
    setMsg(null)
    setError("")
    messagesApi
      .get(messageId)
      .then(async (full) => {
        if (cancelled) return
        setMsg(full)
        const flags = full.flags ?? []
        if (!flags.some((f) => f.includes("Seen"))) {
          try {
            await messagesApi.setFlags(full.id, ["\\Seen"], [])
            onChanged?.()
          } catch {
            // reading a message must not fail because marking read failed
          }
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load message")
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messageId])

  const moveTo = async (destination: string) => {
    if (!msg) return
    setActing(true)
    try {
      await messagesApi.move(msg.id, destination)
      onDismiss()
      onChanged?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Move failed")
    } finally {
      setActing(false)
    }
  }

  if (error) {
    return (
      <div className="flex flex-col h-full border-l border-slate-200 bg-white p-4 gap-3">
        <button onClick={onDismiss} className="self-end p-2 rounded-md hover:bg-slate-200 text-slate-600" aria-label="Close">
          <span className="material-symbols-rounded">close</span>
        </button>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    )
  }

  if (!msg) {
    return (
      <div className="flex flex-col h-full border-l border-slate-200 bg-white p-4 gap-3">
        <div className="h-7 bg-slate-100 rounded w-2/3 animate-pulse" />
        <div className="h-4 bg-slate-100 rounded w-1/3 animate-pulse" />
        <div className="h-24 bg-slate-100 rounded animate-pulse" />
      </div>
    )
  }

  const from = msg.from_json?.name?.trim() || msg.from_json?.address || "Unknown sender"
  const fromAddr = msg.from_json?.address ?? ""
  const date = msg.internal_date ?? msg.received_at ?? ""
  const html = sanitizeHtml(msg.body_html || "")

  return (
    <div className="flex flex-col h-full border-l border-slate-200 bg-white">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50 shrink-0">
        <button onClick={onDismiss} className="p-2 rounded-md hover:bg-slate-200 text-slate-600" aria-label="Close">
          <span className="material-symbols-rounded">close</span>
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(`/compose?reply_to=${encodeURIComponent(msg.id)}`)}
            className="p-2 rounded-md hover:bg-slate-200 text-slate-600"
            aria-label="Reply"
            title="Reply"
          >
            <span className="material-symbols-rounded">reply</span>
          </button>
          <button
            onClick={() => moveTo("Archive")}
            disabled={acting}
            className="p-2 rounded-md hover:bg-slate-200 text-slate-600 disabled:opacity-50"
            aria-label="Archive"
            title="Archive"
          >
            <span className="material-symbols-rounded">archive</span>
          </button>
          <button
            onClick={() => moveTo("Trash")}
            disabled={acting}
            className="p-2 rounded-md hover:bg-slate-200 text-slate-600 disabled:opacity-50"
            aria-label="Delete"
            title="Move to Trash"
          >
            <span className="material-symbols-rounded">delete</span>
          </button>
        </div>
      </div>
      <div className="p-6 overflow-y-auto flex-1">
        <div className="flex flex-col gap-1 mb-6">
          <h1 className="text-xl font-semibold text-slate-900">{msg.subject || "(no subject)"}</h1>
          <div className="text-sm text-slate-500 flex items-center gap-3 flex-wrap">
            <span>{from}</span>
            {fromAddr && from !== fromAddr && (
              <span className="text-xs text-slate-400">&lt;{fromAddr}&gt;</span>
            )}
            <span aria-hidden>·</span>
            <span>{date ? new Date(date).toLocaleString() : ""}</span>
          </div>
        </div>
        {html ? (
          <div
            className={`max-w-none text-slate-800 ${resolvedTheme === "dark" ? "prose-invert" : ""}`}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        ) : (
          <div className="text-slate-800 whitespace-pre-wrap">{msg.body_text || ""}</div>
        )}
      </div>
    </div>
  )
}
