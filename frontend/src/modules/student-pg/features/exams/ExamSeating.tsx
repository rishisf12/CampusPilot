import { useCallback, useEffect, useMemo, useState, FormEvent } from 'react';
import { CalendarDays, CheckCircle2, RefreshCw, Search, Trash2 } from 'lucide-react';
import { Badge, Button, Card, Input, Select, Table, Tabs } from '@/components/ui';
import { authApi, examApi } from '@/api';
import { BRANCH_OPTIONS } from '@shared/constants';
import { formatDate, formatTime, todayIso } from '@shared/lib/time';
import { normaliseRoom, splitCourseCodes } from '@shared/lib/normalise';
import { readQuickLookup, writeQuickLookup } from '@shared/lib/storage';
import { useSettings } from '@shared/features/settings/SettingsProvider';
import { bumpProfileVersion } from '@shared/lib/storage';
import useProfileVersion from '@shared/hooks/useProfileVersion';
import ErrorBanner from '@shared/components/ErrorBanner';
import FileUpload from '@shared/components/FileUpload';
import Spinner from '@shared/components/Spinner';
import UploadPreview from '@shared/components/UploadPreview';

const SUB_TABS = [
  { id: 'timetable', label: 'Exam Timetable' },
  { id: 'seating', label: 'Exam Seating Index' },
] as const;

const PREVIEW_ROWS = 20;

interface ExamDay {
  date?: string;
  day?: string | null;
  exams: ExamRow[];
}

interface ExamRow {
  id?: number | string;
  course_code: string;
  /** The instructor who teaches this student the course, joined from the
      class timetable; missing when the timetable doesn't know. */
  instructor?: string | null;
  semester?: number | string;
  branch?: string;
  date?: string;
  schedule_date?: string;
  day?: string | null;
  room?: string;
  start_time?: string;
  end_time?: string;
}

interface ExamTimetable {
  days?: ExamDay[];
  profile?: { semester?: number | string; branch?: string } | null;
}

interface ExamSeatingDay {
  date: string;
  day?: string | null;
  rooms: SeatingRow[];
}

interface SeatingRow {
  id?: number | string;
  room?: string;
  course_code?: string;
  semester?: number | string;
  branch?: string;
  start_time?: string;
  end_time?: string;
  roll_start_prefix?: string;
  roll_start_num?: number;
  roll_end_num?: number;
}

interface ExamSeating {
  days?: ExamSeatingDay[];
  total?: number;
  profile?: { semester?: number | string; branch?: string } | null;
}

interface LookupResult {
  roll: string;
  exams: ExamRow[];
  profileFiltered: boolean;
  profile: { semester?: number | string; branch?: string } | null;
}

interface ExamSeatingProps {
  onError?: (message: string) => void;
}

