import { useEffect, useState, useCallback, useRef } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { useMessagesStore } from "@/features/mailbox/stores/messages"
import { accountsApi } from "@/lib/accounts"

export function MessageList({ folderId }: { folderId: string | null }) {
  const { messages, setMessages, setLoading, setNextCursor, selectedMessageId } = useMessagesStore()
  const [folderMessages, setFolderMessages] = useState<any[]>([])
  const parentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!folderId) return
    let cancelled = false
    setLoading(true)
    accountsApi.list().then((accounts: any[]) => {
      if (cancelled) return
      // Demo messages for INBOX
      const demo = [
        {
          id: "msg-1",
          uid: 1,
          message_id: "<alice-1@localhost>",
          subject: "Welcome to PostHaven",
          from_json: JSON.stringify({ name: "Alice", address: "alice@localhost" }),
          to_json: JSON.stringify([{ name: "You", address: "you@localhost" }]),
          snippet: "Thanks for joining PostHaven. Your mail account is now connected.",
          flags: JSON.stringify([]),
          size: 1024,
          has_attachments: false,
          received_at: new Date().toISOString(),
        },
        {
          id: "msg-2",
          uid: 2,
          message_id: "<alice-2@localhost>",
          subject: "Project update",
          from_json: JSON.stringify({ name: "Bob", address: "bob@localhost" }),
          to_json: JSON.stringify([{ name: "You", address: "you@localhost" }]),
          snippet: "Here are the latest designs for review.",
          flags: JSON.stringify(["\\Seen"]),
          size: 2048,
          has_attachments: true,
          received_at: new Date(Date.now() - 3600000).toISOString(),
        },
      ]
      setFolderMessages(demo)
      setMessages(demo)
      setLoading(false)
    }).catch(() => setLoading(false))
    return () => { cancelled = true }
  }, [folderId, setLoading, setMessages])

  const rowVirtualizer = useVirtualizer({
    count: folderMessages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 64,
    overscan: 10,
  })

  if (loading) {
    return (
      <div className="p-4 flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 bg-slate-200 rounded animate-pulse"></div>
        ))}
      </div>
    )
  }

  if (folderMessages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-500">
        <span className="material-symbols-rounded text-4xl mb-2">inbox</span>
        <p>No messages</p>
      </div>
    )
  }

  return (
    <div ref={parentRef} className="flex-1 overflow-auto">
      <div style={{ height: rowVirtualizer.totalSize, display: "flex", flexDirection: "column" }}>
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const msg = folderMessages[virtualRow.index]
          const flags = msg.flags ? JSON.parse(msg.flags) : []
          const isUnread = !flags.includes("\\Seen")
          const from = msg.from_json ? JSON.parse(msg.from_json) : { name: "", address: "" }
          return (
            <div
              key={msg.id}
              ref={rowVirtualizer.measureElement}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: rowVirtualizer.getSize(virtualRow.index),
                boxSizing: "border-box",
              }}
              onClick={() => {
                // In a real app this would navigate to /message/:id
              }}
              className={`flex items-center gap-3 px-4 py-3 border-b border-slate-100 cursor-pointer ${
                selectedMessageId === msg.id
                  ? "bg-blue-50 border-blue-200"
                  : "hover:bg-slate-50"
              } ${isUnread ? "font-medium text-slate-900" : "text-slate-600"} transition-colors`}
            >
              <div className="w-2 h-2 rounded-full bg-slate-300"></div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between text-sm">
                  <span className="truncate">{from.name || from.address}</span>
                  <span className="ml-2 text-xs text-slate-400 font-normal">{new Date(msg.received_at!).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between mt-0.5 text-sm">
                  <span className="truncate font-medium">{msg.subject}</span>
                  {msg.has_attachments && (
                    <span className="ml-2 text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">📎</span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-slate-500 truncate max-w-[200px]">{msg.snippet}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
