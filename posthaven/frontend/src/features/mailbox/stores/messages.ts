import { create } from "zustand"
import type { MessageListItem } from "@/lib/messages"

export type MessageItem = MessageListItem

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
