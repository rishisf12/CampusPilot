import { useState } from "react"
import { useAuthStore } from "@/stores/auth"
import { Link } from "react-router-dom"

export function SidebarHeader() {
  const { user, logout } = useAuthStore()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="border-b border-slate-200 bg-white p-3 shrink-0">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 text-sm font-medium">
            {(user?.display_name ?? user?.email?.split("@")[0] ?? "U")?.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="text-sm font-medium text-slate-900 truncate max-w-[120px]">
              {user?.display_name ?? user?.email}
            </div>
            <div className="text-xs text-slate-500 truncate max-w-[120px]">{user?.email}</div>
          </div>
        </div>
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="p-1 rounded-md hover:bg-slate-100 text-slate-600"
          aria-label="User menu"
        >
          <span className="material-symbols-rounded">arrow_drop_down</span>
        </button>
      </div>

      {menuOpen && (
        <div className="absolute left-3 right-3 top-12 bg-white border border-slate-200 rounded-lg shadow-lg py-2 z-20">
          <Link to="/accounts" className="block px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 hover:text-slate-900">
            Accounts
          </Link>
          <div className="border-t border-slate-100 pt-2 mt-2">
            <button
              onClick={logout}
              className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
