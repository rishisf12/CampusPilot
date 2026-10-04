import { useCallback, useEffect, useRef, useState } from 'react'
import { examApi } from '../api'
import Spinner from './Spinner'
import ErrorBanner from './ErrorBanner'

/**
 * Exam page.
 *
 * Three parts:
 *  - upload cards for the exam timetable and the seating index
 *  - the student's timetable grouped by day
 *  - Quick Roll Lookup, which returns only date, room and course code
 */
export default function ExamSeating() {
  const [status, setStatus] = useState({ timetable_rows: 0, seating_rows: 0 })
  const [timetable, setTimetable] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploadMsg, setUploadMsg] = useState(null)
  const [uploading, setUploading] = useState(null)

  // Quick roll lookup
  const [roll, setRoll] = useState('')
  const [quick, setQuick] = useState(null)
  const [quickBusy, setQuickBusy] = useState(false)
  const [quickError, setQuickError] = useState(null)

  const fileInputs = {
    timetable: useRef(null),
    seating: useRef(null),
  }

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [statusData, timetableData] = await Promise.all([
        examApi.status(),
        examApi.timetable(),
      ])
      setStatus(statusData)
      setTimetable(timetableData)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  // Profile changes bump `profile_version`; refetch so the exam data stays in sync.
  // `storage` covers other browser tabs, `profile-updated` covers this one.
  useEffect(() => {
    function onStorage(event) {
      if (event.key === 'profile_version') loadAll()
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener('profile-updated', loadAll)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('profile-updated', loadAll)
    }
  }, [loadAll])

  const handleUpload = async (kind, file) => {
    if (!file) return
    setUploading(kind)
    setUploadMsg(null)
    setError(null)
    try {
      const result =
        kind === 'timetable'
          ? await examApi.uploadTimetable(file)
          : await examApi.uploadSeating(file)
      setUploadMsg(result.message)
      await loadAll()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(null)
      if (fileInputs[kind].current) fileInputs[kind].current.value = ''
    }
  }

  const handleQuickLookup = async (event) => {
    event.preventDefault()
    if (!roll.trim()) return
    setQuickBusy(true)
    setQuickError(null)
    setQuick(null)
    try {
      const data = await examApi.quickLookup(roll.trim().toUpperCase())
      setQuick(data)
    } catch (err) {
      setQuickError(err.message)
    } finally {
      setQuickBusy(false)
    }
  }

  const handlePdf = async () => {
    if (!roll.trim()) return
    setQuickBusy(true)
    try {
      const blob = await examApi.pdf(roll.trim().toUpperCase())
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `exam_timetable_${roll.trim().toUpperCase()}.pdf`
      link.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setQuickError(err.message)
    } finally {
      setQuickBusy(false)
    }
  }

  const hasData = status.timetable_rows > 0 || status.seating_rows > 0

  return (
    <div className="p-4 md:p-6 space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />
      {uploadMsg && (
        <div className="p-3 rounded-lg bg-success-50 border border-success-200 text-success-700 text-sm">
          {uploadMsg}
        </div>
      )}

      {/* Upload cards — two columns while empty, one column once data exists */}
      <div className={hasData ? 'grid grid-cols-1 gap-4' : 'grid md:grid-cols-2 gap-4'}>
        <UploadCard
          title="Exam Timetable"
          hint="Mid-semester exam schedule (date, time, course, semester)."
          accept=".pdf,.csv"
          busy={uploading === 'timetable'}
          rowCount={status.timetable_rows}
          countLabel="rows"
          inputRef={fileInputs.timetable}
          onFile={(file) => handleUpload('timetable', file)}
        />
        <UploadCard
          title="Seating Index"
          hint="Class room index mapping roll ranges to rooms."
          accept=".pdf,.csv"
          busy={uploading === 'seating'}
          rowCount={status.seating_rows}
          countLabel="rows"
          inputRef={fileInputs.seating}
          onFile={(file) => handleUpload('seating', file)}
        />
      </div>

      {/* Quick Roll Lookup */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-1">Quick Roll Lookup</h3>
        <p className="text-sm text-gray-500 mb-4">
          Shows only the date, room and course code for a roll number.
        </p>

        <form onSubmit={handleQuickLookup} className="flex flex-wrap gap-2">
          <input
            type="text"
            value={roll}
            onChange={(e) => setRoll(e.target.value.toUpperCase())}
            placeholder="Enter roll number (e.g., 23BCS125)"
            className="flex-1 min-w-[220px] px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 font-mono outline-none"
            disabled={quickBusy}
          />
          <button type="submit" disabled={quickBusy || !roll.trim()}
            className="px-6 py-2 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2">
            {quickBusy ? <Spinner size={18} /> : 'Lookup'}
          </button>
          <button type="button" onClick={handlePdf} disabled={quickBusy || !roll.trim()}
            className="px-4 py-2 bg-success-500 text-white font-medium rounded-lg hover:bg-success-600 disabled:opacity-50">
            Download PDF
          </button>
        </form>

        {quickError && (
          <p className="mt-3 text-sm text-danger-600">{quickError}</p>
        )}

        {quick && quick.exams.length === 0 && (
          <p className="mt-4 text-sm text-gray-500">
            No exam found for <span className="font-mono">{quick.roll}</span>.
          </p>
        )}

        {quick && quick.exams.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 text-left text-sm text-gray-500">
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Room</th>
                  <th className="px-4 py-3 font-medium">Course Code</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {quick.exams.map((exam, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-700">
                      {exam.date ? new Date(exam.date).toLocaleDateString('en-IN',
                        { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                      {exam.day ? ` (${exam.day})` : ''}
                    </td>
                    <td className="px-4 py-3 font-mono text-primary-600">{exam.room || '—'}</td>
                    <td className="px-4 py-3 font-mono text-gray-900">{exam.course_code}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Student's timetable, grouped by day */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Your Exam Timetable</h3>
          {timetable?.profile && (
            <span className="text-xs text-gray-500">
              {timetable.profile.branch} · Sem {timetable.profile.semester} ·{' '}
              {timetable.total} exam(s)
            </span>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-10">
            <Spinner size={24} />
          </div>
        )}

        {!loading && (!timetable || timetable.days.length === 0) && (
          <p className="text-sm text-gray-500 py-6 text-center">
            No exams match your profile yet. Upload the exam timetable above.
          </p>
        )}

        {!loading && timetable?.days.map((day) => (
          <div key={day.date} className="mb-6 last:mb-0">
            <h4 className="text-sm font-semibold text-gray-900 mb-2">
              {day.date === 'unscheduled'
                ? 'Date not specified'
                : `${new Date(day.date).toLocaleDateString('en-IN',
                    { day: '2-digit', month: 'short', year: 'numeric' })} — ${day.day}`}
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 text-left text-sm text-gray-500">
                    <th className="px-4 py-2 font-medium">Time</th>
                    <th className="px-4 py-2 font-medium">Course Code</th>
                    <th className="px-4 py-2 font-medium">Room</th>
                    <th className="px-4 py-2 font-medium">Branch</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {day.exams.map((exam) => (
                    <tr key={exam.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5 text-gray-700 whitespace-nowrap">
                        {exam.start_time} – {exam.end_time}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-gray-900">
                        {exam.course_code}
                        {exam.is_extra && (
                          <span className="ml-2 text-xs text-primary-600 font-sans">OE</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-primary-600">
                        {exam.room || '—'}
                      </td>
                      <td className="px-4 py-2.5 text-gray-600 text-sm">{exam.branch || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Compact upload card used for both the timetable and the seating index. */
function UploadCard({ title, hint, accept, busy, rowCount, countLabel, inputRef, onFile }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-base font-semibold text-gray-900">{title}</h3>
          <p className="text-xs text-gray-500 mt-0.5">{hint}</p>
        </div>
        {rowCount > 0 && (
          <span className="shrink-0 text-xs font-medium text-success-700 bg-success-50 px-2 py-1 rounded-full">
            {rowCount} {countLabel}
          </span>
        )}
      </div>

      <label className="flex items-center justify-center gap-2 px-4 py-4 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-primary-400 hover:bg-primary-50/40 transition-colors">
        <input ref={inputRef} type="file" accept={accept} className="hidden"
          onChange={(e) => onFile(e.target.files?.[0])} disabled={busy} />
        {busy ? (
          <span className="flex items-center gap-2 text-sm text-gray-600">
            <Spinner size={16} /> Uploading…
          </span>
        ) : (
          <span className="text-sm text-gray-600">Choose a PDF or CSV file</span>
        )}
      </label>
    </div>
  )
}