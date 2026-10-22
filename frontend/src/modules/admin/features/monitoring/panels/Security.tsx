/**
 * Subsection C: Security.
 *
 * Client-side signals (root, emulator, tampering) are shown as *observations*.
 * They are never used to block a request, and the panel says so, because a
 * dashboard that lists "blocked: 0" next to "root: 400" invites an admin to
 * conclude the app is under attack when in fact the app is fine and nobody has
 * asked it to act on anything.
 */
import { KeyRound, ShieldAlert, ShieldCheck, ShieldHalf } from 'lucide-react';
import { Panel, StatTile, EmptyState, AwaitingData, num } from '../components/components';

const KIND_LABELS: Record<string, string> = {
  failed_login: 'Failed logins',
  brute_force: 'Brute-force patterns',
  token_misuse: 'Token misuse',
  api_abuse: 'API abuse',
  rate_limited: 'Rate limited',
  waf_blocked: 'Blocked at the edge',
  root_detected: 'Root detected',
  emulator_detected: 'Emulator detected',
  tamper_detected: 'Tampering detected',
};

const SIGNAL_KINDS = ['root_detected', 'emulator_detected', 'tamper_detected'];

export interface SecurityData {
  security?: {
    counts?: Record<string, number>;
    blocked?: Record<string, number>;
  };
  /**
   * The MCP tool answers behind this panel.
   *
   * `security_signals` counts the events by kind and reports how many were
   * actioned; `failed_logins_by_hour` gives the shape of the failed-login
   * attempts - how many per hour and how many distinct sources each hour
   * saw. The sources stay in the database: the tool reports the count, never
   * the address.
   */
  mcp?: {
    tools?: string[];
    failed?: Record<string, string>;
    security?: {
      events_total?: number;
      events_blocked?: number;
      blocked_pct?: number;
      events_by_kind?: Record<string, { count: number; blocked: number }>;
      logs_by_severity?: Record<string, number>;
      root_signals?: number;
      open_cves_by_severity?: Record<string, number>;
      failed_logins_by_hour?: Array<{
        hour: string;
        failed_logins: number;
        distinct_sources: number;
        distinct_users: number;
      }> | null;
    };
  };
}

interface SecurityPanelProps {
  data?: SecurityData | null;
  loading?: boolean;
  awaiting?: boolean;
}

const iconProps = {
  size: 20,
  strokeWidth: 2,
  'aria-hidden': true,
  style: { color: 'currentColor' },
} as const;

export function SecurityPanel({ data, loading, awaiting }: SecurityPanelProps) {
  if (awaiting) {
    return (
      <Panel title="Security">
        <AwaitingData
          what="No Android client is reporting security signals yet."
          how="POST to /collect/security-signal with kind root_detected, emulator_detected or tamper_detected."
        />
      </Panel>
    );
  }
  if (loading)
    return (
      <Panel title="Security">
        <EmptyState title="Loading…" />
      </Panel>
    );
  if (!data)
    return (
      <Panel title="Security">
        <EmptyState title="Unavailable" detail="The overview endpoint did not answer." />
      </Panel>
    );

  const counts = (data.security || {}).counts || {};
  const blocked = (data.security || {}).blocked || {};
  const total = Object.values(counts).reduce((s, v) => s + (Number(v) || 0), 0);
  const blockedTotal = Object.values(blocked).reduce((s, v) => s + (Number(v) || 0), 0);
  const signalTotal = SIGNAL_KINDS.reduce((s, k) => s + (Number(counts[k]) || 0), 0);

  return (
    <div className="space-y-4" aria-live="polite">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Security events"
          value={num(total)}
          hint="all kinds, this window"
          hue="coral"
          icon={<ShieldAlert {...iconProps} />}
        />
        <StatTile
          label="Integrity signals"
          value={num(signalTotal)}
          hint="root / emulator / tamper"
          hue="amber"
          icon={<ShieldHalf {...iconProps} />}
        />
        <StatTile
          label="Actioned"
          value={num(blockedTotal)}
          hint="system responded, not just observed"
          hue="sky"
          icon={<ShieldCheck {...iconProps} />}
        />
        <StatTile
          label="Response rate"
          value={signalTotal === 0 ? '--' : `${((blockedTotal / signalTotal) * 100).toFixed(0)}%`}
          hint="deliberately low — see below"
          hue="slate"
          icon={<KeyRound {...iconProps} />}
        />
      </div>

      {total === 0 ? (
        <Panel title="Events by kind">
          <EmptyState
            title="No security events recorded"
            detail="This reads as an absence of events, not as a proven-clean system. Nothing is instrumented until a client reports it."
          />
        </Panel>
      ) : (
        <Panel title="Events by kind">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {Object.entries(counts)
              .sort((a, b) => (Number(b[1]) || 0) - (Number(a[1]) || 0))
              .map(([kind, count]) => (
                <div
                  key={kind}
                  className="flex items-center justify-between px-3 py-2"
                  style={{
                    borderRadius: 12,
                    border: '1px solid rgba(163,177,198,.3)',
                    background: 'var(--cp-surface)',
                  }}
                >
                  <span className="text-xs font-medium" style={{ color: 'var(--cp-text)' }}>
                    {KIND_LABELS[kind] || kind}
                  </span>
                  <span
                    className="tabular-nums text-sm font-semibold"
                    style={{ color: 'var(--cp-text)' }}
                  >
                    {num(count)}
                  </span>
                </div>
              ))}
          </div>
        </Panel>
      )}

      <McpSecurityPanel mcp={data.mcp} />

      <Panel title="About integrity signals">
        <div className="space-y-2 text-xs" style={{ color: 'var(--cp-muted)' }}>
          <p>
            Root, emulator and tampering detections are recorded as observations only. They are
            never used to refuse a request.
          </p>
          <p>
            That is a deliberate choice rather than an oversight. These checks are defeated within
            minutes on a device the user controls, so gating access on them mostly produces support
            tickets about the security feature working as designed. Treating them as signals keeps
            the information without the false positives.
          </p>
          <p>
            Server-side authentication and authorisation do not depend on any of this: every
            protected endpoint checks the bearer token and the user record, not a client-supplied
            verdict.
          </p>
        </div>
      </Panel>
    </div>
  );
}

