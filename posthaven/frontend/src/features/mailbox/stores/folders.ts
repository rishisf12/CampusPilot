import { create } from "zustand"

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

interface FoldersState {
  folders: Folder[]
  selectedFolderId: string | null
  loading: boolean
  setFolders: (folders: Folder[]) => void
  setSelectedFolderId: (id: string | null) => void
  setLoading: (loading: boolean) => void
}

export const useFoldersStore = create<FoldersState>((set) => ({
  folders: [],
  selectedFolderId: null,
  loading: false,
  setFolders: (folders) => set({ folders }),
  setSelectedFolderId: (id) => set({ selectedFolderId: id }),
  setLoading: (loading) => set({ loading }),
}))
