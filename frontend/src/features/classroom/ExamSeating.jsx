import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi, examApi } from '../../api'
import { BRANCH_OPTIONS, PROGRAMME_SEMESTERS } from '../../constants'
import { formatDate, formatTime, todayIso } from '../../lib/time'
import { isPostgraduate, normaliseRoom, splitCourseCodes } from '../../lib/normalise'
import { readQuickLookup, writeQuickLookup } from '../../lib/storage'
import { bumpProfileVersion } from '../../lib/storage'
import useProfile from '../../hooks/useProfile'
import useProfileVersion from '../../hooks/useProfileVersion'
import ErrorBanner from '../../components/ErrorBanner'
import FileUpload from '../../components/FileUpload'
import Spinner from '../../components/Spinner'
import UploadPreview from '../../components/UploadPreview'

const SUB_TABS = [
  { id: 'timetable', label: 'Exam Timetable' },
  { id: 'seating', label: 'Exam Seating Index' },
]

const PREVIEW_ROWS = 20

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

  const { branch: profileBranch, semester: profileSemester, electiveCodes } = useProfile()
  const profileVersion = useProfileVersion()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusData, timetableData] = await Promise.all([
        examApi.status(),
        examApi.getTimetable(),
      ])
      setStatus(statusData)
      setTimetable(timetableData)
      // The dropdowns default to the profile. `||` rather than a "keep current"
      // guard: a branch change must move the default, and the user can still
      // override it afterwards.
      setSemester(String(profileSemester ?? timetableData?.profile?.semester ?? ''))
      setBranch(profileBranch || timetableData?.profile?.branch || '')
      setError(null)
    } catch (err) {
      // Keep the last good data: a failed refresh must not blank the exam views.
      setError(err.message)
      onError?.(err.message)
    } finally {
      setLoading(false)
    }
  }, [onError, profileBranch, profileSemester])

  // Refetch on mount and whenever the profile changes, in this tab or another.
  useEffect(() => {
    load()
  }, [load, profileVersion])

  /**
   * Prefill the roll, and restore the last lookup.
   *
   * The saved result is restored so a refresh does not lose it, but it is
   * re-fetched on the next search, never treated as current data.
   */
  useEffect(() => {
    const saved = readQuickLookup()
    if (saved) {
      setLookup(saved)
      setRoll(saved.roll)
      return
    }
    // No cached lookup: /auth/me is the source for the roll number.
    let cancelled = false
    ;(async () => {
      try {
        const user = await authApi.me()
        if (!cancelled && user?.roll_number) setRoll(user.roll_number)
      } catch {
        /* the user can type a roll manually */
      }
    })()
    return () => { cancelled = true }
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

  /**
   * Semester/branch narrowing of the exam timetable.
   *
   * PG papers are hidden from a UG student and vice versa, and a cell listing
   * two codes ("OE3M27/ME5D02") counts as two papers rather than one.
   */
  const visibleDays = useMemo(() => {
    if (!timetable?.days) return []
    const studentIsPg = isPostgraduate(branch)

    return timetable.days
      .map((day) => ({
        ...day,
        exams: day.exams
          // A paired cell is two papers.
          .flatMap((exam) =>
            splitCourseCodes(exam.course_code).map((code) => ({ ...exam, course_code: code })),
          )
          .filter((exam) => {
            if (semester && String(exam.semester ?? '') !== semester) return false
            if (!branch || !exam.branch) return true
            // A PG paper is not a UG student's, and vice versa.
            if (isPostgraduate(exam.branch) !== studentIsPg) return false
            return (
              exam.branch === branch ||
              exam.branch.split(' ')[0] === branch.split(' ')[0]
            )
          }),
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

  /**
   * Electives in the index that the student has not chosen.
   *
   * Shown as a hint, because "my papers are missing" is otherwise impossible to
   * explain: the papers are in the index, just not opted into.
   */
  const hiddenElectives = useMemo(() => {
    const seen = new Set()
    ;(timetable?.days || []).forEach((day) => {
      day.exams.forEach((exam) => {
        splitCourseCodes(exam.course_code).forEach((code) => {
          if (/^(OE|OI)/i.test(code)) seen.add(code)
        })
      })
    })
    return [...seen].filter((code) => !electiveCodes.includes(code)).sort()
  }, [timetable, electiveCodes])

  const runLookup = async (event) => {
    event.preventDefault()
    if (!roll.trim()) return
    setLooking(true)
    setLookupError(null)
    try {
      const data = await examApi.lookup(roll.trim().toUpperCase())
      // Drop duplicate rooms for the same course/date, and split paired codes.
      const seen = new Set()
      const exams = (data.exams || [])
        .flatMap((exam) =>
          splitCourseCodes(exam.course_code).map((code) => ({ ...exam, course_code: code })),
        )
        .filter((exam) => {
          const key = `${exam.course_code}|${exam.date}|${normaliseRoom(exam.room)}`
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
      // Cached so a refresh can restore it; the server remains the source.
      writeQuickLookup(result)
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
      // Tell the other tabs this section's data changed.
      bumpProfileVersion()
    } catch (err) {
      setError(err.message)
    }
  }

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

      {/* Upload cards, side by side whether or not they hold data */}
      <div className="grid md:grid-cols-2 gap-4">
        <ExamUploadCard
          title="Exam Timetable"
          kind="timetable"
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
          kind="seating"
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
          hiddenElectives={hiddenElectives}
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

      {/* Clash check sits at the bottom of the Exam section */}
      <ExamClashCard />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Personal exam clash check                                            */
/* ------------------------------------------------------------------ */

/**
 * "Am I double-booked?"
 *
 * Compares only the exams this student actually sits and reports the ones that
 * share a date and an overlapping time - typically an extra or back-log course
 * scheduled against a regular one. A large exam split across several halls is
 * one exam, not a clash.
 */
function ExamClashCard() {
  const profileVersion = useProfileVersion()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await examApi.clashes())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Re-check whenever the profile changes (branch, semester or electives).
  useEffect(() => {
    load()
  }, [load, profileVersion])

  if (loading) {
    return (
      <div className="card flex items-center justify-center gap-3 py-5 text-sm text-gray-500">
        <Spinner size={16} className="text-primary-500" />
        Checking your exam schedule for clashes…
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">Exam clash check</h3>
        <ErrorBanner message={error} onDismiss={() => setError(null)} />
        <button type="button" onClick={load} className="btn-ghost mt-2">
          Try again
        </button>
      </div>
    )
  }

  const clashes = data?.clashes || []
  const examCount = data?.exam_count || 0

  return (
    <div className="card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Exam clash check</h3>
          <p className="text-xs text-gray-500">
            Compares your {examCount} exam{examCount === 1 ? '' : 's'} for overlapping times.
          </p>
        </div>
        <button type="button" onClick={load} className="btn-ghost">
          Re-check
        </button>
      </div>

      {clashes.length === 0 ? (
        <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-success-500 shrink-0" />
          No clashes - none of your exams overlap.
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-danger-700">
            {clashes.length} clash{clashes.length === 1 ? '' : 'es'} found. You cannot sit both papers
            in each pair.
          </p>
          {clashes.map((clash, index) => (
            <div
              key={`${clash.date}-${clash.start_time}-${index}`}
              className="p-3 rounded-lg border border-danger-200 bg-danger-50"
            >
              <p className="text-xs font-semibold text-danger-800">
                {formatDate(clash.date)}
                {clash.day ? ` (${clash.day})` : ''} · {formatTime(clash.start_time)} -{' '}
                {formatTime(clash.end_time)}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {clash.courses.map((course, position) => (
                  <span key={`${course.course_code}-${position}`} className="flex items-center gap-2">
                    {position > 0 && <span className="text-xs font-bold text-danger-600">vs</span>}
                    <span className="px-2.5 py-1 rounded-lg bg-white border border-danger-200 text-xs">
                      <span className="font-mono font-semibold text-gray-900">{course.course_code}</span>
                      {course.rooms.length > 0 && (
                        <span className="text-gray-500">
                          {' '}
                          @ <span className="font-mono">{course.rooms.join(', ')}</span>
                        </span>
                      )}
                      {course.is_extra && (
                        <span className="ml-1.5 text-[10px] font-semibold text-primary-600">EXTRA</span>
                      )}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Upload card, with a preview of the latest file uploaded to it        */
/* ------------------------------------------------------------------ */

/**
 * A card for one exam section's upload, showing what is currently stored and
 * previewing the PDF that produced it.
 */
function ExamUploadCard({ title, kind, count, onUpload, onRemove }) {
  // Stable identities, so UploadPreview does not re-fetch on every render.
  const fetchLatest = useCallback(() => examApi.latestUpload(kind), [kind])
  const loadObjectUrl = useCallback(() => examApi.previewObjectUrl(kind), [kind])

  return (
    <FileUpload label={title} accept=".pdf,.csv" onUpload={onUpload}>
      {count > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-gray-700">Uploaded ({count} entries)</span>
            <button
              type="button"
              onClick={onRemove}
              className="text-xs font-medium text-danger-600 hover:text-danger-700"
            >
              Remove
            </button>
          </div>

          <UploadPreview
            refreshKey={count}
            fetchLatest={fetchLatest}
            loadObjectUrl={loadObjectUrl}
            rowClassName="flex items-center justify-between gap-2"
            emptyHint="No preview available - upload the file again to preview it."
          />
        </div>
      )}
    </FileUpload>
  )
}

/* ------------------------------------------------------------------ */
/* Exam timetable view                                                  */
/* ------------------------------------------------------------------ */

function TimetableView({
  days,
  semester,
  setSemester,
  branch,
  setBranch,
  isSynced,
  hiddenCount,
  total,
  hiddenElectives = [],
}) {
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

      {hiddenElectives.length > 0 && (
        <p className="mt-2 text-xs text-gray-500">
          {hiddenElectives.length} elective{hiddenElectives.length === 1 ? '' : 's'} in this index{' '}
          {hiddenElectives.length === 1 ? 'is' : 'are'} not in your profile:{' '}
          <span className="font-mono">{hiddenElectives.slice(0, 6).join(', ')}</span>
          {hiddenElectives.length > 6 && ` +${hiddenElectives.length - 6} more`}. Add one under
          Profile &rarr; Electives to see its paper.
        </p>
      )}

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

/**
 * Does a row's branch satisfy the chosen filter?
 *
 * Matched on the leading word so the dropdown's programme-level choices line up
 * with the index's section-level labels in both directions: `DS` matches the
 * `DS A`/`DS B` rows, and `CSE A` matches `CSE B`, because a student in one CSE
 * section genuinely appears in the index rows of both. Rows with no recorded
 * branch stay visible instead of silently disappearing.
 */
function branchMatches(rowBranch, selected) {
  if (!selected || !rowBranch) return true
  return rowBranch === selected || rowBranch.split(' ')[0] === selected.split(' ')[0]
}

function SeatingView({ data, showAll, setShowAll, onLoad }) {
  const [semester, setSemester] = useState('')
  const [branch, setBranch] = useState('')

  const allRows = useMemo(
    () =>
      data?.days
        ? data.days.flatMap((day) =>
            day.rooms.map((room) => ({ ...room, date: day.date, day: day.day })),
          )
        : [],
    [data],
  )

  // Start from the profile, exactly as the exam timetable does.
  useEffect(() => {
    setSemester((current) => current || String(data?.profile?.semester ?? ''))
    setBranch((current) => current || data?.profile?.branch || '')
  }, [data])

  /** Client-side semester/branch narrowing of the returned rows. */
  const rows = useMemo(
    () =>
      allRows.filter(
        (room) =>
          (!semester || String(room.semester ?? '') === semester) &&
          (!branch || branchMatches(room.branch, branch)),
      ),
    [allRows, semester, branch],
  )

  const hiddenCount = allRows.length - rows.length
  const isSynced =
    String(data?.profile?.semester) === semester &&
    (data?.profile?.branch || '') === branch

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

  const visible = showAll ? rows : rows.slice(0, PREVIEW_ROWS)

  return (
    <div className="space-y-3">
      <div className="card flex flex-wrap items-end gap-3">
        <div>
          <span className="label">Semester</span>
          <select
            id="seating-semester"
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
            id="seating-branch"
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

      <div className="flex flex-wrap items-center gap-3">
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

      {rows.length === 0 ? (
        <div className="card text-center py-8 text-sm text-gray-500">
          Nothing matches these filters.
        </div>
      ) : (
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
      )}
    </div>
  )
}