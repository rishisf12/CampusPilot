import { useState, useEffect } from 'react'
import { healthApi } from './api'
import LiveSchedule from './components/LiveSchedule'
import VacantRoomLookup from './components/VacantRoomLookup'
import Attendance from './components/Attendance'
import ExamSeating from './components/ExamSeating'
import Spinner from './components/Spinner'
import ErrorBanner from './components/ErrorBanner'

const tabs = [
  { id: 'schedule', label: 'Live Schedule', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  )},
  { id: 'vacant', label: 'Vacant Room Lookup', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
    </svg>
  )},
  { id: 'attendance', label: 'Attendance', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  )},
  { id: 'exam', label: 'Exam Seating', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )},
]

export default function App() {
  const [activeTab, setActiveTab] = useState('schedule')
  const [online, setOnline] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        await healthApi.check()
        setOnline(true)
      } catch {
        setOnline(false)
        setError('Backend not reachable. Start server: cd CampusPilot/backend/backend && uvicorn main:app --reload --port 8000')
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const renderTab = () => {
    switch (activeTab) {
      case 'schedule': return <LiveSchedule />
      case 'vacant': return <VacantRoomLookup />
      case 'attendance': return <Attendance />
      case 'exam': return <ExamSeating />
      default: return null
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-500 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">CampusPilot</h1>
              <p className="text-xs text-gray-500">ClassPilot — Academic Module</p>
            </div>
          </div>

          {/* Tab Navigation */}
          <nav className="flex gap-1 bg-gray-100 rounded-lg p-1" aria-label="Main navigation">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-white text-primary-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
                aria-current={activeTab === tab.id ? 'page' : undefined}
              >
                {tab.icon}
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            ))}
          </nav>

          {/* Connection Status */}
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${online ? 'bg-success-500' : 'bg-danger-500'}`} />
            <span className="text-xs text-gray-500 hidden sm:inline">{online ? 'Connected' : 'Offline'}</span>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {renderTab()}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-gray-500">
          CampusPilot ClassPilot — Built for students, by students
        </div>
      </footer>
    </div>
  )
}