/**
 * The security signals, as the MCP tools report them.
 *
 * Two answers the panel above does not give. The first is the *ratio*: how
 * many of the events the system acted on, which is the number an operator
 * actually wants and which the per-kind breakdown makes hard to read. The
 * second is the shape of the failed-login attempts - how many per hour, and
 * how many distinct sources each hour saw.
 *
 * The sources stay in the database. The tool reports how many, never which,
 * so an admin can see a spray without this screen becoming a list of
 * addresses to copy.
 */
function McpSecurityPanel({ mcp }: { mcp?: SecurityData['mcp'] }) {
  const signals = mcp?.security;
  const hours = signals?.failed_logins_by_hour ?? [];
  const failed = Object.keys(mcp?.failed ?? {});

  if (!signals) {
    return (
      <Panel
        title="Signals (MCP)"
        subtitle="The actioned ratio and the shape of the failed logins."
      >
        <EmptyState
          title="No signal aggregate"
          detail="The MCP tools did not answer for this window. The panel above still shows the per-kind counts from the store."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="Signals (MCP)"
      subtitle="The actioned ratio, the open CVEs and the shape of the failed logins - read through the MCP tool registry."
      actions={
        failed.length > 0 ? (
          <span className="text-xs" style={{ color: 'var(--cp-warning)' }}>
            {failed.join(', ')} refused
          </span>
        ) : undefined
      }
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Actioned"
          value={num(signals.events_blocked)}
          hint={`of ${num(signals.events_total)} events`}
          hue="sky"
        />
        <StatTile
          label="Actioned ratio"
          value={signals.blocked_pct === undefined ? '--' : `${signals.blocked_pct.toFixed(1)}%`}
          hint="of all events, all kinds"
          hue="slate"
        />
        <StatTile
          label="Open CVEs"
          value={num(Object.values(signals.open_cves_by_severity ?? {}).reduce((s, v) => s + v, 0))}
          hint="dependencies with an open advisory"
          hue="amber"
        />
        <StatTile
          label="Root signals"
          value={num(signals.root_signals)}
          hint="from the security log"
          hue="coral"
        />
      </div>

      {hours.length > 0 && (
        <div className="mt-4">
          <div
            className="text-xs font-medium uppercase tracking-wide mb-2"
            style={{ color: 'var(--cp-muted)' }}
          >
            Failed logins by hour
          </div>
          <div className="space-y-1.5">
            {hours.slice(0, 12).map(h => (
              <div
                key={h.hour}
                className="flex items-center justify-between text-xs px-3 py-1.5"
                style={{ borderRadius: 8 }}
              >
                <span style={{ color: 'var(--cp-muted)' }}>{h.hour}</span>
                <span className="tabular-nums font-medium" style={{ color: 'var(--cp-text)' }}>
                  {num(h.failed_logins)} failed · {num(h.distinct_sources)} sources
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}
