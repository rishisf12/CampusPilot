import { useProfile } from '../../hooks/useProfile.jsx'
import { profileApi, scheduleApi } from '../../api'
import { BRANCH_OPTIONS, PROGRAMME_SEMESTERS } from '../../constants'
import { useState, useMemo } from 'react'
import Spinner from '../../components/Spinner'

/**
 * Profile settings page.
 *
 * Lets the student edit their programme, semester, branch, electives,
 * extra courses and attendance target. Branch change requests are handled
 * here as well. All data lives in the ProfileProvider context so changes
 * propagate to the timetable, attendance, rooms and exam views immediately.
 */
export default function Profile() {
  const {
    profile,
    loading,
    error,
    refresh,
    branch,
    semester,
    programme,
    attendanceTarget,
    electiveCodes,
    extraCourses,
    branchChange,
  } = useProfile()

  const [target, setTarget] = useState(attendanceTarget)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [localError, setLocalError] = useState(null)

  // Branch change state
  const [branchFrom, setBranchFrom] = useState(branchChange.from || branch || '')
  const [branchTo, setBranchTo] = useState(branchChange.to || '')
  const [noBranchChange, setNoBranchChange] = useState(!branchChange.requested)

  // Elective/extra course state
  const [electiveCodesText, setElectiveCodesText] = useState(
    (electiveCodes || []).join(', ')
  )
  const [extraCode, setExtraCode] = useState('')
  const [extraCoursesList, setExtraCoursesList] = useState(extraCourses || [])

  const semesters = useMemo(
    () => (programme ? PROGRAMME_SEMESTERS[programme] || PROGRAMME_SEMESTERS.BTech : []),
    [programme]
  )

  const patch = (key, value) => {
    setMessage(null)
    setError(null)
  }

  const save = async () => {
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      const updated = await profileApi.update({
        programme,
        semester: Number(semester),
        branch,
        elective_codes: electiveCodesText
          .split(',')
          .map((tag) => tag.trim().toUpperCase())
          .filter(Boolean),
        attendance_target: Number(target),
      })
      // Refresh the profile context so all dependent screens update
      await refresh()
      setMessage('Profile saved')
    } catch (err) {
      setLocalError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const submitBranchChange = async () => {
    setMessage(null)
    setLocalError(null)
    try {
      if (noBranchChange) {
        const result = await profileApi.clearBranchChange()
        setMessage(result.message)
        setBranchTo('')
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
        setBranchTo('')
        setBranchFrom(branchTo)
        setNoBranchChange(true)
        await refresh()
      }
    } catch (err) {
      setLocalError(err.message)
    }
  }

  const addExtraCourse = async () => {
    const code = extraCode.trim().toUpperCase()
    if (!code) return
    try {
      const created = await scheduleApi.addExtra(code)
      setExtraCoursesList((prev) => [...prev, created])
      setExtraCode('')
      await refresh()
    } catch (err) {
      setLocalError(err.message)
    }
  }

  const removeExtraCourse = async (code) => {
    try {
      await scheduleApi.removeExtra(code)
      setExtraCoursesList((prev) => prev.filter((c) => c.code !== code))
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size={32} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card border-danger-200 bg-danger-50 p-4">
        <p className="text-danger-700">{error}</p>
        <button
          type="button"
          onClick={() => { window.location.reload(); }}
          className="mt-2 btn-primary text-sm"
        >
          Reload
        </button>
      </div>
    )
  }

  const branchOptions = BRANCH_OPTIONS

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-gray-900">Profile Settings</h2>

      {/* Programme & Semester */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Programme & Semester</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <span className="label">Programme</span>
            <select
              className="select-field"
              value={programme}
              onChange={(e) => patch('programme', e.target.value)}
            >
              <option value="BTech">BTech</option>
              <option value="MTech">MTech</option>
              <option value="MBA">MBA</option>
              <option value="PhD">PhD</option>
            </select>
          </div>
          <div>
            <span className="label">Semester</span>
            <select
              className="select-field"
              value={semester}
              onChange={(e) => patch('semester', Number(e.target.value))}
            >
              {semesters.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Branch */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Branch</h3>
        <select
          className="select-field"
          value={branch}
          onChange={(e) => patch('branch', e.target.value)}
        >
          <option value="">Select branch</option>
          {BRANCH_OPTIONS.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
      </div>

      {/* Electives */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Electives</h3>
        <input
          className="input-field font-mono"
          value={electiveCodesText}
          onChange={(e) => setElectiveCodesText(e.target.value)}
          placeholder="e.g. CS501, CS502, ML101"
        />
        <p className="text-xs text-gray-500">
          Comma-separated codes. These electives are always shown in your timetable.
        </p>
      </div>

      {/* Extra / backlog courses */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Extra / Backlog Courses</h3>
        <div className="flex gap-2">
          <input
            className="input-field flex-1 font-mono"
            value={extraCode}
            onChange={(e) => setExtraCode(e.target.value)}
            placeholder="e.g. CS501"
            onKeyDown={(e) => e.key === 'Enter' && addExtraCourse()}
          />
          <button
            type="button"
            onClick={addExtraCourse}
            className="btn-primary whitespace-nowrap"
          >
            Add
          </button>
        </div>
        {extraCoursesList.length > 0 && (
          <ul className="space-y-1">
            {extraCoursesList.map((c) => (
              <li
                key={c.code}
                className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2"
              >
                <span className="font-mono text-gray-700">{c.code}</span>
                <button
                  type="button"
                  onClick={() => removeExtraCourse(c.code)}
                  className="text-xs text-danger-600 hover:text-danger-800"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Attendance target */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Attendance Target</h3>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0"
            max="100"
            className="input-field w-28"
            value={target}
            onChange={(e) => setTarget(Number(e.target.value))}
          />
          <span className="text-xs text-gray-500">
            Used by the Attendance tab for risk colouring.
          </span>
        </div>
      </div>

      {/* Branch change request */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Branch Change Request</h3>
        {branchChange.requested && branchChange.to && (
          <div className="p-2.5 rounded-lg border border-primary-200 bg-primary-50 text-primary-700 text-sm">
            Pending request: {branchChange.from} &rarr; {branchChange.to}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <span className="label">From branch</span>
            <select
              className="select-field"
              value={branchFrom}
              onChange={(e) => setBranchFrom(e.target.value)}
            >
              <option value="">Select branch</option>
              {branchOptions.map((b) => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
          </div>
          <div>
            <span className="label">To branch</span>
            <select
              className="select-field"
              value={branchTo}
              disabled={noBranchChange}
              onChange={(e) => setBranchTo(e.target.value)}
            >
              <option value="">Select branch</option>
              {branchOptions.map((b) => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={noBranchChange}
              onChange={(e) => setNoBranchChange(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            No branch change (cancel pending)
          </label>
        </div>
        <div className="flex justify-start">
          <button
            type="button"
            onClick={submitBranchChange}
            className="btn-primary text-sm"
            disabled={!noBranchChange && !branchTo}
          >
            {noBranchChange ? 'Cancel pending request' : 'Submit branch change'}
          </button>
        </div>
      </div>

      {/* Save button & messages */}
      {message && (
        <div className="rounded-lg bg-success-50 border border-success-200 px-3 py-2 text-xs text-success-800">
          {message}
        </div>
      )}
      {localError && (
        <div className="rounded-lg bg-danger-50 border border-danger-200 px-3 py-2 text-xs text-danger-800">
          {localError}
        </div>
      )}
      <div className="flex justify-start">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="btn-primary text-sm"
        >
          {saving ? <Spinner size={16} className="text-white" /> : 'Save profile'}
        </button>
      </div>
    </div>
  )
}