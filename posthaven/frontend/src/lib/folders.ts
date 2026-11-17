const API_BASE = import.meta.env.VITE_API_BASE ?? ""

export interface Folder {
  id: string
  account_id: string
  name: string
  delimiter?: string | null
  parent_id?: string | null
  special_use?: string | null
  subscribed: boolean
  message_count: number
  unread_count: number
  synced: boolean
}

export const foldersApi = {
  list: (accountId: string) =>
    fetch(`${API_BASE}/api/v1/folders?account_id=${accountId}`, { credentials: "include" })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load folders (${res.status})`)
        return res.json() as Promise<Folder[]>
      }),
}
