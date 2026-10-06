import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { profileApi, scheduleApi } from '../api'
import useProfileVersion from './useProfileVersion'

/**
 * The signed-in student's profile, shared by every screen.
 *
 * The profile is the single source of truth for semester, branch, electives,
 * extra courses and the attendance target, so it is fetched once here rather
 * than by each tab. Screens read `semester`, `branch` and `electiveCodes` from
 * this context and never hard-code them.
 *
 * It refetches automatically whenever the profile version changes - from a
 * Profile edit, a branch change, or an extra course added from another tab -
 * so a change made in one place reaches the timetable, attendance, rooms and
 * both exam views without a manual reload.
 */
const ProfileContext = createContext(null)

export function useProfile() {
  const value = useContext(ProfileContext)
  if (!value) throw new Error('useProfile must be used inside ProfileProvider')
  return value
}

export function ProfileProvider({ children }) {
  const [profile, setProfile] = useState(null)
  const [extraCourses, setExtraCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const version = useProfileVersion()

  const load = useCallback(async () => {
    try {
      const [data, extras] = await Promise.all([
        profileApi.get(),
        scheduleApi.listExtra().catch(() => []),
      ])
      setProfile(data)
      setExtraCourses(Array.isArray(extras) ? extras : [])
      setError(null)
    } catch (err) {
      // Keep whatever is on screen: a failed sync must never wipe the profile.
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Derived course lists, computed outside the context value so the memo
  // ordering stays valid.
  const electiveCodes = useMemo(
    () =>
      (profile?.elective_codes || [])
        .map((code) => String(code).trim().toUpperCase())
        .filter(Boolean),
    [profile],
  )

  const extraCodes = useMemo(
    () =>
      extraCourses.map((course) => String(course.code || '').trim().toUpperCase()).filter(Boolean),
    [extraCourses],
  )

  /** Electives plus extras: always shown, whatever the student's branch. */
  const optedInCodes = useMemo(
    () => [...new Set([...electiveCodes, ...extraCodes])],
    [electiveCodes, extraCodes],
  )

  // Initial load, then again on every profile version bump.
  useEffect(() => {
    load()
  }, [load, version])

  const value = useMemo(
    () => ({
      profile,
      loading,
      error,
      refresh: load,

      /** The effective branch: a granted branch change wins over the original. */
      branch: profile?.branch || '',
      semester: profile?.semester ?? null,
      programme: profile?.programme || '',
      attendanceTarget: Number(profile?.attendance_target ?? 75),

      /** Elective codes chosen in the profile, normalised. */
      electiveCodes,

      /** Extra / backlog courses created outside the elective list. */
      extraCourses,

      /** Just the extra / backlog codes. */
      extraCodes,

      /** Electives plus extras: the courses always shown, whatever the branch. */
      optedInCodes,

      branchChange: {
        requested: Boolean(profile?.branch_change_requested),
        from: profile?.original_branch || profile?.branch || '',
        to: profile?.requested_branch || '',
        reason: profile?.branch_change_reason || '',
      },
    }),
    [
      profile,
      loading,
      error,
      load,
      electiveCodes,
      extraCourses,
      extraCodes,
      optedInCodes,
    ],
  )

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
}

// Also the default export, so a component can import whichever form reads best.
export default useProfile
