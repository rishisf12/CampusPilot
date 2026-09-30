import { useState, useEffect } from 'react'
import { roomsApi } from '../api'
import ErrorBanner from './ErrorBanner'
import Spinner from './Spinner'

export default function VacantRoomLookup() {
  const [mode, setMode] = useState('live')
  const [manualDay, setManualDay] = useState('Mon')
  const [manualHour, setManualHour] = useState('10:00')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [allRooms, setAllRooms] = useState([])

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  useEffect(() => {
    loadAllRooms()
    fetchVacant()
  }, [mode, manualDay, manualHour])

  const loadAllRooms = async () => {
    try {
      const res = await roomsApi.all()
      setAllRooms(res.rooms)
    } catch (e) {
      console.error(e)
    }
  }

  const fetchVacant = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = mode === 'live' ? { mode: 'live' } : { mode: 'manual', day: manualDay, hour: manualHour }
      const res = await roomsApi.vacant(params)
      setData(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (occupied) => {
    if (occupied.length === 0) return null
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-warning-100 text-warning-800">
        {occupied.length} occupied
      </span>
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Mode Toggle */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Search Mode</h3>
        <div className="flex gap-4">
          {['live', 'manual'].map(m => (
            <label key={m} className={`flex items-center gap-2 cursor-pointer px-4 py-2 rounded-lg border-2 transition-colors ${
              mode === m
                ? 'border-primary-500 bg-primary-50 text-primary-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}>
              <input
                type="radio"
                name="mode"
                value={m}
                checked={mode === m}
                onChange={e => setMode(e.target.value)}
                className="text-primary-500 focus:ring-primary-500"
              />
              <span className="font-medium capitalize">{m}</span>
            </label>
          ))}
        </div>

        {mode === 'manual' && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Day</label>
              <select
                value={manualDay}
                onChange={e => setManualDay(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              >
                {days.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Hour (24h)</label>
              <input
                type="time"
                value={manualHour}
                onChange={e => setManualHour(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* Results */}
      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Vacant Rooms */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success-500" />
                Vacant Rooms ({data.vacant_rooms?.length || 0})
              </h3>
              {getStatusBadge(data.occupied_rooms)}
            </div>
            <div className="p-4 max-h-96 overflow-y-auto">
              {data.vacant_rooms?.length > 0 ? (
                <ul className="space-y-2">
                  {data.vacant_rooms.map(room => (
                    <li key={room} className="flex items-center justify-between p-3 bg-success-50 border border-success-100 rounded-lg">
                      <span className="font-mono text-gray-900">{room}</span>
                      <span className="text-xs text-success-600 font-medium">Available</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-center text-gray-500 py-8">No vacant rooms</p>
              )}
            </div>
          </div>

          {/* Occupied Rooms */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-danger-500" />
                Occupied Rooms ({data.occupied_rooms?.length || 0})
              </h3>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto">
              {data.occupied_rooms?.length > 0 ? (
                <ul className="space-y-2">
                  {data.occupied_rooms.map((occ, i) => (
                    <li key={i} className="p-3 bg-danger-50 border border-danger-100 rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-gray-900">{occ.room}</span>
                        <span className="text-xs text-danger-600 font-medium">Occupied</span>
                      </div>
                      <div className="mt-1 text-sm text-gray-600">
                        <span className="font-medium">{occ.course_code}</span>
                        <span className="mx-2 text-gray-400">|</span>
                        <span>{occ.start_time} - {occ.end_time}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-center text-gray-500 py-8">No occupied rooms</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Info Banner */}
      {data?.message && (
        <div className="bg-blue-50 border border-blue-200 text-blue-800 rounded-lg p-4 flex items-center gap-2">
          <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <span>{data.message}</span>
        </div>
      )}

      {/* Debug Info */}
      <details className="text-sm text-gray-500">
        <summary className="cursor-pointer">Debug Info</summary>
        <pre className="mt-2 p-4 bg-gray-100 rounded text-xs overflow-auto">
          {JSON.stringify({ mode, day: data?.day, time: data?.time, in_college_hours: data?.in_college_hours, is_lunch: data?.is_lunch, is_weekend: data?.is_weekend }, null, 2)}
        </pre>
      </details>
    </div>
  )
}