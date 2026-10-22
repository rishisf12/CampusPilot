/**
 * Subsection A: Health & Performance.
 *
 * Latency and request numbers come from the API's own Prometheus registry,
 * not from this database. A number computed after the fact cannot tell you what
 * the 95th percentile *was*, only how long this particular call took - which is
 * the difference between a latency panel and a stopwatch.
 */
import { Gauge, Server, Siren, TriangleAlert } from 'lucide-react';
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
  /**
   * The MCP tool answers behind this panel.
   *
   * The live figures above are cumulative-since-start or last-sample; these
   * are the *window's* shape - the averages and maxima across every sample
   * in the range, the reader-derived uptime, and the slowest endpoints. They
   * come from the same tool registry the scan agent reads, so they are
   * redacted, scoped and audited like everything else here.
   */
  mcp?: {
    tools?: string[];
    failed?: Record<string, string>;
    telemetry?: {
      samples?: number;
      uptime_pct?: number | null;
      response_p95_ms_avg?: number;
      response_p95_ms_max?: number;
      db_query_p95_ms_avg?: number;
      http_5xx_pct_avg?: number;
      http_5xx_pct_max?: number;
      cpu_pct_avg?: number;
      ram_pct_avg?: number;
    } | null;
    uptime_pct?: number | null;
    latency?: {
      endpoints?: Array<{
        endpoint: string;
        method: string;
        p50_ms: number;
        p95_ms: number;
        p99_ms: number;
        request_count: number;
        error_count: number;
      }>;
      worst_p95_ms?: number;
    } | null;
    crash_clusters?: Array<{
      fingerprint: string;
      exception_type: string;
      count: number;
      fatal_count: number;
      app_versions?: string[];
    }> | null;
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

const iconProps = {
  size: 20,
  strokeWidth: 2,
  'aria-hidden': true,
  style: { color: 'currentColor' },
} as const;

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
    <div className="space-y-4" aria-live="polite">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Requests"
          value={num(totalRequests)}
          hint="since process start"
          hue="sky"
          icon={<Server {...iconProps} />}
        />
        <StatTile
          label="Server errors"
          value={num(total5xx)}
          hint={
            totalRequests
              ? `${((total5xx / totalRequests) * 100).toFixed(2)}% of requests`
              : 'no traffic yet'
          }
          invertDelta
          hue="coral"
          icon={<Siren {...iconProps} />}
        />
        <StatTile
          label="Client errors"
          value={num(total4xx)}
          hint="4xx responses"
          hue="amber"
          icon={<TriangleAlert {...iconProps} />}
        />
        <StatTile
          label="Metrics"
          value={num(http.registry_series)}
          hint={`${num(http.registry_families)} metric names`}
          hue="slate"
          icon={<Gauge {...iconProps} />}
        />
        <StatTile
          label="Error rate"
          value={
            totalRequests ? `${(((total5xx + total4xx) / totalRequests) * 100).toFixed(2)}%` : '--'
          }
          hint="4xx + 5xx of all requests"
          hue="coral"
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
            <div
              key={label}
              className="p-4"
              style={{
                borderRadius: 12,
                border: '1px solid rgba(163,177,198,.3)',
                background: 'var(--cp-surface)',
                boxShadow: 'var(--cp-neu-raised-sm)',
              }}
            >
              <div
                className="text-xs font-medium uppercase tracking-wide"
                style={{ color: 'var(--cp-muted)' }}
              >
                {label}
              </div>
              <div
                className="mt-1 text-2xl font-bold tabular-nums"
                style={{ color: 'var(--cp-text)' }}
              >
                {c.sessions === 0 ? '--' : `${c.crash_free_pct}%`}
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--cp-muted)' }}>
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
                <div
                  key={route}
                  className="flex items-center justify-between text-xs px-3 py-1.5 transition-colors"
                  style={{ borderRadius: 8 }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'var(--cp-bg)';
                    e.currentTarget.style.boxShadow = 'var(--cp-neu-inset)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  <code className="truncate" style={{ color: 'var(--cp-muted)' }}>
                    {route}
                  </code>
                  <span
                    className="tabular-nums font-medium ml-3"
                    style={{ color: 'var(--cp-text)' }}
                  >
                    {num(value)}
                  </span>
                </div>
              ))}
          </div>
        )}
      </Panel>

      <Panel title="Data freshness">
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <dt style={{ color: 'var(--cp-muted)' }}>Latest rollup hour</dt>
            <dd className="mt-0.5 font-medium" style={{ color: 'var(--cp-text)' }}>
              {freshness.latest_rollup_hour ?? 'never'}
            </dd>
          </div>
          <div>
            <dt style={{ color: 'var(--cp-muted)' }}>Rollup lag</dt>
            <dd className="mt-0.5 font-medium" style={{ color: 'var(--cp-text)' }}>
              {freshness.rollup_lag_minutes === null || freshness.rollup_lag_minutes === undefined
                ? '--'
                : `${freshness.rollup_lag_minutes} min`}
            </dd>
          </div>
          <div>
            <dt style={{ color: 'var(--cp-muted)' }}>Latest crash report</dt>
            <dd className="mt-0.5 font-medium" style={{ color: 'var(--cp-text)' }}>
              {freshness.latest_crash_at ?? 'never'}
            </dd>
          </div>
        </dl>
        {(freshness.rollup_lag_minutes ?? 0) > 120 && (
          <p
            className="mt-3 px-3 py-2 text-xs"
            style={{
              borderRadius: 12,
              background: 'var(--cp-bg)',
              boxShadow: 'var(--cp-neu-inset)',
              color: 'var(--cp-warning)',
            }}
          >
            The hourly rollup is more than two hours behind. Volume figures below are stale until it
            runs — either the rollup timer is not running or the collector has stopped.
          </p>
        )}
      </Panel>

      <McpWindowPanel mcp={data.mcp} />
    </div>
  );
}

