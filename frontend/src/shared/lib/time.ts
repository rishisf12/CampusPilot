/**
 * IST (Asia/Kolkata) date and time helpers.
 *
 * Every "today", "now" and weekday decision in the app goes through here.
 * Deriving them from the browser's own timezone would put a student in a
 * different "today" than the college - and near midnight the IST weekday and
 * the local one can disagree, which would mark the wrong day's attendance.
 */

const IST = 'Asia/Kolkata';

/** Today's date in IST as YYYY-MM-DD, which is what the API compares against. */
export function todayIso(now = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: IST }).format(now);
}

/** Current IST weekday as the backend's short form: "Mon" ... "Sun". */
export function todayWeekday(now = new Date()): string {
  const long = new Intl.DateTimeFormat('en-GB', { timeZone: IST, weekday: 'long' }).format(now);
  return long.slice(0, 3);
}

/** Weekday order used across the timetable, starting Monday. */
export const WEEKDAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/**
 * Days from today until `target` (0 = today), wrapping forward.
 *
 * A class on Monday is "3 days away" on Friday, not "4 days ago": without the
 * wrap the countdown would read "starting now" for something days out.
 */
export function daysUntilWeekday(target: string, now = new Date()): number {
  const today = WEEKDAY_ORDER.indexOf(todayWeekday(now));
  const idx = WEEKDAY_ORDER.indexOf(target);
  if (idx < 0 || today < 0) return 0;
  return (idx - today + 7) % 7;
}

export interface IstNowResult {
  date: string;
  time: string;
  weekday: string;
  weekdayShort: string;
  /** Minutes since midnight, IST. */
  minutes: number;
}

/** Wall-clock parts in IST, for the live banner and the "now" comparisons. */
export function istNow(now = new Date()): IstNowResult {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: IST,
    weekday: 'long',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(now);

  const get = (type: string): string => parts.find(part => part.type === type)?.value || '';
  // `hour12: false` can yield "24" at midnight; normalise it to "00".
  const hour = get('hour') === '24' ? '00' : get('hour');

  return {
    date: `${get('weekday')}, ${get('day')} ${get('month')} ${get('year')}`,
    time: `${hour}:${get('minute')}:${get('second')} IST`,
    weekday: get('weekday'),
    weekdayShort: get('weekday').slice(0, 3),
    /** Minutes since midnight, IST. */
    minutes: Number(hour) * 60 + Number(get('minute')),
  };
}

/** Time-aware greeting in IST ("Good morning" / "Good afternoon" / "Good evening"). */
export function greetingFor(now = new Date()): string {
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', { timeZone: IST, hour: '2-digit', hour12: false }).format(now)
  );
  const h = hour === 24 ? 0 : hour;
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

/** "14:30" -> "2:30 PM". */
export function formatTime(value: string | undefined | null): string {
  if (!value) return '';
  const [rawHour, minute] = String(value).split(':');
  const hour = Number(rawHour);
  if (!Number.isFinite(hour)) return '';
  const display = hour % 12 === 0 ? 12 : hour % 12;
  return `${display}:${minute} ${hour >= 12 ? 'PM' : 'AM'}`;
}

/** Format an ISO date as "26 Sept 2026". */
export function formatDate(isoDate: string | undefined | null): string {
  if (!isoDate) return 'Date not specified';
  const date = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}
