import { useCallback, useEffect, useState } from 'react'
import { authApi, getToken, healthApi, setToken } from './api'
import AuthScreen from './components/AuthScreen'
import ErrorBanner from './components/ErrorBanner'
import ProfileSettings from './components/ProfileSettings'
import LiveSchedule from './components/LiveSchedule'
import VacantRoomLookup from './components/VacantRoomLookup'
import Attendance from './components/Attendance'
import ExamSeating from './components/ExamSeating'
import { BRANCH_OPTIONS } from './constants'

/** Top-level sections. */
const SECTIONS = [
  { id: 'classroom', label: 'Classroom' },
  { id: 'profile', label: 'Profile' },
]

/** Sub-tabs shown inside the Classroom section. */
const CLASSROOM_TABS = [
  { id: 'live', label: 'Live Schedule' },
  { id: 'vacant', label: 'Vacant Room Lookup' },
  { id: 'attendance', label: 'Attendance' },
  { id: 'exam', label: 'Exam' },
]

export default function App() {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(true)
  const [section, setSection] = useState('classroom')
  const [classroomTab, setClassroomTab] = useState('live')
  const [online, setOnline] = useState(false)
  const [error, setError] = useState(null)

  // Restore the session from the stored token on first load.
  useEffect(() => {
    ;(async () => {
      if (!getToken()) {
        setBooting(false)
        return
      }
      try {
        setUser(await authApi.me())
      } catch {
        setToken(null)
      } finally {
        setBooting(false)
      }
    })()
  }, [])

  // Live green/red dot for backend reachability.
  useEffect(() => {
    let cancelled = false
    async function ping() {
      try {
        await healthApi.check()
        if (!cancelled) setOnline(true)
      } catch {
        if (!cancelled) setOnline(false)
      }
    }
    ping()
    const timer = setInterval(ping, 30000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Token removal on the client is what actually ends the session.
    }
    setToken(null)
    setUser(null)
    setSection('classroom')
    setClassroomTab('live')
  }, [])

  if (booting) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-pulse text-gray-400 text-sm">Loading CampusPilot…</div>
      </div>
    )
  }

  if (!user) {
    return (
      <AuthScreen
        onAuthenticated={async () => {
          try {
            setUser(await authApi.me())
          } catch {
            setToken(null)
          }
        }}
      />
    )
  }

  const displayName =
    user.full_name?.trim() ||
    user.username ||
    user.email?.split('@')[0] ||
    'Student'

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 bg-primary-500 rounded-xl flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <span className="font-semibold text-gray-900 truncate">{displayName}</span>
          </div>

          <div className="flex items-center gap-4">
            <span
              className={`w-2.5 h-2.5 rounded-full ${online ? 'bg-success-500' : 'bg-danger-500'}`}
              title={online ? 'Connected' : 'Backend offline'}
            />
            <button onClick={handleLogout}
              className="text-sm font-medium text-gray-600 hover:text-gray-900">
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Section navigation */}
      <nav className="bg-white border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 flex gap-1" aria-label="Sections">
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              onClick={() => setSection(item.id)}
              aria-current={section === item.id ? 'page' : undefined}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                section === item.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-900'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Classroom sub-tabs */}
      {section === 'classroom' && (
        <div className="bg-gray-50 border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto" aria-label="Classroom views">
            {CLASSROOM_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setClassroomTab(tab.id)}
                aria-current={classroomTab === tab.id ? 'page' : undefined}
                className={`px-3.5 py-2 text-sm rounded-full whitespace-nowrap transition-colors ${
                  classroomTab === tab.id
                    ? 'bg-primary-500 text-white'
                    : 'bg-white text-gray-600 border border-gray-200 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        {section === 'profile' && <ProfileSettings onProfileSaved={() => setError(null)} />}

        {section === 'classroom' && classroomTab === 'live' && <LiveSchedule />}
        {section === 'classroom' && classroomTab === 'vacant' && <VacantRoomLookup />}
        {section === 'classroom' && classroomTab === 'attendance' && <Attendance />}
        {section === 'classroom' && classroomTab === 'exam' && <ExamSeating />}
      </main>

      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-gray-500">
          CampusPilot — built for students, by students
        </div>
      </footer>
    </div>
  )
}