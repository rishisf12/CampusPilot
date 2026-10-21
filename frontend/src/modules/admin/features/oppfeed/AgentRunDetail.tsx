/**
 * Agent Run Detail — Admin view of a single run with step breakdown.
 */
import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { oppfeedApi } from './api';
import { Badge, Button, Card, ProgressBar, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function AgentRunDetail({
  runId,
  onError,
}: {
  runId: string;
  onError?: (m: string) => void;
}) {
  const [run, setRun] = useState<{
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
    errors: string[] | null;
    llm_calls: number;
    llm_tokens: number;
    current_stage: string | null;
    steps: Array<{
      step_name: string;
      status: string;
      started_at: string | null;
      completed_at: string | null;
      duration_ms: number | null;
      output_data: Record<string, unknown> | null;
      error_message: string | null;
      llm_provider: string | null;
      llm_model: string | null;
    }>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      try {
        const data = await oppfeedApi.getRun(runId);
        setRun(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load run');
        onError?.(err instanceof Error ? err.message : 'Failed to load run');
      } finally {
        setLoading(false);
      }
    },
    [runId, onError]
  );

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Follow a run that is still moving. The pipeline takes minutes, and a
  // detail screen that only refreshes on demand shows a run frozen at
  // "pending" for the whole of it.
  const live = run?.status === 'pending' || run?.status === 'running';
  useEffect(() => {
    if (!live) return;
    const timer = setInterval(() => load(true), 3000);
    return () => clearInterval(timer);
  }, [live, load]);

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading run…
      </Card>
    );
  }

  if (!run) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Run not found.
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          icon={<ArrowLeft size={16} strokeWidth={2} aria-hidden />}
          onClick={() => window.history.back()}
        >
          Back
        </Button>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          Run {run.run_id}
        </h2>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* The progress of the run */}
      {live && (
        <Card className="p-3">
          <ProgressBar
            value={run.steps.filter(s => s.status === 'completed').length}
            max={Math.max(run.steps.length, 1)}
            label={run.current_stage ?? 'starting'}
          />
        </Card>
      )}

      {/* Run summary */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              Status
            </p>
            <Badge
              tone={
                run.status === 'completed'
                  ? 'success'
                  : run.status === 'running'
                    ? 'warning'
                    : run.status === 'failed'
                      ? 'danger'
                      : 'neutral'
              }
            >
              {run.status}
            </Badge>
          </div>
          <div>
            <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              Mode
            </p>
            <span className="font-mono text-xs">{run.mode}</span>
          </div>
          <div>
            <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              Found
            </p>
            <span className="text-xs font-semibold">{run.opportunities_found}</span>
          </div>
          <div>
            <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              Published
            </p>
            <span className="text-xs font-semibold" style={{ color: 'var(--cp-success)' }}>
              {run.opportunities_published}
            </span>
          </div>
          <div>
            <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              LLM Calls
            </p>
            <span className="text-xs font-semibold">{run.llm_calls}</span>
          </div>
          <div>
            <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              Tokens
            </p>
            <span className="text-xs font-semibold">{run.llm_tokens}</span>
          </div>
        </div>
      </Card>

      {/* Steps */}
      <Card>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
          Pipeline Steps
        </h3>
        {run.steps.length === 0 ? (
          <div className="p-3 text-center" style={{ color: 'var(--cp-muted)' }}>
            No steps recorded.
          </div>
        ) : (
          <Table
            head={[
              'Step',
              'Status',
              'Started',
              'Completed',
              'Duration (ms)',
              'Provider',
              'Model',
              'Error',
            ]}
            rows={run.steps.map(s => [
              <span key="sn" className="text-xs font-semibold" style={{ color: 'var(--cp-text)' }}>
                {s.step_name}
              </span>,
              <Badge
                key="ss"
                tone={
                  s.status === 'completed'
                    ? 'success'
                    : s.status === 'running'
                      ? 'warning'
                      : s.status === 'failed'
                        ? 'danger'
                        : 'neutral'
                }
              >
                {s.status}
              </Badge>,
              <span key="ss2" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {s.started_at ? new Date(s.started_at).toLocaleString() : '—'}
              </span>,
              <span key="sc" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {s.completed_at ? new Date(s.completed_at).toLocaleString() : '—'}
              </span>,
              <span key="du" className="text-xs font-mono" style={{ color: 'var(--cp-muted)' }}>
                {s.duration_ms ?? '—'}
              </span>,
              <span key="lp" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {s.llm_provider ?? '—'}
              </span>,
              <span key="lm" className="text-xs font-mono" style={{ color: 'var(--cp-muted)' }}>
                {s.llm_model ?? '—'}
              </span>,
              <span key="er" className="text-xs" style={{ color: 'var(--cp-danger)' }}>
                {s.error_message ?? '—'}
              </span>,
            ])}
          />
        )}
      </Card>

      {run.errors && run.errors.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--cp-text)' }}>
            Errors
          </h3>
          <ul className="list-disc pl-4 text-xs space-y-1" style={{ color: 'var(--cp-danger)' }}>
            {run.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
