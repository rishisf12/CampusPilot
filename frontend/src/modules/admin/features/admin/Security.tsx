import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { adminApi } from '@/api';
import { Card, Badge, Table, Button } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function Security({ onError }: { onError?: (m: string) => void }) {
  const [events, setEvents] = useState<
    Array<{
      type: string;
      severity: string;
      actor_email: string | null;
      actor_id: number | null;
      details: string | null;
      ip_hash: string | null;
      created_at: string;
    }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.securityEvents();
      setEvents(data.events || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      onError?.(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading)
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading security feed…
      </Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Security Events</h2>
        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={16} strokeWidth={2} />}
          onClick={load}
        >
          Refresh
        </Button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <Card>
        <Table
          head={['Time', 'Type', 'Severity', 'Actor', 'Details', 'IP']}
          rows={events.map(e => [
            <span key="t">{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</span>,
            <Badge
              key="ty"
              tone={
                e.type === 'failed_login'
                  ? 'danger'
                  : e.type === 'brute_force'
                    ? 'warning'
                    : 'neutral'
              }
            >
              {e.type}
            </Badge>,
            <Badge
              key="sev"
              tone={
                e.severity === 'critical'
                  ? 'danger'
                  : e.severity === 'high'
                    ? 'warning'
                    : e.severity === 'medium'
                      ? 'neutral'
                      : 'success'
              }
            >
              {e.severity === 'critical'
                ? 'Critical'
                : e.severity === 'high'
                  ? 'High'
                  : e.severity === 'medium'
                    ? 'Medium'
                    : 'Low'}
            </Badge>,
            <span key="a">{e.actor_email || e.actor_id || 'System'}</span>,
            <span key="d" className="truncate max-w-[300px]">
              {e.details || ''}
            </span>,
            <code key="ip" className="text-xs">
              {e.ip_hash ? e.ip_hash.slice(0, 16) + '…' : '—'}
            </code>,
          ])}
        />
      </Card>
    </div>
  );
}
