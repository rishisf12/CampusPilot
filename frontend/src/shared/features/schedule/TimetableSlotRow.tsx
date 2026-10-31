import { Badge } from '@/components/ui';
import type { TimetableSlot } from '@shared/types/api';
import { formatTime } from '@shared/lib/time';
import { subjectTint } from './timetableRows';

/**
 * The class row of the by-day timetable.
 *
 * The pure helpers next to it (tint, gap detection, duration formatting) live in
 * `timetableRows.ts` so they can be tested without React. The two filenames
 * deliberately differ by more than case: `TimetableRows` and `timetableRows`
 * collide on a case-insensitive filesystem, which TypeScript refuses outright.
 */

/**
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
        {slot.semester ? `Sem ${slot.semester}` : ''}{' '}
        {slot.branch_or_program ? `· ${slot.branch_or_program}` : ''}
      </span>
    </button>
  );
}
