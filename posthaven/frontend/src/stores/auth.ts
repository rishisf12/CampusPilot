import { create } from "zustand"
import { persist, createJSONStorage } from "zustand/middleware"
import { authApi, type User } from "@/lib/auth"
import { mailWs } from "@/lib/ws"

interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, display_name?: string) => Promise<void>
  refresh: () => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
  changePassword: (newPassword: string) => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isLoading: true,
      isAuthenticated: false,

      setUser: (user) =>
        set({ user, isAuthenticated: !!user, isLoading: false }),

      login: async (email, password) => {
        await authApi.login(email, password)
        await get().fetchMe()
        mailWs.enable()
      },

      register: async (email, password, display_name) => {
        await authApi.register(email, password, display_name)
        await get().fetchMe()
        mailWs.enable()
      },

      refresh: async () => {
        await authApi.refresh()
        await get().fetchMe()
      },

      logout: async () => {
        mailWs.disable()
        try {
          await authApi.logout()
        } finally {
          set({ user: null, isAuthenticated: false, isLoading: false })
        }
      },

      fetchMe: async () => {
        try {
          const user = await authApi.me()
          set({ user, isAuthenticated: true, isLoading: false })
          mailWs.enable()
        } catch {
          set({ user: null, isAuthenticated: false, isLoading: false })
          mailWs.disable()
        }
      },

      changePassword: async (newPassword) => {
        await authApi.changePassword(newPassword)
      },
    }),
    {
      name: "posthaven-auth",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    },
  ),
)
