import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { attendanceApi, scheduleApi, timetableApi } from '../api'
import ErrorBanner from './ErrorBanner'
import Spinner from './Spinner'
import StatusCard from './StatusCard'

const SUB_TABS = [
  { id: 'subjects', label: 'Subjects' },
  { id: 'history', label: 'History' },
]

const TARGET_KEY = 'attendance_target'
const STATUSES = ['Present', 'Absent', 'Cancelled']

/** Live IST clock, independent of the viewer's timezone. */
function useIstClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])
  return now
}

/** Format a Date as an IST wall-clock string. */
function istParts(date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    weekday: 'long',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const get = (type) => parts.find((part) => part.type === type)?.value || ''
  return {
    date: `${get('weekday')}, ${get('day')} ${get('month')} ${get('year')}`,
    time: `${get('hour')}:${get('minute')}:${get('second')} IST`,
    weekdayShort: get('weekday').slice(0, 3),
  }
}

/** Today's date as YYYY-MM-DD in IST, for API comparisons. */
function todayIso() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())
}

const toMinutes = (value) => {
  const [hour, minute] = String(value || '0:0').split(':').map(Number)
  return hour * 60 + minute
}

/** Colour bucket for a percentage against the student's target. */
function toneFor(percentage, target) {
  if (percentage >= target) return 'success'
  if (percentage >= target - 10) return 'warning'
  return 'danger'
}

/** Advice line: how many classes to attend / can miss. */
function advice(subject) {
  if (subject.status === 'Critical' || subject.must_attend > 0) {
    return `Attend next ${subject.must_attend} to recover.`
  }
  if (subject.can_miss > 0) return `Can miss ${subject.can_miss} more.`
  return 'At the edge - do not miss any.'
}

