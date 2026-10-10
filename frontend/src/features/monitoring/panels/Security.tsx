/**
 * Subsection C: Security.
 *
 * Client-side signals (root, emulator, tampering) are shown as *observations*.
 * They are never used to block a request, and the panel says so, because a
 * dashboard that lists "blocked: 0" next to "root: 400" invites an admin to
 * conclude the app is under attack when in fact the app is fine and nobody has
 * asked it to act on anything.
 */
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
}

interface SecurityPanelProps {
  data?: SecurityData | null;
  loading?: boolean;
  awaiting?: boolean;
}

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
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Security events" value={num(total)} hint="all kinds, this window" />
        <StatTile
          label="Integrity signals"
          value={num(signalTotal)}
          hint="root / emulator / tamper"
        />
        <StatTile
          label="Actioned"
          value={num(blockedTotal)}
          hint="system responded, not just observed"
        />
        <StatTile
          label="Response rate"
          value={signalTotal === 0 ? '--' : `${((blockedTotal / signalTotal) * 100).toFixed(0)}%`}
          hint="deliberately low — see below"
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
                  className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2"
                >
                  <span className="text-xs font-medium text-gray-700">
                    {KIND_LABELS[kind] || kind}
                  </span>
                  <span className="tabular-nums text-sm font-semibold text-gray-900">
                    {num(count)}
                  </span>
                </div>
              ))}
          </div>
        </Panel>
      )}

      <Panel title="About integrity signals">
        <div className="space-y-2 text-xs text-gray-600">
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
