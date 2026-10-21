/**
 * Agent Runs List — Admin view of all agent pipeline runs.
 *
 * A run is a piece of work, not a row: the pipeline has eight stages and
 * the admin watches them go. So a live run carries a progress bar - the
 * stages it has finished out of the stages there are - and the list polls
 * while anything is still moving, because a progress bar that only updates
 * when the admin presses Refresh is not a progress bar.
 */
import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { oppfeedApi } from './api';
import { Badge, Button, Card, ProgressBar, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

interface RunRow {
  run_id: string;
  status: string;
  mode: string;
  started_at: string | null;
  completed_at: string | null;
  opportunities_found: number;
  opportunities_verified: number;
  opportunities_rejected: number;
  opportunities_drafted: number;
  opportunities_published: number;
  current_stage?: string | null;
  stages_completed?: number;
  total_stages?: number;
}

/**
 * Is this run still moving?
 *
 * A run that is running is moving. A run that is pending *and has started*
 * is moving too - it is a run that was created and has not reported yet. A
 * run that is pending and never started is not: it is a run the pipeline
 * never took up, and showing it as live would leave a bar that never moves.
 */
function isLive(run: RunRow): boolean {
  if (run.status === 'running') return true;
  return run.status === 'pending' && Boolean(run.started_at);
}

export default function AgentRunsList({ onError }: { onError?: (m: string) => void }) {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      try {
        const data = await oppfeedApi.listRuns({ page_size: 50 });
        setRuns(data || []);
        setError(null);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to load runs';
        setError(msg);
        onError?.(msg);
      } finally {
        setLoading(false);
      }
    },
    [onError]
  );

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // While a run is live, keep up with it. The pipeline takes minutes, and a
  // list that only refreshes on demand shows a run frozen at "pending"
  // for the whole of it.
  useEffect(() => {
    const live = runs.some(isLive);
    if (!live) return;
    const timer = setInterval(() => load(true), 3000);
    return () => clearInterval(timer);
  }, [runs, load]);

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading runs…
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          Agent Runs
        </h2>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={16} strokeWidth={2} aria-hidden />}
          onClick={() => load()}
        >
          Refresh
        </Button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {runs.length === 0 ? (
        <div className="p-3 text-center" style={{ color: 'var(--cp-muted)' }}>
          No runs yet.
        </div>
      ) : (
        <Card>
          <Table
            head={[
              'Run ID',
              'Status',
              'Mode',
              'Started',
              'Completed',
              'Found',
              'Verified',
              'Rejected',
              'Drafted',
              'Published',
            ]}
            rows={runs.map(r => [
              <span key="id" className="font-mono text-xs" style={{ color: 'var(--cp-text)' }}>
                {r.run_id}
              </span>,
              <Badge
                key="st"
                tone={
                  r.status === 'completed'
                    ? 'success'
                    : r.status === 'running'
                      ? 'warning'
                      : r.status === 'failed'
                        ? 'danger'
                        : 'neutral'
                }
              >
                {r.status}
              </Badge>,
              <span key="md" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {r.mode}
              </span>,
              <span key="stt" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {r.started_at ? new Date(r.started_at).toLocaleString() : '—'}
              </span>,
              <span key="ct" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {r.completed_at ? new Date(r.completed_at).toLocaleString() : '—'}
              </span>,
              <span key="fd" className="text-xs font-semibold" style={{ color: 'var(--cp-text)' }}>
                {r.opportunities_found}
              </span>,
              <span key="vd" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {r.opportunities_verified ?? '—'}
              </span>,
              <span key="rd" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {r.opportunities_rejected ?? '—'}
              </span>,
              <span key="dd" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {r.opportunities_drafted ?? '—'}
              </span>,
              <span
                key="pb"
                className="text-xs font-semibold"
                style={{ color: 'var(--cp-success)' }}
              >
                {r.opportunities_published}
              </span>,
            ])}
          />

          {/* The progress of every run that is still moving. */}
          {runs.some(isLive) && (
            <div className="mt-4 space-y-3">
              {runs.filter(isLive).map(r => {
                const total = r.total_stages ?? 0;
                const done = r.stages_completed ?? 0;
                return (
                  <div
                    key={r.run_id}
                    className="rounded-xl p-3"
                    style={{ background: 'var(--cp-surface)' }}
                  >
                    <div
                      className="flex items-center justify-between text-xs mb-2"
                      style={{ color: 'var(--cp-muted)' }}
                    >
                      <span className="font-mono">{r.run_id}</span>
                      <span>
                        {r.current_stage ? `${r.current_stage} · ` : ''}
                        {total ? `${done} of ${total} stages` : 'starting'}
                      </span>
                    </div>
                    <ProgressBar
                      value={done}
                      max={total || 1}
                      label={r.current_stage ?? undefined}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
