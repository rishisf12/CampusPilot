import { useCallback, useEffect, useMemo, useState } from 'react';
import { Building2, DoorClosed, DoorOpen, Search } from 'lucide-react';
import { Badge, Button, Card, Input, Select } from '@/components/ui';
import { roomsApi } from '@/api';
import { DAYS } from '@shared/constants';
import { formatTime } from '@shared/lib/time';
import { dedupeRooms, normaliseRoom } from '@shared/lib/normalise';
import useProfileVersion from '@shared/hooks/useProfileVersion';
import ErrorBanner from '@shared/components/ErrorBanner';

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

      <Card className="space-y-4">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          Vacant Room Lookup
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-[auto_auto_auto] gap-3 items-end">
          <div>
            <span className="label">Day</span>
            <Select id="vr-day" value={day} onChange={e => setDay(e.target.value)}>
              <option value="">Select day</option>
              {DAYS.map(item => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <span className="label">Time</span>
            <Input id="vr-hour" type="time" value={hour} onChange={e => setHour(e.target.value)} />
          </div>
          <Button
            type="button"
            onClick={search}
            variant="primary"
            size="sm"
            icon={<Search size={16} strokeWidth={2} />}
            loading={loading}
            disabled={!day || !hour || loading}
          >
            Find Vacant Rooms
          </Button>
        </div>

        {result && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span style={{ color: 'var(--cp-muted)' }}>
              {result.day} at {formatTime(result.time)}
            </span>
            {/* The backend already explains a missing timetable, so show it once. */}
            {result.message && <Badge tone="info">{result.message}</Badge>}
          </div>
        )}
      </Card>

      {result && (
        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
              Vacant ({vacantRooms.length})
            </h3>
            {vacantRooms.length ? (
              <div className="flex flex-wrap gap-2">
                {vacantRooms.map(room => (
                  <Badge key={room} tone="success" className="font-mono">
                    <DoorOpen size={12} strokeWidth={2} aria-hidden />
                    {normaliseRoom(room)}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
                No vacant rooms at this time.
              </p>
            )}
          </Card>

          <Card>
            <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
              Occupied ({result.occupied_rooms?.length || 0})
            </h3>
            {result.occupied_rooms?.length ? (
              <div className="space-y-1.5">
                {result.occupied_rooms.map(item => (
                  <div
                    key={`${item.room}-${item.course_code}`}
                    className="flex items-center justify-between gap-2 text-sm"
                  >
                    <Badge tone="danger" className="font-mono">
                      <DoorClosed size={12} strokeWidth={2} aria-hidden />
                      {normaliseRoom(item.room)}
                    </Badge>
                    <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                      {item.course_code} &middot; {formatTime(item.start_time)} -{' '}
                      {formatTime(item.end_time)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
                Nothing is scheduled.
              </p>
            )}
          </Card>
        </div>
      )}

      <Card>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
          All rooms ({allRooms.length})
        </h3>
        {allRooms.length ? (
          <div className="flex flex-wrap gap-2">
            {allRooms.map(room => (
              <Badge key={room} tone="neutral" className="font-mono">
                <Building2 size={12} strokeWidth={2} aria-hidden />
                {normaliseRoom(room)}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
            No rooms yet - upload the class timetable from the Live Schedule tab.
          </p>
        )}
      </Card>
    </div>
  );
}
