import { useCallback, useEffect, useState } from 'react'
import { getProfileVersion } from '../api'

/**
 * The shared profile version, as a reactive value.
 *
 * Every data-dependent screen keys its refetch on this number, so a profile
 * edit made anywhere - Profile settings, a branch change, an extra course -
 * propagates to the timetable, attendance, rooms and both exam views without a
 * manual reload.
 *
 * Three things have to be listened to, because localStorage writes are silent:
 *
 * - the same-tab `profile-updated` event dispatched by `bumpProfileVersion`
 * - the `storage` event, which only fires in *other* tabs
 * - window focus, which covers a write this tab missed entirely
 *
 * The value is re-read on mount too, so a component mounted after the change
 * (or one that survived a hot reload) still converges.
 */
export default function useProfileVersion() {
  const [version, setVersion] = useState(() => getProfileVersion())

  const sync = useCallback(() => {
    setVersion(getProfileVersion())
  }, [])

  useEffect(() => {
    sync()

    const onStorage = (event) => {
      // A change to any key means another tab may have edited the profile.
      if (event.key === null || event.key === 'profile_version') sync()
    }
    const onFocus = () => sync()

    window.addEventListener('profile-updated', sync)
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onFocus)

    return () => {
      window.removeEventListener('profile-updated', sync)
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onFocus)
    }
  }, [sync])

  return version
}
