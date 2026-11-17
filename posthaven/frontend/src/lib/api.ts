const API_BASE = import.meta.env.VITE_API_BASE ?? ""

export async function health() {
  const res = await fetch(`${API_BASE}/api/v1/health`)
  if (!res.ok) throw new Error(`health check failed: ${res.status}`)
  return res.json()
}

export async function ready() {
  const res = await fetch(`${API_BASE}/api/v1/health/ready`)
  if (!res.ok) throw new Error(`ready check failed: ${res.status}`)
  return res.json()
}
