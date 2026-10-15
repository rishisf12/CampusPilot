import { useEffect, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { adminApi } from '@/api';
import { Card, Badge, Table, Input, Button } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function Audit({ onError }: { onError?: (m: string) => void }) {
  const [logs, setLogs] = useState<
    Array<{
      id: number;
      actor_id: number | null;
      actor_email: string | null;
      actor_role: string | null;
      action: string;
      target_type: string | null;
      target_id: string | null;
      before_json: unknown | null;
      after_json: unknown | null;
      ip_hash: string | null;
      user_agent_hash: string | null;
      request_id: string | null;
      created_at: string;
    }>
  >([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    search: '',
    action: '',
    actor_id: '',
    target_type: '',
    target_id: '',
  });

  const load = async () => {
    setLoading(true);
    try {
      const apiFilters = {
        ...filters,
        actor_id: filters.actor_id ? parseInt(filters.actor_id, 10) : undefined,
      };
      const data = await adminApi.auditLogs({
        ...apiFilters,
        page,
        size: 50,
      });
      setLogs(data.logs || []);
      setTotal(data.total);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, filters]);

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      setPage(1);
      load();
    }
  };

  const exportLogs = async (format: 'json' | 'csv') => {
    try {
      const exportFilters = {
        ...filters,
        actor_id: filters.actor_id ? parseInt(filters.actor_id, 10) : undefined,
      };
      const blob = await adminApi.exportAuditLogs({ ...exportFilters, format });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_log.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  if (loading && logs.length === 0)
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading audit log…
      </Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Audit Log</h2>
        <div className="flex gap-2">
          <Button
            variant="primary"
            size="sm"
            icon={<Download size={16} strokeWidth={2} />}
            onClick={() => exportLogs('json')}
          >
            Export JSON
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<Download size={16} strokeWidth={2} />}
            onClick={() => exportLogs('csv')}
          >
            Export CSV
          </Button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <Card>
        <div className="flex flex-wrap gap-2 mb-4">
          <Input
            id="audit-search"
            value={filters.search}
            onChange={e => {
              setFilters({ ...filters, search: e.target.value });
              setPage(1);
            }}
            onKeyDown={handleSearch}
            placeholder="Search actor, action, target…"
            className="w-64"
          />
          <Input
            value={filters.action}
            onChange={e => {
              setFilters({ ...filters, action: e.target.value });
              setPage(1);
            }}
            onKeyDown={handleSearch}
            placeholder="Action (e.g. user.role.change)"
            className="w-48"
          />
          <Input
            value={filters.target_type}
            onChange={e => {
              setFilters({ ...filters, target_type: e.target.value });
              setPage(1);
            }}
            onKeyDown={handleSearch}
            placeholder="Target type"
            className="w-40"
          />
          <Input
            value={filters.target_id}
            onChange={e => {
              setFilters({ ...filters, target_id: e.target.value });
              setPage(1);
            }}
            onKeyDown={handleSearch}
            placeholder="Target ID"
            className="w-40"
          />
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={16} strokeWidth={2} />}
            onClick={() => {
              setFilters({ search: '', action: '', actor_id: '', target_type: '', target_id: '' });
              setPage(1);
              load();
            }}
          >
            Clear
          </Button>
        </div>

        <Table
          head={['Time', 'Actor', 'Action', 'Target', 'Before', 'After', 'IP', 'Request ID']}
          rows={logs.map(l => [
            <span key="t">{l.created_at ? new Date(l.created_at).toLocaleString() : '—'}</span>,
            <div key="a" className="flex flex-col">
              <span className="font-medium">{l.actor_email || 'System'}</span>
              <span className="text-xs text-gray-500">{l.actor_role || ''}</span>
            </div>,
            <Badge key="ac" tone="neutral">
              {l.action}
            </Badge>,
            <div key="tg" className="text-sm">
              <span>{l.target_type || '—'}</span>
              <span className="text-gray-500">#{l.target_id || ''}</span>
            </div>,
            <code key="b" className="text-xs truncate max-w-[150px]">
              {l.before_json ? JSON.stringify(l.before_json).slice(0, 60) : '—'}
            </code>,
            <code key="af" className="text-xs truncate max-w-[150px]">
              {l.after_json ? JSON.stringify(l.after_json).slice(0, 60) : '—'}
            </code>,
            <code key="ip" className="text-xs">
              {l.ip_hash ? l.ip_hash.slice(0, 16) + '…' : '—'}
            </code>,
            <code key="r" className="text-xs">
              {l.request_id ? l.request_id.slice(0, 16) + '…' : '—'}
            </code>,
          ])}
        />

        <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
          <span>
            Page {page} · {total} total
          </span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              Prev
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={logs.length < 50}
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
