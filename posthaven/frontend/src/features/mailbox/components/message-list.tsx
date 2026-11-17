import { useEffect, useRef } from "react"
import { useMessagesStore } from "@/features/mailbox/stores/messages"
import { messagesApi } from "@/lib/messages"

function senderOf(fromJson: { name?: string; address?: string } | null | undefined): string {
  if (!fromJson) return "Unknown sender"
  return fromJson.name?.trim() || fromJson.address || "Unknown sender"
}

function dateOf(msg: { received_at?: string | null; internal_date?: string | null }): string {
  const raw = msg.received_at ?? msg.internal_date
  if (!raw) return ""
  const d = new Date(raw)
  const today = new Date()
  const sameDay = d.toDateString() === today.toDateString()
  return sameDay
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString()
}

export function MessageList({ folderId }: { folderId: string | null }) {
  const {
    messages, selectedMessageId, loading, nextCursor, setMessages,
    setSelectedMessageId, setLoading, setNextCursor,
  } = useMessagesStore()
  const reqId = useRef(0)

  useEffect(() => {
    if (!folderId) return
    const id = ++reqId.current
    setLoading(true)
    setMessages([])
    setNextCursor(null)
    messagesApi
      .list(folderId)
      .then((res) => {
        if (reqId.current !== id) return
        setMessages(res.messages)
        setNextCursor(res.next_cursor)
      })
      .finally(() => {
        if (reqId.current === id) setLoading(false)
      })
  }, [folderId, setLoading, setMessages, setNextCursor])

  const loadMore = () => {
    if (!folderId || !nextCursor) return
    setLoading(true)
    messagesApi
      .list(folderId, { cursor: nextCursor })
      .then((res) => {
        setMessages(res.messages, true)
        setNextCursor(res.next_cursor)
      })
      .finally(() => setLoading(false))
  }

  if (!folderId) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500">
        <span className="material-symbols-rounded text-4xl mb-2">inbox</span>
        <p>Select a folder</p>
      </div>
    )
  }

  if (loading && messages.length === 0) {
    return (
      <div className="p-4 flex flex-col gap-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-16 bg-slate-100 rounded animate-pulse" />
        ))}
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500">
        <span className="material-symbols-rounded text-4xl mb-2">inbox</span>
        <p>No messages</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        {messages.map((msg) => {
          const flags = msg.flags ?? []
          const isUnread = !flags.some((f) => f.includes("Seen"))
          const isFlagged = flags.some((f) => f.includes("Flagged"))
          return (
            <button
              key={msg.id}
              onClick={() => setSelectedMessageId(msg.id)}
              className={`w-full text-left flex items-start gap-3 px-4 py-3 border-b border-slate-100 transition-colors ${
                selectedMessageId === msg.id
                  ? "bg-blue-50"
                  : "hover:bg-slate-50"
              }`}
            >
              <div
                className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${
                  isUnread ? "bg-blue-600" : "bg-transparent"
                }`}
                aria-hidden
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span
                    className={`truncate ${
                      isUnread ? "font-semibold text-slate-900" : "text-slate-600"
                    }`}
                  >
                    {senderOf(msg.from_json)}
                  </span>
                  <span className="ml-2 text-xs text-slate-400 shrink-0">
                    {dateOf(msg)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-0.5 text-sm">
                  <span
                    className={`truncate ${
                      isUnread ? "font-medium text-slate-800" : "text-slate-600"
                    }`}
                  >
                    {msg.subject || "(no subject)"}
                  </span>
                  {msg.has_attachments && (
                    <span
                      className="material-symbols-rounded text-base text-slate-400 shrink-0"
                      title="Has attachments"
                    >
                      attach_file
                    </span>
                  )}
                  {isFlagged && (
                    <span className="material-symbols-rounded text-base text-amber-500 shrink-0" title="Flagged">
                      star
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-slate-500 truncate">{msg.snippet}</div>
              </div>
            </button>
          )
        })}
      </div>
      {nextCursor && (
        <div className="p-2 border-t border-slate-100">
          <button
            onClick={loadMore}
            disabled={loading}
            className="w-full py-2 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-50 rounded disabled:opacity-50"
          >
            {loading ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
    </div>
  )
}