export default function ExamSeating({ onError }: ExamSeatingProps) {
  const [subTab, setSubTab] = useState('timetable');
  const [status, setStatus] = useState({ timetable_rows: 0, seating_rows: 0 });
  const [timetable, setTimetable] = useState<ExamTimetable | null>(null);
  const [seating, setSeating] = useState<ExamSeating | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [showAll, setShowAll] = useState({ timetable: false, seating: false });

  // Quick roll lookup
  const [roll, setRoll] = useState('');
  const [lookup, setLookup] = useState<LookupResult | null>(null);
  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const profileVersion = useProfileVersion();
  // Privacy & Data > "Remember my exam lookup".
  const rememberLookup = useSettings().get('remember_exam_lookup') !== false;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statusData, timetableData] = await Promise.all([
        examApi.status(),
        examApi.getTimetable(),
      ]);
      setStatus(statusData);
      setTimetable(timetableData);
      setError(null);
    } catch (err) {
      // Keep the last good data: a failed refresh must not blank the exam views.
      const msg = err instanceof Error ? err.message : 'Failed to load exam data';
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  // Refetch on mount and whenever the profile changes, in this tab or another.
  useEffect(() => {
    load();
  }, [load, profileVersion]);

  /**
   * Prefill the roll, and restore the last lookup.
   *
   * The saved result is restored so a refresh does not lose it, but it is
   * re-fetched on the next search, never treated as current data.
   */
  useEffect(() => {
    const saved = readQuickLookup();
    if (saved) {
      setLookup(saved);
      setRoll(saved.roll);
      return;
    }
    // No cached lookup: /auth/me is the source for the roll number.
    let cancelled = false;
    (async () => {
      try {
        const user = await authApi.me();
        if (!cancelled && user?.roll_number) setRoll(user.roll_number);
      } catch {
        /* the user can type a roll manually */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadSeating = async () => {
    try {
      setSeating(await examApi.getSeating());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load seating');
    }
  };

  useEffect(() => {
    if (subTab === 'seating' && !seating) loadSeating();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab]);

  /**
   * The papers as the profile gave them, one row per code.
   *
   * The backend narrows the list to the profile's synced subjects, so there is
   * no semester or branch menu here to fight it: a paper the student does not
   * sit is not in the payload at all. A paired cell ("OE3M27/ME5D02") still
   * counts as two papers rather than one.
   */
  const visibleDays = useMemo(() => {
    if (!timetable?.days) return [];

    return timetable.days
      .map(day => ({
        ...day,
        exams: day.exams
          // A paired cell is two papers.
          .flatMap(exam =>
            splitCourseCodes(exam.course_code).map(code => ({ ...exam, course_code: code }))
          ),
      }))
      .filter(day => day.exams.length > 0);
  }, [timetable]);

  const runLookup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!roll.trim()) return;
    setLooking(true);
    setLookupError(null);
    try {
      const data = await examApi.lookup(roll.trim().toUpperCase());
      // Drop duplicate rooms for the same course/date, and split paired codes.
      const seen = new Set<string>();
      const exams = (data.exams || [])
        .flatMap((exam: ExamRow) =>
          splitCourseCodes(exam.course_code).map(code => ({ ...exam, course_code: code }))
        )
        .filter((exam: ExamRow) => {
          const key = `${exam.course_code}|${exam.date}|${normaliseRoom(exam.room)}`;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
      const result: LookupResult = {
        roll: data.roll,
        exams,
        // True when the backend narrowed the list to the signed-in profile.
        profileFiltered: Boolean(data.profile_filter_applied),
        profile: timetable?.profile || null,
      };
      setLookup(result);
      // Cached so a refresh can restore it; the server remains the source.
      // Skipped when the student has turned the cache off in Privacy & Data.
      if (rememberLookup) writeQuickLookup(result);
    } catch (err) {
      setLookupError(err instanceof Error ? err.message : 'Lookup failed');
      setLookup(null);
    } finally {
      setLooking(false);
    }
  };

  const removeData = async (kind: 'timetable' | 'seating') => {
    const label = kind === 'timetable' ? 'exam timetable' : 'seating index';
    if (!window.confirm(`Remove the uploaded ${label}?`)) return;
    try {
      if (kind === 'timetable') {
        await examApi.clearTimetable().catch(() => null);
        setMessage('Exam timetable removed');
      } else {
        await examApi.clearSeating().catch(() => null);
        setMessage('Seating index removed');
      }
      await load();
      if (kind === 'seating') setSeating(null);
      // Tell the other tabs this section's data changed.
      bumpProfileVersion();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove data');
    }
  };

  const today = todayIso();

  return (
    <div className="space-y-5">
      {/* Quick Roll Lookup - small and centred */}
      <Card className="max-w-xl mx-auto">
        <h3 className="text-sm font-semibold text-center" style={{ color: 'var(--cp-text)' }}>
          Quick Roll Lookup
        </h3>
        <form onSubmit={runLookup} className="mt-3 flex gap-2">
          <Input
            id="exam-roll"
            className="font-mono flex-1"
            value={roll}
            onChange={event => {
              setRoll(event.target.value.toUpperCase());
              setLookupError(null);
            }}
            placeholder="e.g. 23BCS125"
          />
          <Button
            type="submit"
            variant="primary"
            size="sm"
            icon={<Search size={16} strokeWidth={2} />}
            loading={looking}
            disabled={looking || !roll.trim()}
            className="shrink-0"
          >
            Find Room
          </Button>
        </form>

        {lookupError && (
          <div className="mt-3">
            <ErrorBanner message={lookupError} onDismiss={() => setLookupError(null)} />
          </div>
        )}

        {lookup && lookup.exams.length === 0 && (
          <p className="mt-3 text-sm text-center" style={{ color: 'var(--cp-muted)' }}>
            No exam found for <span className="font-mono">{lookup.roll}</span>.
          </p>
        )}

        {lookup && lookup.exams.length > 0 && (
          <>
            {lookup.profileFiltered && (
              <p className="mt-3 text-xs text-center" style={{ color: 'var(--cp-muted)' }}>
                Filtered to your profile
                {lookup.profile
                  ? ` (${lookup.profile.branch} · Sem ${lookup.profile.semester})`
                  : ''}
                .
              </p>
            )}
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
              {lookup.exams.map((exam, index) => {
                const isToday = exam.date === today;
                return (
                  <div
                    key={`${exam.course_code}-${exam.date}-${exam.room}-${index}`}
                    className="neu-raised-sm p-3"
                    style={isToday ? { borderColor: 'var(--cp-primary)' } : undefined}
                  >
                    {isToday && (
                      <Badge tone="primary" className="mb-1 text-[10px] font-bold">
                        <CalendarDays size={10} strokeWidth={2} aria-hidden />
                        TODAY
                      </Badge>
                    )}
                    <p
                      className="text-sm font-mono font-semibold"
                      style={{ color: 'var(--cp-text)' }}
                    >
                      {exam.course_code}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--cp-text)' }}>
                      Room{' '}
                      <span className="font-mono" style={{ color: 'var(--cp-primary)' }}>
                        {exam.room || '—'}
                      </span>
                    </p>
                    <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                      {formatDate(exam.date)}
                      {exam.day ? ` (${exam.day})` : ''}
                      {exam.start_time
                        ? ` · ${formatTime(exam.start_time)}-${formatTime(exam.end_time)}`
                        : ''}
                    </p>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </Card>

      {message && (
        <div className="p-3 rounded-lg border border-success-200 bg-success-50 text-success-700 text-sm">
          {message}
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Upload cards, always on a single horizontal row */}
      <div className="flex flex-nowrap gap-4 overflow-x-auto">
        <ExamUploadCard
          title="Exam Timetable"
          kind="timetable"
          count={status.timetable_rows}
          busyLabel="Parsing exam timetable"
          onUpload={async file => {
            const result = await examApi.uploadTimetable(file);
            await load();
            bumpProfileVersion();
            return result;
          }}
          onRemove={() => removeData('timetable')}
        />
        <ExamUploadCard
          title="Exam Seating Index"
          kind="seating"
          count={status.seating_rows}
          busyLabel="Parsing seating index"
          onUpload={async file => {
            const result = await examApi.uploadSeating(file);
            await load();
            bumpProfileVersion();
            if (subTab === 'seating') setSeating(null);
            return result;
          }}
          onRemove={() => removeData('seating')}
        />
      </div>

      {/* Views */}
      <Tabs
        tabs={SUB_TABS.map(item => ({ id: item.id, label: item.label }))}
        active={subTab}
        onChange={id => setSubTab(id)}
      />

      {loading && !timetable && (
        <div className="flex justify-center py-10">
          <Spinner size={24} className="text-primary-500" />
        </div>
      )}

      {subTab === 'timetable' && <TimetableView days={visibleDays} total={status.timetable_rows} />}

      {subTab === 'seating' && (
        <SeatingView
          data={seating}
          showAll={showAll.seating}
          setShowAll={value => setShowAll(prev => ({ ...prev, seating: value }))}
          onLoad={loadSeating}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Upload card, with a preview of the latest file uploaded to it        */
/* ------------------------------------------------------------------ */

interface ExamUploadCardProps {
  title: string;
  kind: 'timetable' | 'seating';
  count: number;
  busyLabel?: string;
  onUpload: (file: File) => Promise<unknown>;
  onRemove: () => void;
}

/**
 * A card for one exam section's upload, showing what is currently stored and
 * previewing the PDF that produced it.
 */
function ExamUploadCard({ title, kind, count, onUpload, onRemove }: ExamUploadCardProps) {
  // Stable identities, so UploadPreview does not re-fetch on every render.
  const fetchLatest = useCallback(() => examApi.latestUpload(kind), [kind]);
  const loadObjectUrl = useCallback(() => examApi.previewObjectUrl(kind), [kind]);

  return (
    <div className="max-w-[calc(50%-0.5rem)] shrink-0">
      <FileUpload label={title} accept=".pdf,.csv" onUpload={onUpload}>
        {count > 0 && (
          <div
            className="mt-3 pt-3 border-t space-y-2"
            style={{ borderColor: 'rgba(163,177,198,.3)' }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium" style={{ color: 'var(--cp-text)' }}>
                Uploaded ({count} entries)
              </span>
              <Button
                type="button"
                onClick={onRemove}
                variant="ghost"
                size="sm"
                icon={<Trash2 size={14} strokeWidth={2} />}
              >
                Remove
              </Button>
            </div>

            <UploadPreview
              refreshKey={count}
              fetchLatest={fetchLatest}
              loadObjectUrl={loadObjectUrl}
              rowClassName="flex items-center justify-between gap-2"
              emptyHint="No preview available - upload the file again to preview it."
            />
          </div>
        )}
      </FileUpload>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Exam timetable view                                                  */
/* ------------------------------------------------------------------ */

interface TimetableViewProps {
  days: ExamDay[];
  total?: number;
}

function TimetableView({ days, total }: TimetableViewProps) {
  if (!total) {
    return (
      <Card className="text-center py-10 text-sm" style={{ color: 'var(--cp-muted)' }}>
        No exam timetable uploaded yet. Add the exam timetable PDF above.
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {days.length === 0 ? (
        <Card className="text-center py-8 text-sm" style={{ color: 'var(--cp-muted)' }}>
          None of the papers in this index are courses your profile lists.
        </Card>
      ) : (
        days.map((day, index) => (
          <div key={day.date || index} className="space-y-2">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
              Day-{index + 1} {day.day || formatDate(day.date)}
            </h3>
            <Table
              head={['Date', 'Time', 'Course Code', 'Instructor']}
              rows={day.exams.map(exam => [
                <span key="date" className="whitespace-nowrap" style={{ color: 'var(--cp-text)' }}>
                  {formatDate(exam.schedule_date)}
                </span>,
                <span key="time" className="whitespace-nowrap" style={{ color: 'var(--cp-muted)' }}>
                  {formatTime(exam.start_time)} - {formatTime(exam.end_time)}
                </span>,
                <span key="code" className="font-mono" style={{ color: 'var(--cp-text)' }}>
                  {exam.course_code}
                </span>,
                <span key="instructor" style={{ color: 'var(--cp-muted)' }}>
                  {exam.instructor || '—'}
                </span>,
              ])}
            />
          </div>
        ))
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Seating index view                                                   */
/* ------------------------------------------------------------------ */

/**
 * Does a row's branch satisfy the chosen filter?
 *
 * Matched on the leading word so the dropdown's programme-level choices line up
 * with the index's section-level labels in both directions: `DS` matches the
 * `DS A`/`DS B` rows, and `CSE A` matches `CSE B`, because a student in one CSE
 * section genuinely appears in the index rows of both. Rows with no recorded
 * branch stay visible instead of silently disappearing.
 */
function branchMatches(rowBranch: string | undefined, selected: string): boolean {
  if (!selected || !rowBranch) return true;
  return rowBranch === selected || rowBranch.split(' ')[0] === selected.split(' ')[0];
}

interface SeatingViewProps {
  data: ExamSeating | null;
  showAll: boolean;
  setShowAll: (value: boolean) => void;
  onLoad: () => void;
}

function SeatingView({ data, showAll, setShowAll, onLoad }: SeatingViewProps) {
  const [semester, setSemester] = useState('');
  const [branch, setBranch] = useState('');

  const allRows = useMemo(
    () =>
      data?.days
        ? data.days.flatMap(day =>
            day.rooms.map(room => ({ ...room, date: day.date, day: day.day }))
          )
        : [],
    [data]
  );

  // Start from the profile, exactly as the exam timetable does.
  useEffect(() => {
    setSemester(current => current || String(data?.profile?.semester ?? ''));
    setBranch(current => current || data?.profile?.branch || '');
  }, [data]);

  /** Client-side semester/branch narrowing of the returned rows. */
  const rows = useMemo(
    () =>
      allRows.filter(
        room =>
          (!semester || String(room.semester ?? '') === semester) &&
          (!branch || branchMatches(room.branch, branch))
      ),
    [allRows, semester, branch]
  );

  const hiddenCount = allRows.length - rows.length;
  const isSynced =
    String(data?.profile?.semester) === semester && (data?.profile?.branch || '') === branch;

  if (!data) {
    return (
      <Card className="text-center py-10 text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading seating index…
      </Card>
    );
  }
  if (!data.total) {
    return (
      <Card className="text-center py-10 text-sm" style={{ color: 'var(--cp-muted)' }}>
        No seating index uploaded yet. Add the seating index PDF above.
      </Card>
    );
  }

  const visible = showAll ? rows : rows.slice(0, PREVIEW_ROWS);

  return (
    <div className="space-y-3">
      <Card className="flex flex-wrap items-end gap-3">
        <div>
          <span className="label">Semester</span>
          <Select
            id="seating-semester"
            className="w-32"
            value={semester}
            onChange={event => setSemester(event.target.value)}
          >
            <option value="">All</option>
            {[1, 2, 3, 4, 5, 6, 7, 8].map(value => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <span className="label">Branch</span>
          <Select
            id="seating-branch"
            className="w-40"
            value={branch}
            onChange={event => setBranch(event.target.value)}
          >
            <option value="">All</option>
            {BRANCH_OPTIONS.map(item => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
        </div>
        {isSynced && (
          <Badge tone="success">
            <CheckCircle2 size={12} strokeWidth={2} aria-hidden />
            Synced with profile
          </Badge>
        )}
        {hiddenCount > 0 && (
          <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            {hiddenCount} row{hiddenCount === 1 ? '' : 's'} hidden by these filters.
          </span>
        )}
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          {rows.length} entries
        </span>
        {rows.length > PREVIEW_ROWS && (
          <Button
            type="button"
            onClick={() => setShowAll(!showAll)}
            variant="ghost"
            size="sm"
            className="ml-auto"
          >
            {showAll ? 'Show less' : `Show All (${rows.length})`}
          </Button>
        )}
        <Button
          type="button"
          onClick={onLoad}
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={14} strokeWidth={2} />}
        >
          Refresh
        </Button>
      </div>

      {rows.length === 0 ? (
        <Card className="text-center py-8 text-sm" style={{ color: 'var(--cp-muted)' }}>
          Nothing matches these filters.
        </Card>
      ) : (
        <Table
          head={['Date', 'Time', 'Lecture Hall', 'Course Code', 'Roll Numbers']}
          rows={visible.map(room => [
            <span key="date" className="whitespace-nowrap" style={{ color: 'var(--cp-text)' }}>
              {formatDate(room.date)}
            </span>,
            <span key="time" className="whitespace-nowrap" style={{ color: 'var(--cp-muted)' }}>
              {formatTime(room.start_time)} - {formatTime(room.end_time)}
            </span>,
            <span key="room" className="font-mono" style={{ color: 'var(--cp-primary)' }}>
              {room.room || '—'}
            </span>,
            <span key="code" className="font-mono" style={{ color: 'var(--cp-text)' }}>
              {room.course_code}
            </span>,
            <span key="rolls" className="font-mono text-xs" style={{ color: 'var(--cp-muted)' }}>
              {room.roll_start_prefix}
              {String(room.roll_start_num).padStart(3, '0')}
              {room.roll_start_num === room.roll_end_num
                ? ''
                : ` - ${room.roll_start_prefix}${String(room.roll_end_num).padStart(3, '0')}`}
            </span>,
          ])}
        />
      )}
    </div>
  );
}
