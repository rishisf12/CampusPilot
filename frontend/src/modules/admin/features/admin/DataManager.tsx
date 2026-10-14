import { useEffect, useState } from 'react';
import { timetableApi, examApi } from '@/api';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function DataManager({ onError }: { onError?: (m: string) => void }) {
  const [tt, setTt] = useState<{ available: boolean; filename?: string; rows?: number } | null>(
    null
  );
  const [status, setStatus] = useState<{ timetable_rows: number; seating_rows: number } | null>(
    null
  );
  const [ttOptions, setTtOptions] = useState<{ total_slots: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    try {
      const [a, b, c] = await Promise.all([
        timetableApi.latestUpload(),
        examApi.status(),
        timetableApi.options(),
      ]);
      setTt(a);
      setStatus(b as { timetable_rows: number; seating_rows: number });
      setTtOptions({ total_slots: (c as unknown as { total_slots: number }).total_slots });
      setError(null);
    } catch (err) {
      const m = err instanceof Error ? err.message : 'Failed to load data status';
      setError(m);
      onError?.(m);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const up = async (kind: 'timetable' | 'exam-tt' | 'exam-seat', file: File) => {
    setBusy(kind);
    setMsg(null);
    try {
      if (kind === 'timetable') await timetableApi.upload(file);
      if (kind === 'exam-tt') await examApi.uploadTimetable(file);
      if (kind === 'exam-seat') await examApi.uploadSeating(file);
      setMsg('Upload parsed successfully.');
      await load();
    } catch (err) {
      const m = err instanceof Error ? err.message : 'Upload failed';
      setError(m);
    } finally {
      setBusy(null);
    }
  };

  const clear = async (kind: 'timetable' | 'exam-tt' | 'exam-seat') => {
    if (!confirm(`Delete ${kind}? This wipes the stored rows.`)) return;
    setBusy(kind);
    try {
      if (kind === 'timetable') await timetableApi.clear();
      if (kind === 'exam-tt') await examApi.clearTimetable();
      if (kind === 'exam-seat') await examApi.clearSeating();
      setMsg('Deleted.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setBusy(null);
    }
  };

  const Row = ({
    title,
    sub,
    kind,
    accept,
  }: {
    title: string;
    sub: string;
    kind: 'timetable' | 'exam-tt' | 'exam-seat';
    accept: string;
  }) => (
    <div className="card p-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-sm font-medium text-gray-900">{title}</p>
        <p className="text-xs text-gray-500">{sub}</p>
      </div>
      <div className="flex items-center gap-2">
        <label className="btn-primary text-sm cursor-pointer">
          {busy === kind ? 'Working…' : 'Upload'}
          <input
            type="file"
            accept={accept}
            className="hidden"
            disabled={busy !== null}
            onChange={e => {
              const f = e.target.files?.[0];
              e.target.value = '';
              if (f) up(kind, f);
            }}
          />
        </label>
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => clear(kind)}
          className="btn-ghost text-sm disabled:opacity-50"
        >
          Delete
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900">Data</h2>
        <p className="text-sm text-gray-600 mt-1">
          Timetable slots: {ttOptions?.total_slots ?? '—'}
          {' · '}Exam rows: {status ? `${status.timetable_rows}/${status.seating_rows}` : '—'}
          {' · '}Latest timetable file: {tt?.available ? tt.filename : 'none'}
        </p>
      </div>
      {msg && (
        <div className="rounded-xl border border-success-200 bg-success-50 px-4 py-3 text-xs text-success-800">
          {msg}
        </div>
      )}
      <ErrorBanner message={error} onDismiss={() => setError(null)} />
      <Row
        title="Master timetable"
        sub="PDF/CSV/Excel — replaces all slots"
        kind="timetable"
        accept=".pdf,.csv,.xlsx"
      />
      <Row title="Exam timetable (midsem)" sub="PDF/CSV" kind="exam-tt" accept=".pdf,.csv" />
      <Row title="Exam seating index" sub="PDF/CSV" kind="exam-seat" accept=".pdf,.csv" />
    </div>
  );
}
