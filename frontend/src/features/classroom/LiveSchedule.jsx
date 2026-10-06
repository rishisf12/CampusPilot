import { useCallback, useEffect, useMemo, useState } from 'react'
import { profileApi, scheduleApi, timetableApi } from '../../api'
import {
  BRANCH_OPTIONS,
  DAYS,
  PROGRAMMES,
  PROGRAMME_SEMESTERS,
  semesterLabel,
} from '../../constants'
import { formatTime as formatClock, istNow, todayWeekday } from '../../lib/time'
import { afterProfileChange, afterTimetableChange } from '../../lib/sync'
import { isOpenElective, splitCourseCodes, toMinutes } from '../../lib/normalise'
import useProfile from '../../hooks/useProfile'
import useProfileCourses from '../../hooks/useProfileCourses'
import useProfileVersion from '../../hooks/useProfileVersion'
import ErrorBanner from '../../components/ErrorBanner'
import FileUpload from '../../components/FileUpload'
import ManagePasskeys from '../../components/ManagePasskeys'
import UploadPreview from '../../components/UploadPreview'
import Spinner from '../../components/Spinner'
import StatusCard from '../../components/StatusCard'

const SUB_TABS = [
  { id: 'schedule', label: 'Schedule' },
  { id: 'profile', label: 'Profile' },
  { id: 'timetable', label: 'Timetable' },
]

const formatTime = formatClock

/** "Mon" -> "Monday", for the weekday headings. */
const DAY_NAMES = {
  Mon: 'Monday',
  Tue: 'Tuesday',
  Wed: 'Wednesday',
  Thu: 'Thursday',
  Fri: 'Friday',
  Sat: 'Saturday',
  Sun: 'Sunday',
}

/** Weekday order, so Monday comes before Tuesday however the rows arrived. */
const WEEKDAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

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
  const profileVersion = useProfileVersion()
  const { semester, optedInCodes } = useProfile()

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
      // Keep the last good schedule on screen; a failed refresh is not a reason
      // to blank the screen or sign the user out.
      setError(err.message)
      onError?.(err.message)
    } finally {
      setLoading(false)
    }
  }, [onError])

  useEffect(() => {
    load()
  }, [load, profileVersion])

  // Auto-refresh the live schedule every minute.
  useEffect(() => {
    const timer = setInterval(load, 60000)
    return () => clearInterval(timer)
  }, [load])

  const current = schedule?.current_class || null

  /**
   * The student's own classes, narrowed by their profile.
   *
   * The master timetable holds every branch, so the backend's current/next class
   * can be a paper the student does not sit. This list is the filtered truth,
   * and the same-slot lookup is derived from it.
   */
  const myClasses = useProfileCourses(slots)

  /**
   * Electives that are scheduled in this semester but not claimed by the profile.
   *
   * They are no longer shown - that was most of the timetable, and courses nobody
   * chose - but they must not simply vanish. The count is surfaced on the
   * timetable so a student who *is* sitting one can add it and see it.
   */
  const hiddenElectives = useMemo(() => {
    const claimed = new Set((optedInCodes || []).map((code) => String(code).toUpperCase()))
    const found = new Set()
    for (const slot of slots || []) {
      if (semester && slot.semester && slot.semester !== semester) continue
      for (const code of splitCourseCodes(slot.course_code)) {
        const upper = code.toUpperCase()
        if (isOpenElective(upper) && !claimed.has(upper)) found.add(upper)
      }
    }
    return [...found].sort()
  }, [slots, semester, optedInCodes])

  const myCurrent = useMemo(() => {
    const today = todayWeekday()
    const nowMinutes = istNow().minutes
    return (
      myClasses.find(
        (slot) =>
          slot.day === today &&
          toMinutes(slot.start_time) <= nowMinutes &&
          nowMinutes < toMinutes(slot.end_time),
      ) || null
    )
  }, [myClasses])

  /** Other classes running in the same slot as the current one. */
  const sameTimeSlot = useMemo(() => {
    if (!myCurrent) return []
    const start = toMinutes(myCurrent.start_time)
    const end = toMinutes(myCurrent.end_time)
    return myClasses.filter(
      (slot) =>
        slot.day === myCurrent.day &&
        toMinutes(slot.start_time) < end &&
        toMinutes(slot.end_time) > start &&
        !(slot.course_code === myCurrent.course_code && slot.start_time === myCurrent.start_time),
    )
  }, [myCurrent, myClasses])

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
          current={myCurrent}
          nextClass={schedule?.next_class}
          sameTimeSlot={sameTimeSlot}
          formatTime={formatTime}
          courseLabel={courseLabel}
          hasTimetable={slots.length > 0}
          myClasses={myClasses}
        />
      )}

      {subTab === 'profile' && <ProfileView onSaved={load} />}

      {subTab === 'timetable' && (
        <TimetableView
          slots={myClasses}
          onChanged={load}
          totalSlots={slots.length}
          hiddenElectives={hiddenElectives}
        />
      )}
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

