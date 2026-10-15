import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  BarChart3,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Minus,
  Plus,
  RefreshCw,
  X,
} from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  IconTile,
  Input,
  Modal,
  ProgressBar,
  Table,
  Tabs,
} from '@/components/ui';
import { attendanceApi, profileApi, scheduleApi, timetableApi } from '@/api';
import { istNow, todayIso } from '@shared/lib/time';
import { afterProfileChange } from '@shared/lib/sync';
import { instructorFor, toMinutes } from '@shared/lib/normalise';
import useProfile from '@shared/hooks/useProfile';
import useProfileCourses from '@shared/hooks/useProfileCourses';
import useProfileVersion from '@shared/hooks/useProfileVersion';
import ErrorBanner from '@shared/components/ErrorBanner';
import Spinner from '@shared/components/Spinner';
import type { TimetableSlot } from '@shared/types/api';

const SUB_TABS = [
  { id: 'subjects', label: 'Subjects' },
  { id: 'history', label: 'History' },
] as const;

const STATUSES = ['Present', 'Absent', 'Cancelled'] as const;

type Status = (typeof STATUSES)[number];

interface AttendanceSubject {
  course_id: number;
  course_code: string;
  course_name?: string;
  present: number;
  absent: number;
  cancelled: number;
  total_held: number;
  percentage: number;
  status: string;
  must_attend: number;
  can_miss: number;
}

interface AttendanceRecord {
  id: number;
  course_id: number;
  date: string;
  status: Status;
}

interface CalendarEntry {
  date: string;
  status: Status;
}

/** Live IST clock, independent of the viewer's timezone. */
function useIstClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

/** Colour bucket for a percentage against the student's target. */
function toneFor(percentage: number, target: number): 'success' | 'warning' | 'danger' {
  if (percentage >= target) return 'success';
  if (percentage >= target - 10) return 'warning';
  return 'danger';
}

/**
 * Has any class actually been held for this subject?
 *
 * The backend reports a percentage even when nothing has been recorded - a
 * subject with zero classes held comes back as 100% and "Safe". That is not a
 * result, it is the absence of one, and showing it as a green 100% is the single
 * most misleading thing on this screen. The frontend cannot change the backend,
 * so the distinction is made here instead.
 */
function hasRecords(subject: AttendanceSubject): boolean {
  return Number(subject.total_held) > 0;
}

/** Advice line: how many classes to attend / can miss. */
function advice(subject: AttendanceSubject): string {
  if (!hasRecords(subject)) return 'No classes recorded yet.';
  if (subject.status === 'Critical' || subject.must_attend > 0) {
    return `Attend next ${subject.must_attend} to recover.`;
  }
  if (subject.can_miss > 0) return `Can miss ${subject.can_miss} more.`;
  return 'At the edge - do not miss any.';
}

interface AttendanceProps {
  onError?: (message: string) => void;
}

