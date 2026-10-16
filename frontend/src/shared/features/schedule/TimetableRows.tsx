import { Badge } from '@/components/ui';
import type { TimetableSlot } from '@shared/types/api';
import { formatTime } from '@shared/lib/time';
import { toMinutes } from '@shared/lib/normalise';

/**
 * The rows of one day in the timetable.
 *
 * Shared by the undergraduate and postgraduate schedules, which render the same
 * grid. It was duplicated between the two modules before; the copy is what let
 * one of them gain a setting and the other quietly not have it.
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

/**
 * A class row in the by-day timetable.
 *
 * Generic over the slot so each module's richer slot type flows through to its
 * `onOpen` handler - the row only needs the fields below, but the caller knows
 * the whole object.
 */
export function SlotRow<T extends TimetableSlot>({
  slot,
  onOpen,
}: {
  slot: T;
  onOpen: (slot: T) => void;
}) {
  const tint = subjectTint(slot.course_code);
  return (
    <button
      type="button"
      onClick={() => onOpen(slot)}
      aria-label={`${slot.course_code}, ${formatTime(slot.start_time)} to ${formatTime(slot.end_time)}, Room ${slot.room || 'TBA'}. Show details.`}
      className="w-full text-left flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-3 py-2 row-pad transition-transform duration-150 active:scale-[0.98] hover:-translate-y-px"
      style={{
        background: tint.bg,
        boxShadow: 'var(--cp-neu-inset)',
        borderLeft: `4px solid ${tint.edge}`,
      }}
    >
      <span
        className="font-mono text-sm font-semibold w-24 shrink-0"
        style={{ color: 'var(--cp-text)' }}
      >
        {slot.course_code}
      </span>

      <span className="text-xs w-20 shrink-0" style={{ color: 'var(--cp-muted)' }}>
        {slot.instructor || '—'}
      </span>

      <Badge tone="neutral" className="font-mono shrink-0">
        {slot.room || 'TBA'}
      </Badge>

      <Badge tone="info" className="whitespace-nowrap">
        {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
      </Badge>

      <span className="text-xs truncate" style={{ color: 'var(--cp-muted)' }}>
        {slot.branch_or_program}
      </span>
    </button>
  );
}

/** A gap shorter than this is breathing room, not a free period worth naming. */
export const FREE_PERIOD_MINUTES = 45;

export type TimetableDayRow<T extends TimetableSlot = TimetableSlot> =
  { kind: 'slot'; slot: T } | { kind: 'free'; from: string; to: string; minutes: number };

/**
 * One day's classes, with a free-period marker in each long enough gap.
 *
 * Only gaps between consecutive classes are marked. The gap before the first
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
