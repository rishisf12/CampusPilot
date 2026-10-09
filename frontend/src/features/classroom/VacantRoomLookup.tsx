import { useCallback, useEffect, useMemo, useState } from 'react';
import { roomsApi } from '../../api';
import { DAYS } from '../../constants';
import { formatTime } from '../../lib/time';
import { dedupeRooms, normaliseRoom } from '../../lib/normalise';
import useProfileVersion from '../../hooks/useProfileVersion';
import ErrorBanner from '../../components/ErrorBanner';
import Spinner from '../../components/Spinner';

interface VacantRoomResult {
  mode: 'live' | 'manual';
  day?: string;
  time?: string;
  vacant_rooms?: string[];
  occupied_rooms?: Array<{
    room: string;
    course_code: string;
    start_time: string;
    end_time: string;
  }>;
  has_timetable: boolean;
  message?: string;
}

interface AllRoomsResult {
  rooms?: string[];
}

/**
 * Vacant room lookup with day/time filters, plus the full room list.
 *
 * Rooms come from the uploaded class timetable, so the list refetches whenever
 * the timetable is uploaded or removed - that is the profile version bump the
 * upload triggers.
 */
interface VacantRoomLookupProps {
  onError?: (message: string) => void;
}

export default function VacantRoomLookup({ onError }: VacantRoomLookupProps) {
  const [day, setDay] = useState('');
  const [hour, setHour] = useState('');
  const [result, setResult] = useState<VacantRoomResult | null>(null);
  const [allRooms, setAllRooms] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const profileVersion = useProfileVersion();

  const search = useCallback(async () => {
    if (!day || !hour) return;
    setLoading(true);
    try {
      const data = await roomsApi.vacant({ mode: 'manual', day, hour });
      setResult(data);
      setError(null);
    } catch (err) {
      // Keep the previous result visible rather than blanking the screen.
      setError(err instanceof Error ? err.message : 'Search failed');
      onError?.(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }, [day, hour, onError]);

  // Live mode by default; refetched whenever the timetable changes.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [live, rooms] = await Promise.all([
          roomsApi.vacant({ mode: 'live' }),
          roomsApi.all(),
        ]);
        if (cancelled) return;
        setResult(live);
        // Normalise and de-duplicate: "CR 201" and "CR-201" are one room.
        setAllRooms(dedupeRooms((rooms as AllRoomsResult).rooms || []));
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load rooms');
          onError?.(err instanceof Error ? err.message : 'Failed to load rooms');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onError, profileVersion]);

  // Seed the filters from the live result so they reflect "now".
  useEffect(() => {
    if (result?.day && !day) setDay(result.day);
    if (result?.time && !hour) setHour(result.time);
    // Only seed once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  // De-duplicated once here rather than inside the JSX, where it would run on
  // every render and create new arrays each time.
  const vacantRooms = useMemo(() => dedupeRooms(result?.vacant_rooms || []), [result]);

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Vacant Room Lookup</h3>

        <div className="grid grid-cols-1 sm:grid-cols-[auto_auto_auto] gap-3 items-end">
          <div>
            <span className="label">Day</span>
            <select
              id="vr-day"
              className="select-field"
              value={day}
              onChange={e => setDay(e.target.value)}
            >
              <option value="">Select day</option>
              {DAYS.map(item => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
          <div>
            <span className="label">Time</span>
            <input
              id="vr-hour"
              type="time"
              className="input-field"
              value={hour}
              onChange={e => setHour(e.target.value)}
            />
          </div>
          <button
            type="button"
            onClick={search}
            className="btn-primary text-sm"
            disabled={!day || !hour || loading}
          >
            {loading ? <Spinner size={16} className="text-white" /> : 'Find Vacant Rooms'}
          </button>
        </div>

        {result && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-gray-500">
              {result.day} at {formatTime(result.time)}
            </span>
            {/* The backend already explains a missing timetable, so show it once. */}
            {result.message && <span className="text-primary-600">{result.message}</span>}
          </div>
        )}
      </div>

      {result && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Vacant ({vacantRooms.length})
            </h3>
            {vacantRooms.length ? (
              <div className="flex flex-wrap gap-2">
                {vacantRooms.map(room => (
                  <span
                    key={room}
                    className="px-2.5 py-1 rounded-lg bg-success-50 text-success-700 text-xs font-mono font-medium"
                  >
                    {normaliseRoom(room)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No vacant rooms at this time.</p>
            )}
          </div>

          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Occupied ({result.occupied_rooms?.length || 0})
            </h3>
            {result.occupied_rooms?.length ? (
              <div className="space-y-1.5">
                {result.occupied_rooms.map(item => (
                  <div
                    key={`${item.room}-${item.course_code}`}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="font-mono text-gray-900">{normaliseRoom(item.room)}</span>
                    <span className="text-xs text-gray-600">
                      {item.course_code} &middot; {formatTime(item.start_time)} -{' '}
                      {formatTime(item.end_time)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Nothing is scheduled.</p>
            )}
          </div>
        </div>
      )}

      <div className="card">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">All rooms ({allRooms.length})</h3>
        {allRooms.length ? (
          <div className="flex flex-wrap gap-2">
            {allRooms.map(room => (
              <span
                key={room}
                className="px-2.5 py-1 rounded-lg bg-gray-100 text-gray-700 text-xs font-mono"
              >
                {normaliseRoom(room)}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            No rooms yet - upload the class timetable from the Live Schedule tab.
          </p>
        )}
      </div>
    </div>
  );
}
