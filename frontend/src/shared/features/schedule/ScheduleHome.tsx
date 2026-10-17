import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlarmClock,
  BellRing,
  CalendarDays,
  CheckCircle2,
  Clock,
  DoorOpen,
  FileText,
  X,
} from 'lucide-react';
import { Badge, Button, Card } from '@/components/ui';
import { formatTime as formatClock, daysUntilWeekday, istNow, todayIso } from '@shared/lib/time';
import { toMinutes } from '@shared/lib/normalise';
import { readJson, writeJson, STORAGE_KEY } from '@shared/lib/storage';

export interface HomeClass {
  course_code: string;
  course_name?: string;
  instructor?: string | null;
  room: string;
  start_time: string;
  end_time: string;
  day: string;
}

interface ScheduleHomeProps {
  loading: boolean;
  hasTimetable: boolean;
  /** Class happening right now (profile-filtered), or null. */
  current: HomeClass | null;
  /** Next upcoming class, or null. */
  nextClass: HomeClass | null;
  /**
   * The next classes in calendar order, the first being nextClass itself.
   * Optional: callers that only know a single next class simply omit it and
   * the Up-next section falls back to that one card.
   */
  nextClasses?: HomeClass[];
  /** Today's classes that have not ended yet, sorted. */
  todayRemaining: HomeClass[];
  courseLabel: (item: { course_name?: string; course_code?: string }) => string;
  /** Jump to a classroom tab (attendance / vacant / exam). */
  onJumpTab: (id: string) => void;
  /** True when the classroom bundle has no attendance tab (PG/PhD). */
  showAttendanceAction: boolean;
  /** True when the classroom bundle has no vacant-rooms tab (PG/PhD). */
  showVacantAction: boolean;
}

/** Ticks so countdowns and progress bars stay live without a refetch. */
function useNow(intervalMs = 30000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}

function minutesUntil(startTime: string, nowMinutes: number): number {
  return Math.max(0, toMinutes(startTime) - nowMinutes);
}

function formatCountdown(totalMins: number, dayOffset = 0): string {
  // A class later in the week is never "starting now"; say which day instead.
  if (dayOffset > 0) {
    if (dayOffset === 1) return 'tomorrow';
    return `in ${dayOffset} days`;
  }
  if (totalMins < 1) return 'starting now';
  if (totalMins < 60) return `in ${totalMins} min`;
  const h = Math.floor(totalMins / 60);
  const m = totalMins % 60;
  return m === 0 ? `in ${h} hr` : `in ${h} hr ${m} min`;
}

function formatRemaining(totalMins: number): string {
  if (totalMins < 1) return 'ending now';
  if (totalMins < 60) return `${totalMins} min left`;
  const h = Math.floor(totalMins / 60);
  const m = totalMins % 60;
  return m === 0 ? `${h} hr left` : `${h} hr ${m} min left`;
}

