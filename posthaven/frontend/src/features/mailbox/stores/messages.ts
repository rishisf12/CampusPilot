import { create } from "zustand"

export interface MessageItem {
  id: string
  thread_id?: string | null
  uid: number
  message_id?: string | null
  from_json?: string | null
  to_json?: string | null
  subject?: string | null
  snippet?: string | null
  flags?: string | null
  size: number
  has_attachments: boolean
  internal_date?: string | null
  received_at?: string | null
}

interface MessagesState {
  messages: MessageItem[]
  selectedMessageId: string | null
  loading: boolean
  nextCursor: string | null
  setMessages: (messages: MessageItem[], append?: boolean) => void
  setSelectedMessageId: (id: string | null) => void
  setLoading: (loading: boolean) => void
  setNextCursor: (cursor: string | null) => void
}

export const useMessagesStore = create<MessagesState>((set) => ({
  messages: [],
  selectedMessageId: null,
  loading: false,
  nextCursor: null,
  setMessages: (messages, append = false) =>
    set((state) => ({ messages: append ? [...state.messages, ...messages] : messages })),
  setSelectedMessageId: (id) => set({ selectedMessageId: id }),
  setLoading: (loading) => set({ loading }),
  setNextCursor: (cursor) => set({ nextCursor: cursor }),
}))
