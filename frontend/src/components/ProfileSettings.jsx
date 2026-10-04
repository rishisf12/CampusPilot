import { useEffect, useMemo, useState } from 'react'
import { profileApi } from '../api'
import {
  BRANCH_OPTIONS,
  PROGRAMMES,
  PROGRAMME_SEMESTERS,
  semesterLabel,
} from '../constants'
import Spinner from './Spinner'

/**
 * Profile Settings.
 *
 * Holds programme / semester / branch / electives plus the Branch Change block,
 * which lives inside this same card.  Saving bumps `profile_version` in
 * localStorage so the Exam page knows to refetch.
 */
export default function ProfileSettings({ onProfileSaved }) {
  const [profile, setProfile] = useState(null)
  const [electiveInput, setElectiveInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  // Branch change block state
  const [branchFrom, setBranchFrom] = useState('')
  const [branchTo, setBranchTo] = useState('')
  const [noBranchChange, setNoBranchChange] = useState(false)
  const [branchMsg, setBranchMsg] = useState(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await profileApi.get()
        if (cancelled) return
        setProfile(data)
        setBranchFrom(data.branch || '')
        // A pending request pre-selects the target branch.
        if (data.branch_change_requested && data.requested_branch) {
          setBranchTo(data.requested_branch)
        }
        setNoBranchChange(!data.branch_change_requested)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const semesterOptions = useMemo(() => {
    if (!profile) return []
    return PROGRAMME_SEMESTERS[profile.programme] || PROGRAMME_SEMESTERS.BTech
  }, [profile])

  const update = (key, value) => {
    setProfile({ ...profile, [key]: value })
    setMessage(null)
  }

  const addElective = () => {
    const code = electiveInput.trim().toUpperCase()
    if (!code) return
    const list = profile.elective_codes || []
    if (!list.includes(code)) {
      setProfile({ ...profile, elective_codes: [...list, code] })
    }
    setElectiveInput('')
  }

  const removeElective = (code) => {
    setProfile({
      ...profile,
      elective_codes: (profile.elective_codes || []).filter((c) => c !== code),
    })
  }

  /** Persist the profile and notify other pages that it changed. */
  const save = async () => {
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const payload = {
        programme: profile.programme,
        semester: profile.semester,
        branch: profile.branch,
        elective_codes: profile.elective_codes || [],
      }
      const updated = await profileApi.update(payload)
      setProfile(updated)
      bumpProfileVersion()
      setMessage('Profile saved')
      onProfileSaved?.(updated)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const submitBranchChange = async () => {
    setError(null)
    setBranchMsg(null)
    try {
      if (noBranchChange) {
        const res = await profileApi.clearBranchChange()
        setBranchMsg(res.message)
      } else {
        if (!branchTo) {
          setError('Select the branch you want to move to')
          return
        }
        const res = await profileApi.requestBranchChange({
          from_branch: branchFrom,
          to_branch: branchTo,
        })
        setBranchMsg(res.message)
      }
      const fresh = await profileApi.get()
      setProfile(fresh)
      setBranchFrom(fresh.branch)
      bumpProfileVersion()
      onProfileSaved?.(fresh)
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size={24} />
      </div>
    )
  }
  if (!profile) {
    return (
      <div className="p-3 rounded-lg bg-danger-50 border border-danger-200 text-danger-700 text-sm">
        {error || 'Could not load the profile.'}
      </div>
    )
  }

  const inputClass =
    'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 outline-none bg-white'
  const labelClass = 'block text-xs font-medium text-gray-600 mb-1'

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Profile Settings</h3>
        {profile.original_branch && (
          <span className="text-xs text-gray-500">
            Admitted branch: <span className="font-medium">{profile.original_branch}</span>
          </span>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-danger-50 border border-danger-200 text-danger-700 text-sm">
          {error}
        </div>
      )}
      {message && (
        <div className="p-3 rounded-lg bg-success-50 border border-success-200 text-success-700 text-sm">
          {message}
        </div>
      )}

      {/* Programme / semester / branch */}
      <div className="grid md:grid-cols-3 gap-4">
        <div>
          <label className={labelClass} htmlFor="pf-programme">Programme</label>
          <select id="pf-programme" className={inputClass} value={profile.programme || 'BTech'}
            onChange={(e) => {
              const programme = e.target.value
              const options = PROGRAMME_SEMESTERS[programme] || PROGRAMME_SEMESTERS.BTech
              setProfile({
                ...profile,
                programme,
                semester: profile.semester && options.includes(profile.semester)
                  ? profile.semester
                  : options[0],
              })
            }}>
            {PROGRAMMES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        <div>
          <label className={labelClass} htmlFor="pf-semester">Semester</label>
          <select id="pf-semester" className={inputClass} value={profile.semester}
            onChange={(e) => {
              const raw = e.target.value
              update('semester', raw === 'Coursework' ? 1 : Number(raw))
            }}>
            {semesterOptions.map((s) => (
              <option key={s} value={s}>{semesterLabel(s)}</option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelClass} htmlFor="pf-branch">Branch</label>
          <select id="pf-branch" className={inputClass} value={profile.branch}
            onChange={(e) => update('branch', e.target.value)}>
            <option value="">Select branch</option>
            {BRANCH_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
      </div>

      {/* Electives */}
      <div>
        <label className={labelClass} htmlFor="pf-elective">Elective course codes</label>
        <div className="flex gap-2">
          <input id="pf-elective" className={inputClass} value={electiveInput}
            onChange={(e) => setElectiveInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addElective() } }}
            placeholder="e.g. OE3E33" />
          <button type="button" onClick={addElective}
            className="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 whitespace-nowrap">
            Add
          </button>
        </div>
        {(profile.elective_codes || []).length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {profile.elective_codes.map((code) => (
              <span key={code}
                className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-primary-50 text-primary-700 text-xs font-medium">
                {code}
                <button type="button" onClick={() => removeElective(code)}
                  className="text-primary-500 hover:text-danger-500" aria-label={`Remove ${code}`}>
                  x
                </button>
              </span>
            ))}
          </div>
        )}
        <p className="text-xs text-gray-500 mt-2">
          Electives you add here are matched against open-elective rows in the exam data.
        </p>
      </div>

      <div className="flex justify-end">
        <button type="button" onClick={save} disabled={saving}
          className="px-5 py-2 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2">
          {saving ? <Spinner size={16} /> : null}
          Save profile
        </button>
      </div>

      {/* Branch Change block — inside the Profile Settings card */}
      <div className="pt-5 border-t border-gray-100 space-y-4">
        <div>
          <h4 className="text-sm font-semibold text-gray-900">Branch Change</h4>
          <p className="text-xs text-gray-500">
            Request a branch transfer, or confirm that no change is needed.
          </p>
        </div>

        {profile.branch_change_requested && profile.requested_branch && (
          <div className="p-3 rounded-lg bg-primary-50 border border-primary-200 text-primary-800 text-sm">
            Pending request: <span className="font-medium">{profile.branch}</span> to{' '}
            <span className="font-medium">{profile.requested_branch}</span>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass} htmlFor="bc-from">From branch</label>
            <select id="bc-from" className={inputClass} value={branchFrom}
              onChange={(e) => setBranchFrom(e.target.value)}>
              <option value="">Select branch</option>
              {BRANCH_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          <div>
            <label className={labelClass} htmlFor="bc-to">To branch</label>
            <select id="bc-to" className={inputClass} value={branchTo}
              disabled={noBranchChange}
              onChange={(e) => setBranchTo(e.target.value)}>
              <option value="">Select branch</option>
              {BRANCH_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
        </div>

        {branchMsg && (
          <div className="p-3 rounded-lg bg-success-50 border border-success-200 text-success-700 text-sm">
            {branchMsg}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <button type="button" onClick={submitBranchChange}
            className="px-5 py-2 bg-primary-500 text-white font-medium rounded-lg hover:bg-primary-600">
            Change Branch
          </button>

          <label className="inline-flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input type="checkbox" className="w-4 h-4 rounded border-gray-300"
              checked={noBranchChange}
              onChange={(e) => {
                setNoBranchChange(e.target.checked)
                // Checking the box clears any pending request inputs.
                if (e.target.checked) {
                  setBranchTo('')
                  setBranchMsg(null)
                }
              }} />
            No branch change
          </label>
        </div>
      </div>
    </div>
  )
}

/**
 * Bump the shared profile version.
 *
 * The Exam page watches this key and refetches whenever it changes, keeping the
 * exam filters in sync with the profile.  The `storage` event only fires in
 * *other* tabs, so a same-tab `profile-updated` event is dispatched as well.
 */
export function bumpProfileVersion() {
  const current = Number(localStorage.getItem('profile_version') || 0)
  const next = String(current + 1)
  localStorage.setItem('profile_version', next)
  window.dispatchEvent(new CustomEvent('profile-updated', { detail: { version: next } }))
}