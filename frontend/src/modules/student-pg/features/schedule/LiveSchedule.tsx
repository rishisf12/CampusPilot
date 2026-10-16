import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw, Trash2, Users } from 'lucide-react';
import { Badge, Button, Card, Modal, Tabs } from '@/components/ui';
import { scheduleApi, timetableApi } from '@/api';
import { DAYS, GROUP_CLASSROOM_TABS, programmeGroupOf } from '@shared/constants';
import {
  formatTime as formatClock,
  istNow,
  todayWeekday,
  weekOrderStartingOn,
} from '@shared/lib/time';
import { afterTimetableChange } from '@shared/lib/sync';
import { isOpenElective, splitCourseCodes, toMinutes } from '@shared/lib/normalise';
import useProfile from '@shared/hooks/useProfile';
import useProfileCourses from '@shared/hooks/useProfileCourses';
import useProfileVersion from '@shared/hooks/useProfileVersion';
import ErrorBanner from '@shared/components/ErrorBanner';
import FileUpload from '@shared/components/FileUpload';
import UploadPreview from '@shared/components/UploadPreview';
import Spinner from '@shared/components/Spinner';
import StatusCard from '@shared/components/StatusCard';
import { useLiveDay } from '@shared/hooks/useLiveDay';
import type { ScheduleClass, TimetableSlot } from '@shared/types/api';

const SUB_TABS = [
  { id: 'schedule', label: 'Schedule' },
  { id: 'timetable', label: 'Timetable' },
] as const;

const formatTime = formatClock;

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

import ScheduleHome from '@shared/features/schedule/ScheduleHome';
import { SlotRow } from '@shared/features/schedule/TimetableSlotRow';
import { formatDuration, rowsForDay } from '@shared/features/schedule/timetableRows';
import { useSettings } from '@shared/features/settings/SettingsProvider';

interface LiveScheduleProps {
  onError?: (message: string) => void;
  /** Jump to a classroom-level tab (used by the home quick actions). */
  onJumpTab?: (id: string) => void;
}

interface ScheduleNow {
  current_class?: ScheduleClass | null;
  next_class?: ScheduleClass | null;
}

interface ProfileCourseLike extends TimetableSlot {
  sort_key: number;
  is_opted_in: boolean;
}