/**
 * The window's shape, as the MCP tools report it.
 *
 * The panels above answer "what is it like right now" - the last sample, the
 * counters since the process started. This one answers "what was the window
 * like", which is the question an admin asks after something went wrong: the
 * averages and the maxima across every sample in the range, the slowest
 * endpoints by p95, and the crash fingerprints.
 *
 * A tool that refused is named rather than silently absent. "Not measured" and
 * "measured as zero" are different facts, and only one of them is reassuring.
 */
function McpWindowPanel({ mcp }: { mcp?: HealthData['mcp'] }) {
  const telemetry = mcp?.telemetry;
  const endpoints = mcp?.latency?.endpoints ?? [];
  const clusters = mcp?.crash_clusters ?? [];
  const failed = Object.keys(mcp?.failed ?? {});

  if (!mcp || (!telemetry && endpoints.length === 0 && clusters.length === 0)) {
    return (
      <Panel
        title="Window shape (MCP)"
        subtitle="The averages and maxima across the whole window, not just the latest sample."
      >
        <EmptyState
          title="No window aggregates"
          detail="The MCP tools answered with nothing for this window - either no sample was taken, or the tool refused. The panels above still show the live figures."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="Window shape (MCP)"
      subtitle="Averages and maxima across every sample in the window, read through the MCP tool registry."
      actions={
        failed.length > 0 ? (
          <span className="text-xs" style={{ color: 'var(--cp-warning)' }}>
            {failed.join(', ')} refused
          </span>
        ) : undefined
      }
    >
      {telemetry && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile
            label="Uptime"
            value={
              mcp?.uptime_pct === null || mcp?.uptime_pct === undefined
                ? '--'
                : `${(mcp.uptime_pct as number).toFixed(2)}%`
            }
            hint="reader-derived, over the window"
            hue="mint"
          />
          <StatTile
            label="Latency p95"
            value={
              telemetry.response_p95_ms_avg === undefined
                ? '--'
                : `${num(telemetry.response_p95_ms_avg)} ms`
            }
            hint={
              telemetry.response_p95_ms_max === undefined
                ? 'window average'
                : `avg, max ${num(telemetry.response_p95_ms_max)} ms`
            }
          />
          <StatTile
            label="Server errors"
            value={
              telemetry.http_5xx_pct_avg === undefined
                ? '--'
                : `${telemetry.http_5xx_pct_avg.toFixed(2)}%`
            }
            hint={
              telemetry.http_5xx_pct_max === undefined
                ? 'window average'
                : `avg, max ${telemetry.http_5xx_pct_max.toFixed(2)}%`
            }
            invertDelta
            hue="coral"
          />
          <StatTile
            label="CPU"
            value={
              telemetry.cpu_pct_avg === undefined ? '--' : `${telemetry.cpu_pct_avg.toFixed(1)}%`
            }
            hint="window average"
            hue="slate"
          />
          <StatTile
            label="Memory"
            value={
              telemetry.ram_pct_avg === undefined ? '--' : `${telemetry.ram_pct_avg.toFixed(1)}%`
            }
            hint="window average"
            hue="slate"
          />
          <StatTile
            label="DB query p95"
            value={
              telemetry.db_query_p95_ms_avg === undefined
                ? '--'
                : `${num(telemetry.db_query_p95_ms_avg)} ms`
            }
            hint="window average"
          />
          <StatTile
            label="Samples"
            value={num(telemetry.samples)}
            hint="health rows in the window"
          />
          <StatTile
            label="Worst endpoint"
            value={
              mcp?.latency?.worst_p95_ms === undefined
                ? '--'
                : `${num(mcp.latency.worst_p95_ms)} ms`
            }
            hint="p95 of the slowest route"
          />
        </div>
      )}

      {endpoints.length > 0 && (
        <div className="mt-4">
          <div
            className="text-xs font-medium uppercase tracking-wide mb-2"
            style={{ color: 'var(--cp-muted)' }}
          >
            Slowest endpoints
          </div>
          <div className="space-y-1.5">
            {endpoints.slice(0, 8).map(e => (
              <div
                key={`${e.method} ${e.endpoint}`}
                className="flex items-center justify-between text-xs px-3 py-1.5"
                style={{ borderRadius: 8 }}
              >
                <code className="truncate" style={{ color: 'var(--cp-muted)' }}>
                  {e.method} {e.endpoint}
                </code>
                <span className="tabular-nums font-medium ml-3" style={{ color: 'var(--cp-text)' }}>
                  p95 {num(e.p95_ms)} ms · {num(e.error_count)} errors
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {clusters.length > 0 && (
        <div className="mt-4">
          <div
            className="text-xs font-medium uppercase tracking-wide mb-2"
            style={{ color: 'var(--cp-muted)' }}
          >
            Crash clusters
          </div>
          <div className="space-y-1.5">
            {clusters.slice(0, 6).map(c => (
              <div
                key={c.fingerprint}
                className="flex items-center justify-between text-xs px-3 py-1.5"
                style={{ borderRadius: 8 }}
              >
                <code className="truncate" style={{ color: 'var(--cp-muted)' }}>
                  {c.exception_type}
                </code>
                <span className="tabular-nums font-medium ml-3" style={{ color: 'var(--cp-text)' }}>
                  {num(c.count)} crashes
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}
