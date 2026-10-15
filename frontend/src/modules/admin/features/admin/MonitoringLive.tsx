import { useEffect, useState } from 'react';
import { Activity, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { monitoringApi } from '@/api';
import { Card, Badge } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function MonitoringLive({ onError }: { onError?: (m: string) => void }) {
  const [overview, setOverview] = useState<{
    database?: { status?: string };
    cpu?: { usage_percent?: number };
    memory?: { usage_percent?: number };
    disk?: { usage_percent?: number };
  } | null>(null);
  const [health, setHealth] = useState<{
    components?: Array<{ name: string; status: string }>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [o, h] = await Promise.all([monitoringApi.overview(), monitoringApi.health()]);
      setOverview(
        o as {
          database?: { status?: string };
          cpu?: { usage_percent?: number };
          memory?: { usage_percent?: number };
          disk?: { usage_percent?: number };
        }
      );
      setHealth(
        h as {
          components?: Array<{ name: string; status: string }>;
        }
      );
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
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading)
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading monitoring…
      </Card>
    );

  const statusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle size={16} className="text-green-500" />;
      case 'warning':
        return <AlertTriangle size={16} className="text-yellow-500" />;
      case 'critical':
        return <XCircle size={16} className="text-red-500" />;
      default:
        return <Activity size={16} className="text-gray-500" />;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Monitoring Live</h2>
        <span className="text-xs text-green-500 flex items-center gap-1">
          <Activity size={12} /> Auto-refresh 30s
        </span>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <h3 className="text-sm font-medium text-gray-500">Database</h3>
          <p className="text-2xl font-bold">{overview?.database?.status || '—'}</p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500">CPU</h3>
          <p className="text-2xl font-bold">{overview?.cpu?.usage_percent?.toFixed(1) || '—'}%</p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500">Memory</h3>
          <p className="text-2xl font-bold">
            {overview?.memory?.usage_percent?.toFixed(1) || '—'}%
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500">Disk</h3>
          <p className="text-2xl font-bold">{overview?.disk?.usage_percent?.toFixed(1) || '—'}%</p>
        </Card>
      </div>

      <Card className="mt-4">
        <h3 className="text-lg font-semibold mb-4">Component Health</h3>
        <div className="space-y-2">
          {health?.components?.map((c: { name: string; status: string }) => (
            <div
              key={c.name}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
            >
              <div className="flex items-center gap-2">
                {statusIcon(c.status)}
                <span className="font-medium">{c.name}</span>
              </div>
              <Badge
                tone={
                  c.status === 'healthy' ? 'success' : c.status === 'warning' ? 'warning' : 'danger'
                }
              >
                {c.status}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
