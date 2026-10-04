import { useCallback, useEffect, useMemo, useState } from 'react'
import { bumpProfileVersion, profileApi, scheduleApi, timetableApi } from '../api'
import {
  BRANCH_OPTIONS,
  PROGRAMMES,
  PROGRAMME_SEMESTERS,
  semesterLabel,
} from '../constants'
import ErrorBanner from './ErrorBanner'
import FileUpload from './FileUpload'
import Spinner from './Spinner'
import StatusCard from './StatusCard'

const SUB_TABS = [
  { id: 'schedule', label: 'Schedule' },
  { id: 'profile', label: 'Profile' },
  { id: 'timetable', label: 'Timetable' },
]

const TARGET_KEY = 'attendance_target'

/** "09:00" -> minutes, for overlap maths. */
function toMinutes(value) {
  const [hour, minute] = String(value || '0:0').split(':').map(Number)
  return hour * 60 + minute
}

/** Format "14:30" as "2:30 PM". */
function formatTime(value) {
  if (!value) return ''
  const [hour, minute] = value.split(':')
  const h = Number(hour)
  const suffix = h >= 12 ? 'PM' : 'AM'
  const display = h % 12 === 0 ? 12 : h % 12
  return `${display}:${minute} ${suffix}`
}

/** Course code once; "(CODE)" appended only when the name differs. */
function courseLabel(item) {
  const name = (item.course_name || '').trim()
  const code = (item.course_code || '').trim()
  if (!name || name === code) return code || name
  return `${name} (${code})`
}

export default function LiveSchedule({ onError }) {
  const [subTab, setSubTab] = useState('schedule')
  const [schedule, setSchedule] = useState(null)
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [now, slotList] = await Promise.all([
        scheduleApi.now(),
        timetableApi.listSlots().catch(() => []),
      ])
      setSchedule(now)
      setSlots(Array.isArray(slotList) ? slotList : [])
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

  // Auto-refresh the live schedule every minute.
  useEffect(() => {
    const timer = setInterval(load, 60000)
    return () => clearInterval(timer)
  }, [load])

  const current = schedule?.current_class || null

  /** Other classes running in the same slot as the current one. */
  const sameTimeSlot = useMemo(() => {
    if (!current) return []
    const start = toMinutes(current.start_time)
    const end = toMinutes(current.end_time)
    return slots.filter(
      (slot) =>
        slot.day === current.day &&
        toMinutes(slot.start_time) < end &&
        toMinutes(slot.end_time) > start &&
        !(slot.course_code === current.course_code && slot.start_time === current.start_time),
    )
  }, [current, slots])

  if (loading && !schedule) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size={28} className="text-primary-500" />
      </div>
    )
  }

  return (
    <div className="space-y-5">
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
        <button type="button" onClick={load} className="btn-ghost ml-auto" disabled={loading}>
          {loading ? <Spinner size={14} /> : 'Refresh'}
        </button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {subTab === 'schedule' && (
        <ScheduleView
          schedule={schedule}
          current={current}
          sameTimeSlot={sameTimeSlot}
          formatTime={formatTime}
          courseLabel={courseLabel}
          hasTimetable={slots.length > 0}
        />
      )}

      {subTab === 'profile' && <ProfileView onSaved={load} />}

      {subTab === 'timetable' && <TimetableView slots={slots} onChanged={load} />}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Schedule                                                            */
/* ------------------------------------------------------------------ */

function ClassCard({ title, tone, item, emptyText, formatTime, courseLabel }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-3">
        <span className={`w-2 h-2 rounded-full bg-${tone}-500`} />
        {title}
      </h3>
      {item ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Cell label="Course" value={courseLabel(item)} mono />
          <Cell label="Room" value={item.room} mono />
          <Cell label="Time" value={`${formatTime(item.start_time)} - ${formatTime(item.end_time)}`} />
          <Cell label="Day" value={item.day} />
        </div>
      ) : (
        <p className="text-sm text-gray-500 py-3">{emptyText}</p>
      )}
    </div>
  )
}

function Cell({ label, value, mono }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`text-sm font-medium text-gray-900 ${mono ? 'font-mono' : ''}`}>{value || '—'}</p>
    </div>
  )
}

