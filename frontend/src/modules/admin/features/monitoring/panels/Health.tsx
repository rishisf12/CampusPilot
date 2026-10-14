/**
 * Subsection A: Health & Performance.
 *
 * Latency and request numbers come from the API's own Prometheus registry,
 * not from this database. A number computed after the fact cannot tell you what
 * the 95th percentile *was*, only how long this particular call took - which is
 * the difference between a latency panel and a stopwatch.
 */
import { Panel, StatTile, EmptyState, num } from '../components/components';

export interface HealthSnapshot {
  ts?: string;
  response_time_ms?: number | null;
  response_time_p95_ms?: number | null;
  response_time_p99_ms?: number | null;
  http_2xx_pct?: number | null;
  http_4xx_pct?: number | null;
  http_5xx_pct?: number | null;
  db_query_p50_ms?: number | null;
  db_query_p95_ms?: number | null;
  db_slow_queries_count?: number | null;
  db_connections_active?: number | null;
  db_connections_idle?: number | null;
  cpu_pct?: number | null;
  ram_pct?: number | null;
  disk_pct?: number | null;
}

export interface HealthData {
  /**
   * The newest sampled reading: windowed latency, error mix and DB figures.
   * Distinct from `http` below, which is a live registry read and therefore
   * cumulative since process start.
   */
  snapshot?: HealthSnapshot | null;
  http?: {
    requests_by_route?: Record<string, number>;
    requests_by_status?: Record<string, number>;
    registry_series?: number;
    registry_families?: number;
  };
  db?: { active_users?: number; sessions?: number };
  crashes?: {
    web?: CrashStats;
    android?: CrashStats;
  };
  data_freshness?: {
    latest_rollup_hour?: string | null;
    rollup_lag_minutes?: number | null;
    latest_crash_at?: string | null;
  };
}

interface CrashStats {
  sessions?: number;
  crashed_sessions?: number;
  crash_free_pct?: number;
}

interface HealthPanelProps {
  data?: HealthData | null;
  loading?: boolean;
  /** Accepted for symmetry with the other panels; health has no awaiting state. */
  awaiting?: boolean;
}