export default function Attendance({ onError }) {
  const [subTab, setSubTab] = useState('subjects')
  const [summary, setSummary] = useState(null)
  const [subjects, setSubjects] = useState([])
  const [records, setRecords] = useState([])
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [calendarFor, setCalendarFor] = useState(null)
  const [extraCode, setExtraCode] = useState('')
  const [target, setTarget] = useState(() => Number(localStorage.getItem(TARGET_KEY)) || 75)
  const [targetDraft, setTargetDraft] = useState(() => Number(localStorage.getItem(TARGET_KEY)) || 75)

  const clock = useIstClock()
  const ist = istParts(clock)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [summaryData, subjectData, recordData, slotData] = await Promise.all([
        attendanceApi.summary(),
        attendanceApi.subjects(),
        attendanceApi.records(),
        timetableApi.listSlots().catch(() => []),
      ])
      setSummary(summaryData)
      setSubjects(subjectData.subjects || [])
      setRecords(recordData || [])
      setSlots(Array.isArray(slotData) ? slotData : [])
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

  /** Today's classes for the student's timetable, with periods. */
  const todayClasses = useMemo(() => {
    const weekday = ist.weekdayShort
    const todays = slots
      .filter((slot) => slot.day === weekday)
      .sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time))
    return todays
  }, [slots, ist.weekdayShort])

  /** Which subjects have a class today, and which of those are still unmarked. */
  const todayState = useMemo(() => {
    const today = todayIso()
    const scheduled = new Map()
    todayClasses.forEach((slot) => {
      if (!scheduled.has(slot.course_code)) scheduled.set(slot.course_code, [])
      scheduled.get(slot.course_code).push(slot)
    })

    const idByCode = new Map(subjects.map((subject) => [subject.course_code, subject.course_id]))
    const markedToday = new Set(
      records.filter((record) => record.date === today).map((record) => record.course_id),
    )
    // Only the student's own subjects count towards "unmarked"; the timetable
    // also holds other branches' classes.
    const unmarked = [...scheduled.keys()].filter(
      (code) => idByCode.has(code) && !markedToday.has(idByCode.get(code)),
    ).length

    return { scheduled, unmarked, today, markedToday }
  }, [todayClasses, records, subjects])

  const toastTimer = useRef(null)

  const showToast = (message, undo) => {
    setToast({ message, undo })
    // Auto-dismiss so the toast never sticks around, but long enough to undo.
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), undo ? 8000 : 4000)
  }

  useEffect(() => () => toastTimer.current && clearTimeout(toastTimer.current), [])

  /** Optimistic mark with a one-tap undo. */
  const mark = async (subject, status, dateOverride) => {
    const date = dateOverride || todayState.today
    const previous = subjects
    const delta = status === 'Present' ? 1 : status === 'Absent' ? -1 : 0

    setSubjects((current) =>
      current.map((item) =>
        item.course_id === subject.course_id
          ? {
              ...item,
              present: Math.max(0, item.present + (status === 'Present' ? 1 : 0)),
              absent: Math.max(0, item.absent + (status === 'Absent' ? 1 : 0)),
              cancelled: item.cancelled + (status === 'Cancelled' ? 1 : 0),
            }
          : item,
      ),
    )

    try {
      await attendanceApi.mark({ course_id: subject.course_id, date, status })
      setError(null)
      await load()
      showToast(`${subject.course_code} marked ${status}`, async () => {
        // Undo by removing the record we just created.
        const fresh = await attendanceApi.records(subject.course_id)
        const added = fresh.find(
          (record) => record.date === date && record.status === status,
        )
        if (added) {
          await attendanceApi.remove(added.id).catch(() => {})
        }
        await load()
        setToast(null)
      })
    } catch (err) {
      setSubjects(previous)
      setError(err.message)
      void delta
    }
  }

  const addExtraClass = async () => {
    const code = extraCode.trim().toUpperCase()
    if (!code) return
    try {
      // Extra classes are extra courses on the backend.
      await scheduleApi.addExtra({ code, name: code, semester: 1, branch: 'ALL' })
      setExtraCode('')
      await load()
      showToast(`${code} added`)
    } catch (err) {
      setError(err.message)
    }
  }

  const saveTarget = () => {
    const clamped = Math.min(100, Math.max(0, Number(targetDraft) || 0))
    setTarget(clamped)
    setTargetDraft(clamped)
    localStorage.setItem(TARGET_KEY, String(clamped))
    showToast(`Attendance target set to ${clamped}%`)
  }

  const atRisk = subjects.filter((subject) => subject.must_attend > 0)

  /** course_id -> course_code, so the history table can show codes not ids. */
  const codeById = useMemo(
    () => new Map(subjects.map((subject) => [subject.course_id, subject.course_code])),
    [subjects],
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size={28} className="text-primary-500" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex flex-wrap items-end gap-3">
        <button type="button" onClick={addExtraClass} className="btn-secondary text-sm">
          + Extra Class
        </button>
        <div className="flex items-end gap-2">
          <div>
            <span className="label">Add subject</span>
            <input
              id="att-add-code"
              className="input-field w-36 font-mono"
              value={extraCode}
              onChange={(event) => setExtraCode(event.target.value.toUpperCase())}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  addExtraClass()
                }
              }}
              placeholder="e.g. OE3E33"
            />
          </div>
          <button type="button" onClick={addExtraClass} className="btn-primary text-sm">
            Add
          </button>
        </div>
        <div className="ml-auto flex items-end gap-2">
          <div>
            <span className="label">Target %</span>
            <input
              id="att-target"
              type="number"
              min="0"
              max="100"
              className="input-field w-24"
              value={targetDraft}
              onChange={(event) => setTargetDraft(event.target.value)}
            />
          </div>
          <button type="button" onClick={saveTarget} className="btn-primary text-sm">
            Save
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Daily banner */}
      <div className="card space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-gray-900">{ist.date}</p>
            <p className="text-xs text-gray-500 font-mono">{ist.time}</p>
          </div>
          <div className="flex gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-full bg-primary-50 text-primary-700 font-medium">
              {todayClasses.length} class{todayClasses.length === 1 ? '' : 'es'} today
            </span>
            <span className="px-2.5 py-1 rounded-full bg-gray-100 text-gray-700 font-medium">
              {todayClasses.length === 0
                ? 'No classes'
                : todayState.unmarked > 0
                  ? `${todayState.unmarked} unmarked`
                  : 'All marked'}
            </span>
          </div>
        </div>

        {atRisk.length > 0 && (
          <div className="pt-2 border-t border-gray-100">
            <p className="text-xs font-semibold text-danger-600 mb-1.5">At risk</p>
            <div className="flex flex-wrap gap-2">
              {atRisk.map((subject) => (
                <span
                  key={subject.course_id}
                  className="px-2.5 py-1 rounded-full bg-danger-50 text-danger-700 text-xs font-medium"
                >
                  {subject.course_code} &middot; attend next {subject.must_attend}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Overall */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <StatusCard
            label="Overall attendance"
            value={`${summary.overall_percentage}%`}
            tone={toneFor(summary.overall_percentage, target)}
            subtext={`Target ${target}%`}
          />
          <StatusCard label="Present" value={summary.total_present} tone="success" />
          <StatusCard label="Absent" value={summary.total_absent} tone="danger" />
        </div>
      )}

      {/* Sub-tabs */}
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
        <button type="button" onClick={load} className="btn-ghost ml-auto">
          Refresh
        </button>
      </div>

      {subTab === 'subjects' &&
        (subjects.length === 0 ? (
          <div className="card text-center py-10 text-sm text-gray-500">
            No subjects yet. Upload the class timetable so subjects sync automatically, or add one
            above.
          </div>
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {subjects.map((subject) => (
              <SubjectCard
                key={subject.course_id}
                subject={subject}
                target={target}
                periods={todayState.scheduled.get(subject.course_code) || []}
                hasClassToday={(todayState.scheduled.get(subject.course_code) || []).length > 0}
                onMark={(status) => mark(subject, status)}
                onDetails={() => setCalendarFor(subject)}
              />
            ))}
          </div>
        ))}

      {subTab === 'history' && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Recent records</h3>
          {records.length === 0 ? (
            <p className="text-sm text-gray-500">Nothing recorded yet.</p>
          ) : (
            <div className="overflow-x-auto scrollbar-thin">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-gray-400">
                    <th className="py-2 pr-3 font-medium">Date</th>
                    <th className="py-2 pr-3 font-medium">Course</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {records
                    .slice()
                    .reverse()
                    .slice(0, 50)
                    .map((record) => (
                      <tr key={record.id}>
                        <td className="py-2 pr-3 text-gray-700">{record.date}</td>
                        <td className="py-2 pr-3 font-mono text-gray-900">
                          {codeById.get(record.course_id) || `#${record.course_id}`}
                        </td>
                        <td className="py-2">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                              record.status === 'Present'
                                ? 'bg-success-50 text-success-700'
                                : record.status === 'Absent'
                                  ? 'bg-danger-50 text-danger-700'
                                  : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            {record.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Toast with undo */}
      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-primary-500 text-white text-sm shadow-lg">
          <span>{toast.message}</span>
          {toast.undo && (
            <button
              type="button"
              onClick={() => toast.undo()}
              className="underline font-medium"
            >
              Undo
            </button>
          )}
        </div>
      )}

      {/* Details modal */}
      {calendarFor && (
        <CalendarModal
          subject={calendarFor}
          onClose={() => setCalendarFor(null)}
          onMark={(date, status) => mark(calendarFor, status, date)}
        />
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Subject card                                                        */
/* ------------------------------------------------------------------ */

function SubjectCard({ subject, target, periods, hasClassToday, onMark, onDetails }) {
  const tone = toneFor(subject.percentage, target)
  const barTone = tone === 'success' ? 'bg-success-500' : tone === 'warning' ? 'bg-warning-500' : 'bg-danger-500'

  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">{subject.course_name || subject.course_code}</p>
          <p className="text-[11px] font-mono text-gray-500">{subject.course_code}</p>
        </div>
        <span
          className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
            tone === 'success'
              ? 'bg-success-50 text-success-700'
              : tone === 'warning'
                ? 'bg-warning-50 text-warning-700'
                : 'bg-danger-50 text-danger-700'
          }`}
        >
          {subject.status}
        </span>
      </div>

      <div>
        <p className="text-3xl font-bold text-gray-900 leading-none">{subject.percentage}%</p>
        <p className="text-[11px] text-gray-500 mt-1">
          {subject.present}/{subject.total_held} attended
        </p>
      </div>

      <div className="w-full h-1 rounded-full bg-gray-200">
        <div
          className={`h-1 rounded-full ${barTone} transition-all`}
          style={{ width: `${Math.min(100, subject.percentage)}%` }}
        />
      </div>

      <p className="text-[11px] text-gray-500">{advice(subject)}</p>

      {periods.length > 1 && (
        <div className="flex flex-wrap gap-1">
          {periods.map((slot) => (
            <span
              key={`${slot.id}`}
              className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 text-[10px] font-mono"
              title={slot.room}
            >
              P{periods.indexOf(slot) + 1}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1 mt-auto pt-1">
        {STATUSES.map((status) => {
          // Without a class today there is nothing to mark.
          const disabled = status !== 'Cancelled' && !hasClassToday
          return (
            <button
              key={status}
              type="button"
              title={disabled ? 'No class scheduled today' : `Mark ${status}`}
              onClick={() => onMark(status)}
              disabled={disabled}
              className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                status === 'Present'
                  ? 'bg-success-500 text-white hover:bg-success-600'
                  : status === 'Absent'
                    ? 'bg-danger-500 text-white hover:bg-danger-600'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {status === 'Present' ? 'P' : status === 'Absent' ? 'A' : 'C'}
            </button>
          )
        })}
        <button
          type="button"
          onClick={onDetails}
          className="px-2 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100"
        >
          Details
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Calendar modal                                                      */
/* ------------------------------------------------------------------ */

const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

/** ISO date for a (year, month 1-12, day) triple. */
function iso(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

/** Monday-first grid of the given month, padded with nulls. */
function monthGrid(year, month) {
  const first = new Date(Date.UTC(year, month - 1, 1))
  const offset = (first.getUTCDay() + 6) % 7
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const cells = new Array(offset).fill(null)
  for (let day = 1; day <= daysInMonth; day += 1) cells.push(day)
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}

function CalendarModal({ subject, onClose, onMark }) {
  const today = todayIso()
  const now = new Date()
  const [cursor, setCursor] = useState({
    year: Number(today.slice(0, 4)),
    month: Number(today.slice(5, 7)),
  })
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const data = await attendanceApi.course(subject.course_id)
        if (cancelled) return
        setEntries(data.calendar || [])
      } catch {
        if (!cancelled) setEntries([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [subject.course_id])

  const byDate = useMemo(() => {
    const map = new Map()
    entries.forEach((entry) => {
      if (!map.has(entry.date)) map.set(entry.date, [])
      map.get(entry.date).push(entry)
    })
    return map
  }, [entries])

  const shift = (delta) => {
    setCursor((current) => {
      const next = new Date(Date.UTC(current.year, current.month - 1 + delta, 1))
      return { year: next.getUTCFullYear(), month: next.getUTCMonth() + 1 }
    })
  }

  const monthName = new Date(Date.UTC(cursor.year, cursor.month - 1, 1)).toLocaleString('en-GB', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-md card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">{subject.course_code}</h3>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-700">
            x
          </button>
        </div>

        <div className="flex items-center justify-between mb-2">
          <button type="button" onClick={() => shift(-1)} className="btn-ghost">
            &larr; Prev
          </button>
          <span className="text-sm font-medium text-gray-800">{monthName}</span>
          <button type="button" onClick={() => shift(1)} className="btn-ghost">
            Next &rarr;
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <Spinner size={20} className="text-primary-500" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-7 gap-1 text-center text-[10px] uppercase text-gray-400 mb-1">
              {WEEKDAYS.map((day) => (
                <span key={day}>{day}</span>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {monthGrid(cursor.year, cursor.month).map((day, index) => {
                if (day === null) return <span key={`pad-${index}`} />
                const date = iso(cursor.year, cursor.month, day)
                const marks = byDate.get(date) || []
                const hasExtra = marks.length > 1
                const present = marks.some((m) => m.status === 'Present')
                const absent = marks.some((m) => m.status === 'Absent')
                const cancelled = marks.some((m) => m.status === 'Cancelled')
                const isToday = date === today
                const isPast = date < today
                const tone = present
                  ? 'bg-success-500 text-white'
                  : absent
                    ? 'bg-danger-500 text-white'
                    : cancelled
                      ? 'bg-gray-300 text-gray-700'
                      : isPast
                        ? 'bg-gray-100 text-gray-400 border border-dashed border-gray-300'
                        : 'bg-white text-gray-600 border border-gray-200'
                return (
                  <button
                    key={date}
                    type="button"
                    disabled={!isPast}
                    onClick={() => setSelected(date)}
                    className={`relative aspect-square rounded-md text-xs font-medium ${tone} ${
                      isToday ? 'ring-2 ring-primary-500 ring-offset-1' : ''
                    } ${hasExtra ? 'border-2 border-primary-500' : ''} ${
                      isPast ? 'cursor-pointer' : 'cursor-default'
                    }`}
                  >
                    {day}
                  </button>
                )
              })}
            </div>

            <div className="flex flex-wrap gap-3 mt-3 text-[10px] text-gray-500">
              <Legend className="bg-success-500" label="Present" />
              <Legend className="bg-danger-500" label="Absent" />
              <Legend className="bg-gray-300" label="Cancelled" />
              <Legend className="bg-gray-100 border border-dashed border-gray-300" label="Not marked" />
              <Legend className="bg-white border-2 border-primary-500" label="Extra / multi-period" />
            </div>
          </>
        )}

        {selected && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-700 mb-2">{selected}</p>
            <div className="flex flex-wrap gap-2">
              {STATUSES.map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={async () => {
                    await onMark(selected, status)
                    setSelected(null)
                  }}
                  className="btn-secondary text-xs"
                >
                  Mark {status}
                </button>
              ))}
              <button type="button" onClick={() => setSelected(null)} className="btn-ghost">
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Legend({ className, label }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`w-3 h-3 rounded ${className}`} />
      {label}
    </span>
  )
}