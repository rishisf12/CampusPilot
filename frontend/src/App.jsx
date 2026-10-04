import { useEffect, useState } from 'react'
import AuthWrapper, { useAuth } from './components/AuthWrapper'
import LiveSchedule from './components/LiveSchedule'
import VacantRoomLookup from './components/VacantRoomLookup'
import Attendance from './components/Attendance'
import ExamSeating from './components/ExamSeating'
import ErrorBanner from './components/ErrorBanner'
import { healthApi } from './api'
import { NAV_TABS } from './constants'

/** Poll the backend so the header dot reflects real connectivity. */
function useBackendStatus() {
  const [online, setOnline] = useState(false)
  useEffect(() => {
    let cancelled = false
    const ping = async () => {
      try {
        await healthApi.check()
        if (!cancelled) setOnline(true)
      } catch {
        if (!cancelled) setOnline(false)
      }
    }
    ping()
    const timer = setInterval(ping, 30000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])
  return online
}

function Shell() {
  const { user, logout, offline } = useAuth()
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tab')
    return NAV_TABS.some((item) => item.id === requested) ? requested : 'live'
  })
  const online = useBackendStatus()
  const [connectionError, setConnectionError] = useState(null)

  // Keep the tab in the URL so a reload returns to the same view.
  const selectTab = (id) => {
    setTab(id)
    const url = new URL(window.location.href)
    url.searchParams.set('tab', id)
    window.history.replaceState({}, '', url)
  }

  const displayName =
    user?.full_name?.trim() || user?.username || user?.email?.split('@')[0] || 'Student'

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Single static header, flush at the top, never scrolls away */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between gap-4 h-16">
            {/* Brand */}
            <div className="flex items-center gap-3 shrink-0">
              <img src="/logo-icon.svg" alt="Essential" className="w-12 h-12" />
              <div className="leading-tight">
                <p className="text-lg font-bold text-primary-500">essential</p>
                <p className="text-[10px] tracking-widest font-semibold text-cyan-600 whitespace-nowrap">
                  YOUR CAMPUS ASSISTANT
                </p>
              </div>
            </div>

            {/* Tabs live directly in the header */}
            <nav className="hidden lg:flex items-center gap-1 shrink-0" aria-label="Main">
              {NAV_TABS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => selectTab(item.id)}
                  aria-current={tab === item.id ? 'page' : undefined}
                  className={`px-3 py-2 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
                    tab === item.id
                      ? 'bg-primary-500 text-white'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>

            {/* User, logout and the live dot */}
            <div className="flex items-center gap-3 shrink-0">
              <span className="hidden sm:inline text-sm font-medium text-gray-700 max-w-[160px] truncate">
                {displayName}
              </span>
              <button type="button" onClick={logout} className="btn-ghost">
                Logout
              </button>
              <span
                className={`w-2.5 h-2.5 rounded-full ${online ? 'bg-success-500' : 'bg-danger-500'}`}
                title={online ? 'Backend connected' : 'Backend offline'}
                aria-label={online ? 'Backend connected' : 'Backend offline'}
              />
            </div>
          </div>

          {/* Tabs wrap onto their own row on small screens */}
          <nav className="lg:hidden flex items-center gap-1 pb-2 overflow-x-auto" aria-label="Main mobile">
            {NAV_TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => selectTab(item.id)}
                aria-current={tab === item.id ? 'page' : undefined}
                className={`px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-full transition-colors ${
                  tab === item.id
                    ? 'bg-primary-500 text-white'
                    : 'bg-gray-100 text-gray-600 border border-gray-200'
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Content, centred */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {offline && !online && (
          <ErrorBanner
            message="Backend offline - start it with: uvicorn main:app --port 8001"
            onDismiss={() => setConnectionError(null)}
            className="mb-4"
          />
        )}
        {connectionError && (
          <ErrorBanner message={connectionError} onDismiss={() => setConnectionError(null)} className="mb-4" />
        )}

        {tab === 'live' && <LiveSchedule onError={setConnectionError} />}
        {tab === 'vacant' && <VacantRoomLookup onError={setConnectionError} />}
        {tab === 'attendance' && <Attendance onError={setConnectionError} />}
        {tab === 'exam' && <ExamSeating onError={setConnectionError} />}
      </main>

      {/* Single footer */}
      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-gray-500">
          essential &mdash; your campus assistant
        </div>
      </footer>
    </div>
  )
}

export default function App() {
  return (
    <AuthWrapper>
      <Shell />
    </AuthWrapper>
  )
}