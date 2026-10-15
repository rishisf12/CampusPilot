import { useCallback, useEffect, useMemo, useState } from 'react';
import { CalendarDays, Clock, RefreshCw, Trash2, Users } from 'lucide-react';
import { Badge, Button, Card, Tabs } from '@/components/ui';
import { scheduleApi, timetableApi } from '@/api';
import { DAYS } from '@shared/constants';
import { formatTime as formatClock, istNow, todayWeekday } from '@shared/lib/time';
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

interface LiveScheduleProps {
  onError?: (message: string) => void;
}

interface ScheduleNow {
  current_class?: ScheduleClass | null;
  next_class?: ScheduleClass | null;
}

interface ProfileCourseLike extends TimetableSlot {
  sort_key: number;
  is_opted_in: boolean;
}

export default function LiveSchedule({ onError }: LiveScheduleProps) {
  const [subTab, setSubTab] = useState('schedule');
  const [schedule, setSchedule] = useState<ScheduleNow | null>(null);
  const [slots, setSlots] = useState<TimetableSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const profileVersion = useProfileVersion();
  const { semester, optedInCodes } = useProfile();

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
          current={myCurrent}
          nextClass={schedule?.next_class}
          sameTimeSlot={sameTimeSlot}
          formatTime={formatTime}
          courseLabel={courseLabel}
          hasTimetable={slots.length > 0}
          myClasses={myClasses}
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

interface ClassCardProps {
  title: string;
  tone: string;
  item: TimetableSlot | ProfileCourseLike | ScheduleClass | null;
  emptyText: string;
  formatTime: (time: string) => string;
  courseLabel: (item: CourseLike) => string;
}

const TONE_DOT: Record<string, string> = {
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
};

function ClassCard({ title, tone, item, emptyText, formatTime, courseLabel }: ClassCardProps) {
  const Icon = title === 'Current Class' ? Clock : CalendarDays;
  return (
    <Card>
      <h3
        className="text-sm font-semibold flex items-center gap-2 mb-3"
        style={{ color: 'var(--cp-text)' }}
      >
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: TONE_DOT[tone] || TONE_DOT.success }}
          aria-hidden
        />
        <Icon size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
        {title}
      </h3>
      {item ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Cell label="Course" value={courseLabel(item)} mono />
          <Cell label="Room" value={item.room} mono />
          <Cell
            label="Time"
            value={`${formatTime(item.start_time)} - ${formatTime(item.end_time)}`}
            badge
          />
          <Cell label="Day" value={item.day} />
        </div>
      ) : (
        <p className="text-sm py-3" style={{ color: 'var(--cp-muted)' }}>
          {emptyText}
        </p>
      )}
    </Card>
  );
}

interface CellProps {
  label: string;
  value?: string | null;
  mono?: boolean;
  badge?: boolean;
}

function Cell({ label, value, mono, badge }: CellProps) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide" style={{ color: 'var(--cp-muted)' }}>
        {label}
      </p>
      {badge && value ? (
        <Badge tone="info" className="mt-1 font-mono">
          {value}
        </Badge>
      ) : (
        <p
          className={`text-sm font-medium ${mono ? 'font-mono' : ''}`}
          style={{ color: 'var(--cp-text)' }}
        >
          {value || '—'}
        </p>
      )}
    </div>
  );
}

/**
 * The student's day at a glance, plus the next class.
 *
 * The current class comes from the profile-filtered timetable rather than the
 * server's answer, because the master timetable lists every branch and the
 * backend cannot know which electives the student opted into.
 */
interface ScheduleViewProps {
  current: ProfileCourseLike | null;
  nextClass?: ScheduleClass | TimetableSlot | null;
  sameTimeSlot: ProfileCourseLike[];
  formatTime: (time: string) => string;
  courseLabel: (item: CourseLike) => string;
  hasTimetable: boolean;
  myClasses: ProfileCourseLike[];
}

function ScheduleView({
  current,
  nextClass,
  sameTimeSlot,
  formatTime,
  courseLabel,
  hasTimetable,
  myClasses,
}: ScheduleViewProps) {
  const today = todayWeekday();

  /** The student's classes today, then the next one later in the week. */
  const { todaySlots, upcoming } = useMemo(() => {
    const now = istNow().minutes;
    const todays = myClasses
      .filter(slot => slot.day === today)
      .sort((a, b) => a.sort_key - b.sort_key);

    let next: ProfileCourseLike | null = null;
    WEEKDAY_ORDER.forEach((day, offset) => {
      if (next) return;
      const candidates = myClasses
        .filter(slot => slot.day === day && (offset > 0 || toMinutes(slot.start_time) > now))
        .sort((a, b) => a.sort_key - b.sort_key);
      if (candidates.length) next = candidates[0];
    });

    return { todaySlots: todays, upcoming: next };
  }, [myClasses, today]);

  return (
    <div className="space-y-4">
      {!hasTimetable && (
        <div
          className="p-3 rounded-lg border border-primary-200 text-sm"
          style={{ background: 'var(--cp-surface)', color: 'var(--cp-text)' }}
        >
          No class timetable uploaded yet. Open the Timetable tab to add it.
        </div>
      )}

      {todaySlots.length === 0 && hasTimetable && (
        <div
          className="p-3 rounded-lg border text-sm"
          style={{
            background: 'var(--cp-surface)',
            borderColor: 'rgba(163,177,198,.3)',
            color: 'var(--cp-muted)',
          }}
        >
          No classes for you on {DAY_NAMES[today]}.
        </div>
      )}

      <ClassCard
        title="Current Class"
        tone="success"
        item={current}
        emptyText="No class right now."
        formatTime={formatTime}
        courseLabel={courseLabel}
      />
      <ClassCard
        title="Next Class"
        tone="warning"
        item={nextClass || upcoming}
        emptyText="No upcoming classes."
        formatTime={formatTime}
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
  const byDay = useMemo(() => {
    const groups: Record<string, ProfileCourseLike[]> = {};
    slots.forEach(slot => {
      const key = slot.day || 'Mon';
      if (!groups[key]) groups[key] = [];
      groups[key].push(slot);
    });

    return WEEKDAY_ORDER.filter(day => groups[day]?.length).map(day => ({
      day,
      slots: groups[day].sort((a, b) => a.sort_key - b.sort_key),
    }));
  }, [slots]);

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

      {byDay.map(({ day, slots: daySlots }) => (
        <Card key={day}>
          <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
            {DAY_NAMES[day] || day}
          </h4>

          <div className="space-y-2">
            {daySlots.map(slot => (
              <div
                key={slot.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-3 py-2"
                style={{
                  background: 'var(--cp-bg)',
                  boxShadow: 'var(--cp-neu-inset)',
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
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}