export default function Attendance({ onError }: AttendanceProps) {
  const [subTab, setSubTab] = useState('subjects');
  const [subjects, setSubjects] = useState<AttendanceSubject[]>([]);
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [slots, setSlots] = useState<TimetableSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; undo?: () => void } | null>(null);
  const [calendarFor, setCalendarFor] = useState<AttendanceSubject | null>(null);
  const [extraCode, setExtraCode] = useState('');
  // Holds either the number seeded from the profile or what the number input
  // has been typed into; `Number()` normalises both at every use site.
  const [targetDraft, setTargetDraft] = useState<number | string>(75);

  const clock = useIstClock();
  const ist = istNow(clock);
  const { attendanceTarget: target, branch, semester } = useProfile();
  const profileVersion = useProfileVersion();

  // The target lives on the profile; seed the input from it.
  useEffect(() => {
    setTargetDraft(target);
  }, [target]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // No /attendance/summary call: it only ever produced the overall card, and
      // /attendance/subjects already carries every field the cards need
      // (percentage, status, must_attend). Dropping it saves a request per load.
      const [subjectData, recordData, slotData] = await Promise.all([
        attendanceApi.subjects(),
        attendanceApi.records(),
        timetableApi.listSlots().catch(() => []),
      ]);
      setSubjects(subjectData.subjects || []);
      setRecords(recordData || []);
      setSlots(Array.isArray(slotData) ? slotData : []);
      setError(null);
    } catch (err) {
      // Keep the last good data on screen; a failed sync must not blank it.
      const msg = err instanceof Error ? err.message : 'Failed to load attendance';
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  // Refetch on mount and on every profile change: semester, branch and extra
  // courses all decide which subjects apply.
  useEffect(() => {
    load();
  }, [load, profileVersion]);

  /** The student's own classes, narrowed by their profile. */
  const myClasses = useProfileCourses(slots);

  /** Today's classes, from the timetable, for the student's weekday (IST). */
  const todayClasses = useMemo(
    () =>
      myClasses
        .filter(slot => slot.day === ist.weekdayShort)
        .sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time)),
    [myClasses, ist.weekdayShort]
  );

  /** Which subjects have a class today, and which of those are still unmarked. */
  const todayState = useMemo(() => {
    const today = todayIso();
    const scheduled = new Map<string, typeof myClasses>();
    todayClasses.forEach(slot => {
      if (!scheduled.has(slot.course_code)) scheduled.set(slot.course_code, []);
      scheduled.get(slot.course_code)!.push(slot);
    });

    const idByCode = new Map(subjects.map(subject => [subject.course_code, subject.course_id]));
    const markedToday = new Set(
      records.filter(record => record.date === today).map(record => record.course_id)
    );
    // Only the student's own subjects count towards "unmarked"; the timetable
    // also holds other branches' classes.
    const unmarked = [...scheduled.keys()].filter(
      code => idByCode.has(code) && !markedToday.has(idByCode.get(code)!)
    ).length;

    return { scheduled, unmarked, today, markedToday };
  }, [todayClasses, records, subjects]);

  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (message: string, undo?: () => void) => {
    setToast({ message, undo });
    // Auto-dismiss so the toast never sticks around, but long enough to undo.
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), undo ? 8000 : 4000);
  };

  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    },
    []
  );

  /** Optimistic mark with a one-tap undo. */
  const mark = async (subject: AttendanceSubject, status: Status, dateOverride?: string) => {
    const date = dateOverride || todayState.today;
    const previous = subjects;

    // Optimistic: the count moves immediately. total_held and the percentage are
    // deliberately left alone - they are recomputed by the load() below once the
    // server has agreed, so the number shown is never one this screen invented.
    setSubjects(current =>
      current.map(item =>
        item.course_id === subject.course_id
          ? {
              ...item,
              present: Math.max(0, item.present + (status === 'Present' ? 1 : 0)),
              absent: Math.max(0, item.absent + (status === 'Absent' ? 1 : 0)),
              cancelled: item.cancelled + (status === 'Cancelled' ? 1 : 0),
            }
          : item
      )
    );

    try {
      await attendanceApi.mark({ course_id: subject.course_id, date, status });
      setError(null);
      await load();
      showToast(`${subject.course_code} marked ${status}`, async () => {
        // Undo by removing the record we just created.
        const fresh = await attendanceApi.records(subject.course_id);
        const added = (fresh as AttendanceRecord[]).find(
          record => record.date === date && record.status === status
        );
        if (added) {
          await attendanceApi.remove(added.id).catch(() => {});
        }
        await load();
        setToast(null);
      });
    } catch (err) {
      // Roll back to exactly what was on screen, not an approximation.
      setSubjects(previous);
      setError(err instanceof Error ? err.message : 'Failed to mark attendance');
    }
  };

  const addExtraClass = async () => {
    const code = extraCode.trim().toUpperCase();
    if (!code) return;
    setError(null);
    try {
      // A manually added subject is an extra course, so it survives a timetable
      // re-upload rather than being wiped by the sync.
      await scheduleApi.addExtra({
        code,
        name: code,
        semester: semester || 1,
        branch: branch || 'ALL',
      });
      setExtraCode('');
      // The extra course changes the profile's course list, so re-sync.
      await afterProfileChange();
      await load();
      showToast(`${code} added`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add class');
    }
  };

  /**
   * Save the attendance target to the profile.
   *
   * It lives on the profile rather than in storage, so the colours, advice and
   * at-risk list on every screen agree, and it survives on another device.
   */
  const saveTarget = async () => {
    const clamped = Math.min(100, Math.max(0, Number(targetDraft) || 0));
    setTargetDraft(clamped);
    try {
      await profileApi.update({ attendance_target: clamped });
      setError(null);
      showToast(`Attendance target set to ${clamped}%`);
      // The profile changed, so dependent screens refetch.
      await afterProfileChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save target');
    }
  };

  const atRisk = subjects.filter(subject => subject.must_attend > 0);

  /**
   * Course codes present in the student's timetable.
   *
   * Since the backend now filters subjects to only those in the student's
   * timetable (plus elected electives), we can derive the set directly from
   * the API response.
   */
  const timetableCodes = useMemo(
    () => new Set(subjects.map(subject => subject.course_code.toUpperCase())),
    [subjects]
  );

  /** course_id -> course_code, so the history table can show codes not ids. */
  const codeById = useMemo(
    () => new Map(subjects.map(subject => [subject.course_id, subject.course_code])),
    [subjects]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size={28} className="text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex flex-wrap items-end gap-3">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          icon={<Plus size={16} strokeWidth={2} aria-hidden />}
          onClick={addExtraClass}
        >
          Extra Class
        </Button>
        <div className="flex items-end gap-2">
          <div>
            <span className="label">Add subject</span>
            <Input
              id="att-add-code"
              className="w-36 font-mono"
              value={extraCode}
              onChange={event => setExtraCode(event.target.value.toUpperCase())}
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  addExtraClass();
                }
              }}
              placeholder="e.g. OE3E33"
            />
          </div>
          <Button
            type="button"
            variant="primary"
            size="sm"
            icon={<Plus size={16} strokeWidth={2} aria-hidden />}
            onClick={addExtraClass}
          >
            Add
          </Button>
        </div>
        <div className="ml-auto flex items-end gap-2">
          <div>
            <span className="label">Target %</span>
            <Input
              id="att-target"
              type="number"
              min="0"
              max="100"
              className="w-24"
              value={targetDraft}
              onChange={event => setTargetDraft(event.target.value)}
            />
          </div>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={saveTarget}
            disabled={Number(targetDraft) === target}
          >
            Save
          </Button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Daily banner */}
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <IconTile hue="indigo" size={44}>
              <CalendarDays
                size={22}
                strokeWidth={2}
                aria-hidden
                style={{ color: 'currentColor' }}
              />
            </IconTile>
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
                {ist.date}
              </p>
              <p className="text-xs font-mono" style={{ color: 'var(--cp-muted)' }}>
                {ist.time}
              </p>
            </div>
          </div>
          <div className="flex gap-2 text-xs">
            <Badge tone="primary">
              {todayClasses.length} class{todayClasses.length === 1 ? '' : 'es'} today
            </Badge>
            <Badge tone="neutral">
              {todayClasses.length === 0
                ? 'No classes'
                : todayState.unmarked > 0
                  ? `${todayState.unmarked} unmarked`
                  : 'All marked'}
            </Badge>
          </div>
        </div>

        {atRisk.length > 0 && (
          <div className="pt-2" style={{ borderTop: '1px solid rgba(163,177,198,.3)' }}>
            <p className="text-xs font-semibold mb-1.5" style={{ color: 'var(--cp-text)' }}>
              At risk
            </p>
            <div className="flex flex-wrap gap-2">
              {atRisk.map(subject => (
                <Badge key={subject.course_id} tone="danger">
                  {subject.course_code} &middot; attend next {subject.must_attend}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/*
        No overall card. An average across subjects hides the thing a student
        actually needs to act on: one subject at 60% is invisible behind a total
        of 90%, and it is the per-subject numbers that decide whether they can
        skip a class. The per-subject cards below carry the same target, so
        nothing actionable is lost.
      */}

      {/* Sub-tabs */}
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
          onClick={load}
          className="ml-auto"
        >
          Refresh
        </Button>
      </div>

      {subTab === 'subjects' &&
        (subjects.length === 0 ? (
          <Card className="text-center py-10 text-sm" style={{ color: 'var(--cp-muted)' }}>
            No subjects yet. Upload the class timetable so subjects sync automatically, or add one
            above.
          </Card>
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {subjects.map(subject => (
              <SubjectCard
                key={subject.course_id}
                subject={subject}
                target={target}
                periods={(todayState.scheduled.get(subject.course_code) || []) as TimetableSlot[]}
                slots={slots}
                hasClassToday={(todayState.scheduled.get(subject.course_code) || []).length > 0}
                inTimetable={timetableCodes.has(subject.course_code)}
                onMark={status => mark(subject, status)}
                onDetails={() => setCalendarFor(subject)}
              />
            ))}
          </div>
        ))}

      {subTab === 'history' && (
        <Card>
          <h3
            className="text-sm font-semibold mb-3 flex items-center gap-2"
            style={{ color: 'var(--cp-text)' }}
          >
            <BarChart3 size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
            Recent records
          </h3>
          {records.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
              Nothing recorded yet.
            </p>
          ) : (
            <Table
              head={['Date', 'Course', 'Status']}
              rows={records
                .slice()
                .reverse()
                .slice(0, 50)
                .map(record => [
                  <span key="d" style={{ color: 'var(--cp-text)' }}>
                    {record.date}
                  </span>,
                  <span key="c" className="font-mono" style={{ color: 'var(--cp-text)' }}>
                    {codeById.get(record.course_id) || `#${record.course_id}`}
                  </span>,
                  <Badge
                    key="s"
                    tone={
                      record.status === 'Present'
                        ? 'success'
                        : record.status === 'Absent'
                          ? 'danger'
                          : 'neutral'
                    }
                  >
                    {record.status}
                  </Badge>,
                ])}
            />
          )}
        </Card>
      )}

      {/* Toast with undo */}
      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-primary-500 text-white text-sm shadow-lg">
          <span>{toast.message}</span>
          {toast.undo && (
            <button type="button" onClick={() => toast.undo!()} className="underline font-medium">
              Undo
            </button>
          )}
        </div>
      )}

      {/* Details modal */}
      {calendarFor && (
        <CalendarModal
          subject={calendarFor}
          onClose={() => setCalendarFor(null)}
          onMark={(date, status) => mark(calendarFor, status, date)}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Subject card                                                        */
/* ------------------------------------------------------------------ */

const STATUS_BADGE: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  Safe: 'success',
  Warning: 'warning',
  Critical: 'danger',
};

interface SubjectCardProps {
  subject: AttendanceSubject;
  target: number;
  periods: TimetableSlot[];
  slots?: TimetableSlot[];
  hasClassToday: boolean;
  inTimetable: boolean;
  onMark: (status: Status) => void;
  onDetails: () => void;
}

function SubjectCard({
  subject,
  target,
  periods,
  slots = [],
  hasClassToday,
  inTimetable,
  onMark,
  onDetails,
}: SubjectCardProps) {
  const recorded = hasRecords(subject);
  const instructor = instructorFor(subject.course_code, slots);
  const tone = recorded ? toneFor(subject.percentage, target) : 'neutral';

  return (
    <Card className="flex flex-col gap-2" style={inTimetable ? undefined : { opacity: 0.7 }}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold truncate" style={{ color: 'var(--cp-text)' }}>
            {subject.course_name || subject.course_code}
          </p>
          <p className="text-[11px] font-mono" style={{ color: 'var(--cp-muted)' }}>
            {subject.course_code}
          </p>
          {/* The subject API has no teacher field, so it is read off the
              timetable, which names one for every class. */}
          {instructor && (
            <p
              className="text-[11px] mt-0.5"
              style={{ color: 'var(--cp-muted)' }}
              title={instructor}
            >
              {instructor}
            </p>
          )}
          {/* Kept, but no longer in the timetable: history is still real. */}
          {!inTimetable && (
            <p className="text-[10px] mt-0.5" style={{ color: 'var(--cp-text)' }}>
              Not in this semester&apos;s timetable
            </p>
          )}
        </div>
        <Badge tone={recorded ? STATUS_BADGE[subject.status] || 'neutral' : 'neutral'}>
          {recorded ? subject.status : 'No data'}
        </Badge>
      </div>

      <div>
        {/* Nothing recorded is shown as a dash, not as a number the backend
            invented. A 0/0 subject is not 100% attended. */}
        {recorded ? (
          <>
            <p className="text-3xl font-bold leading-none" style={{ color: 'var(--cp-text)' }}>
              {subject.percentage}%
            </p>
            <p className="text-[11px] mt-1" style={{ color: 'var(--cp-muted)' }}>
              {subject.present}/{subject.total_held} attended
            </p>
          </>
        ) : (
          <>
            <p className="text-3xl font-bold leading-none" style={{ color: 'var(--cp-muted)' }}>
              &mdash;
            </p>
            <p className="text-[11px] mt-1" style={{ color: 'var(--cp-muted)' }}>
              No classes recorded
            </p>
          </>
        )}
      </div>

      {/* An empty bar at 0% would read as "you have missed everything". */}
      {recorded && (
        <ProgressBar
          value={subject.percentage}
          max={100}
          label={`${subject.course_code} attendance`}
        />
      )}

      <p className="text-[11px]" style={{ color: 'var(--cp-muted)' }}>
        {tone !== 'neutral' && (
          <Badge tone={tone === 'success' ? 'success' : tone === 'warning' ? 'warning' : 'danger'}>
            {tone === 'success' ? 'On track' : tone === 'warning' ? 'Watch' : 'At risk'}
          </Badge>
        )}{' '}
        {advice(subject)}
      </p>

      {periods.length > 1 && (
        <div className="flex flex-wrap gap-1">
          {periods.map(slot => (
            <Badge key={`${slot.id}`} tone="neutral" className="font-mono" title={slot.room}>
              P{periods.indexOf(slot) + 1}
            </Badge>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1 mt-auto pt-1">
        <Button
          type="button"
          variant="success"
          size="sm"
          icon={<Check size={16} strokeWidth={2} aria-hidden />}
          title={hasClassToday ? 'Mark Present' : 'No class scheduled today'}
          onClick={() => onMark('Present')}
          disabled={!hasClassToday}
          className="flex-1"
        >
          Present
        </Button>
        <Button
          type="button"
          variant="danger"
          size="sm"
          icon={<X size={16} strokeWidth={2} aria-hidden />}
          title={hasClassToday ? 'Mark Absent' : 'No class scheduled today'}
          onClick={() => onMark('Absent')}
          disabled={!hasClassToday}
          className="flex-1"
        >
          Absent
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          icon={<Minus size={16} strokeWidth={2} aria-hidden />}
          title="Mark Cancelled"
          onClick={() => onMark('Cancelled')}
          className="flex-1"
        >
          Cancelled
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDetails}>
          Details
        </Button>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Calendar modal                                                      */
/* ------------------------------------------------------------------ */

const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];

/** ISO date for a (year, month 1-12, day) triple. */
function iso(year: number, month: number, day: number): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

/** Monday-first grid of the given month, padded with nulls. */
function monthGrid(year: number, month: number): (number | null)[] {
  const first = new Date(Date.UTC(year, month - 1, 1));
  const offset = (first.getUTCDay() + 6) % 7;
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const cells: (number | null)[] = new Array(offset).fill(null);
  for (let day = 1; day <= daysInMonth; day += 1) cells.push(day);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

interface CalendarModalProps {
  subject: AttendanceSubject;
  onClose: () => void;
  onMark: (date: string, status: Status) => Promise<void> | void;
}

function CalendarModal({ subject, onClose, onMark }: CalendarModalProps) {
  const today = todayIso();
  const [cursor, setCursor] = useState({
    year: Number(today.slice(0, 4)),
    month: Number(today.slice(5, 7)),
  });
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await attendanceApi.course(subject.course_id);
        if (cancelled) return;
        setEntries(data.calendar || []);
      } catch {
        if (!cancelled) setEntries([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [subject.course_id]);

  const byDate = useMemo(() => {
    const map = new Map<string, CalendarEntry[]>();
    entries.forEach(entry => {
      if (!map.has(entry.date)) map.set(entry.date, []);
      map.get(entry.date)!.push(entry);
    });
    return map;
  }, [entries]);

  const shift = (delta: number) => {
    setCursor(current => {
      const next = new Date(Date.UTC(current.year, current.month - 1 + delta, 1));
      return { year: next.getUTCFullYear(), month: next.getUTCMonth() + 1 };
    });
  };

  const monthName = new Date(Date.UTC(cursor.year, cursor.month - 1, 1)).toLocaleString('en-GB', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });

  return (
    <Modal title={subject.course_code} onClose={onClose}>
      <div className="flex items-center justify-between mb-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          icon={<ChevronLeft size={16} strokeWidth={2} aria-hidden />}
          onClick={() => shift(-1)}
        >
          Prev
        </Button>
        <span className="text-sm font-medium" style={{ color: 'var(--cp-text)' }}>
          {monthName}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          icon={<ChevronRight size={16} strokeWidth={2} aria-hidden />}
          iconPosition="right"
          onClick={() => shift(1)}
        >
          Next
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <Spinner size={20} className="text-primary-500" />
        </div>
      ) : (
        <>
          <div
            className="grid grid-cols-7 gap-1 text-center text-[10px] uppercase mb-1"
            style={{ color: 'var(--cp-muted)' }}
          >
            {WEEKDAYS.map(day => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {monthGrid(cursor.year, cursor.month).map((day, index) => {
              if (day === null) return <span key={`pad-${index}`} />;
              const date = iso(cursor.year, cursor.month, day);
              const marks = byDate.get(date) || [];
              const hasExtra = marks.length > 1;
              const present = marks.some(m => m.status === 'Present');
              const absent = marks.some(m => m.status === 'Absent');
              const cancelled = marks.some(m => m.status === 'Cancelled');
              const isToday = date === today;
              const isPast = date < today;
              const tone = present
                ? 'bg-success-500 text-white'
                : absent
                  ? 'bg-danger-500 text-white'
                  : cancelled
                    ? 'bg-gray-300 text-gray-700'
                    : isPast
                      ? 'bg-gray-100 text-gray-400 border border-dashed border-gray-300'
                      : 'bg-white text-gray-600 border border-gray-200';
              return (
                <button
                  key={date}
                  type="button"
                  disabled={!isPast}
                  onClick={() => setSelected(date)}
                  aria-label={`${date}${present ? ', present' : absent ? ', absent' : cancelled ? ', cancelled' : ', not marked'}`}
                  className={`relative aspect-square rounded-md text-xs font-medium ${tone} ${
                    isToday ? 'ring-2 ring-primary-500 ring-offset-1' : ''
                  } ${hasExtra ? 'border-2 border-primary-500' : ''} ${
                    isPast ? 'cursor-pointer' : 'cursor-default'
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>

          <div
            className="flex flex-wrap gap-3 mt-3 text-[10px]"
            style={{ color: 'var(--cp-muted)' }}
          >
            <Legend className="bg-success-500" label="Present" />
            <Legend className="bg-danger-500" label="Absent" />
            <Legend className="bg-gray-300" label="Cancelled" />
            <Legend
              className="bg-gray-100 border border-dashed border-gray-300"
              label="Not marked"
            />
            <Legend className="bg-white border-2 border-primary-500" label="Extra / multi-period" />
          </div>
        </>
      )}

      {selected && (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid rgba(163,177,198,.3)' }}>
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--cp-text)' }}>
            {selected}
          </p>
          <div className="flex flex-wrap gap-2">
            {STATUSES.map(status => (
              <Button
                key={status}
                type="button"
                variant="secondary"
                size="sm"
                icon={
                  status === 'Present' ? (
                    <Check size={16} strokeWidth={2} aria-hidden />
                  ) : status === 'Absent' ? (
                    <X size={16} strokeWidth={2} aria-hidden />
                  ) : (
                    <Minus size={16} strokeWidth={2} aria-hidden />
                  )
                }
                onClick={async () => {
                  await onMark(selected, status);
                  setSelected(null);
                }}
              >
                Mark {status}
              </Button>
            ))}
            <Button type="button" variant="ghost" size="sm" onClick={() => setSelected(null)}>
              Close
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`w-3 h-3 rounded ${className}`} />
      {label}
    </span>
  );
}
