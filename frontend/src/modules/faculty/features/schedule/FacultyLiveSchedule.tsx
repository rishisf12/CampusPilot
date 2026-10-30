import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, Users } from 'lucide-react';
import { Badge, Button, Card, Modal, Tabs } from '@/components/ui';
import { timetableApi } from '@/api';
import { DAYS } from '@shared/constants';
import {
  formatTime as formatClock,
  istNow,
  todayWeekday,
  weekOrderStartingOn,
} from '@shared/lib/time';
import { toMinutes } from '@shared/lib/normalise';
import useProfile from '@shared/hooks/useProfile';
import useProfileVersion from '@shared/hooks/useProfileVersion';
import ErrorBanner from '@shared/components/ErrorBanner';
import Spinner from '@shared/components/Spinner';
import ScheduleHome, { type HomeClass } from '@shared/features/schedule/ScheduleHome';
import { SlotRow } from '@shared/features/schedule/TimetableSlotRow';
import { formatDuration, rowsForDay } from '@shared/features/schedule/timetableRows';
import { useSettings } from '@shared/features/settings/SettingsProvider';
import { useLiveDay } from '@shared/hooks/useLiveDay';
import type { TimetableSlot } from '@shared/types/api';

const SUB_TABS = [
  { id: 'schedule', label: 'Schedule' },
  { id: 'timetable', label: 'Timetable' },
] as const;

/** "Mon" -> "Monday", for the weekday headings. */
const DAY_NAMES: Record<string, string> = {
  Mon: 'Monday',
  Tue: 'Tuesday',
  Wed: 'Wednesday',
  Thu: 'Thursday',
  Fri: 'Friday',
  Sat: 'Saturday',
  Sun: 'Sunday',
};

/** Weekday order, so Monday comes before Tuesday however the rows arrived. */
const WEEKDAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface CourseLike {
  course_name?: string;
  course_code?: string;
}

/** Course code once; "(CODE)" appended only when the name differs. */
function courseLabel(item: CourseLike): string {
  const name = (item.course_name || '').trim();
  const code = (item.course_code || '').trim();
  if (!name || name === code) return code || name;
  return `${name} (${code})`;
}

interface FacultyLiveScheduleProps {
  onError?: (message: string) => void;
}

/**
 * The instructor's timetable, filtered by the notation set at signup.
 *
 * The timetable's `instructor` column holds the notation (e.g. "ARR", or
 * "ARR/MKA" when two instructors share a cell), so a slot is mine when my
 * notation equals one of the slash-separated instructor parts. Matching is
 * case-insensitive and ignores surrounding spaces: the parser normalises the
 * notation to capitals, but defence in depth costs nothing.
 */
function matchesNotation(slot: TimetableSlot, notation: string): boolean {
  const target = notation.trim().toUpperCase();
  if (!target) return false;
  const instructor = String(slot.instructor || '').toUpperCase();
  return instructor.split('/').some(part => part.trim() === target);
}

