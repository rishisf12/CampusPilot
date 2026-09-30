import { useState, useEffect } from 'react'
import { attendanceApi } from '../api'
import ErrorBanner from './ErrorBanner'
import StatusCard from './StatusCard'
import Spinner from './Spinner'

export default function Attendance() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [marking, setMarking] = useState({})

  useEffect(() => {
    loadSummary()
  }, [])

  const loadSummary = async () => {
    try {
      setLoading(true)
      const data = await attendanceApi.summary()
      setSummary(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleMark = async (courseId, status) => {
    const key = `${courseId}-${status}`
    setMarking(prev => ({ ...prev, [key]: true }))
    try {
      await attendanceApi.mark({
        course_id: courseId,
        date: new Date().toISOString().split('T')[0],
        status,
      })
      setError(null)
      await loadSummary()
    } catch (e) {
      setError(e.message)
    } finally {
      setMarking(prev => ({ ...prev, [key]: false }))
    }
  }

  const handleDelete = async (recordId) => {
    if (!window.confirm('Delete this attendance record?')) return
    try {
      await attendanceApi.delete(recordId)
      await loadSummary()
    } catch (e) {
      setError(e.message)
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'Safe': return 'success'
      case 'Warning': return 'warning'
      case 'Critical': return 'danger'
      default: return 'gray'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size={32} />
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Overall Summary */}
      {summary && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Overall Attendance</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatusCard
              label="Overall Percentage"
              value={`${summary.overall_percentage}%`}
              status={summary.overall_status}
              subtext={`${summary.total_present} present / ${summary.total_absent} absent`}
            />
            <StatusCard
              label="Total Classes Held"
              value={summary.total_present + summary.total_absent}
              status="default"
              subtext="Cancelled classes excluded"
            />
            <StatusCard
              label="Status"
              value={summary.overall_status}
              status={summary.overall_status}
            />
          </div>
        </div>
      )}

      {/* Per-Course Cards */}
      {summary && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900">Per Course</h3>
          {summary.courses?.length > 0 ? (
            summary.courses.map(course => (
              <div
                key={course.course_id}
                className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="font-semibold text-gray-900">{course.course_name}</h4>
                      <span className="text-sm text-gray-500 font-mono">{course.course_code}</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium bg-${getStatusColor(course.status)}-100 text-${getStatusColor(course.status)}-700`}
                      >
                        {course.status}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Present</p>
                        <p className="font-semibold text-success-600">{course.present}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Absent</p>
                        <p className="font-semibold text-danger-600">{course.absent}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Cancelled</p>
                        <p className="font-semibold text-gray-500">{course.cancelled}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Can Miss</p>
                        <p className="font-semibold text-warning-600">{course.can_miss}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Must Attend</p>
                        <p className="font-semibold text-primary-600">{course.must_attend}</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => handleMark(course.course_id, 'Present')}
                      disabled={marking[`${course.course_id}-Present`]}
                      className="px-3 py-1.5 bg-success-500 text-white text-sm rounded-lg hover:bg-success-600 disabled:opacity-50"
                    >
                      {marking[`${course.course_id}-Present`] ? <Spinner size={14} /> : 'Present'}
                    </button>
                    <button
                      onClick={() => handleMark(course.course_id, 'Absent')}
                      disabled={marking[`${course.course_id}-Absent`]}
                      className="px-3 py-1.5 bg-danger-500 text-white text-sm rounded-lg hover:bg-danger-600 disabled:opacity-50"
                    >
                      {marking[`${course.course_id}-Absent`] ? <Spinner size={14} /> : 'Absent'}
                    </button>
                    <button
                      onClick={() => handleMark(course.course_id, 'Cancelled')}
                      disabled={marking[`${course.course_id}-Cancelled`]}
                      className="px-3 py-1.5 bg-gray-500 text-white text-sm rounded-lg hover:bg-gray-600 disabled:opacity-50"
                    >
                      {marking[`${course.course_id}-Cancelled`] ? <Spinner size={14} /> : 'Cancelled'}
                    </button>
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-gray-100">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        course.percentage >= 75 ? 'bg-success-500' :
                        course.percentage >= 65 ? 'bg-warning-500' : 'bg-danger-500'
                      }`}
                      style={{ width: `${Math.min(course.percentage, 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1 text-right">{course.percentage}%</p>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-12 text-gray-500">
              <p>No courses found. Seed the database or add courses.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}