import { useEffect, useState } from 'react';
import { RefreshCw, Trash2 } from 'lucide-react';
import {
  adminApi,
  type AdminFlag,
  type AdminMaintenanceWindow,
  type AdminRemoteConfig,
} from '@/api';
import { Badge, Button, Card, Table, Tabs } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

export default function Control({ onError }: { onError?: (m: string) => void }) {
  const [flags, setFlags] = useState<AdminFlag[]>([]);
  const [maintenance, setMaintenance] = useState<AdminMaintenanceWindow[]>([]);
  const [configs, setConfigs] = useState<AdminRemoteConfig[]>([]);
  const [activeTab, setActiveTab] = useState<'flags' | 'maintenance' | 'configs'>('flags');
  const handleTabChange = (id: string) => setActiveTab(id as 'flags' | 'maintenance' | 'configs');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [f, m, c] = await Promise.all([
        adminApi.flags(),
        adminApi.maintenance(),
        adminApi.remoteConfigs(),
      ]);
      setFlags(f.flags || []);
      setMaintenance(m.windows || []);
      setConfigs(c.configs || []);
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
  }, []);

  const toggleFlag = async (flag: AdminFlag) => {
    try {
      await adminApi.updateFlag(flag.key, { enabled: !flag.enabled });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle');
    }
  };

  const deleteFlag = async (key: string) => {
    if (!confirm(`Delete feature flag "${key}"?`)) return;
    try {
      await adminApi.deleteFlag(key);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const toggleMaintenance = async (window: AdminMaintenanceWindow) => {
    try {
      await adminApi.updateMaintenance(window.id, { enabled: !window.enabled });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle');
    }
  };

  if (loading)
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading control panel…
      </Card>
    );

  return (
    <div className="space-y-4">
      <Tabs
        tabs={[
          { id: 'flags', label: 'Feature Flags' },
          { id: 'maintenance', label: 'Maintenance' },
          { id: 'configs', label: 'Remote Config' },
        ]}
        active={activeTab}
        onChange={handleTabChange}
      />

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {activeTab === 'flags' && (
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Feature Flags</h3>
              <Button variant="primary" size="sm" onClick={() => alert('Create flag modal')}>
                New Flag
              </Button>
            </div>
            <Table
              head={[
                'Key',
                'Name',
                'Enabled',
                'Rollout %',
                'Target Roles',
                'Target Platforms',
                'Actions',
              ]}
              rows={flags.map(f => [
                <code key="k" className="text-sm">
                  {f.key}
                </code>,
                <span key="n">{f.name}</span>,
                <Badge key="e" tone={f.enabled ? 'success' : 'neutral'}>
                  {f.enabled ? 'On' : 'Off'}
                </Badge>,
                <span key="r">{f.rollout_percentage}%</span>,
                <span key="tr">{f.target_roles?.join(', ') || '—'}</span>,
                <span key="tp">{f.target_platforms?.join(', ') || '—'}</span>,
                <div key="a" className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => toggleFlag(f)}>
                    {f.enabled ? 'Disable' : 'Enable'}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => deleteFlag(f.key)}>
                    <Trash2 size={16} strokeWidth={2} className="text-red-500" />
                  </Button>
                </div>,
              ])}
            />
          </Card>
        </div>
      )}

      {activeTab === 'maintenance' && (
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Maintenance Windows</h3>
              <Button variant="primary" size="sm" onClick={() => alert('Create maintenance modal')}>
                New Window
              </Button>
            </div>
            <Table
              head={['Name', 'Global', 'Features', 'Message', 'Schedule', 'Enabled', 'Actions']}
              rows={maintenance.map(m => [
                <span key="n">{m.name}</span>,
                <Badge key="g" tone={m.global_maintenance ? 'warning' : 'neutral'}>
                  {m.global_maintenance ? 'Yes' : 'No'}
                </Badge>,
                <span key="f">{m.target_features?.join(', ') || 'All'}</span>,
                <span key="m">{m.message || '—'}</span>,
                <span key="s">
                  {m.scheduled_start ? new Date(m.scheduled_start).toLocaleString() : 'Always'}
                </span>,
                <Badge key="e" tone={m.enabled ? 'success' : 'neutral'}>
                  {m.enabled ? 'On' : 'Off'}
                </Badge>,
                <div key="a" className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => toggleMaintenance(m)}>
                    {m.enabled ? 'Disable' : 'Enable'}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => alert('Delete maintenance')}>
                    <Trash2 size={16} strokeWidth={2} className="text-red-500" />
                  </Button>
                </div>,
              ])}
            />
          </Card>
        </div>
      )}

      {activeTab === 'configs' && (
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Remote Config</h3>
              <Button variant="primary" size="sm" onClick={() => alert('Create config modal')}>
                New Config
              </Button>
            </div>
            <Table
              head={['Key', 'Value', 'Type', 'Schema Ver', 'Public', 'Updated', 'Actions']}
              rows={configs.map(c => [
                <code key="k" className="text-sm">
                  {c.key}
                </code>,
                <span key="v" className="text-xs truncate max-w-[200px]">
                  {JSON.stringify(c.value).slice(0, 80)}
                </span>,
                <Badge key="t" tone="neutral">
                  {c.value_type}
                </Badge>,
                <span key="sv">v{c.schema_version}</span>,
                <Badge key="p" tone={c.is_public ? 'success' : 'neutral'}>
                  {c.is_public ? 'Yes' : 'No'}
                </Badge>,
                <span key="u">{c.updated_at ? new Date(c.updated_at).toLocaleString() : '—'}</span>,
                <div key="a" className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => alert('Rollback modal')}>
                    <RefreshCw size={16} strokeWidth={2} />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => alert('Delete config')}>
                    <Trash2 size={16} strokeWidth={2} className="text-red-500" />
                  </Button>
                </div>,
              ])}
            />
          </Card>
        </div>
      )}
    </div>
  );
}