export default function FacultyLiveSchedule({ onError }: FacultyLiveScheduleProps) {
  const [subTab, setSubTab] = useState('schedule');
  const [slots, setSlots] = useState<TimetableSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const profileVersion = useProfileVersion();
  const { profile } = useProfile();
  const notation = (profile?.timetable_notation || '').trim().toUpperCase();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // The student /schedule/now endpoint is filtered by a student profile
      // (semester/branch), so it is meaningless for faculty. The current and
      // next class are computed locally from the notation-filtered slots.
      const slotList = await timetableApi.listSlots();
      setSlots(Array.isArray(slotList) ? slotList : []);
      setError(null);
    } catch (err) {
      // Keep the last good schedule on screen; a failed refresh is not a reason
      // to blank the screen or sign the user out.
      const message = err instanceof Error ? err.message : 'Failed to load schedule';
      setError(message);
      onError?.(message);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
  }, [load, profileVersion]);

  // Auto-refresh the live schedule every minute.
  useEffect(() => {
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, [load]);

  /** The instructor's own slots, across every branch and semester they teach. */
  const myClasses = useMemo(() => {
    if (!notation) return [];
    return (slots || []).filter(slot => matchesNotation(slot, notation));
  }, [slots, notation]);

  const myCurrent = useMemo(() => {
    const today = todayWeekday();
    const nowMinutes = istNow().minutes;
    return (
      myClasses.find(
        slot =>
          slot.day === today &&
          toMinutes(slot.start_time) <= nowMinutes &&
          nowMinutes < toMinutes(slot.end_time)
      ) || null
    );
  }, [myClasses]);

  /** Other classes running in the same slot as the current one. */
  const sameTimeSlot = useMemo(() => {
    if (!myCurrent) return [];
    const start = toMinutes(myCurrent.start_time);
    const end = toMinutes(myCurrent.end_time);
    return myClasses.filter(
      slot =>
        slot.day === myCurrent.day &&
        toMinutes(slot.start_time) < end &&
        toMinutes(slot.end_time) > start &&
        !(slot.course_code === myCurrent.course_code && slot.start_time === myCurrent.start_time)
    );
  }, [myCurrent, myClasses]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size={28} className="text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 py-0.5">
        <Tabs
          tabs={SUB_TABS.map(item => ({ id: item.id, label: item.label }))}
          active={subTab}
          onChange={setSubTab}
          variant="underline"
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={16} strokeWidth={2} aria-hidden />}
          loading={loading}
          onClick={load}
          className="ml-auto"
        >
          Refresh
        </Button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {!notation && (
        <div
          className="p-3 rounded-lg border text-sm"
          style={{ background: 'var(--cp-surface)', color: 'var(--cp-muted)' }}
        >
          Your account has no timetable notation set, so your schedule cannot be matched. Faculty
          accounts choose a notation at signup (for example ARR).
        </div>
      )}

      {subTab === 'schedule' && (
        <ScheduleView
          loading={loading}
          current={myCurrent}
          sameTimeSlot={sameTimeSlot}
          hasTimetable={slots.length > 0}
          myClasses={myClasses}
        />
      )}

      {subTab === 'timetable' && <TimetableView slots={myClasses} totalSlots={slots.length} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Schedule                                                            */
/* ------------------------------------------------------------------ */

interface ScheduleViewProps {
  loading: boolean;
  current: TimetableSlot | null;
  sameTimeSlot: TimetableSlot[];
  hasTimetable: boolean;
  myClasses: TimetableSlot[];
}

function ScheduleView({
  loading,
  current,
  sameTimeSlot,
  hasTimetable,
  myClasses,
}: ScheduleViewProps) {
  const today = todayWeekday();

  /** The instructor's classes today, then the next two later in the week. */
  const { nextList } = useMemo(() => {
    const now = istNow().minutes;
    const list: TimetableSlot[] = [];
    // Walk forward from today, wrapping. The "already started" cut applies only
    // to today: WEEKDAY_ORDER[0] is Monday, so a plain forEach would wrongly
    // skip Monday's morning classes and leap to Tuesday.
    const todayIndex = WEEKDAY_ORDER.indexOf(today);
    for (let step = 0; step < WEEKDAY_ORDER.length && list.length < 2; step++) {
      const day = WEEKDAY_ORDER[(todayIndex + step) % WEEKDAY_ORDER.length];
      const candidates = myClasses
        .filter(slot => slot.day === day && (step > 0 || toMinutes(slot.start_time) > now))
        .sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time));
      for (const slot of candidates) {
        list.push(slot);
        if (list.length >= 2) break;
      }
    }
    return { nextList: list };
  }, [myClasses, today]);

  /** Classes later today that have not ended yet, for the timeline. */
  const nowMinutes = istNow().minutes;
  const todayRemaining = myClasses
    .filter(slot => slot.day === today && toMinutes(slot.end_time) > nowMinutes)
    .sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time));

  return (
    <div className="space-y-4">
      <ScheduleHome
        loading={loading}
        hasTimetable={hasTimetable}
        current={(current as HomeClass | null) ?? null}
        nextClass={(nextList[0] as HomeClass | null) ?? null}
        nextClasses={nextList as HomeClass[]}
        todayRemaining={todayRemaining as HomeClass[]}
        courseLabel={courseLabel}
      />

      {sameTimeSlot.length > 0 && (
        <Card>
          <h3
            className="text-sm font-semibold mb-3 flex items-center gap-2"
            style={{ color: 'var(--cp-text)' }}
          >
            <Users size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
            Also running now
          </h3>
          <div className="space-y-2">
            {sameTimeSlot.map(slot => (
              <div
                key={`${slot.course_code}-${slot.start_time}-${slot.room}`}
                className="flex items-center justify-between gap-2 p-2.5 rounded-lg"
                style={{ background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
              >
                <span className="text-sm font-mono" style={{ color: 'var(--cp-text)' }}>
                  {slot.course_code}
                </span>
                <Badge tone="info" className="font-mono">
                  {formatClock(slot.start_time)} - {formatClock(slot.end_time)} &middot; {slot.room}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Timetable                                                           */
/* ------------------------------------------------------------------ */

interface TimetableViewProps {
  slots: TimetableSlot[];
  totalSlots?: number;
}

function TimetableView({ slots, totalSlots }: TimetableViewProps) {
  // Which weekdays this timetable actually has, so the filter offers only those.
  const availableDays = useMemo(() => {
    const present = new Set((slots || []).map(slot => slot.day));
    return DAYS.filter(name => present.has(name));
  }, [slots]);

  // Live day selection: defaults to today (IST), weekends -> "all",
  // updates automatically when the day rolls over.
  const { day, onSelect } = useLiveDay(availableDays as string[]);

  const visibleSlots = useMemo(
    () =>
      day === 'all'
        ? slots
        : (slots || [])
            .filter(slot => slot.day === day)
            .sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time)),
    [slots, day]
  );

  return (
    <div className="space-y-4">
      {slots.length > 0 && (
        <DayFilter
          days={availableDays as string[]}
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
        <Card className="text-center py-10 text-sm" style={{ color: 'var(--cp-muted)' }}>
          No classes on {day}.
        </Card>
      )}
    </div>
  );
}

/**
 * Weekday filter for the timetable.
 *
 * Only days the instructor actually teaches appear, so the row never offers a
 * dead choice. The counts are per day, which is the number people are looking
 * for when they filter - not the whole-week total repeated.
 */
interface DayFilterProps {
  days: string[];
  selected: string;
  onSelect: (day: string) => void;
  count: number;
}

function DayFilter({ days, selected, onSelect, count }: DayFilterProps) {
  if (days.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Tabs
        tabs={[{ id: 'all', label: 'All' }, ...days.map(name => ({ id: name, label: name }))]}
        active={selected}
        onChange={onSelect}
      />
      <Badge tone="neutral">
        {count} class{count === 1 ? '' : 'es'}
      </Badge>
    </div>
  );
}

/**
 * The instructor's teaching timetable, one card per weekday.
 *
 * Grouping by day is what makes a weekly timetable readable. Rows are the
 * notation-filtered classes, so cohorts taught by someone else never appear.
 */
interface TimetableByDayProps {
  slots: TimetableSlot[];
  hidden?: number;
}

function TimetableByDay({ slots, hidden = 0 }: TimetableByDayProps) {
  const today = todayWeekday();
  const [selected, setSelected] = useState<TimetableSlot | null>(null);
  const settings = useSettings();
  // Settings > Schedule. The day order is the week the user says they live in;
  // free periods are opt-in, because a day of three classes reads better as
  // three cards than as six rows with three of them empty.
  const weekStart = settings.get('week_start');
  const dayOrder = useMemo(() => weekOrderStartingOn(String(weekStart)), [weekStart]);

  const byDay = useMemo(() => {
    const groups: Record<string, TimetableSlot[]> = {};
    slots.forEach(slot => {
      const key = slot.day || 'Mon';
      if (!groups[key]) groups[key] = [];
      groups[key].push(slot);
    });

    return dayOrder
      .filter(day => groups[day]?.length)
      .map(day => ({
        day,
        slots: groups[day].sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time)),
      }));
  }, [slots, dayOrder]);

  const total = byDay.reduce((sum, group) => sum + group.slots.length, 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Timetable
          <span className="ml-2 text-xs font-normal" style={{ color: 'var(--cp-muted)' }}>
            {total} slot{total === 1 ? '' : 's'} across {byDay.length} day
            {byDay.length === 1 ? '' : 's'}
          </span>
        </h3>
        {/* Explain the gap, so a short list is never mistaken for missing data. */}
        {hidden > 0 && (
          <Badge tone="neutral">
            {hidden} slot{hidden === 1 ? '' : 's'} hidden - other instructors
          </Badge>
        )}
      </div>

      {byDay.map(({ day, slots: daySlots }) => {
        const isToday = day === today;
        return (
          <Card
            key={day}
            style={
              isToday
                ? { boxShadow: 'var(--cp-neu-raised), 0 0 0 2px var(--cp-primary)' }
                : undefined
            }
          >
            <h4
              className="text-sm font-semibold mb-3 flex items-center gap-2"
              style={{ color: 'var(--cp-text)' }}
            >
              {DAY_NAMES[day] || day}
              {isToday && (
                <Badge tone="primary" className="ml-1">
                  Today
                </Badge>
              )}
            </h4>

            <div className="space-y-2">
              {rowsForDay(daySlots, false).map((row, index) =>
                row.kind === 'free' ? (
                  <div
                    key={`free-${row.from}-${row.to}`}
                    className="flex items-center gap-3 px-3 py-1.5 text-xs"
                    style={{ color: 'var(--cp-muted)' }}
                  >
                    <span className="w-24 shrink-0" aria-hidden />
                    <span className="shrink-0">
                      {formatClock(row.from)} - {formatClock(row.to)}
                    </span>
                    <span className="truncate">Free ({formatDuration(row.minutes)})</span>
                  </div>
                ) : (
                  <SlotRow
                    key={`slot-${row.slot.id}-${index}`}
                    slot={row.slot}
                    onOpen={setSelected}
                  />
                )
              )}
            </div>
          </Card>
        );
      })}

      {selected && (
        <Modal sheet title={courseLabel(selected)} onClose={() => setSelected(null)}>
          <dl className="space-y-2 text-sm">
            {(
              [
                ['Course', courseLabel(selected)],
                [
                  'Cohort',
                  [selected.branch_or_program, selected.semester ? `Sem ${selected.semester}` : '']
                    .filter(Boolean)
                    .join(' · ') || '—',
                ],
                ['Room', selected.room || 'TBA'],
                ['Day', DAY_NAMES[selected.day] || selected.day],
                ['Time', `${formatClock(selected.start_time)} - ${formatClock(selected.end_time)}`],
              ] as Array<[string, string]>
            ).map(([term, value]) => (
              <div key={term} className="flex items-center justify-between gap-3">
                <dt style={{ color: 'var(--cp-muted)' }}>{term}</dt>
                <dd className="font-medium text-right" style={{ color: 'var(--cp-text)' }}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </Modal>
      )}
    </div>
  );
}
