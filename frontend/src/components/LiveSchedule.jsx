import { useCallback, useEffect, useState } from 'react'
import { scheduleApi, timetableApi } from '../api'
import FileUpload from './FileUpload'
import Spinner from './Spinner'
import ErrorBanner from './ErrorBanner'

/**
 * Live Schedule.
 *
 * Shows the current and next class plus the master-timetable upload.  Profile
 * editing lives in its own Profile section, and the extra-course list here
 * feeds the elective handling on the exam side.
 */
export default function LiveSchedule() {
  const [activeTab, setActiveTab] = useState('schedule')
  const [schedule, setSchedule] = useState(null)
  const [extraCodes, setExtraCodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [error, setError] = useState(null)

  const loadSchedule = useCallback(async () => {
    setLoading(true)
    try {
      setSchedule(await scheduleApi.now())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadExtras = useCallback(async () => {
    try {
      const data = await scheduleApi.listExtra()
      setExtraCodes(data.map((c) => c.code))
    } catch {
      // The extra-course list is optional context; ignore failures here.
    }
  }, [])

  useEffect(() => {
    loadSchedule()
    loadExtras()
  }, [loadSchedule, loadExtras])

  useEffect(() => {
    if (!autoRefresh) return undefined
    const timer = setInterval(loadSchedule, 60000)
    return () => clearInterval(timer)
  }, [autoRefresh, loadSchedule])

  const handleTimetableUpload = async (file) => {
    try {
      const result = await timetableApi.upload(file)
      setError(result.warnings?.length ? `Uploaded with warnings: ${result.warnings.join('; ')}` : null)
      await loadSchedule()
    } catch (err) {
      setError(err.message)
      throw err
    }
  }

  const formatTime = (value) => {
    if (!value) return ''
    const [hour, minute] = value.split(':')
    const h = Number(hour)
    const ampm = h >= 12 ? 'PM' : 'AM'
    const displayHour = h % 12 === 0 ? 12 : h % 12
    return `${displayHour}:${minute} ${ampm}`
  }

  const ClassCard = ({ title, dotClass, item, emptyText }) => (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
        {title}
      </h3>
      {item ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Course</p>
              <p className="font-semibold text-gray-900">
                {item.course_name} ({item.course_code})
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Room</p>
              <p className="font-semibold text-gray-900">{item.room}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Time</p>
              <p className="font-semibold text-gray-900">
                {formatTime(item.start_time)} - {formatTime(item.end_time)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Day</p>
              <p className="font-semibold text-gray-900">{item.day}</p>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-500 py-6 text-center">{emptyText}</p>
      )}
    </div>
  )

  return (
    <div className="p-4 md:p-6 space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="flex flex-wrap items-center gap-2 border-b border-gray-200">
        {['schedule', 'timetable'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab === 'schedule' ? 'Live Schedule' : 'Timetable Upload'}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3 pb-2">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
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

      {activeTab === 'schedule' && (
        <div className="space-y-6">
          {schedule?.current_class ? (
            <ClassCard
              title="Current Class"
              dotClass="bg-success-500"
              item={schedule.current_class}
            />
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-success-500" />
                Current Class
              </h3>
              <div className="text-center py-8 text-gray-500">
                <p className="text-lg">{schedule?.message || 'No class right now'}</p>
                <p className="text-sm mt-1">
                  Current time: {schedule?.current_time || '—'}
                </p>
              </div>
            </div>
          )}

          <ClassCard
            title="Next Class"
            dotClass="bg-warning-500"
            item={schedule?.next_class}
            emptyText="No upcoming classes"
          />

          {extraCodes.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Extra Courses</h3>
              <div className="flex flex-wrap gap-2">
                {extraCodes.map((code) => (
                  <span key={code}
                    className="px-2.5 py-1 rounded-full bg-gray-100 text-gray-700 text-xs font-mono">
                    {code}
                  </span>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Extra courses are cross-semester papers that also appear in your exam schedule.
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'timetable' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <FileUpload
              label="Upload Master Timetable (PDF or CSV)"
              accept=".pdf,.csv"
              onUpload={handleTimetableUpload}
              loading={loading}
              error={null}
              clearError={() => setError(null)}
            />
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <button
              onClick={async () => {
                try {
                  await timetableApi.clear()
                  await loadSchedule()
                } catch (err) {
                  setError(err.message)
                }
              }}
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