export function HealthPanel({ data, loading }: HealthPanelProps) {
  if (loading)
    return (
      <Panel title="Health & Performance">
        <EmptyState title="Loading metrics…" />
      </Panel>
    );
  if (!data)
    return (
      <Panel title="Health & Performance">
        <EmptyState
          title="Metrics unavailable"
          detail="The endpoint did not answer. Check that the API is running and that METRICS_ENABLED is set."
        />
      </Panel>
    );

  const http = data.http || {};
  const routeTotals = http.requests_by_route || {};
  const byStatus = http.requests_by_status || {};
  const db = data.db || {};
  const crashes = data.crashes || {};
  const web = crashes.web || {};
  const android = crashes.android || {};
  const freshness = data.data_freshness || {};
  const snap = data.snapshot || null;

  const totalRequests = Object.values(routeTotals).reduce((s, v) => s + (Number(v) || 0), 0);
  const total5xx = Object.entries(byStatus)
    .filter(([status]) => status.endsWith('5xx'))
    .reduce((s, [, v]) => s + (Number(v) || 0), 0);
  const total4xx = Object.entries(byStatus)
    .filter(([status]) => status.endsWith('4xx'))
    .reduce((s, [, v]) => s + (Number(v) || 0), 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Requests" value={num(totalRequests)} hint="since process start" />
        <StatTile
          label="Server errors"
          value={num(total5xx)}
          hint={
            totalRequests
              ? `${((total5xx / totalRequests) * 100).toFixed(2)}% of requests`
              : 'no traffic yet'
          }
          invertDelta
        />
        <StatTile label="Client errors" value={num(total4xx)} hint="4xx responses" />
        <StatTile
          label="Metrics"
          value={num(http.registry_series)}
          hint={`${num(http.registry_families)} metric names`}
        />
        <StatTile
          label="Error rate"
          value={
            totalRequests ? `${(((total5xx + total4xx) / totalRequests) * 100).toFixed(2)}%` : '--'
          }
          hint="4xx + 5xx of all requests"
        />
      </div>

      <Panel
        title="Latency & error mix"
        subtitle={
          snap?.ts
            ? `Sampled ${new Date(snap.ts).toLocaleString()} — figures cover the interval since the previous sample, not all time.`
            : 'No sample taken yet. Enable HEALTH_SAMPLE_INLINE or POST /monitoring/health/sample.'
        }
      >
        {!snap ? (
          <EmptyState
            title="Awaiting first sample"
            detail="The health sampler writes one row per interval. Until it has run once there is nothing windowed to report."
          />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatTile
              label="Latency p50"
              value={snap.response_time_ms == null ? '--' : `${num(snap.response_time_ms)} ms`}
              hint="median request"
            />
            <StatTile
              label="Latency p95"
              value={
                snap.response_time_p95_ms == null ? '--' : `${num(snap.response_time_p95_ms)} ms`
              }
              hint="warn above 500 ms"
            />
            <StatTile
              label="Latency p99"
              value={
                snap.response_time_p99_ms == null ? '--' : `${num(snap.response_time_p99_ms)} ms`
              }
              hint="slowest tail"
            />
            <StatTile
              label="Server errors"
              value={snap.http_5xx_pct == null ? '--' : `${snap.http_5xx_pct}%`}
              hint={
                snap.http_5xx_pct == null ? 'no traffic in window' : '5xx of requests in window'
              }
              invertDelta
            />
            <StatTile
              label="Client errors"
              value={snap.http_4xx_pct == null ? '--' : `${snap.http_4xx_pct}%`}
              hint="4xx of requests in window"
            />
            <StatTile
              label="DB query p95"
              value={snap.db_query_p95_ms == null ? '--' : `${num(snap.db_query_p95_ms)} ms`}
              hint="warn above 500 ms"
            />
            <StatTile
              label="Slow queries"
              value={snap.db_slow_queries_count == null ? '--' : num(snap.db_slow_queries_count)}
              hint="over 500 ms in window"
            />
            <StatTile
              label="DB connections"
              value={
                snap.db_connections_active == null
                  ? '--'
                  : `${num(snap.db_connections_active)} / ${num(snap.db_connections_idle ?? 0)}`
              }
              hint="active / idle"
            />
          </div>
        )}
      </Panel>

      <Panel
        title="Crash-free rate"
        subtitle="Measured on sessions, not on raw events. A user who crashes three times in one session counts as one affected session."
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {(
            [
              ['Web', web],
              ['Android', android],
            ] as Array<[string, CrashStats]>
          ).map(([label, c]) => (
            <div key={label} className="rounded-xl border border-gray-200 p-4">
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                {label}
              </div>
              <div className="mt-1 text-2xl font-bold text-gray-900 tabular-nums">
                {c.sessions === 0 ? '--' : `${c.crash_free_pct}%`}
              </div>
              <div className="mt-1 text-xs text-gray-500">
                {c.sessions === 0
                  ? 'no sessions recorded yet'
                  : `${num(c.crashed_sessions)} of ${num(c.sessions)} sessions crashed`}
              </div>
            </div>
          ))}
        </div>
        {(web.sessions ?? 0) === 0 && (android.sessions ?? 0) === 0 && (
          <div className="mt-4">
            <EmptyState
              title="No sessions recorded"
              detail="Crash-free rate is 100% by definition when nothing has run. That is the absence of evidence, not evidence of health."
            />
          </div>
        )}
      </Panel>

      <Panel title="Database" subtitle="Session-level activity over the selected window.">
        <div className="grid grid-cols-2 gap-3">
          <StatTile label="Active users" value={num(db.active_users)} />
          <StatTile label="Sessions" value={num(db.sessions)} />
        </div>
      </Panel>

      <Panel title="Request volume by route" subtitle="Route templates, not concrete URLs.">
        {Object.keys(routeTotals).length === 0 ? (
          <EmptyState
            title="No requests recorded"
            detail="Prometheus counters start at zero and only appear once a request has been served. Reload this page to generate some."
          />
        ) : (
          <div className="space-y-1.5">
            {Object.entries(routeTotals)
              .sort((a, b) => (Number(b[1]) || 0) - (Number(a[1]) || 0))
              .slice(0, 12)
              .map(([route, value]) => (
                <div key={route} className="flex items-center justify-between text-xs">
                  <code className="text-gray-600 truncate">{route}</code>
                  <span className="tabular-nums font-medium text-gray-800 ml-3">{num(value)}</span>
                </div>
              ))}
          </div>
        )}
      </Panel>

      <Panel title="Data freshness">
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <dt className="text-gray-500">Latest rollup hour</dt>
            <dd className="mt-0.5 font-medium text-gray-800">
              {freshness.latest_rollup_hour ?? 'never'}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Rollup lag</dt>
            <dd className="mt-0.5 font-medium text-gray-800">
              {freshness.rollup_lag_minutes === null || freshness.rollup_lag_minutes === undefined
                ? '--'
                : `${freshness.rollup_lag_minutes} min`}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Latest crash report</dt>
            <dd className="mt-0.5 font-medium text-gray-800">
              {freshness.latest_crash_at ?? 'never'}
            </dd>
          </div>
        </dl>
        {(freshness.rollup_lag_minutes ?? 0) > 120 && (
          <p className="mt-3 rounded-lg bg-warning-50 border border-warning-200 px-3 py-2 text-xs text-warning-800">
            The hourly rollup is more than two hours behind. Volume figures below are stale until it
            runs — either the rollup timer is not running or the collector has stopped.
          </p>
        )}
      </Panel>
    </div>
  );
}
