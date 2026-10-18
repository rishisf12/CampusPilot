/**
 * Agent Runs List — Admin view of all agent pipeline runs.
 */
import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { oppfeedApi } from './api';
import { Badge, Button, Card, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function AgentRunsList({ onError }: { onError?: (m: string) => void }) {
  const [runs, setRuns] = useState<
    Array<{
      run_id: string;
      status: string;
      mode: string;
      started_at: string | null;
      completed_at: string | null;
      opportunities_found: number;
      opportunities_published: number;
    }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await oppfeedApi.listRuns({ page_size: 50 });
      setRuns(data || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load runs');
      onError?.(err instanceof Error ? err.message : 'Failed to load runs');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          onClick={load}
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
                —
              </span>,
              <span key="rd" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                —
              </span>,
              <span key="dd" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                —
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
        </Card>
      )}
    </div>
  );
}
