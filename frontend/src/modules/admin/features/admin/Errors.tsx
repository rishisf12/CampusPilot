import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { adminApi } from '@/api';
import { Card, Badge, Table, Button } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function Errors({ onError }: { onError?: (m: string) => void }) {
  const [errors, setErrors] = useState<
    Array<{
      fingerprint: string;
      message: string;
      status: string;
      count: number;
      first_seen: string;
      last_seen: string;
      assignee: string | null;
    }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await adminApi.errors();
      setErrors(data.errors || []);
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
        Loading errors…
      </Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Error Tracking</h2>
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
          head={[
            'Fingerprint',
            'Message',
            'Status',
            'Count',
            'First Seen',
            'Last Seen',
            'Assignee',
          ]}
          rows={errors.map(e => [
            <code key="f" className="text-xs">
              {e.fingerprint}
            </code>,
            <span key="m" className="truncate max-w-[300px]">
              {e.message}
            </span>,
            <Badge
              key="s"
              tone={
                e.status === 'resolved'
                  ? 'success'
                  : e.status === 'investigating'
                    ? 'warning'
                    : e.status === 'ignored'
                      ? 'neutral'
                      : 'danger'
              }
            >
              {e.status}
            </Badge>,
            <span key="c">{e.count}</span>,
            <span key="fs">{e.first_seen ? new Date(e.first_seen).toLocaleString() : '—'}</span>,
            <span key="ls">{e.last_seen ? new Date(e.last_seen).toLocaleString() : '—'}</span>,
            <span key="a">{e.assignee || 'Unassigned'}</span>,
          ])}
        />
      </Card>
    </div>
  );
}
