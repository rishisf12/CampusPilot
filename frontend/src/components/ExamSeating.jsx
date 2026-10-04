import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi, examApi } from '../api'
import { BRANCH_OPTIONS, PROGRAMME_SEMESTERS } from '../constants'
import ErrorBanner from './ErrorBanner'
import FileUpload from './FileUpload'
import Spinner from './Spinner'

const SUB_TABS = [
  { id: 'timetable', label: 'Exam Timetable' },
  { id: 'seating', label: 'Exam Seating Index' },
]

const LAST_RESULT_KEY = 'exam_last_lookup'
const PREVIEW_ROWS = 20

/** "09:30" -> "9:30 AM" */
function formatTime(value) {
  if (!value) return ''
  const [hour, minute] = value.split(':')
  const h = Number(hour)
  return `${h % 12 === 0 ? 12 : h % 12}:${minute} ${h >= 12 ? 'PM' : 'AM'}`
}

function formatDate(iso) {
  if (!iso) return 'Date not specified'
  const date = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

const todayIso = () => new Date().toLocaleDateString('en-CA')

export default function ExamSeating({ onError }) {
  const [subTab, setSubTab] = useState('timetable')
  const [status, setStatus] = useState({ timetable_rows: 0, seating_rows: 0 })
  const [timetable, setTimetable] = useState(null)
  const [seating, setSeating] = useState(null)
  const [semester, setSemester] = useState('')
  const [branch, setBranch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [showAll, setShowAll] = useState({ timetable: false, seating: false })

  // Quick roll lookup
  const [roll, setRoll] = useState('')
  const [lookup, setLookup] = useState(null)
  const [looking, setLooking] = useState(false)
  const [lookupError, setLookupError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusData, timetableData] = await Promise.all([
        examApi.status(),
        examApi.getTimetable(),
      ])
      setStatus(statusData)
      setTimetable(timetableData)
      // Filters start from the profile.
      setSemester((current) => current || String(timetableData?.profile?.semester ?? ''))
      setBranch((current) => current || timetableData?.profile?.branch || '')
      setError(null)
    } catch (err) {
      setError(err.message)
      onError?.(err.message)
    } finally {
      setLoading(false)
    }
  }, [onError])

  useEffect(() => {
    load()
  }, [load])

  // Refetch when the profile changes in this tab or another one.
  useEffect(() => {
    const onProfile = () => load()
    window.addEventListener('profile-updated', onProfile)
    window.addEventListener('storage', onProfile)
    return () => {
      window.removeEventListener('profile-updated', onProfile)
      window.removeEventListener('storage', onProfile)
    }
  }, [load])

  // Prefill the roll from the signed-in user; /auth/me is the fallback source.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LAST_RESULT_KEY) || 'null')
      if (saved) {
        setLookup(saved)
        setRoll(saved.roll)
        return
      }
    } catch {
      /* ignore */
    }
    ;(async () => {
      try {
        const cached = localStorage.getItem('user_roll')
        if (cached) {
          setRoll(cached)
          return
        }
        const user = await authApi.me()
        if (user?.roll_number) {
          setRoll(user.roll_number)
          try {
            localStorage.setItem('user_roll', user.roll_number)
          } catch {
            /* ignore */
          }
        }
      } catch {
        /* the user can type a roll manually */
      }
    })()
  }, [])

  const loadSeating = async () => {
    try {
      setSeating(await examApi.getSeating())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    if (subTab === 'seating' && !seating) loadSeating()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab])

  /** Client-side semester/branch narrowing of the returned rows. */
  const visibleDays = useMemo(() => {
    if (!timetable?.days) return []
    return timetable.days
      .map((day) => ({
        ...day,
        exams: day.exams.filter(
          (exam) =>
            (!semester || String(exam.semester ?? '') === semester) &&
            (!branch || !exam.branch || exam.branch === branch || exam.branch === branch.split(' ')[0]),
        ),
      }))
      .filter((day) => day.exams.length > 0)
  }, [timetable, semester, branch])

  const hiddenCount = useMemo(() => {
    const total = (timetable?.days || []).reduce((sum, day) => sum + day.exams.length, 0)
    const visible = visibleDays.reduce((sum, day) => sum + day.exams.length, 0)
    return total - visible
  }, [timetable, visibleDays])

  const isSynced =
    String(timetable?.profile?.semester) === semester &&
    (timetable?.profile?.branch || '') === branch

  const runLookup = async (event) => {
    event.preventDefault()
    if (!roll.trim()) return
    setLooking(true)
    setLookupError(null)
    try {
      const data = await examApi.lookup(roll.trim().toUpperCase())
      // Drop duplicate rooms for the same course/date.
      const seen = new Set()
      const exams = (data.exams || []).filter((exam) => {
        const key = `${exam.course_code}|${exam.date}|${exam.room}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
      const result = {
        roll: data.roll,
        exams,
        // True when the backend narrowed the list to the signed-in profile.
        profileFiltered: Boolean(data.profile_filter_applied),
        profile: timetable?.profile || null,
      }
      setLookup(result)
      try {
        localStorage.setItem(LAST_RESULT_KEY, JSON.stringify(result))
      } catch {
        /* ignore */
      }
    } catch (err) {
      setLookupError(err.message)
      setLookup(null)
    } finally {
      setLooking(false)
    }
  }

  const removeData = async (kind) => {
    const label = kind === 'timetable' ? 'exam timetable' : 'seating index'
    if (!window.confirm(`Remove the uploaded ${label}?`)) return
    try {
      if (kind === 'timetable') {
        await examApi.clearTimetable().catch(() => null)
        setMessage('Exam timetable removed')
      } else {
        await examApi.clearSeating().catch(() => null)
        setMessage('Seating index removed')
      }
      await load()
      if (kind === 'seating') setSeating(null)
    } catch (err) {
      setError(err.message)
    }
  }

  const hasData = status.timetable_rows > 0 || status.seating_rows > 0
  const today = todayIso()

  return (
    <div className="space-y-5">
      {/* Quick Roll Lookup - small and centred */}
      <div className="max-w-xl mx-auto card">
        <h3 className="text-sm font-semibold text-gray-900 text-center">Quick Roll Lookup</h3>
        <form onSubmit={runLookup} className="mt-3 flex gap-2">
          <input
            id="exam-roll"
            className="input-field font-mono flex-1"
            value={roll}
            onChange={(event) => {
              setRoll(event.target.value.toUpperCase())
              setLookupError(null)
            }}
            placeholder="e.g. 23BCS125"
          />
          <button type="submit" className="btn-primary text-sm shrink-0" disabled={looking || !roll.trim()}>
            {looking ? <Spinner size={16} className="text-white" /> : 'Find Room'}
          </button>
        </form>

        {lookupError && (
          <div className="mt-3">
            <ErrorBanner message={lookupError} onDismiss={() => setLookupError(null)} />
          </div>
        )}

        {lookup && lookup.exams.length === 0 && (
          <p className="mt-3 text-sm text-gray-500 text-center">
            No exam found for <span className="font-mono">{lookup.roll}</span>.
          </p>
        )}

        {lookup && lookup.exams.length > 0 && (
          <>
            {lookup.profileFiltered && (
              <p className="mt-3 text-xs text-gray-500 text-center">
                Filtered to your profile
                {lookup.profile ? ` (${lookup.profile.branch} · Sem ${lookup.profile.semester})` : ''}.
              </p>
            )}
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
              {lookup.exams.map((exam, index) => {
              const isToday = exam.date === today
              return (
                <div
                  key={`${exam.course_code}-${exam.date}-${exam.room}-${index}`}
                  className={`rounded-lg border p-3 ${
                    isToday ? 'border-primary-400 bg-primary-50' : 'border-gray-200 bg-white'
                  }`}
                >
                  {isToday && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-primary-600 mb-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-primary-500" />
                      TODAY
                    </span>
                  )}
                  <p className="text-sm font-mono font-semibold text-gray-900">{exam.course_code}</p>
                  <p className="text-xs text-gray-700 mt-0.5">
                    Room <span className="font-mono text-primary-600">{exam.room || '—'}</span>
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatDate(exam.date)}
                    {exam.day ? ` (${exam.day})` : ''}
                    {exam.start_time ? ` · ${formatTime(exam.start_time)}-${formatTime(exam.end_time)}` : ''}
                  </p>
                </div>
              )
            })}
            </div>
          </>
        )}
      </div>

      {message && (
        <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
          {message}
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Upload cards: side by side while empty, stacked once populated */}
      <div className={hasData ? 'grid grid-cols-1 gap-4' : 'grid md:grid-cols-2 gap-4'}>
        <ExamUploadCard
          title="Exam Timetable"
          storageKey="exam_timetable_file"
          count={status.timetable_rows}
          busyLabel="Parsing exam timetable"
          onUpload={async (file) => {
            const result = await examApi.uploadTimetable(file)
            await load()
            return result
          }}
          onRemove={() => removeData('timetable')}
        />
        <ExamUploadCard
          title="Exam Seating Index"
          storageKey="exam_seating_file"
          count={status.seating_rows}
          busyLabel="Parsing seating index"
          onUpload={async (file) => {
            const result = await examApi.uploadSeating(file)
            await load()
            if (subTab === 'seating') setSeating(null)
            return result
          }}
          onRemove={() => removeData('seating')}
        />
      </div>

      {/* Views */}
      <div className="flex items-center gap-1 border-b border-gray-200">
        {SUB_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setSubTab(item.id)}
            className={`sub-tab ${subTab === item.id ? 'sub-tab-active' : 'sub-tab-idle'}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading && !timetable && (
        <div className="flex justify-center py-10">
          <Spinner size={24} className="text-primary-500" />
        </div>
      )}

      {subTab === 'timetable' && (
        <TimetableView
          days={visibleDays}
          semester={semester}
          setSemester={setSemester}
          branch={branch}
          setBranch={setBranch}
          isSynced={isSynced}
          hiddenCount={hiddenCount}
          total={status.timetable_rows}
        />
      )}

      {subTab === 'seating' && (
        <SeatingView
          data={seating}
          showAll={showAll.seating}
          setShowAll={(value) => setShowAll((prev) => ({ ...prev, seating: value }))}
          onLoad={loadSeating}
        />
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Upload card with its own uploaded-data preview                       */
/* ------------------------------------------------------------------ */

function ExamUploadCard({ title, count, onUpload, onRemove, storageKey, busyLabel }) {
  return (
    <FileUpload label={title} accept=".pdf,.csv" storageKey={storageKey} onUpload={onUpload}>
      {count > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-700">Uploaded ({count} entries)</span>
            <button
              type="button"
              onClick={onRemove}
              className="text-xs font-medium text-danger-600 hover:text-danger-700"
            >
              Remove
            </button>
          </div>
        </div>
      )}
    </FileUpload>
  )
}

/* ------------------------------------------------------------------ */
/* Exam timetable view                                                  */
/* ------------------------------------------------------------------ */

function TimetableView({ days, semester, setSemester, branch, setBranch, isSynced, hiddenCount, total }) {
  if (!total) {
    return (
      <div className="card text-center py-10 text-sm text-gray-500">
        No exam timetable uploaded yet. Add the exam timetable PDF above.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="card flex flex-wrap items-end gap-3">
        <div>
          <span className="label">Semester</span>
          <select
            id="exam-semester"
            className="select-field w-32"
            value={semester}
            onChange={(event) => setSemester(event.target.value)}
          >
            <option value="">All</option>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </div>
        <div>
          <span className="label">Branch</span>
          <select
            id="exam-branch"
            className="select-field w-40"
            value={branch}
            onChange={(event) => setBranch(event.target.value)}
          >
            <option value="">All</option>
            {BRANCH_OPTIONS.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </div>
        {isSynced && (
          <span className="px-2.5 py-1 rounded-full bg-success-50 text-success-700 text-xs font-medium">
            Synced with profile
          </span>
        )}
        {hiddenCount > 0 && (
          <span className="text-xs text-gray-500">
            {hiddenCount} row{hiddenCount === 1 ? '' : 's'} hidden by these filters.
          </span>
        )}
      </div>

      {days.length === 0 ? (
        <div className="card text-center py-8 text-sm text-gray-500">
          Nothing matches these filters.
        </div>
      ) : (
        days.map((day, index) => (
          <div key={day.date || index} className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">
              Day-{index + 1} {day.day || formatDate(day.date)}
            </h3>
            <div className="overflow-x-auto scrollbar-thin">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-gray-400">
                    <th className="py-2 pr-3 font-medium">Date</th>
                    <th className="py-2 pr-3 font-medium">Time</th>
                    <th className="py-2 pr-3 font-medium">Course Code</th>
                    <th className="py-2 font-medium">Instructor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {day.exams.map((exam) => (
                    <tr key={exam.id}>
                      <td className="py-2 pr-3 text-gray-700 whitespace-nowrap">{formatDate(exam.schedule_date)}</td>
                      <td className="py-2 pr-3 text-gray-600 whitespace-nowrap">
                        {formatTime(exam.start_time)} - {formatTime(exam.end_time)}
                      </td>
                      <td className="py-2 pr-3 font-mono text-gray-900">{exam.course_code}</td>
                      <td className="py-2 text-gray-500">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Seating index view                                                   */
/* ------------------------------------------------------------------ */

function SeatingView({ data, showAll, setShowAll, onLoad }) {
  if (!data) {
    return (
      <div className="card text-center py-10 text-sm text-gray-500">Loading seating index…</div>
    )
  }
  if (!data.total) {
    return (
      <div className="card text-center py-10 text-sm text-gray-500">
        No seating index uploaded yet. Add the seating index PDF above.
      </div>
    )
  }

  const rows = data.days.flatMap((day) =>
    day.rooms.map((room) => ({ ...room, date: day.date, day: day.day })),
  )
  const visible = showAll ? rows : rows.slice(0, PREVIEW_ROWS)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="px-2.5 py-1 rounded-full bg-success-50 text-success-700 text-xs font-medium">
          Synced with profile
        </span>
        <span className="text-xs text-gray-500">{rows.length} entries</span>
        {rows.length > PREVIEW_ROWS && (
          <button
            type="button"
            onClick={() => setShowAll(!showAll)}
            className="btn-ghost ml-auto"
          >
            {showAll ? 'Show less' : `Show All (${rows.length})`}
          </button>
        )}
        <button type="button" onClick={onLoad} className="btn-ghost">
          Refresh
        </button>
      </div>

      <div className="card overflow-x-auto scrollbar-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-gray-400">
              <th className="py-2 pr-3 font-medium">Date</th>
              <th className="py-2 pr-3 font-medium">Time</th>
              <th className="py-2 pr-3 font-medium">Lecture Hall</th>
              <th className="py-2 pr-3 font-medium">Course Code</th>
              <th className="py-2 font-medium">Roll Numbers</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {visible.map((room) => (
              <tr key={room.id}>
                <td className="py-2 pr-3 text-gray-700 whitespace-nowrap">{formatDate(room.date)}</td>
                <td className="py-2 pr-3 text-gray-600 whitespace-nowrap">
                  {formatTime(room.start_time)} - {formatTime(room.end_time)}
                </td>
                <td className="py-2 pr-3 font-mono text-primary-600">{room.room || '—'}</td>
                <td className="py-2 pr-3 font-mono text-gray-900">{room.course_code}</td>
                <td className="py-2 font-mono text-xs text-gray-600">
                  {room.roll_start_prefix}
                  {String(room.roll_start_num).padStart(3, '0')}
                  {room.roll_start_num === room.roll_end_num
                    ? ''
                    : ` - ${room.roll_start_prefix}${String(room.roll_end_num).padStart(3, '0')}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}