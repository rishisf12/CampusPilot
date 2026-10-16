import type { TimetableSlot } from '@shared/types/api';
import { toMinutes } from '@shared/lib/normalise';

/**
 * Pure helpers for the by-day timetable.
 *
 * Kept apart from `TimetableRows.tsx` so they can be unit-tested without pulling
 * React and the component barrel into a Node test run. Nothing here touches the
 * DOM or the settings store.
 */

/**
 * Stable per-subject colour derived from the course code.
 *
 * One hue per subject is what makes a weekly timetable scannable; random or
 * rotating colours would teach nothing. HSL with fixed saturation/lightness
 * keeps every subject equally vivid, and the soft color-mix background adapts
 * to both themes without a second palette.
 */
export function subjectHue(courseCode: string): number {
  let hash = 0;
  for (let i = 0; i < courseCode.length; i++) {
    hash = (hash * 31 + courseCode.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % 360;
}

export function subjectTint(courseCode: string): { bg: string; edge: string } {
  const hue = subjectHue(courseCode || '?');
  return {
    bg: `color-mix(in srgb, hsl(${hue} 70% 50%) 10%, transparent)`,
    edge: `hsl(${hue} 65% 45%)`,
  };
}

/** A gap shorter than this is breathing room, not a free period worth naming. */
export const FREE_PERIOD_MINUTES = 45;

export type TimetableDayRow<T extends TimetableSlot = TimetableSlot> =
  { kind: 'slot'; slot: T } | { kind: 'free'; from: string; to: string; minutes: number };

/**
 * One day's classes, with a free-period marker in each long enough gap.
 *
 * Only gaps *between consecutive classes* are marked. The run before the first
 * class is just the morning, and a row for it would put "Free 7:00 - 9:00" above
 * every day including the ones that start at 9:00.
 */
export function rowsForDay<T extends TimetableSlot>(
  daySlots: T[],
  showFree: boolean
): TimetableDayRow<T>[] {
  const rows: TimetableDayRow<T>[] = [];
  daySlots.forEach((slot, index) => {
    rows.push({ kind: 'slot', slot });
    const next = daySlots[index + 1];
    if (!showFree || !next) return;
    const minutes = toMinutes(next.start_time) - toMinutes(slot.end_time);
    if (minutes >= FREE_PERIOD_MINUTES) {
      rows.push({ kind: 'free', from: slot.end_time, to: next.start_time, minutes });
    }
  });
  return rows;
}

/** "95" -> "1 hr 35 min". Used for the free-period labels. */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} hr` : `${h} hr ${m} min`;
}
