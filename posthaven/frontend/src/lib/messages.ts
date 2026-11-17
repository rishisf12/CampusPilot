const API_BASE = import.meta.env.VITE_API_BASE ?? ""

export interface MessageListItem {
  id: string
  thread_id?: string | null
  uid: number
  message_id?: string | null
  from_json?: { name: string; address: string } | null
  to_json?: { name: string; address: string }[] | null
  subject?: string | null
  snippet?: string | null
  flags?: string[] | null
  size: number
  has_attachments: boolean
  internal_date?: string | null
  received_at?: string | null
}

export interface Message extends MessageListItem {
  account_id: string
  folder_id: string
  cc_json?: { name: string; address: string }[] | null
  bcc_json?: { name: string; address: string }[] | null
  in_reply_to?: string | null
  references?: string | null
  body_text?: string | null
  body_html?: string | null
}

export interface ListResponse {
  messages: MessageListItem[]
  next_cursor: string | null
  count: number
}

async function request(path: string, opts?: RequestInit) {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const msg = body?.detail || `Request failed (${res.status})`
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg))
  }
  if (res.status === 204) return null
  return res.json()
}

export const messagesApi = {
  list: (folderId: string, opts?: { cursor?: string | null; unreadOnly?: boolean; limit?: number }) => {
    const params = new URLSearchParams({ folder_id: folderId })
    if (opts?.cursor) params.set("cursor", opts.cursor)
    if (opts?.unreadOnly) params.set("unread_only", "true")
    if (opts?.limit) params.set("limit", String(opts.limit))
    return request(`/messages?${params}`) as Promise<ListResponse>
  },
  get: (id: string) => request(`/messages/${id}`) as Promise<Message>,
  setFlags: (id: string, add: string[], remove: string[]) =>
    request(`/messages/${id}/flags`, {
      method: "PATCH",
      body: JSON.stringify({ add, remove }),
    }) as Promise<{ flags: string[] }>,
  move: (id: string, destination: string) =>
    request(`/messages/${id}/move`, {
      method: "POST",
      body: JSON.stringify({ destination }),
    }) as Promise<{ ok: boolean; destination: string }>,
  send: (payload: {
    account_id: string
    to: string[]
    cc?: string[]
    bcc?: string[]
    subject: string
    body_text?: string
    body_html?: string
  }) =>
    request("/messages/send", {
      method: "POST",
      body: JSON.stringify(payload),
    }) as Promise<{ ok: boolean; appended_to_sent: boolean }>,
}
