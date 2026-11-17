const API_BASE = import.meta.env.VITE_API_BASE ?? "/api"

export interface Draft {
  id: string
  account_id: string
  identity_id?: string | null
  to_json: string
  cc_json?: string | null
  bcc_json?: string | null
  subject: string
  body_text?: string | null
  body_html?: string | null
  updated_at: string
}

export interface ScheduledSend {
  id: string
  status: string
  send_at: string
  subject: string
  error_message?: string | null
}

export interface Template {
  id: string
  name: string
  subject?: string | null
  body_html?: string | null
  body_text?: string | null
}

async function request(path: string, opts?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    credentials: "include",
    ...opts,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const msg = body?.detail || `Request failed (${res.status})`
    throw new Error(msg)
  }
  if (res.status === 204) return null
  return res.json()
}

export const composeApi = {
  listDrafts: () => request("/api/v1/compose/drafts") as Promise<Draft[]>,
  upsertDraft: (data: any) =>
    request("/api/v1/compose/drafts", { method: "POST", body: JSON.stringify(data) }) as Promise<Draft>,
  deleteDraft: (id: string) =>
    request(`/api/v1/compose/drafts/${id}`, { method: "DELETE" }),
  listScheduled: () => request("/api/v1/compose/scheduled") as Promise<ScheduledSend[]>,
  createScheduled: (data: any) =>
    request("/api/v1/compose/scheduled", { method: "POST", body: JSON.stringify(data) }) as Promise<ScheduledSend>,
  listTemplates: () => request("/api/v1/compose/templates") as Promise<Template[]>,
  createTemplate: (data: any) =>
    request("/api/v1/compose/templates", { method: "POST", body: JSON.stringify(data) }) as Promise<Template>,
}
