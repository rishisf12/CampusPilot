/**
 * Live weekday selection.
 *
 * - Defaults to today's weekday (IST) if the student has classes that day.
 * - On weekends (Sat/Sun) defaults to "all" so the full week is visible.
 * - If today isn't in the student's available days, falls back to "all".
 * - Updates automatically when the day changes (tab left open overnight).
 * - Never overrides an explicit user choice; once the user picks a day, the
 *   automatic default stops until the available days change (new timetable
 *   upload, branch/semester switch) or the user refreshes.
 */
import { useEffect, useMemo, useState } from 'react';
import { todayWeekday } from '../lib/time';

// Weekends in the IST short form the backend uses.
const WEEKEND = new Set(['Sat', 'Sun']);

export interface UseLiveDayReturn {
  day: string;
  onSelect: (nextDay: string) => void;
  isManual: boolean;
}

export function useLiveDay(availableDays: string[]): UseLiveDayReturn {
  // has the user explicitly clicked a day button?
  const [manual, setManual] = useState(false);
  // the day we show - either the live default or the user's pick
  const [day, setDay] = useState('all');

  // compute the automatic default from today's IST weekday
  const autoDefault = useMemo(() => {
    const today = todayWeekday(); // "Mon" ... "Sun"
    if (WEEKEND.has(today)) return 'all';
    if (availableDays.includes(today)) return today;
    return 'all';
  }, [availableDays]);

  // live tick: recompute the default every minute; if the day changed and the
  // user hasn't picked manually, switch to the new default.
  useEffect(() => {
    const id = setInterval(() => {
      if (manual) return;
      const today = todayWeekday();
      const next = WEEKEND.has(today) || !availableDays.includes(today) ? 'all' : today;
      if (next !== day) setDay(next);
    }, 60_000);
    return () => clearInterval(id);
  }, [availableDays, day, manual]);

  // when available days change (new upload, branch switch), reset manual so the
  // live default takes over again - but keep the user's pick if it's still valid
  useEffect(() => {
    if (!manual) {
      setDay(autoDefault);
    } else if (!availableDays.includes(day) && day !== 'all') {
      // user's explicit day no longer exists; fall back gracefully
      setManual(false);
      setDay(autoDefault);
    }
  }, [availableDays, autoDefault, day, manual]);

  const onSelect = (nextDay: string) => {
    setManual(nextDay !== autoDefault);
    setDay(nextDay);
  };

  return { day, onSelect, isManual: manual };
}
