import { useEffect } from "react"
import { Routes, Route, Navigate, Outlet } from "react-router-dom"
import { useAuthStore } from "@/stores/auth"
import Health from "./pages/Health"
import Login from "./pages/Login"
import Register from "./pages/Register"
import Accounts from "./pages/Accounts"
import AddAccount from "./pages/AddAccount"
import Compose from "./pages/Compose"
import { ThemeProvider } from "@/components/theme-provider"
import { LayoutShell } from "@/components/layout-shell"

function PrivateRoute() {
  const isLoading = useAuthStore((s) => s.isLoading)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const fetchMe = useAuthStore((s) => s.fetchMe)

  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-500">
        Loading…
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Outlet />
}

function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<PrivateRoute />}>
            <Route path="/" element={<Navigate to="/mail" replace />} />
            <Route path="/mail" element={<LayoutShell />} />
            <Route path="/health" element={<Health />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/add-account" element={<AddAccount />} />
            <Route path="/compose" element={<Compose />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </div>
    </ThemeProvider>
  )
}

export default App
