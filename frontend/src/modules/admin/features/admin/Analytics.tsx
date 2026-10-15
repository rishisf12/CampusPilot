import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { Users, TrendingUp, AlertTriangle, RefreshCw, Plus } from 'lucide-react';
import { adminApi } from '@/api';
import { Card, Badge, Input, Select, Button, Tabs, Table } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';

const COLORS = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#ec4899',
  '#06b6d4',
  '#84cc16',
];

export default function Analytics({ onError }: { onError?: (m: string) => void }) {
  const [overview, setOverview] = useState<{
    dau: number;
    wau: number;
    mau: number;
    new_signups: number;
    retention_d7: number;
    verified_rate: number;
  } | null>(null);
  const [featureUsage, setFeatureUsage] = useState<
    Array<{ feature: string; platform: string; unique_users: number; opens: number }>
  >([]);
  const [retention, setRetention] = useState<{ d1: number; d7: number; d30: number } | null>(null);
  const [platforms, setPlatforms] = useState<
    Array<{ platform: string; version: string; unique_users: number; count: number }>
  >([]);
  const [segments, setSegments] = useState<
    Array<{
      id: number;
      name: string;
      description: string | null;
      criteria_json: Record<string, unknown>;
      is_active: boolean;
      created_at: string;
      updated_at: string;
    }>
  >([]);
  const [funnels, setFunnels] = useState<
    Array<{
      id: number;
      name: string;
      description: string | null;
      steps: string[];
      window_hours: number;
      is_active: boolean;
      created_at: string;
      updated_at: string;
    }>
  >([]);
  const [anomalies, setAnomalies] = useState<
    Array<{
      id: number;
      metric_name: string;
      dimension: string | null;
      dimension_value: string | null;
      expected_value: number;
      actual_value: number;
      deviation_pct: number;
      severity: string;
      description: string;
      status: string;
      detected_at: string;
    }>
  >([]);
  const [activeTab, setActiveTab] = useState<
    'overview' | 'features' | 'retention' | 'segments' | 'funnels' | 'anomalies' | 'platforms'
  >('overview');
  const handleTabChange = (id: string) =>
    setActiveTab(
      id as
        'overview' | 'features' | 'retention' | 'segments' | 'funnels' | 'anomalies' | 'platforms'
    );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  const [search, setSearch] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const [ov, fu, ret, plat, segRes, funRes, anomRes] = await Promise.all([
        adminApi.analyticsOverview(days),
        adminApi.featureUsage(days),
        adminApi.retention(days),
        adminApi.platformVersions(days),
        adminApi.segments(),
        adminApi.funnels(),
        adminApi.anomalies(),
      ]);
      setOverview(ov);
      setFeatureUsage(fu);
      setRetention(ret);
      setPlatforms(plat);
      setSegments(segRes.segments || []);
      setFunnels(funRes.funnels || []);
      setAnomalies(anomRes.anomalies || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
      onError?.(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const runAggregation = async () => {
    try {
      await adminApi.runAggregation();
      setError(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Aggregation failed');
    }
  };

  const detectAnomalies = async () => {
    try {
      await adminApi.detectAnomalies();
      setError(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Anomaly detection failed');
    }
  };

  if (loading)
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading analytics…
      </Card>
    );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Analytics</h2>
        <div className="flex items-center gap-2">
          <Select
            value={days}
            onChange={e => {
              setDays(Number(e.target.value));
              load();
            }}
            className="w-32"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </Select>
          <Button
            variant="primary"
            size="sm"
            icon={<RefreshCw size={16} strokeWidth={2} />}
            onClick={runAggregation}
            disabled={loading}
          >
            Run Aggregation
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={<AlertTriangle size={16} strokeWidth={2} />}
            onClick={detectAnomalies}
            disabled={loading}
          >
            Detect Anomalies
          </Button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <Tabs
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'features', label: 'Feature Usage' },
          { id: 'retention', label: 'Retention' },
          { id: 'platforms', label: 'Platforms' },
          { id: 'segments', label: 'Segments' },
          { id: 'funnels', label: 'Funnels' },
          { id: 'anomalies', label: 'Anomalies' },
        ]}
        active={activeTab}
        onChange={handleTabChange}
      />

      {activeTab === 'overview' && overview && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <div className="flex items-center gap-2">
                <Users size={24} className="text-blue-500" />
                <div>
                  <p className="text-sm text-gray-500">DAU</p>
                  <p className="text-2xl font-bold">{overview.dau || '—'}</p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-2">
                <Users size={24} className="text-green-500" />
                <div>
                  <p className="text-sm text-gray-500">WAU</p>
                  <p className="text-2xl font-bold">{overview.wau || '—'}</p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-2">
                <Users size={24} className="text-purple-500" />
                <div>
                  <p className="text-sm text-gray-500">MAU</p>
                  <p className="text-2xl font-bold">{overview.mau || '—'}</p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-2">
                <TrendingUp size={24} className="text-orange-500" />
                <div>
                  <p className="text-sm text-gray-500">Retention D7</p>
                  <p className="text-2xl font-bold">{overview.retention_d7 || '—'}%</p>
                </div>
              </div>
            </Card>
          </div>

          <Card className="mt-4">
            <h3 className="text-lg font-semibold mb-4">Key Metrics</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-gray-500">New Signups</span>
                <span className="font-bold">{overview.new_signups || '—'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Verified Rate</span>
                <span className="font-bold">{overview.verified_rate || '—'}%</span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'features' && (
        <div className="space-y-4">
          <Card>
            <h3 className="text-lg font-semibold mb-4">Feature Usage</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={featureUsage.slice(0, 10)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="feature" tick={{ fontSize: 10 }} angle={-45} dy={10} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar
                  dataKey="unique_users"
                  name="Unique Users"
                  fill="#3b82f6"
                  radius={[4, 4, 0, 0]}
                />
                <Bar dataKey="opens" name="Opens" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-4">
              <Table
                head={['Feature', 'Platform', 'Unique Users', 'Opens']}
                rows={featureUsage.slice(0, 20).map(f => [
                  <code key="f" className="text-sm">
                    {f.feature}
                  </code>,
                  <Badge key="p" tone="neutral">
                    {f.platform}
                  </Badge>,
                  <span key="u">{f.unique_users}</span>,
                  <span key="o">{f.opens}</span>,
                ])}
              />
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'retention' && (
        <div className="space-y-4">
          <Card>
            <h3 className="text-lg font-semibold mb-4">Retention Cohorts</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <p className="text-sm text-gray-500">D1 Retention</p>
                <p className="text-2xl font-bold">{retention?.d1 || '—'}%</p>
              </Card>
              <Card>
                <p className="text-sm text-gray-500">D7 Retention</p>
                <p className="text-2xl font-bold">{retention?.d7 || '—'}%</p>
              </Card>
              <Card>
                <p className="text-sm text-gray-500">D30 Retention</p>
                <p className="text-2xl font-bold">{retention?.d30 || '—'}%</p>
              </Card>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'platforms' && (
        <div className="space-y-4">
          <Card>
            <h3 className="text-lg font-semibold mb-4">Platform & Version Distribution</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={platforms}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="count"
                  nameKey="platform"
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                >
                  {platforms.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-4">
              <Table
                head={['Platform', 'Version', 'Users', 'Opens']}
                rows={platforms.map(p => [
                  <Badge key="p" tone="neutral">
                    {p.platform}
                  </Badge>,
                  <code key="v" className="text-sm">
                    {p.version || 'unknown'}
                  </code>,
                  <span key="u">{p.unique_users}</span>,
                  <span key="o">{p.count}</span>,
                ])}
              />
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'segments' && (
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">User Segments</h3>
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={16} strokeWidth={2} />}
                onClick={() => alert('Create segment modal')}
              >
                New Segment
              </Button>
            </div>
            <div className="flex gap-2 mb-4">
              <Input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search segments…"
                className="w-64"
              />
            </div>
            <Table
              head={['Name', 'Description', 'Criteria', 'Active', 'Created', 'Actions']}
              rows={segments
                .filter(
                  s =>
                    s.name.toLowerCase().includes(search.toLowerCase()) ||
                    JSON.stringify(s.criteria_json).toLowerCase().includes(search.toLowerCase())
                )
                .map(s => [
                  <span key="n" className="font-medium">
                    {s.name}
                  </span>,
                  <span key="d" className="truncate max-w-[200px] text-gray-500">
                    {s.description || '—'}
                  </span>,
                  <code key="c" className="text-xs truncate max-w-[200px]">
                    {JSON.stringify(s.criteria_json)}
                  </code>,
                  <Badge key="a" tone={s.is_active ? 'success' : 'neutral'}>
                    {s.is_active ? 'Yes' : 'No'}
                  </Badge>,
                  <span key="cr">
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                  </span>,
                  <div key="a" className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => alert('View users')}>
                      Users
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => alert('Edit segment')}>
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => alert('Delete segment')}>
                      Delete
                    </Button>
                  </div>,
                ])}
            />
          </Card>
        </div>
      )}

      {activeTab === 'funnels' && (
        <div className="space-y-4">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Funnels</h3>
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={16} strokeWidth={2} />}
                onClick={() => alert('Create funnel modal')}
              >
                New Funnel
              </Button>
            </div>
            {funnels.map(f => (
              <Card key={f.id} className="mt-2">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium">{f.name}</h4>
                  <Button variant="ghost" size="sm" onClick={() => alert('Analyze funnel')}>
                    Analyze
                  </Button>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span>Steps: {f.steps?.join(' → ')}</span>
                  <span>Window: {f.window_hours}h</span>
                  <Badge tone={f.is_active ? 'success' : 'neutral'}>
                    {f.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </Card>
            ))}
            {funnels.length === 0 && (
              <Card className="text-center text-sm text-gray-500">No funnels created yet.</Card>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'anomalies' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Anomalies</h3>
            <Button
              variant="primary"
              size="sm"
              icon={<AlertTriangle size={16} strokeWidth={2} />}
              onClick={detectAnomalies}
              disabled={loading}
            >
              Detect Now
            </Button>
          </div>

          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <Card>
            <Table
              head={[
                'Metric',
                'Dimension',
                'Expected',
                'Actual',
                'Deviation',
                'Severity',
                'Status',
                'Detected',
              ]}
              rows={anomalies.map(a => [
                <Badge key="m" tone="neutral">
                  {a.metric_name}
                </Badge>,
                <span key="d">{a.dimension || '—'}</span>,
                <span key="e">{a.expected_value}</span>,
                <span key="a">{a.actual_value}</span>,
                <Badge key="dev" tone={a.deviation_pct > 50 ? 'danger' : 'warning'}>
                  {a.deviation_pct > 0 ? '+' : ''}
                  {a.deviation_pct.toFixed(1)}%
                </Badge>,
                <Badge key="s" tone={a.severity === 'critical' ? 'danger' : 'warning'}>
                  {a.severity}
                </Badge>,
                <Badge
                  key="s2"
                  tone={
                    a.status === 'resolved'
                      ? 'success'
                      : a.status === 'acknowledged'
                        ? 'warning'
                        : 'danger'
                  }
                >
                  {a.status}
                </Badge>,
                <span key="dt">
                  {a.detected_at ? new Date(a.detected_at).toLocaleString() : '—'}
                </span>,
              ])}
            />
          </Card>
        </div>
      )}
    </div>
  );
}