function SkeletonCard() {
  return (
    <Card aria-hidden>
      <div className="animate-pulse space-y-3">
        <div className="h-4 w-32 rounded" style={{ background: 'var(--cp-bg)' }} />
        <div className="h-5 w-3/4 rounded" style={{ background: 'var(--cp-bg)' }} />
        <div className="h-4 w-1/2 rounded" style={{ background: 'var(--cp-bg)' }} />
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Class alarms                                                        */
/* ------------------------------------------------------------------ */

/** Lead times a student can pick, in minutes before the class starts. */
const ALARM_OPTIONS = [5, 10, 15, 30, 60];

/** An alarm is bound to the weekly slot, so it re-arms for every occurrence. */
interface ClassAlarm {
  /** Minutes before the class to fire. */
  lead: number;
  /** ISO date (IST) of the occurrence last fired; never refire it. */
  lastFired: string | null;
}

type AlarmMap = Record<string, ClassAlarm>;

/** Slot key: same course, day and start time share one alarm, week after week. */
function slotKeyOf(item: HomeClass): string {
  return `${item.course_code}|${item.day}|${item.start_time}`;
}

function readAlarms(): AlarmMap {
  return readJson<AlarmMap>(STORAGE_KEY.classAlarms, {}) ?? {};
}

/**
 * The bell on an upcoming-class card. Opens a popover with a Disable row on
 * top and lead-time choices under it. No alarm library here: the choice is
 * stored locally and a tick in ScheduleHome decides when it rings.
 */
function AlarmButton({
  courseCode,
  alarm,
  onChange,
}: {
  courseCode: string;
  alarm: ClassAlarm | null;
  onChange: (alarm: ClassAlarm | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const armed = alarm !== null;

  // Open the panel moving focus into it, so keyboard users are not left at the
  // bell with a dialog rendered elsewhere in the tab order.
  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  // The permission prompt must ride on a user gesture - a click on a time
  // choice, never page load.
  const choose = (lead: number) => {
    if ('Notification' in window && Notification.permission === 'default') {
      void Notification.requestPermission();
    }
    onChange({ lead, lastFired: alarm?.lastFired ?? null });
    setOpen(false);
  };

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        aria-label={
          armed
            ? `Alarm set for ${courseCode}: ${alarm.lead} minutes before, change or disable`
            : `Set an alarm for ${courseCode}`
        }
        className="inline-flex items-center justify-center w-7 h-7 rounded-full transition-opacity hover:opacity-100"
        style={{
          color: armed ? 'var(--cp-warning)' : 'var(--cp-muted)',
          opacity: armed ? 1 : 0.75,
        }}
      >
        {armed ? (
          <BellRing size={15} strokeWidth={2} aria-hidden />
        ) : (
          <AlarmClock size={15} strokeWidth={2} aria-hidden />
        )}
      </button>
      {open && (
        <>
          {/* Click-away catcher: closes the popover without a focus trap. */}
          <button
            type="button"
            tabIndex={-1}
            aria-hidden
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-20 cursor-default"
          />
          <div
            ref={panelRef}
            role="dialog"
            aria-label={`Alarm for ${courseCode}`}
            tabIndex={-1}
            onKeyDown={e => {
              if (e.key === 'Escape') setOpen(false);
            }}
            className="absolute right-0 top-full mt-1 z-30 w-52 rounded-xl p-3 space-y-2 outline-none"
            style={{
              background: 'var(--cp-surface, var(--cp-bg))',
              border: '1px solid rgba(127,127,127,.3)',
              boxShadow: '0 12px 28px rgba(0,0,0,.28)',
            }}
          >
            <button
              type="button"
              disabled={!armed}
              onClick={() => {
                onChange(null);
                setOpen(false);
              }}
              className="w-full text-xs font-medium rounded-lg py-1.5 disabled:cursor-not-allowed"
              style={{
                color: armed ? 'var(--cp-text)' : 'var(--cp-muted)',
                opacity: armed ? 1 : 0.55,
                background: 'rgba(127,127,127,.12)',
              }}
            >
              Disable alarm
            </button>
            <p className="text-xs font-medium" style={{ color: 'var(--cp-muted)' }}>
              Min before class
            </p>
            <div className="flex flex-wrap gap-1.5">
              {ALARM_OPTIONS.map(mins => {
                const selected = armed && alarm.lead === mins;
                return (
                  <button
                    key={mins}
                    type="button"
                    onClick={() => choose(mins)}
                    aria-pressed={selected}
                    className="text-xs font-medium rounded-full px-2.5 py-1 focus-visible:outline-2"
                    style={
                      selected
                        ? { background: 'var(--cp-warning)', color: 'var(--cp-on-accent)' }
                        : { background: 'rgba(127,127,127,.14)', color: 'var(--cp-text)' }
                    }
                  >
                    {mins} min
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </span>
  );
}

export default function ScheduleHome({
  loading,
  hasTimetable,
  current,
  nextClass,
  nextClasses,
  todayRemaining,
  courseLabel,
  onJumpTab,
  showAttendanceAction,
  showVacantAction,
}: ScheduleHomeProps) {
  // Ticks every second so countdowns stay live and alarms fire on time.
  const now: number = useNow(1000);

  // Alarms are a localStorage-backed preference; the ref lets the tick effect
  // read the current map without being recreated by every write.
  const [alarms, setAlarms] = useState<AlarmMap>(readAlarms);
  const alarmsRef = useRef(alarms);
  alarmsRef.current = alarms;

  /** Persist a one-slot change. Stable identity, so effects can depend on it. */
  const writeAlarms = useCallback((key: string, alarm: ClassAlarm | null) => {
    setAlarms(prev => {
      const next = { ...prev };
      if (alarm) next[key] = alarm;
      else delete next[key];
      writeJson(STORAGE_KEY.classAlarms, next);
      return next;
    });
  }, []);

  /** The ring: an in-app banner on top of the schedule. */
  const [notice, setNotice] = useState<{ code: string; text: string } | null>(null);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 90_000);
    return () => clearTimeout(timer);
  }, [notice]);

  const nowMinutes = istNow(new Date(now)).minutes;
  const next = nextClass;
  // The next class can fall on a later weekday once today is over, so ask the
  // day-aware helper instead of assuming it is today.
  const nextOffset = next ? daysUntilWeekday(next.day, new Date(now)) : 0;
  // Up-next cards: the next two classes on the calendar. Falls back to the
  // single nextClass when the caller only knows one.
  const upcomingList = (nextClasses && nextClasses.length ? nextClasses : next ? [next] : []).slice(
    0,
    2
  );
  // Friendly empty states name the next class when there is one.
  const nextHint = next
    ? nextOffset > 0
      ? `Next class is ${nextOffset === 1 ? 'tomorrow' : next.day} at ${formatClock(
          next.start_time
        )} in Room ${next.room || 'TBA'}.`
      : `Next one starts at ${formatClock(next.start_time)} in Room ${next.room || 'TBA'}.`
    : null;

  /**
   * The tick that rings alarms. Ran every second `now` moves; each slotted
   * alarm fires once per weekly occurrence, inside the window from its fire
   * time to the class end, and records that occurrence so it re-arms next week.
   */
  useEffect(() => {
    // Upcoming cards and later-today slots overlap; a slot is checked once.
    const seen = new Set<string>();
    const slots: Array<{ item: HomeClass; key: string }> = [];
    for (const item of [...upcomingList, ...todayRemaining]) {
      const key = slotKeyOf(item);
      if (seen.has(key)) continue;
      seen.add(key);
      slots.push({ item, key });
    }

    for (const { item, key } of slots) {
      const alarm = alarmsRef.current[key];
      if (!alarm) continue;

      const n = istNow(new Date(now));
      const offset = daysUntilWeekday(item.day, new Date(now));
      const startMin = toMinutes(item.start_time);
      const endMin = toMinutes(item.end_time) || startMin;
      // Days-out classes sit beyond the 1439-minute day, so they cannot fire
      // early; on the class day the offset clamps to zero and the window opens.
      const fireAbs = offset * 1440 + startMin - alarm.lead;
      const endAbs = offset * 1440 + endMin;
      if (n.minutes < fireAbs || n.minutes > endAbs) continue;
      const occIso = todayIso(new Date(now + offset * 86400000));
      if (alarm.lastFired === occIso) continue;

      const text = `starts at ${formatClock(item.start_time)} in Room ${item.room || 'TBA'}`;
      setNotice({ code: item.course_code, text });
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(`Class alarm · ${item.course_code}`, {
          body: `${text} — ${alarm.lead} min reminder`,
        });
      }
      // Fire-and-rearm: mark only this occurrence, so it rings again next week.
      writeAlarms(key, { lead: alarm.lead, lastFired: occIso });
      break; // one ring at a time; the next tick can ring a later slot.
    }
  }, [now, upcomingList, todayRemaining, writeAlarms]);

  if (loading) {
    return (
      <div className="space-y-4" aria-label="Loading today's schedule">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 0 — Alarm ring: shown on top, one at a time; lives 90 seconds or
          until dismissed. */}
      {notice && (
        <Card
          role="alert"
          style={{ background: 'var(--cp-warning-bg)', borderColor: 'transparent' }}
        >
          <div className="flex items-center gap-2">
            <BellRing
              size={16}
              strokeWidth={2}
              aria-hidden
              style={{ color: 'var(--cp-warning)' }}
            />
            <p className="text-sm min-w-0" style={{ color: 'var(--cp-text)' }}>
              <span className="font-semibold">{notice.code}</span>
              <span style={{ color: 'var(--cp-muted)' }}> · {notice.text}</span>
            </p>
            <button
              type="button"
              onClick={() => setNotice(null)}
              aria-label="Dismiss alarm"
              className="ml-auto shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full"
              style={{ color: 'var(--cp-muted)' }}
            >
              <X size={14} aria-hidden />
            </button>
          </div>
        </Card>
      )}

      {/* 1 — Hero: what is happening right now */}
      {current ? (
        <Card
          style={{
            background: 'var(--cp-success-bg)',
            borderColor: 'transparent',
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="relative flex w-2.5 h-2.5" aria-hidden>
              <span
                className="absolute inline-flex w-full h-full rounded-full"
                style={{ background: 'var(--cp-success)' }}
              />
            </span>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
              Current class
            </h3>
            <span
              className="ml-auto text-xs font-medium"
              style={{ color: 'var(--cp-success)' }}
              aria-live="off"
            >
              {formatRemaining(toMinutes(current.end_time) - nowMinutes)}
            </span>
          </div>
          <p className="text-xl font-semibold" style={{ color: 'var(--cp-text)' }}>
            {courseLabel(current)}
          </p>
          <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
            Room {current.room || 'TBA'}
            {current.instructor ? ` · ${current.instructor}` : ''}
            {' · '}
            {formatClock(current.start_time)} - {formatClock(current.end_time)}
          </p>
          {/* Live progress through the class. */}
          <div
            className="mt-3 h-2 overflow-hidden"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(
              ((nowMinutes - toMinutes(current.start_time)) /
                Math.max(1, toMinutes(current.end_time) - toMinutes(current.start_time))) *
                100
            )}
            aria-label={`Class progress, ${formatRemaining(toMinutes(current.end_time) - nowMinutes)}`}
            style={{ borderRadius: 9999, background: 'rgba(127,127,127,.25)' }}
          >
            <div
              className="h-full transition-all duration-500"
              style={{
                width: `${Math.min(
                  100,
                  Math.max(
                    0,
                    ((nowMinutes - toMinutes(current.start_time)) /
                      Math.max(1, toMinutes(current.end_time) - toMinutes(current.start_time))) *
                      100
                  )
                )}%`,
                borderRadius: 9999,
                background: 'var(--cp-success)',
              }}
            />
          </div>
        </Card>
      ) : (
        <Card>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
            No class right now
          </h3>
          <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
            {hasTimetable
              ? (nextHint ?? 'Nothing else scheduled today. Enjoy the break.')
              : 'No class timetable uploaded yet. Open the Timetable tab to add it.'}
          </p>
        </Card>
      )}

      {/* 2 — Up next: one card per class, first then second. The card count
          is what the caller computed; the countdown is per card, since the
          second can sit on the same day as the first, only hours later. */}
      {upcomingList.map((item, idx) => {
        const offset = daysUntilWeekday(item.day);
        return (
          <Card
            key={`${item.course_code}-${item.start_time}`}
            style={{ background: 'var(--cp-warning-bg)', borderColor: 'transparent' }}
          >
            <div className="flex items-start gap-2 mb-2">
              <Clock size={16} strokeWidth={2} aria-hidden style={{ color: 'var(--cp-warning)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
                {idx === 0 ? 'Up next' : 'Then'}
              </h3>
              {/* Countdown on top, its alarm right under it - one column so
                  the two stay visually paired. */}
              <div className="ml-auto flex flex-col items-end gap-1">
                <span
                  className="text-xs font-medium"
                  style={{ color: 'var(--cp-warning)' }}
                  aria-live="off"
                >
                  {formatCountdown(minutesUntil(item.start_time, nowMinutes), offset)}
                </span>
                <AlarmButton
                  courseCode={item.course_code}
                  alarm={alarms[slotKeyOf(item)] ?? null}
                  onChange={next => writeAlarms(slotKeyOf(item), next)}
                />
              </div>
            </div>
            <p className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
              {courseLabel(item)}
            </p>
            <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
              {offset > 0 ? `${item.day} · ` : ''}Room {item.room || 'TBA'}
              {item.instructor ? ` · ${item.instructor}` : ''}
              {' · '}
              {formatClock(item.start_time)} - {formatClock(item.end_time)}
            </p>
          </Card>
        );
      })}

      {/* 3 — Today's remaining timeline */}
      {todayRemaining.length > 0 && (
        <Card>
          <h3
            className="text-sm font-semibold mb-3 flex items-center gap-2"
            style={{ color: 'var(--cp-text)' }}
          >
            <CalendarDays size={16} strokeWidth={2} aria-hidden style={{ color: 'currentColor' }} />
            Later today
          </h3>
          <ol className="relative ml-1 space-y-0">
            {todayRemaining.map((slot, i) => {
              const isNext = next != null && slot.start_time === next.start_time;
              return (
                <li
                  key={`${slot.course_code}-${slot.start_time}`}
                  className="relative flex gap-3 pb-4 last:pb-0"
                >
                  <span className="flex flex-col items-center" aria-hidden>
                    <span
                      className="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0"
                      style={{
                        background: isNext ? 'var(--cp-warning)' : 'var(--cp-muted)',
                        opacity: isNext ? 1 : 0.5,
                      }}
                    />
                    {i < todayRemaining.length - 1 && (
                      <span
                        className="w-px flex-1"
                        style={{ background: 'rgba(163,177,198,.4)' }}
                      />
                    )}
                  </span>
                  <div className="flex-1 min-w-0 pb-1">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--cp-text)' }}>
                      {courseLabel(slot)}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                      {formatClock(slot.start_time)} - {formatClock(slot.end_time)} · Room{' '}
                      {slot.room || 'TBA'}
                      {isNext && (
                        <Badge tone="warning" className="ml-2">
                          {formatCountdown(minutesUntil(slot.start_time, nowMinutes))}
                        </Badge>
                      )}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </Card>
      )}

      {/* 4 — Quick actions. Only tabs in this student's bundle appear. */}
      <div
        className={`grid gap-2 ${showAttendanceAction && showVacantAction ? 'grid-cols-3' : showAttendanceAction || showVacantAction ? 'grid-cols-2' : 'grid-cols-1'}`}
      >
        {showAttendanceAction && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={<CheckCircle2 size={16} strokeWidth={2} aria-hidden />}
            onClick={() => onJumpTab('attendance')}
            aria-label="Go to Attendance"
          >
            Attendance
          </Button>
        )}
        {showVacantAction && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={<DoorOpen size={16} strokeWidth={2} aria-hidden />}
            onClick={() => onJumpTab('vacant')}
            aria-label="Find free rooms"
          >
            Free Rooms
          </Button>
        )}
        <Button
          type="button"
          variant="secondary"
          size="sm"
          icon={<FileText size={16} strokeWidth={2} aria-hidden />}
          onClick={() => onJumpTab('exam')}
          aria-label="Go to Exams"
        >
          Exams
        </Button>
      </div>
    </div>
  );
}
