import { useState, useEffect } from 'react'
import { scheduleApi, profileApi, timetableApi } from '../api'
import FileUpload from './FileUpload'
import Spinner from './Spinner'
import ErrorBanner from './ErrorBanner'
import StatusCard from './StatusCard'

export default function LiveSchedule() {
  const [activeTab, setActiveTab] = useState('schedule') // 'schedule' | 'profile' | 'timetable'
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [schedule, setSchedule] = useState(null)
  const [profile, setProfile] = useState({ semester: 5, branch: 'CSE', elective_codes: ['CS304'] })
  const [electiveOptions, setElectiveOptions] = useState([])
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Load profile on mount
  useEffect(() => {
    loadProfile()
    loadElectives()
  }, [])

  // Auto-refresh schedule every 60s
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(loadSchedule, 60000)
    loadSchedule()
    return () => clearInterval(interval)
  }, [autoRefresh])

  const loadProfile = async () => {
    try {
      const data = await profileApi.get()
      setProfile(data)
    } catch (e) {
      console.error(e)
    }
  }

  const loadElectives = async () => {
    try {
      const data = await scheduleApi.listExtra()
      setElectiveOptions(data.map(c => c.code))
    } catch (e) {
      console.error(e)
    }
  }

  const loadSchedule = async () => {
    try {
      setLoading(true)
      const data = await scheduleApi.now()
      setSchedule(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleProfileUpdate = async (e) => {
    e.preventDefault()
    const formData = new FormData(e.target)
    const data = {
      semester: parseInt(formData.get('semester')),
      branch: formData.get('branch'),
      elective_codes: formData.getAll('electives'),
    }
    try {
      setLoading(true)
      await profileApi.update(data)
      setProfile(data)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleTimetableUpload = async (file) => {
    try {
      await timetableApi.upload(file)
      await loadSchedule()
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }

  const handleAddExtra = async (e) => {
    e.preventDefault()
    const formData = new FormData(e.target)
    const data = {
      code: formData.get('code'),
      name: formData.get('name'),
      semester: parseInt(formData.get('semester')),
      branch: formData.get('branch'),
    }
    try {
      await scheduleApi.addExtra(data)
      await loadElectives()
      await loadSchedule()
      e.target.reset()
    } catch (e) {
      setError(e.message)
    }
  }

  const formatTime = (timeStr) => {
    if (!timeStr) return ''
    const [h, m] = timeStr.split(':')
    const hour = parseInt(h)
    const ampm = hour >= 12 ? 'PM' : 'AM'
    const displayHour = hour % 12 || 12
    return `${displayHour}:${m} ${ampm}`
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Tab Navigation */}
      <div className="flex border-b border-gray-200">
        {['schedule', 'profile', 'timetable'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300 text-primary-500 focus:ring-primary-500"
            />
            Auto-refresh (60s)
          </label>
          <button
            onClick={loadSchedule}
            disabled={loading}
            className="px-3 py-1 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
          >
            {loading ? <Spinner size={16} /> : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'schedule' && (
        <div className="space-y-6">
          {/* Current Class */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success-500" />
              Current Class
            </h3>
            {schedule?.current_class ? (
              <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Course</p>
                    <p className="font-semibold text-gray-900">{schedule.current_class.course_name} ({schedule.current_class.course_code})</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Room</p>
                    <p className="font-semibold text-gray-900">{schedule.current_class.room}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Time</p>
                    <p className="font-semibold text-gray-900">
                      {formatTime(schedule.current_class.start_time)} - {formatTime(schedule.current_class.end_time)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Day</p>
                    <p className="font-semibold text-gray-900">{schedule.current_class.day}</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <svg className="w-12 h-12 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-lg">{schedule?.message || 'No class right now'}</p>
                <p className="text-sm mt-1">Current time: {schedule?.current_time || 'Loading...'}</p>
              </div>
            )}
          </div>

          {/* Next Class */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-warning-500" />
              Next Class
            </h3>
            {schedule?.next_class ? (
              <div className="bg-warning-50 border border-warning-200 rounded-lg p-4">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Course</p>
                    <p className="font-semibold text-gray-900">{schedule.next_class.course_name} ({schedule.next_class.course_code})</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Room</p>
                    <p className="font-semibold text-gray-900">{schedule.next_class.room}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Time</p>
                    <p className="font-semibold text-gray-900">
                      {formatTime(schedule.next_class.start_time)} - {formatTime(schedule.next_class.end_time)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Day</p>
                    <p className="font-semibold text-gray-900">{schedule.next_class.day}</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p className="text-lg">No upcoming classes</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'profile' && (
        <div className="space-y-6">
          {/* Profile Form */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Profile Settings</h3>
            <form onSubmit={handleProfileUpdate} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Semester</label>
                  <select
                    name="semester"
                    defaultValue={profile.semester}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    {[1,2,3,4,5,6,7,8].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
                  <input
                    name="branch"
                    defaultValue={profile.branch}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="e.g., CSE, ECE, ME"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Elective Courses</label>
                <div className="flex flex-wrap gap-2">
                  {electiveOptions.map(code => (
                    <label key={code} className="inline-flex items-center gap-1 px-3 py-1 bg-gray-50 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-100">
                      <input
                        type="checkbox"
                        name="electives"
                        value={code}
                        defaultChecked={profile.elective_codes?.includes(code)}
                        className="rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                      />
                      <span className="text-sm">{code}</span>
                    </label>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-1">Select elective courses you're enrolled in</p>
              </div>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
              >
                {loading && <Spinner size={18} />}
                Save Profile
              </button>
            </form>
          </div>

          {/* Extra Courses */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Extra Courses (Cross-Semester)</h3>
            <form onSubmit={handleAddExtra} className="space-y-4 mb-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <input name="code" placeholder="Code (e.g., HS101)" className="px-3 py-2 border border-gray-300 rounded-lg" required />
                <input name="name" placeholder="Name (e.g., Professional Ethics)" className="px-3 py-2 border border-gray-300 rounded-lg" required />
                <input name="semester" type="number" placeholder="Semester" defaultValue={profile.semester} className="px-3 py-2 border border-gray-300 rounded-lg" required />
                <input name="branch" placeholder="Branch" defaultValue={profile.branch} className="px-3 py-2 border border-gray-300 rounded-lg" required />
              </div>
              <button type="submit" className="px-4 py-2 bg-success-500 text-white font-medium rounded-lg hover:bg-success-600">Add Extra Course</button>
            </form>
            {electiveOptions.length > 0 && (
              <div className="space-y-2">
                {electiveOptions.map(code => (
                  <div key={code} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                    <span className="font-mono text-sm">{code}</span>
                    <button
                      onClick={async () => {
                        try { await scheduleApi.removeExtra(code); await loadElectives(); } catch(e) { setError(e.message); }
                      }}
                      className="text-danger-500 hover:text-danger-700 text-sm"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'timetable' && (
        <div className="space-y-6">
          <FileUpload
            label="Upload Master Timetable (PDF or CSV)"
            accept=".pdf,.csv"
            onUpload={handleTimetableUpload}
            loading={loading}
            error={error}
            clearError={() => setError(null)}
          />
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <button
              onClick={async () => { try { await timetableApi.clear(); await loadSchedule(); } catch(e) { setError(e.message); } }}
              className="px-4 py-2 bg-danger-500 text-white font-medium rounded-lg hover:bg-danger-600"
            >
              Clear All Timetable Data
            </button>
          </div>
        </div>
      )}
    </div>
  )
}