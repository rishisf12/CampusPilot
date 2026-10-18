/**
 * LLM Status — Admin view of LLM provider health.
 */
import { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { oppfeedApi } from './api';
import { Badge, Button, Card, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function LLMStatus({ onError }: { onError?: (m: string) => void }) {
  const [status, setStatus] = useState<{
    providers: Array<{
      provider: string;
      status: string;
      model: string;
      latency_ms: number | null;
      last_checked: string | null;
      error: string | null;
      rate_limit_remaining: number | null;
      rate_limit_total: number | null;
    }>;
    active_provider: string;
    cache_hit_rate: number;
    total_calls_today: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await oppfeedApi.llmStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load LLM status');
      onError?.(err instanceof Error ? err.message : 'Failed to load LLM status');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading LLM status…
      </Card>
    );
  }

  if (!status) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        No LLM status available.
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
          LLM Provider Status
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

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card className="p-3">
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Active Provider
          </p>
          <p className="text-lg font-semibold font-mono" style={{ color: 'var(--cp-text)' }}>
            {status.active_provider}
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Cache Hit Rate
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
            {(status.cache_hit_rate * 100).toFixed(1)}%
          </p>
        </Card>
        <Card className="p-3">
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            Calls Today
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
            {status.total_calls_today}
          </p>
        </Card>
      </div>

      <Card>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--cp-text)' }}>
          Providers
        </h3>
        {status.providers.length === 0 ? (
          <div className="p-3 text-center" style={{ color: 'var(--cp-muted)' }}>
            No providers configured.
          </div>
        ) : (
          <Table
            head={['Provider', 'Status', 'Model', 'Latency', 'Rate Limit', 'Last Checked', 'Error']}
            rows={status.providers.map(p => [
              <span key="pr" className="text-xs font-mono" style={{ color: 'var(--cp-text)' }}>
                {p.provider}
              </span>,
              <Badge
                key="st"
                tone={
                  p.status === 'healthy'
                    ? 'success'
                    : p.status === 'degraded'
                      ? 'warning'
                      : 'danger'
                }
              >
                {p.status}
              </Badge>,
              <span key="md" className="text-xs font-mono" style={{ color: 'var(--cp-muted)' }}>
                {p.model}
              </span>,
              <span key="lt" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {p.latency_ms ?? '—'} ms
              </span>,
              <span key="rl" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {p.rate_limit_remaining ?? '—'}/{p.rate_limit_total ?? '—'}
              </span>,
              <span key="lc" className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {p.last_checked ? new Date(p.last_checked).toLocaleString() : '—'}
              </span>,
              <span key="er" className="text-xs" style={{ color: 'var(--cp-danger)' }}>
                {p.error ?? '—'}
              </span>,
            ])}
          />
        )}
      </Card>
    </div>
  );
}
