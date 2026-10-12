import { attendanceApi } from '../../api';
import { bumpProfileVersion } from './storage';

/**
 * Sync helpers that must run after a change to a data source.
 *
 * These live outside the components so the ordering is identical wherever they
 * are triggered: a timetable upload from the Live Schedule tab and one from a
 * future import button must leave the app in exactly the same state.
 */

/**
 * Re-run the timetable -> course sync, then confirm attendance subjects.
 *
 * The backend already syncs on `GET /attendance/subjects`, but calling the
 * explicit trigger first means the sync is complete before anything reads the
 * list, so a screen can never render the pre-sync version.
 *
 * Failures are swallowed: a sync failure must not wipe displayed data or sign
 * the user out. The caller keeps whatever it was showing.
 */
export async function syncAttendanceFromTimetable(): Promise<void> {
  try {
    await attendanceApi.sync();
  } catch {
    // The next subjects read syncs anyway, so a failure here is not fatal.
  }
}

/**
 * Push a profile change through everything derived from it.
 *
 * Bumping the profile version is what tells the timetable, attendance, rooms
 * and both exam views to refetch; the attendance sync is what turns the new
 * branch and semester into subjects.
 */
export async function afterProfileChange(): Promise<void> {
  bumpProfileVersion();
  await syncAttendanceFromTimetable();
}

/**
 * Push a timetable upload or removal through everything derived from it.
 *
 * Both the upload and the clear path call this, so attendance subjects and the
 * room lists are refreshed whichever way the timetable changed.
 */
export async function afterTimetableChange(): Promise<void> {
  bumpProfileVersion();
  await syncAttendanceFromTimetable();
}