export default function LiveSchedule({ onError, onJumpTab }: LiveScheduleProps) {
  const [subTab, setSubTab] = useState('schedule');
  const [schedule, setSchedule] = useState<ScheduleNow | null>(null);
  const [slots, setSlots] = useState<TimetableSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const profileVersion = useProfileVersion();
  const { semester, optedInCodes, programme } = useProfile();
  const group = programmeGroupOf(programme);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [now, slotList] = await Promise.all([
        scheduleApi.now(),
        timetableApi.listSlots().catch(() => []),
      ]);
      setSchedule(now);
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

  /**
   * The student's own classes, narrowed by their profile.
   *
   * The master timetable holds every branch, so the backend's current/next class
   * can be a paper the student does not sit. This list is the filtered truth,
   * and the same-slot lookup is derived from it.
   */
  const myClasses = useProfileCourses(slots) as ProfileCourseLike[];

  /**
   * Electives that are scheduled in this semester but not claimed by the profile.
   *
   * They are no longer shown - that was most of the timetable, and courses nobody
   * chose - but they must not simply vanish. The count is surfaced on the
   * timetable so a student who *is* sitting one can add it and see it.
   */
  const hiddenElectives = useMemo(() => {
    const claimed = new Set((optedInCodes || []).map(code => String(code).toUpperCase()));
    const found = new Set<string>();
    for (const slot of slots || []) {
      if (semester && slot.semester && slot.semester !== semester) continue;
      for (const code of splitCourseCodes(slot.course_code)) {
        const upper = code.toUpperCase();
        if (isOpenElective(upper) && !claimed.has(upper)) found.add(upper);
      }
    }
    return [...found].sort();
  }, [slots, semester, optedInCodes]);

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

  if (loading && !schedule) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size={28} className="text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
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

      {subTab === 'schedule' && (
        <ScheduleView
          loading={loading}
          current={myCurrent}
          nextClass={schedule?.next_class}
          sameTimeSlot={sameTimeSlot}
          formatTime={formatTime}
          courseLabel={courseLabel}
          hasTimetable={slots.length > 0}
          myClasses={myClasses}
          onJumpTab={onJumpTab}
          showAttendanceAction={GROUP_CLASSROOM_TABS[group].includes('attendance')}
          showVacantAction={GROUP_CLASSROOM_TABS[group].includes('vacant')}
        />
      )}

      {subTab === 'timetable' && (
        <TimetableView
          slots={myClasses}
          onChanged={load}
          totalSlots={slots.length}
          hiddenElectives={hiddenElectives}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Schedule                                                            */
/* ------------------------------------------------------------------ */

interface ScheduleViewProps {
  loading: boolean;
  current: ProfileCourseLike | null;
  nextClass?: ScheduleClass | TimetableSlot | null;
  sameTimeSlot: ProfileCourseLike[];
  formatTime: (time: string) => string;
  courseLabel: (item: CourseLike) => string;
  hasTimetable: boolean;
  myClasses: ProfileCourseLike[];
  onJumpTab?: (id: string) => void;
  showAttendanceAction: boolean;
  showVacantAction: boolean;
}

function ScheduleView({
  loading,
  current,
  nextClass,
  sameTimeSlot,
  formatTime,
  courseLabel,
  hasTimetable,
  myClasses,
  onJumpTab,
  showAttendanceAction,
  showVacantAction,
}: ScheduleViewProps) {
  const today = todayWeekday();

  /** The student's classes today, then the next one later in the week. */
  const { todaySlots, upcoming } = useMemo(() => {
    const now = istNow().minutes;
    const todays = myClasses
      .filter(slot => slot.day === today)
      .sort((a, b) => a.sort_key - b.sort_key);

    let next: ProfileCourseLike | null = null;
    // Walk forward from today, wrapping. The "already started" cut applies only
    // to today: WEEKDAY_ORDER[0] is Monday, so a plain forEach would wrongly
    // skip Monday's morning classes and leap to Tuesday.
    const todayIndex = WEEKDAY_ORDER.indexOf(today);
    for (let step = 0; step < WEEKDAY_ORDER.length && !next; step++) {
      const day = WEEKDAY_ORDER[(todayIndex + step) % WEEKDAY_ORDER.length];
      const candidates = myClasses
        .filter(slot => slot.day === day && (step > 0 || toMinutes(slot.start_time) > now))
        .sort((a, b) => a.sort_key - b.sort_key);
      if (candidates.length) next = candidates[0];
    }

    return { todaySlots: todays, upcoming: next };
  }, [myClasses, today]);

  // Classes later today that have not ended yet, for the timeline.
  const nowMinutes = istNow().minutes;
  const todayRemaining = todaySlots.filter(slot => toMinutes(slot.end_time) > nowMinutes);

  return (
    <div className="space-y-4">
      <ScheduleHome
        loading={loading}
        hasTimetable={hasTimetable}
        current={current}
        nextClass={nextClass || upcoming}
        todayRemaining={todayRemaining}
        courseLabel={courseLabel}
        onJumpTab={onJumpTab ?? (() => {})}
        showAttendanceAction={showAttendanceAction}
        showVacantAction={showVacantAction}
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
                  {formatTime(slot.start_time)} - {formatTime(slot.end_time)} &middot; {slot.room}
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
/* Timetable upload                                                     */
/* ------------------------------------------------------------------ */

interface TimetableViewProps {
  slots: ProfileCourseLike[];
  onChanged?: () => void;
  totalSlots?: number;
  hiddenElectives?: string[];
}

function TimetableView({ slots, onChanged, totalSlots, hiddenElectives = [] }: TimetableViewProps) {
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Which weekdays this timetable actually has, so the filter offers only those.
  const availableDays = useMemo(() => {
    const present = new Set((slots || []).map(slot => slot.day));
    return DAYS.filter(name => present.has(name));
  }, [slots]);

  // Live day selection: defaults to today (IST), weekends -> "all",
  // updates automatically when the day rolls over.
  const { day, onSelect } = useLiveDay(availableDays as string[]);

  const visibleSlots = useMemo(
    () => (day === 'all' ? slots : (slots || []).filter(slot => slot.day === day)),
    [slots, day]
  );

  // Stable identities, so UploadPreview does not re-fetch on every render.
  const fetchTimetableUpload = useCallback(() => timetableApi.latestUpload(), []);
  const loadTimetablePreview = useCallback(() => timetableApi.previewObjectUrl(), []);

  const clearAll = async () => {
    if (!window.confirm('Remove every timetable slot?')) return;
    setBusy(true);
    try {
      // Clear All must tolerate an empty (204 / no body) response.
      const result = await timetableApi.clear().catch(() => null);
      setMessage(result?.message || 'Timetable cleared');
      setError(null);
      // Attendance subjects and the room lists are derived from the timetable,
      // so they have to be told it is gone.
      await afterTimetableChange();
      onChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear timetable');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {message && (
        <div
          className="p-3 rounded-lg border text-sm"
          style={{ background: 'var(--cp-surface)', color: 'var(--cp-text)' }}
        >
          {message}
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="grid md:grid-cols-2 gap-4">
        <FileUpload
          label="Upload class timetable"
          accept=".pdf,.csv"
          hint="The master timetable PDF or CSV."
          onUpload={async file => {
            const result = await timetableApi.upload(file);
            // New slots mean new attendance subjects and a new room list.
            await afterTimetableChange();
            onChanged?.();
            return result;
          }}
        >
          <UploadPreview
            refreshKey={slots.length}
            fetchLatest={fetchTimetableUpload}
            loadObjectUrl={loadTimetablePreview}
            emptyHint="No preview available - upload the timetable to preview it."
          />
        </FileUpload>

        <Card className="space-y-3">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
            Uploaded timetable
          </h3>
          <StatusCard
            label="Slots loaded"
            value={totalSlots ?? slots.length}
            tone={totalSlots ? 'success' : 'default'}
            subtext={
              totalSlots
                ? `You see ${slots.length} for your branch. Live schedule and vacant rooms use these slots.`
                : 'Nothing uploaded yet.'
            }
          />
          <Button
            type="button"
            variant="danger"
            size="sm"
            icon={<Trash2 size={16} strokeWidth={2} aria-hidden />}
            loading={busy}
            onClick={clearAll}
            disabled={busy || (totalSlots ?? slots.length) === 0}
          >
            Clear All
          </Button>
        </Card>
      </div>

      {hiddenElectives.length > 0 && (
        <div
          className="p-3 rounded-lg border text-xs"
          style={{
            background: 'var(--cp-surface)',
            borderColor: 'rgba(163,177,198,.3)',
            color: 'var(--cp-muted)',
          }}
        >
          <span className="font-medium" style={{ color: 'var(--cp-text)' }}>
            {hiddenElectives.length} elective{hiddenElectives.length === 1 ? '' : 's'} in this
            semester
          </span>{' '}
          {hiddenElectives.length === 1 ? 'is' : 'are'} not shown because{' '}
          {hiddenElectives.length === 1 ? 'it is' : 'they are'} not in your profile:{' '}
          {hiddenElectives.slice(0, 6).join(', ')}
          {hiddenElectives.length > 6 && ` +${hiddenElectives.length - 6} more`}. Add one under
          Profile &rarr; Electives to see its class.
        </div>
      )}

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
 * Only days the student actually has classes appear, so the row never offers a
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
 * The student's timetable, one card per weekday.
 *
 * Grouping by day is what makes a weekly timetable readable: the source PDF is a
 * grid of days against times, and flattening it into a single table loses the
 * only structure a student actually plans around. Rows are the profile-filtered
 * classes, so another branch's paper never appears here.
 */
interface TimetableByDayProps {
  slots: ProfileCourseLike[];
  hidden?: number;
}

function TimetableByDay({ slots, hidden = 0 }: TimetableByDayProps) {
  const today = todayWeekday();
  const [selected, setSelected] = useState<ProfileCourseLike | null>(null);
  const settings = useSettings();
  // Settings > Schedule, same as the undergraduate timetable.
  const weekStart = settings.get('week_start');
  const dayOrder = useMemo(() => weekOrderStartingOn(String(weekStart)), [weekStart]);
  const showFreePeriods = settings.get('show_empty_slots') === true;

  const byDay = useMemo(() => {
    const groups: Record<string, ProfileCourseLike[]> = {};
    slots.forEach(slot => {
      const key = slot.day || 'Mon';
      if (!groups[key]) groups[key] = [];
      groups[key].push(slot);
    });

    return dayOrder
      .filter(day => groups[day]?.length)
      .map(day => ({
        day,
        slots: groups[day].sort((a, b) => a.sort_key - b.sort_key),
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
            {hidden} slot{hidden === 1 ? '' : 's'} hidden - other branches
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
              {rowsForDay(daySlots, showFreePeriods).map((row, index) =>
                row.kind === 'free' ? (
                  <div
                    key={`free-${row.from}-${row.to}`}
                    className="flex items-center gap-3 px-3 py-1.5 text-xs"
                    style={{ color: 'var(--cp-muted)' }}
                  >
                    <span className="w-24 shrink-0" aria-hidden />
                    <span className="shrink-0">
                      {formatTime(row.from)} - {formatTime(row.to)}
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
                ['Faculty', selected.instructor || '—'],
                ['Room', selected.room || 'TBA'],
                ['Day', DAY_NAMES[selected.day] || selected.day],
                ['Time', `${formatTime(selected.start_time)} - ${formatTime(selected.end_time)}`],
                ['Branch', selected.branch_or_program],
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
