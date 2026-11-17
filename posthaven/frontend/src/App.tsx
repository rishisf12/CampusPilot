import React from "react"
import { Routes, Route, Navigate } from "react-router-dom"
import { useAuthStore } from "@/stores/auth"
import Health from "./pages/Health"
import Login from "./pages/Login"
import Register from "./pages/Register"
import Accounts from "./pages/Accounts"
import AddAccount from "./pages/AddAccount"
import Compose from "./pages/Compose"
import { ThemeProvider } from "@/components/theme-provider"
import { LayoutShell } from "@/components/layout-shell"

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated, fetchMe } = useAuthStore()
  React.useEffect(() => {
    fetchMe()
  }, [fetchMe])
  if (isLoading) return null
  if (!isAuthenticated) return <Navigate to="/login" replace={true} />
  return <>{children}</>
}

function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            element={
              <PrivateRoute>
                <Routes>
                  <Route path="/health" element={<LayoutShell />} />
                  <Route path="/accounts" element={<Accounts />} />
                  <Route path="/add-account" element={<AddAccount />} />
                  <Route path="/compose" element={<Compose />} />
                  <Route path="/" element={<Navigate to="/health" replace />} />
                </Routes>
              </PrivateRoute>
            }
          />
        </Routes>
      </div>
    </ThemeProvider>
  )
}

export default App
