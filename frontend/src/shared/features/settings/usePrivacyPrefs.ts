import { useEffect } from 'react';
import { writeQuickLookup } from '@shared/lib/storage';
import { useSettings } from './SettingsProvider';

/**
 * Side effects the settings need beyond their own value.
 *
 * A setting that only changes what the Settings page shows is not really a
 * setting - it is a label. These are the ones that change what the rest of the
 * app does, so they live here rather than being scattered through whichever
 * screen happened to read them first.
 */

/**
 * `remember_exam_lookup`: drop anything already cached the moment it is turned
 * off.
 *
 * Without this, switching the setting off would stop *new* lookups being stored
 * while a roll number already on the device stayed there indefinitely - which is
 * the opposite of what the student just asked for, and not something they can
 * discover or undo from the settings page.
 */
export function useCachedLookupPolicy(): void {
  const remember = useSettings().get('remember_exam_lookup') === true;

  useEffect(() => {
    if (!remember) writeQuickLookup(null);
  }, [remember]);
}
