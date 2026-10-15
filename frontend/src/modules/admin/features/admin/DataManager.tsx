import { useEffect, useState } from 'react';
import { Trash2, Upload } from 'lucide-react';
import { timetableApi, examApi } from '@/api';
import { Button, Card } from '@/components/ui';
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
    <Card className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--cp-text)' }}>
          {title}
        </p>
        <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          {sub}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="primary"
          size="sm"
          icon={<Upload size={16} strokeWidth={2} aria-hidden />}
          loading={busy === kind}
          disabled={busy !== null}
          onClick={() => document.getElementById(`upload-${kind}`)?.click()}
        >
          Upload
        </Button>
        <input
          id={`upload-${kind}`}
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
        <Button
          type="button"
          variant="danger"
          size="sm"
          icon={<Trash2 size={16} strokeWidth={2} aria-hidden />}
          disabled={busy !== null}
          onClick={() => clear(kind)}
        >
          Delete
        </Button>
      </div>
    </Card>
  );

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          Data
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }} aria-live="polite">
          Timetable slots: {ttOptions?.total_slots ?? '—'}
          {' · '}Exam rows: {status ? `${status.timetable_rows}/${status.seating_rows}` : '—'}
          {' · '}Latest timetable file: {tt?.available ? tt.filename : 'none'}
        </p>
      </Card>
      {msg && (
        <div
          className="px-4 py-3 text-xs"
          style={{
            borderRadius: 12,
            border: '1px solid rgba(163,177,198,.3)',
            background: 'var(--cp-bg)',
            boxShadow: 'var(--cp-neu-inset)',
            color: 'var(--cp-success)',
          }}
          aria-live="polite"
        >
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
