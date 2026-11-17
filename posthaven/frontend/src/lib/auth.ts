const API_BASE = import.meta.env.VITE_API_BASE ?? ""

export interface User {
  id: string
  email: string
  display_name?: string | null
  is_admin: boolean
  is_active: boolean
  email_verified: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

async function request(path: string, opts?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    credentials: "include", // send httpOnly cookies
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

export const authApi = {
  register: (email: string, password: string, display_name?: string) =>
    request("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string) =>
    request("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  refresh: () =>
    request("/api/v1/auth/refresh", { method: "POST" }),
  me: () => request("/api/v1/auth/me") as Promise<User>,
  logout: () => request("/api/v1/auth/logout", { method: "POST" }),
  changePassword: (newPassword: string) =>
    request("/api/v1/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ new_password: newPassword }),
    }),
}