function ScheduleView({ schedule, current, sameTimeSlot, formatTime, courseLabel, hasTimetable }) {
  return (
    <div className="space-y-4">
      {!hasTimetable && (
        <div className="p-3 rounded-lg border border-primary-200 bg-primary-50 text-primary-700 text-sm">
          No class timetable uploaded yet. Open the Timetable tab to add it.
        </div>
      )}

      {schedule?.message && !current && (
        <div className="p-3 rounded-lg border border-gray-200 bg-white text-gray-600 text-sm">
          {schedule.message}
          {schedule.current_time && (
            <span className="block text-xs text-gray-400 mt-0.5">Server time: {schedule.current_time}</span>
          )}
        </div>
      )}

      <ClassCard
        title="Current Class"
        tone="success"
        item={current}
        emptyText="No class right now."
        formatTime={formatTime}
        courseLabel={courseLabel}
      />
      <ClassCard
        title="Next Class"
        tone="warning"
        item={schedule?.next_class}
        emptyText="No upcoming classes."
        formatTime={formatTime}
        courseLabel={courseLabel}
      />

      {sameTimeSlot.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Also running now</h3>
          <div className="space-y-2">
            {sameTimeSlot.map((slot) => (
              <div
                key={`${slot.course_code}-${slot.start_time}-${slot.room}`}
                className="flex items-center justify-between p-2.5 rounded-lg bg-gray-50"
              >
                <span className="text-sm text-gray-900 font-mono">{slot.course_code}</span>
                <span className="text-xs text-gray-600">
                  {formatTime(slot.start_time)} - {formatTime(slot.end_time)} &middot;{' '}
                  <span className="font-mono">{slot.room}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Profile                                                             */
/* ------------------------------------------------------------------ */

function ProfileView({ onSaved }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [extras, setExtras] = useState([])
  const [extraCode, setExtraCode] = useState('')
  const [target, setTarget] = useState(() => Number(localStorage.getItem(TARGET_KEY)) || 75)

  // Branch change block
  const [branchFrom, setBranchFrom] = useState('')
  const [branchTo, setBranchTo] = useState('')
  const [noBranchChange, setNoBranchChange] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [data, extraList] = await Promise.all([profileApi.get(), scheduleApi.listExtra().catch(() => [])])
      setProfile(data)
      setBranchFrom(data.branch || '')
      setNoBranchChange(!data.branch_change_requested)
      if (data.branch_change_requested && data.requested_branch) setBranchTo(data.requested_branch)
      setExtras(Array.isArray(extraList) ? extraList : [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const semesters = profile ? PROGRAMME_SEMESTERS[profile.programme] || PROGRAMME_SEMESTERS.BTech : []

  const patch = (key, value) => {
    setProfile((previous) => ({ ...previous, [key]: value }))
    setMessage(null)
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const updated = await profileApi.update({
        programme: profile.programme,
        semester: Number(profile.semester),
        branch: profile.branch,
        elective_codes: profile.elective_codes || [],
      })
      setProfile(updated)
      localStorage.setItem(TARGET_KEY, String(target))
      bumpProfileVersion()
      setMessage('Profile saved')
      onSaved?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const submitBranchChange = async () => {
    setError(null)
    setMessage(null)
    try {
      if (noBranchChange) {
        const result = await profileApi.clearBranchChange()
        setMessage(result.message)
        setBranchTo('')
        // Requesting nothing resets the checkbox to its resting state.
        setNoBranchChange(true)
      } else {
        if (!branchTo) {
          setError('Select the branch you want to move to')
          return
        }
        const result = await profileApi.requestBranchChange({
          from_branch: branchFrom,
          to_branch: branchTo,
        })
        setMessage(result.message)
        // A made request clears the "no branch change" tick.
        setNoBranchChange(false)
      }
      const fresh = await profileApi.get()
      setProfile(fresh)
      setBranchFrom(fresh.branch)
      bumpProfileVersion()
    } catch (err) {
      setError(err.message)
    }
  }

  const addExtra = async () => {
    const code = extraCode.trim().toUpperCase()
    if (!code) return
    setError(null)
    try {
      // An OE course is open to every branch, so it is stored as an elective.
      const isOE = code.startsWith('OE')
      if (isOE) {
        await profileApi.update({
          elective_codes: [...(profile.elective_codes || []), code],
        })
      } else {
        await scheduleApi.addExtra({
          code,
          name: code,
          semester: Number(profile.semester),
          branch: profile.branch,
        })
      }
      setExtraCode('')
      const fresh = await profileApi.get()
      setProfile(fresh)
      setExtras(await scheduleApi.listExtra())
      bumpProfileVersion()
      setMessage(`${code} added`)
    } catch (err) {
      setError(err.message)
    }
  }

  const removeExtra = async (code) => {
    try {
      if (code.startsWith('OE')) {
        await profileApi.update({
          elective_codes: (profile.elective_codes || []).filter((item) => item !== code),
        })
        setProfile(await profileApi.get())
      } else {
        await scheduleApi.removeExtra(code)
        setExtras(await scheduleApi.listExtra())
      }
      bumpProfileVersion()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading || !profile) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size={24} className="text-primary-500" />
      </div>
    )
  }

  const electives = profile.elective_codes || []
  const nonOECourses = extras.filter((course) => !course.code.startsWith('OE'))

  return (
    <div className="space-y-4">
      {message && (
        <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
          {message}
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Profile</h3>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <span className="label">Programme</span>
            <select
              id="pf-programme"
              className="select-field"
              value={profile.programme || 'BTech'}
              onChange={(event) => {
                const programme = event.target.value
                const options = PROGRAMME_SEMESTERS[programme] || []
                setProfile({
                  ...profile,
                  programme,
                  semester: options.includes(Number(profile.semester)) ? profile.semester : options[0],
                })
              }}
            >
              {PROGRAMMES.map((programme) => (
                <option key={programme} value={programme}>{programme}</option>
              ))}
            </select>
          </div>

          <div>
            <span className="label">Semester</span>
            <select
              id="pf-semester"
              className="select-field"
              value={profile.semester}
              onChange={(event) => patch('semester', event.target.value)}
            >
              {semesters.map((value) => (
                <option key={value} value={value}>{semesterLabel(value)}</option>
              ))}
            </select>
          </div>

          <div>
            <span className="label">Branch</span>
            <select
              id="pf-branch"
              className="select-field"
              value={profile.branch || ''}
              onChange={(event) => patch('branch', event.target.value)}
            >
              <option value="">Select branch</option>
              {BRANCH_OPTIONS.map((branch) => (
                <option key={branch} value={branch}>{branch}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Electives and extra / backlog courses */}
        <div>
          <span className="label">Electives and extra courses</span>
          <div className="flex gap-2">
            <input
              id="pf-extra-code"
              className="input-field font-mono"
              value={extraCode}
              onChange={(event) => setExtraCode(event.target.value.toUpperCase())}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  addExtra()
                }
              }}
              placeholder="e.g. OE3E33 or HS1001"
            />
            <button type="button" onClick={addExtra} className="btn-secondary text-sm shrink-0">
              Add
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            OE courses are open to every branch; anything else is added as an extra course.
          </p>

          {(electives.length > 0 || nonOECourses.length > 0) && (
            <div className="flex flex-wrap gap-2 mt-3">
              {electives.map((code) => (
                <Chip key={code} code={code} onRemove={() => removeExtra(code)} />
              ))}
              {nonOECourses.map((course) => (
                <Chip key={course.code} code={course.code} onRemove={() => removeExtra(course.code)} />
              ))}
            </div>
          )}
        </div>

        {/* Attendance target */}
        <div>
          <span className="label">Attendance target (%)</span>
          <div className="flex items-center gap-2">
            <input
              id="pf-target"
              type="number"
              min="0"
              max="100"
              className="input-field w-28"
              value={target}
              onChange={(event) => setTarget(Number(event.target.value))}
            />
            <span className="text-xs text-gray-500">Used by the Attendance tab for risk colouring.</span>
          </div>
        </div>

        <div className="flex justify-end">
          <button type="button" onClick={save} className="btn-primary text-sm" disabled={saving}>
            {saving ? <Spinner size={16} className="text-white" /> : 'Save profile'}
          </button>
        </div>
      </div>

      {/* Branch change, inside the profile */}
      <div className="card space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Branch Change</h3>
          {profile.original_branch && (
            <p className="text-xs text-gray-500">Admitted branch: {profile.original_branch}</p>
          )}
        </div>

        {profile.branch_change_requested && profile.requested_branch && (
          <div className="p-2.5 rounded-lg border border-primary-200 bg-primary-50 text-primary-700 text-sm">
            Pending request: {profile.branch} &rarr; {profile.requested_branch}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <span className="label">From branch</span>
            <select
              id="bc-from"
              className="select-field"
              value={branchFrom}
              onChange={(event) => setBranchFrom(event.target.value)}
            >
              <option value="">Select branch</option>
              {BRANCH_OPTIONS.map((branch) => (
                <option key={branch} value={branch}>{branch}</option>
              ))}
            </select>
          </div>
          <div>
            <span className="label">To branch</span>
            <select
              id="bc-to"
              className="select-field"
              value={branchTo}
              disabled={noBranchChange}
              onChange={(event) => setBranchTo(event.target.value)}
            >
              <option value="">Select branch</option>
              {BRANCH_OPTIONS.map((branch) => (
                <option key={branch} value={branch}>{branch}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <button type="button" onClick={submitBranchChange} className="btn-primary text-sm">
            Change Branch
          </button>
          <label className="inline-flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              id="bc-none"
              type="checkbox"
              checked={noBranchChange}
              onChange={(event) => {
                const checked = event.target.checked
                setNoBranchChange(checked)
                // Ticking the box resets any pending request inputs.
                if (checked) {
                  setBranchTo('')
                  setMessage(null)
                }
              }}
              className="w-4 h-4 rounded border-gray-300"
            />
            No branch change
          </label>
        </div>
      </div>
    </div>
  )
}

function Chip({ code, onRemove }) {
  return (
    <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-primary-50 text-primary-700 text-xs font-medium font-mono">
      {code}
      <button type="button" onClick={onRemove} className="text-primary-400 hover:text-danger-600" aria-label={`Remove ${code}`}>
        x
      </button>
    </span>
  )
}

/* ------------------------------------------------------------------ */
/* Timetable upload                                                     */
/* ------------------------------------------------------------------ */

function TimetableView({ slots, onChanged }) {
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  const clearAll = async () => {
    if (!window.confirm('Remove every timetable slot?')) return
    setBusy(true)
    try {
      // Clear All must tolerate an empty (204 / no body) response.
      const result = await timetableApi.clear().catch(() => null)
      setMessage(result?.message || 'Timetable cleared')
      setError(null)
      onChanged?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {message && (
        <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
          {message}
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="grid md:grid-cols-2 gap-4">
        <FileUpload
          label="Upload class timetable"
          accept=".pdf,.csv"
          storageKey="timetable_file"
          hint="The master timetable PDF or CSV."
          onUpload={async (file) => {
            const result = await timetableApi.upload(file)
            onChanged?.()
            return result
          }}
        />

        <div className="card p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Uploaded timetable</h3>
          <StatusCard
            label="Slots loaded"
            value={slots.length}
            tone={slots.length ? 'success' : 'default'}
            subtext={slots.length ? 'Live schedule and vacant rooms use these slots.' : 'Nothing uploaded yet.'}
          />
          <button type="button" onClick={clearAll} className="btn-danger text-sm" disabled={busy || slots.length === 0}>
            Clear All
          </button>
        </div>
      </div>

      {slots.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Preview (first 20)</h3>
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-gray-400">
                  <th className="py-2 pr-3 font-medium">Day</th>
                  <th className="py-2 pr-3 font-medium">Time</th>
                  <th className="py-2 pr-3 font-medium">Course</th>
                  <th className="py-2 font-medium">Room</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {slots.slice(0, 20).map((slot) => (
                  <tr key={slot.id}>
                    <td className="py-2 pr-3 text-gray-700">{slot.day}</td>
                    <td className="py-2 pr-3 text-gray-600">
                      {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
                    </td>
                    <td className="py-2 pr-3 font-mono text-gray-900">{slot.course_code}</td>
                    <td className="py-2 font-mono text-primary-600">{slot.room}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {slots.length > 20 && (
            <p className="text-xs text-gray-400 mt-2">Showing 20 of {slots.length}.</p>
          )}
        </div>
      )}
    </div>
  )
}