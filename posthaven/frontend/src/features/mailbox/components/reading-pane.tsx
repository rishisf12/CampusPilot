import { useEffect, useState } from "react"
import { useMessagesStore } from "@/features/mailbox/stores/messages"
import { useTheme } from "@/components/theme-provider"
import { sanitizeHtml } from "@/lib/sanitize"

export function ReadingPane({
  messageId,
  onDismiss,
}: {
  messageId: string
  onDismiss: () => void
}) {
  const { messages } = useMessagesStore()
  const { resolvedTheme } = useTheme()
  const [html, setHtml] = useState("")
  const [text, setText] = useState("")
  const [subject, setSubject] = useState("")
  const [from, setFrom] = useState("")
  const [date, setDate] = useState("")

  useEffect(() => {
    const msg = messages.find((m) => m.id === messageId)
    if (!msg) return
    setSubject(msg.subject || "(no subject)")
    const fromParsed = msg.from_json ? JSON.parse(msg.from_json) : { name: "", address: "" }
    setFrom(fromParsed.name || fromParsed.address)
    setDate(msg.received_at || "")
    setText(msg.snippet || "")
    setHtml(sanitizeHtml(msg.body_html || ""))
  }, [messageId, messages])

  if (!subject) return null

  return (
    <div className="flex flex-col h-full border-l border-slate-200 bg-white">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50 shrink-0">
        <button onClick={onDismiss} className="p-2 rounded-md hover:bg-slate-200 text-slate-600" aria-label="Close">
          <span className="material-symbols-rounded">close</span>
        </button>
        <div className="flex items-center gap-2">
          <button className="p-2 rounded-md hover:bg-slate-200 text-slate-600" aria-label="Reply">
            <span className="material-symbols-rounded">reply</span>
          </button>
          <button className="p-2 rounded-md hover:bg-slate-200 text-slate-600" aria-label="Archive">
            <span className="material-symbols-rounded">archive</span>
          </button>
          <button className="p-2 rounded-md hover:bg-slate-200 text-slate-600" aria-label="Delete">
            <span className="material-symbols-rounded">delete</span>
          </button>
        </div>
      </div>
      <div className="p-6 overflow-y-auto flex-1">
        <div className="flex flex-col gap-1 mb-6">
          <h1 className="text-xl font-semibold text-slate-900">{subject}</h1>
          <div className="text-sm text-slate-500 flex items-center gap-3">
            <span>{from}</span>
            <span className="text-xs mx-1">•</span>
            <span>{date}</span>
          </div>
        </div>
        <div
          className={`prose prose-sm max-w-none ${resolvedTheme === "dark" ? "prose-invert" : ""}`}
          dangerouslySetInnerHTML={{ __html: html }}
        ></div>
        {text && !html && <div className="text-slate-700 whitespace-pre-wrap">{text}</div>}
      </div>
    </div>
  )
}
