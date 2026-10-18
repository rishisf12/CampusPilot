/**
 * OppFeed Dashboard — Admin overview.
 *
 * Shows run stats, recent opportunities, and quick actions for the agent.
 * Read-only data with one action: trigger a manual run.
 */
import { useCallback, useEffect, useState } from 'react';
import { Play } from 'lucide-react';
import { oppfeedApi } from './api';
import { Card, Badge, Button, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function OppFeedDashboard({ onError }: { onError?: (m: string) => void }) {
  const [runs, setRuns] = useState<
    Array<{
      run_id: string;
      status: string;
      mode: string;
      started_at: string | null;
      opportunities_found: number;
      opportunities_published: number;
    }>
  >([]);
  const [settings, setSettings] = useState<{
    auto_publish_enabled: boolean;
    auto_publish_threshold: number;
    llm_provider_chain: string;
    enable_agent: boolean;
    enable_scheduler: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [runsData, settingsData] = await Promise.all([
        oppfeedApi.listRuns({ page_size: 10 }),
        oppfeedApi.getSettings(),
      ]);
      setRuns(runsData || []);
      setSettings(settingsData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load OppFeed dashboard');
      onError?.(err instanceof Error ? err.message : 'Failed to load OppFeed dashboard');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const triggerRun = async () => {
    try {
      await oppfeedApi.createRun({ mode: 'manual' });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger run');
      onError?.(err instanceof Error ? err.message : 'Failed to trigger run');
    }
  };

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading OppFeed dashboard…
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          OppFeed Dashboard
        </h2>
        <Button
          type="button"
          variant="primary"
          size="sm"
          icon={<Play size={16} strokeWidth={2} aria-hidden />}
          onClick={triggerRun}
        >
          Trigger Run
        </Button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="p-3">
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Total Runs
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
            {runs.length}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Published
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--cp-success)' }}>
            {runs.reduce((sum, r) => sum + r.opportunities_published, 0)}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Auto-Publish
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
            {settings?.auto_publish_enabled ? 'On' : 'Off'}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Scheduler
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
            {settings?.enable_scheduler ? 'On' : 'Off'}
          </p>
        </Card>
      </div>

      {/* Settings summary */}
      {settings && (
        <Card className="p-3">
          <p className="text-xs font-semibold mb-2" style={{ color: 'var(--cp-muted)' }}>
            Agent Settings
          </p>
          <div className="flex items-center justify-between gap-2 text-sm">
            <span style={{ color: 'var(--cp-muted)' }}>LLM Chain</span>
            <span className="font-mono text-xs" style={{ color: 'var(--cp-text)' }}>
              {settings.llm_provider_chain}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2 text-sm mt-1">
            <span style={{ color: 'var(--cp-muted)' }}>Threshold</span>
            <Badge tone="neutral">{settings.auto_publish_threshold}</Badge>
          </div>
        </Card>
      )}

      {/* Recent runs */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
            Recent Runs
          </h3>
        </div>
        {runs.length === 0 ? (
          <div className="p-3 text-center" style={{ color: 'var(--cp-muted)' }}>
            No runs yet. Trigger a run to start discovering opportunities.
          </div>
        ) : (
          <Table
            head={['Run ID', 'Status', 'Mode', 'Started', 'Found', 'Published']}
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
              <span key="fd" className="text-xs font-semibold" style={{ color: 'var(--cp-text)' }}>
                {r.opportunities_found}
              </span>,
              <span key="pb" className="text-xs" style={{ color: 'var(--cp-success)' }}>
                {r.opportunities_published}
              </span>,
            ])}
          />
        )}
      </Card>
    </div>
  );
}
