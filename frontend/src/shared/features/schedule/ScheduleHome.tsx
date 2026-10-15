import { useEffect, useState } from 'react';
import { CalendarDays, CheckCircle2, Clock, DoorOpen, FileText } from 'lucide-react';
import { Badge, Button, Card } from '@/components/ui';
import { formatTime as formatClock, istNow } from '@shared/lib/time';
import { toMinutes } from '@shared/lib/normalise';

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

function formatCountdown(totalMins: number): string {
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

export default function ScheduleHome({
  loading,
  hasTimetable,
  current,
  nextClass,
  todayRemaining,
  courseLabel,
  onJumpTab,
  showAttendanceAction,
  showVacantAction,
}: ScheduleHomeProps) {
  useNow();

  if (loading) {
    return (
      <div className="space-y-4" aria-label="Loading today's schedule">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  const nowMinutes = istNow().minutes;
  const next = nextClass;
  // Friendly empty states name the next class when there is one.
  const nextHint = next
    ? `Next one starts at ${formatClock(next.start_time)} in Room ${next.room || 'TBA'}.`
    : null;

  return (
    <div className="space-y-4">
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

      {/* 2 — Up next */}
      {next && (
        <Card style={{ background: 'var(--cp-warning-bg)', borderColor: 'transparent' }}>
          <div className="flex items-center gap-2 mb-2">
            <Clock size={16} strokeWidth={2} aria-hidden style={{ color: 'var(--cp-warning)' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
              Up next
            </h3>
            <span
              className="ml-auto text-xs font-medium"
              style={{ color: 'var(--cp-warning)' }}
              aria-live="off"
            >
              {formatCountdown(minutesUntil(next.start_time, nowMinutes))}
            </span>
          </div>
          <p className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
            {courseLabel(next)}
          </p>
          <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
            Room {next.room || 'TBA'}
            {next.instructor ? ` · ${next.instructor}` : ''}
            {' · '}
            {formatClock(next.start_time)} - {formatClock(next.end_time)}
          </p>
        </Card>
      )}

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
