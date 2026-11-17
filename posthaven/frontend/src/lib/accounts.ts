const API_BASE = import.meta.env.VITE_API_BASE ?? ""

export interface MailAccount {
  id: string
  user_id: string
  provider: string
  host: string
  imap_port: number
  smtp_port: number
  imap_security: string
  smtp_security: string
  username: string
  is_enabled: boolean
  sync_enabled: boolean
  last_sync_at?: string | null
  status: string
  status_message?: string | null
  capabilities?: string | null
  special_use?: string | null
  created_at: string
  updated_at: string
}

export interface MailAccountCreate {
  provider: string
  host: string
  imap_port: number
  smtp_port: number
  imap_security: string
  smtp_security: string
  username: string
  password: string
  is_enabled?: boolean
  sync_enabled?: boolean
}

export interface MailAccountUpdate {
  is_enabled?: boolean
  sync_enabled?: boolean
}

export interface TestResult {
  ok: boolean
  imap_capabilities?: string[]
  message: string
}

export const PROVIDER_PRESETS: Record<string, Partial<MailAccountCreate>> = {
  greenmail: {
    provider: "greenmail",
    imap_port: 3143,
    smtp_port: 3025,
    imap_security: "none",
    smtp_security: "none",
  },
  gmail: {
    provider: "gmail",
    host: "imap.gmail.com",
    imap_port: 993,
    smtp_port: 465,
    imap_security: "ssl",
    smtp_security: "ssl",
  },
  outlook: {
    provider: "outlook",
    host: "outlook.office365.com",
    imap_port: 993,
    smtp_port: 587,
    imap_security: "ssl",
    smtp_security: "starttls",
  },
  yahoo: {
    provider: "yahoo",
    host: "imap.mail.yahoo.com",
    imap_port: 993,
    smtp_port: 465,
    imap_security: "ssl",
    smtp_security: "ssl",
  },
  fastmail: {
    provider: "fastmail",
    host: "imap.fastmail.com",
    imap_port: 993,
    smtp_port: 465,
    imap_security: "ssl",
    smtp_security: "ssl",
  },
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

export const accountsApi = {
  list: () => request("/api/v1/accounts") as Promise<MailAccount[]>,
  get: (id: string) => request(`/api/v1/accounts/${id}`) as Promise<MailAccount>,
  create: (data: MailAccountCreate) =>
    request("/api/v1/accounts", {
      method: "POST",
      body: JSON.stringify(data),
    }) as Promise<MailAccount>,
  update: (id: string, data: MailAccountUpdate) =>
    request(`/api/v1/accounts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }) as Promise<MailAccount>,
  remove: (id: string) =>
    request(`/api/v1/accounts/${id}`, { method: "DELETE" }),
  sync: (id: string, headersLimit = 200) =>
    request(`/api/v1/accounts/${id}/sync?headers_limit=${headersLimit}`, {
      method: "POST",
    }) as Promise<{ folders: number; messages: number; errors: string[] }>,
  test: (params: {
    account_id?: string
    host?: string
    port?: number
    username?: string
    password?: string
    security?: string
  }) => {
    const qs = new URLSearchParams()
    if (params.account_id) qs.set("account_id", params.account_id)
    if (params.host) qs.set("host", params.host)
    if (params.port !== undefined) qs.set("port", String(params.port))
    if (params.username) qs.set("username", params.username)
    if (params.password !== undefined) qs.set("password", params.password)
    if (params.security) qs.set("security", params.security)
    return request(`/api/v1/accounts/test?${qs.toString()}`, {
      method: "POST",
    }) as Promise<TestResult>
  },
}
