import { useEffect, useState } from 'react';
import { Activity, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { mcpApi } from '@/api';
import { Card, Badge } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

/**
 * The compact monitoring strip on the admin panel.
 *
 * It reads the same MCP panel endpoints the full Monitoring tab does, so the
 * two screens cannot disagree: the numbers here are the ones the tool
 * registry produced, not a second, cheaper source of truth.
 */
export default function MonitoringLive({ onError }: { onError?: (m: string) => void }) {
  const [overview, setOverview] = useState<{
    mcp?: {
      health?: {
        uptime_pct?: number | null;
        cpu_pct_avg?: number;
        ram_pct_avg?: number;
        response_p95_ms_avg?: number;
        http_5xx_pct_avg?: number;
      } | null;
    };
  } | null>(null);
  const [health, setHealth] = useState<{
    mcp?: {
      latency?: {
        endpoints?: Array<{ endpoint: string; p95_ms: number; error_count: number }>;
      } | null;
    };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [o, h] = await Promise.all([mcpApi.overview(), mcpApi.health()]);
      setOverview(o as never);
      setHealth(h as never);
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

  const telemetry = overview?.mcp?.health ?? {};
  const endpoints = health?.mcp?.latency?.endpoints ?? [];

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
          <h3 className="text-sm font-medium text-gray-500">Uptime</h3>
          <p className="text-2xl font-bold">
            {telemetry.uptime_pct === null || telemetry.uptime_pct === undefined
              ? '—'
              : `${telemetry.uptime_pct.toFixed(2)}%`}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500">CPU</h3>
          <p className="text-2xl font-bold">
            {telemetry.cpu_pct_avg === undefined ? '—' : `${telemetry.cpu_pct_avg.toFixed(1)}%`}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500">Memory</h3>
          <p className="text-2xl font-bold">
            {telemetry.ram_pct_avg === undefined ? '—' : `${telemetry.ram_pct_avg.toFixed(1)}%`}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500">HTTP 5xx</h3>
          <p className="text-2xl font-bold">
            {telemetry.http_5xx_pct_avg === undefined
              ? '—'
              : `${telemetry.http_5xx_pct_avg.toFixed(2)}%`}
          </p>
        </Card>
      </div>

      <Card className="mt-4">
        <h3 className="text-lg font-semibold mb-4">Slowest endpoints</h3>
        {endpoints.length === 0 ? (
          <p className="text-sm text-gray-500">
            No slow endpoint recorded in the window. The p95 tool reports none, which means no
            endpoint crossed its budget - not that the tool failed to answer.
          </p>
        ) : (
          <div className="space-y-2">
            {endpoints.map(e => (
              <div
                key={e.endpoint}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-2">
                  {statusIcon(e.error_count > 0 ? 'warning' : 'healthy')}
                  <span className="font-medium">{e.endpoint}</span>
                </div>
                <Badge tone={e.error_count > 0 ? 'warning' : 'success'}>p95 {e.p95_ms} ms</Badge>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