/**
 * The student's day at a glance, plus the next class.
 *
 * The current class comes from the profile-filtered timetable rather than the
 * server's answer, because the master timetable lists every branch and the
 * backend cannot know which electives the student opted into.
 */
function ScheduleView({
  current,
  nextClass,
  sameTimeSlot,
  formatTime,
  courseLabel,
  hasTimetable,
  myClasses,
}) {
  const today = todayWeekday()

  /** The student's classes today, then the next one later in the week. */
  const { todaySlots, upcoming } = useMemo(() => {
    const now = istNow().minutes
    const todays = myClasses
      .filter((slot) => slot.day === today)
      .sort((a, b) => a.sort_key - b.sort_key)

    let next = null
    WEEKDAY_ORDER.forEach((day, offset) => {
      if (next) return
      const candidates = myClasses
        .filter((slot) => slot.day === day && (offset > 0 || toMinutes(slot.start_time) > now))
        .sort((a, b) => a.sort_key - b.sort_key)
      if (candidates.length) next = candidates[0]
    })

    return { todaySlots: todays, upcoming: next }
  }, [myClasses, today])

  return (
    <div className="space-y-4">
      {!hasTimetable && (
        <div className="p-3 rounded-lg border border-primary-200 bg-primary-50 text-primary-700 text-sm">
          No class timetable uploaded yet. Open the Timetable tab to add it.
        </div>
      )}

      {todaySlots.length === 0 && hasTimetable && (
        <div className="p-3 rounded-lg border border-gray-200 bg-white text-gray-600 text-sm">
          No classes for you on {DAY_NAMES[today]}.
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
        item={nextClass || upcoming}
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

/**
 * Profile settings: the single source of truth for everything else.
 *
 * Semester, branch, electives, extra courses and the attendance target are all
 * written to the backend here, and every save ends with `afterProfileChange()`,
 * which bumps the profile version and re-syncs attendance so the timetable,
 * attendance, rooms and both exam views all pick the change up.
 */
function ProfileView({ onSaved }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [extras, setExtras] = useState([])
  const [extraCode, setExtraCode] = useState('')
  const [target, setTarget] = useState(75)
  // Team-finding fields: comma-separated skill tags plus a short bio/contact.
  const [skillsText, setSkillsText] = useState('')
  const [bio, setBio] = useState('')
  const [contact, setContact] = useState('')

  // Branch change block
  const [branchFrom, setBranchFrom] = useState('')
  const [branchTo, setBranchTo] = useState('')
  const [noBranchChange, setNoBranchChange] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [data, extraList] = await Promise.all([profileApi.get(), scheduleApi.listExtra().catch(() => [])])
      setProfile(data)
      // The target lives on the profile, so it loads from there, not from storage.
      setTarget(Number(data.attendance_target ?? 75))
      setSkillsText((data.skills || []).join(', '))
      setBio(data.bio || '')
      setContact(data.contact || '')
      setBranchFrom(data.branch || '')
      setNoBranchChange(!data.branch_change_requested)
      setBranchTo(data.branch_change_requested && data.requested_branch ? data.requested_branch : '')
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
        // The attendance target is part of the profile, so it is saved with it.
        attendance_target: Number(target),
        // Skills drive My Team matching; free-form, normalised server-side.
        skills: skillsText.split(',').map((tag) => tag.trim()).filter(Boolean),
        bio: bio.trim(),
        contact: contact.trim(),
      })
      setProfile(updated)
      setTarget(Number(updated.attendance_target ?? target))
      setMessage('Profile saved')
      // Tell every dependent screen, then re-sync attendance for the new branch.
      await afterProfileChange()
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
      // The effective branch may have moved, so every screen must refetch.
      await afterProfileChange()
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
      // An extra course changes what the student sits, so re-sync everything.
      await afterProfileChange()
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
      await afterProfileChange()
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

        {/* Team-finding: skills drive My Team matching, bio/contact show on teams */}
        <div>
          <span className="label">Team skills</span>
          <input
            id="pf-skills"
            className="input-field font-mono"
            value={skillsText}
            onChange={(event) => setSkillsText(event.target.value)}
            placeholder="e.g. react, python, ml"
          />
          <p className="text-xs text-gray-500 mt-1">
            Comma separated. Teams needing what you know will rank higher for you.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <span className="label">Bio</span>
            <input
              id="pf-bio"
              className="input-field"
              value={bio}
              onChange={(event) => setBio(event.target.value)}
              placeholder="One line about you"
            />
          </div>
          <div>
            <span className="label">Contact</span>
            <input
              id="pf-contact"
              className="input-field"
              value={contact}
              onChange={(event) => setContact(event.target.value)}
              placeholder="How teammates reach you"
            />
          </div>
        </div>

        <div className="flex justify-start">
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

      {/* Sign-in methods live with the profile: they are account settings too. */}
      <ManagePasskeys />
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

import { useLiveDay } from '../../hooks/useLiveDay'

function TimetableView({ slots, onChanged, totalSlots, hiddenElectives = [] }) {
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  // Which weekdays this timetable actually has, so the filter offers only those.
  const availableDays = useMemo(() => {
    const present = new Set((slots || []).map((slot) => slot.day))
    return DAYS.filter((name) => present.has(name))
  }, [slots])

  // Live day selection: defaults to today (IST), weekends -> "all",
  // updates automatically when the day rolls over.
  const { day, onSelect } = useLiveDay(availableDays)

  const visibleSlots = useMemo(
    () => (day === 'all' ? slots : (slots || []).filter((slot) => slot.day === day)),
    [slots, day],
  )

  // Stable identities, so UploadPreview does not re-fetch on every render.
  const fetchTimetableUpload = useCallback(() => timetableApi.latestUpload(), [])
  const loadTimetablePreview = useCallback(() => timetableApi.previewObjectUrl(), [])

  const clearAll = async () => {
    if (!window.confirm('Remove every timetable slot?')) return
    setBusy(true)
    try {
      // Clear All must tolerate an empty (204 / no body) response.
      const result = await timetableApi.clear().catch(() => null)
      setMessage(result?.message || 'Timetable cleared')
      setError(null)
      // Attendance subjects and the room lists are derived from the timetable,
      // so they have to be told it is gone.
      await afterTimetableChange()
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
          hint="The master timetable PDF or CSV."
          onUpload={async (file) => {
            const result = await timetableApi.upload(file)
            // New slots mean new attendance subjects and a new room list.
            await afterTimetableChange()
            onChanged?.()
            return result
          }}
        >
          <UploadPreview
            refreshKey={slots.length}
            fetchLatest={fetchTimetableUpload}
            loadObjectUrl={loadTimetablePreview}
            emptyHint="No preview available - upload the timetable to preview it."
          />
        </FileUpload>

        <div className="card p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Uploaded timetable</h3>
          <StatusCard
            label="Slots loaded"
            value={totalSlots ?? slots.length}
            tone={totalSlots ? 'success' : 'default'}
            subtext={
              totalSlots
                ? `You see ${slots.length} for your branch. Live schedule and vacant rooms use these slots.`
                : 'Nothing uploaded yet.'
            }
          />
          <button
            type="button"
            onClick={clearAll}
            className="btn-danger text-sm"
            disabled={busy || (totalSlots ?? slots.length) === 0}
          >
            Clear All
          </button>
        </div>
      </div>

      {hiddenElectives.length > 0 && (
        <div className="p-3 rounded-lg border border-gray-200 bg-gray-50 text-xs text-gray-600">
          <span className="font-medium text-gray-700">
            {hiddenElectives.length} elective{hiddenElectives.length === 1 ? '' : 's'} in this
            semester
          </span>{' '}
          {hiddenElectives.length === 1 ? 'is' : 'are'} not shown because {hiddenElectives.length === 1 ? 'it is' : 'they are'} not
          in your profile: {hiddenElectives.slice(0, 6).join(', ')}
          {hiddenElectives.length > 6 && ` +${hiddenElectives.length - 6} more`}. Add one under
          Profile &rarr; Electives to see its class.
        </div>
      )}

      {slots.length > 0 && (
        <DayFilter
          days={availableDays}
          selected={day}
          onSelect={onSelect}
          count={visibleSlots.length}
        />
      )}

      {visibleSlots.length > 0 && (
        <TimetableByDay
          slots={visibleSlots}
          hidden={Math.max(0, (totalSlots || 0) - slots.length)}
        />
      )}

      {slots.length > 0 && visibleSlots.length === 0 && (
        <div className="card text-center py-10 text-sm text-gray-500">
          No classes on {day}.
        </div>
      )}
    </div>
  )
}

/**
 * Weekday filter for the timetable.
 *
 * Only days the student actually has classes appear, so the row never offers a
 * dead choice. The counts are per day, which is the number people are looking
 * for when they filter - not the whole-week total repeated.
 */
function DayFilter({ days, selected, onSelect, count }) {
  if (days.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Day</span>
      <div className="flex flex-wrap items-center gap-1">
        <button
          type="button"
          onClick={() => onSelect('all')}
          aria-pressed={selected === 'all'}
          className={`px-2.5 py-1 text-xs font-medium rounded-full border transition-colors ${
            selected === 'all'
              ? 'bg-primary-500 text-white border-primary-500'
              : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
          }`}
        >
          All
        </button>
        {days.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => onSelect(name)}
            aria-pressed={selected === name}
            className={`px-2.5 py-1 text-xs font-medium rounded-full border transition-colors ${
              selected === name
                ? 'bg-primary-500 text-white border-primary-500'
                : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
            }`}
          >
            {name}
          </button>
        ))}
      </div>
      <span className="text-xs text-gray-500">
        {count} class{count === 1 ? '' : 'es'}
      </span>
    </div>
  )
}

/**
 * The student's timetable, one card per weekday.
 *
 * Grouping by day is what makes a weekly timetable readable: the source PDF is a
 * grid of days against times, and flattening it into a single table loses the
 * only structure a student actually plans around. Rows are the profile-filtered
 * classes, so another branch's paper never appears here.
 */
function TimetableByDay({ slots, hidden = 0 }) {
  const byDay = useMemo(() => {
    const groups = {}
    slots.forEach((slot) => {
      const key = slot.day || 'Mon'
      if (!groups[key]) groups[key] = []
      groups[key].push(slot)
    })

    return WEEKDAY_ORDER.filter((day) => groups[day]?.length).map((day) => ({
      day,
      slots: groups[day].sort((a, b) => a.sort_key - b.sort_key),
    }))
  }, [slots])

  const total = byDay.reduce((sum, group) => sum + group.slots.length, 0)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-900">
          Timetable
          <span className="ml-2 text-xs font-normal text-gray-500">
            {total} slot{total === 1 ? '' : 's'} across {byDay.length} day
            {byDay.length === 1 ? '' : 's'}
          </span>
        </h3>
        {/* Explain the gap, so a short list is never mistaken for missing data. */}
        {hidden > 0 && (
          <span className="text-xs text-gray-500">
            {hidden} slot{hidden === 1 ? '' : 's'} hidden - other branches
          </span>
        )}
      </div>

      {byDay.map(({ day, slots: daySlots }) => (
        <div key={day} className="card">
          <h4 className="text-sm font-semibold text-gray-900 mb-3">
            {DAY_NAMES[day] || day}
          </h4>

          <div className="space-y-2">
            {daySlots.map((slot) => (
              <div
                key={slot.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2"
              >
                <span className="font-mono text-sm font-semibold text-gray-900 w-24 shrink-0">
                  {slot.course_code}
                </span>

                <span className="text-xs text-gray-500 w-20 shrink-0">
                  {slot.instructor || '—'}
                </span>

                <span className="font-mono text-xs text-primary-600 w-20 shrink-0">
                  {slot.room || 'TBA'}
                </span>

                <span className="text-xs text-gray-600 whitespace-nowrap">
                  {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
                </span>

                <span className="text-xs text-gray-500 truncate">{slot.branch_or_program}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}