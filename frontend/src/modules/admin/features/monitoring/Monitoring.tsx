/**
 * Web App Monitoring and Android App Monitoring.
 *
 * Two groups of four subsections, sharing one data fetch. The eight subsections
 * come from the server (`/monitoring/subsections`) rather than a local copy: a
 * hardcoded list would eventually disagree with the backend's scan allowlist,
 * and the visible symptom would be a "Scan now" button that always fails with
 * no obvious cause.
 *
 * Two design commitments are visible throughout:
 *
 * * **No fake data.** The Android subsections report "awaiting first data"
 *   because there is no Android client. Rendering zeroes would be
 *   indistinguishable from a healthy app, and that is the one thing a
 *   monitoring screen must never do.
 *
 * * **Freshness is always on screen.** An admin who cannot tell "healthy" from
 *   "the collector is broken" will trust the wrong one, so the collector's age
 *   is reported next to the numbers rather than buried.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Download, RefreshCw, ScanLine } from 'lucide-react';

import { monitoringApi, adminApi, type ScanResultResponse } from '@/api';
import type { MonitoringSubsection } from '@shared/types/api';
import { Badge, Button, Card } from '@/components/ui';
import { ActivityPanel, type ActivityData } from './panels/Activity';
import { FeedbackPanel, type FeedbackData } from './panels/Feedback';
import { HealthPanel, type HealthData } from './panels/Health';
import { HistoryPanel, type HistoryData } from './panels/History';
import { type MonetisationData, MonetisationPanel } from './panels/Monetisation';
import { SecurityPanel, type SecurityData } from './panels/Security';

const RANGES = [
  { days: 1, label: '24h' },
  { days: 7, label: '7d' },
  { days: 30, label: '30d' },
  { days: 90, label: '90d' },
] as const;

/** Rendered when a platform has never reported anything. */
function isAwaiting(group: string): boolean {
  return group === 'Android App Monitoring';
}

/**
 * Scan history is a tab across all eight subsections, not a ninth one.
 *
 * Kept out of the server-provided list so the count of eight stays
 * authoritative and the backend's scan allowlist cannot drift from what the UI
 * offers.
 */
const HISTORY_TAB = 'E_HISTORY';

interface MonitoringProps {
  platformGroup?: string | null;
}

export default function Monitoring({ platformGroup }: MonitoringProps) {
  const [subsections, setSubsections] = useState<MonitoringSubsection[]>([]);
  const [selected, setSelected] = useState('A_W_HEALTH');
  const [days, setDays] = useState(7);
  const [overview, setOverview] = useState<ActivityData | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [feedback, setFeedback] = useState<FeedbackData | null>(null);
  const [history, setHistory] = useState<HistoryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rolling, setRolling] = useState(false);
  // Scan capability, reported by the server on the call above. Previously the
  // button was hardcoded off, so enabling SCAN_ENABLED changed nothing here and
  // the tooltip kept blaming the installation.
  const [scanEnabled, setScanEnabled] = useState(false);
  const [scanLlmEnabled, setScanLlmEnabled] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [lastScan, setLastScan] = useState<ScanResultResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    monitoringApi
      .subsections()
      .then(
        (r: {
          subsections: MonitoringSubsection[];
          scan_enabled?: boolean;
          scan_llm_enabled?: boolean;
        }) => {
          if (cancelled) return;
          setSubsections(r.subsections || []);
          setScanEnabled(Boolean(r.scan_enabled));
          setScanLlmEnabled(Boolean(r.scan_llm_enabled));
        }
      )
      .catch(() => {
        if (!cancelled) setError('Could not load the subsection list.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const current = useMemo(
    () => subsections.find(s => s.id === selected) || null,
    [subsections, selected]
  );

  // Each admin tab shows exactly one group. The server still owns the full list
  // of eight; this only narrows which of them are reachable here, so a
  // subsection can never be present in the UI and absent from the backend.
  //
  // E_HISTORY is explicitly exempt. It is a cross-cutting tab rather than one
  // of the eight, so it is not in `subsections` and would otherwise be treated
  // as an invalid selection and immediately reset - which is exactly what
  // happened before this check existed: clicking "Scan history" left the
  // previous panel on screen with no error anywhere.
  useEffect(() => {
    if (!platformGroup) return;
    if (selected === HISTORY_TAB) return;
    const wanted = subsections.filter(s => s.group === platformGroup).map(s => s.id);
    if (wanted.length && !wanted.includes(selected)) {
      setSelected(wanted[0]);
    }
  }, [platformGroup, subsections, selected]);

  const [monetisation, setMonetisation] = useState<MonetisationData | null>(null);
  const [exporting, setExporting] = useState<'json' | 'csv' | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const platform = current?.platform ?? 'web';
    // Android has no client, so asking for its numbers would only ever produce
    // zeros. Fetch anyway so the moment a client starts reporting, the panel is
    // already wired to it.
    const results = await Promise.allSettled([
      monitoringApi.overview(days, platform),
      monitoringApi.health(days, platform),
      monitoringApi.feedback(days),
      monitoringApi.history(selected),
      monitoringApi.monetisation(days),
    ]);
    if (results[0].status === 'fulfilled') setOverview(results[0].value as ActivityData);
    if (results[1].status === 'fulfilled') setHealth(results[1].value as HealthData);
    if (results[2].status === 'fulfilled') setFeedback(results[2].value as FeedbackData);
    if (results[3].status === 'fulfilled') setHistory(results[3].value as HistoryData);
    if (results[4].status === 'fulfilled') setMonetisation(results[4].value as MonetisationData);

    const failures = results.filter(r => r.status === 'rejected');
    if (failures.length === results.length) {
      setError('The monitoring endpoints did not answer. Is the API running?');
    }
    setLoading(false);
  }, [days, current, selected]);

  useEffect(() => {
    load();
  }, [load]);

  async function runRollup() {
    setRolling(true);
    try {
      await monitoringApi.rollup(48);
      await load();
    } catch {
      setError('The rollup could not be triggered.');
    } finally {
      setRolling(false);
    }
  }

  async function runScan() {
    if (!scanEnabled || scanning || !selected || selected === HISTORY_TAB) return;
    setScanning(true);
    setLastScan(null);
    try {
      const result = await monitoringApi.scan(selected, days);
      setLastScan(result);
      // The scan is persisted, so the history tab is now stale.
      try {
        const fresh = (await monitoringApi.history(selected, 50)) as HistoryData;
        setHistory(fresh);
      } catch {
        // A stale history is not worth failing the whole scan over.
      }
    } catch {
      setError('The scan did not complete. Check that the API is running.');
    } finally {
      setScanning(false);
    }
  }

  async function runExport(format: 'json' | 'csv') {
    if (selected === HISTORY_TAB || !selected) return;
    setExporting(format);
    try {
      const data = await adminApi.exportSubsection(selected, days, format);
      const text = format === 'json' ? JSON.stringify(data, null, 2) : String(data);
      const blob = new Blob([text], {
        type: format === 'json' ? 'application/json' : 'text/csv',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selected}_${days}d.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError(`Export ${format.toUpperCase()} failed.`);
    } finally {
      setExporting(null);
    }
  }

  const groups = useMemo(() => {
    const out = new Map<string, MonitoringSubsection[]>();
    for (const s of subsections) {
      if (platformGroup && s.group !== platformGroup) continue;
      if (!out.has(s.group)) out.set(s.group, []);
      out.get(s.group)!.push(s);
    }
    return [...out.entries()];
  }, [subsections, platformGroup]);

  return (
    <div className="space-y-4">
      {/* Toolbar: range, freshness, manual rollup */}
      <Card className="flex flex-wrap items-center justify-between gap-3 !p-4">
        <div
          className="flex items-center gap-2 p-1.5"
          role="group"
          aria-label="Date range"
          style={{ borderRadius: 20, background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
        >
          {RANGES.map(r => {
            const on = days === r.days;
            return (
              <button
                key={r.days}
                type="button"
                onClick={() => setDays(r.days)}
                aria-pressed={on}
                className="px-4 py-2 text-xs font-medium transition-all duration-200"
                style={
                  on
                    ? {
                        borderRadius: 16,
                        background: 'var(--cp-primary)',
                        color: 'var(--cp-on-primary)',
                        boxShadow: 'var(--cp-clay)',
                      }
                    : { borderRadius: 16, background: 'transparent', color: 'var(--cp-muted)' }
                }
              >
                {r.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <FreshnessBadge overview={overview} />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={<Download size={16} strokeWidth={2} aria-hidden />}
            loading={exporting === 'json'}
            disabled={exporting !== null || selected === 'E_HISTORY'}
            onClick={() => runExport('json')}
            title="Download this subsection as JSON"
          >
            Export JSON
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={<Download size={16} strokeWidth={2} aria-hidden />}
            loading={exporting === 'csv'}
            disabled={exporting !== null || selected === 'E_HISTORY'}
            onClick={() => runExport('csv')}
            title="Download this subsection as CSV"
          >
            Export CSV
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={16} strokeWidth={2} aria-hidden />}
            loading={rolling}
            disabled={rolling}
            onClick={runRollup}
            title="Recompute the hourly rollup now instead of waiting for the timer"
          >
            Rebuild rollup
          </Button>
        </div>
      </Card>

      {error && (
        <div
          className="px-4 py-3 text-xs"
          style={{
            borderRadius: 12,
            border: '1px solid rgba(163,177,198,.3)',
            background: 'var(--cp-bg)',
            boxShadow: 'var(--cp-neu-inset)',
            color: 'var(--cp-danger)',
          }}
          role="alert"
          aria-live="polite"
        >
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4">
        {/* Subsection nav */}
        <Card className="!p-2 h-fit">
          <nav aria-label="Monitoring subsections">
            {groups.map(([group, items]) => (
              <div key={group} className="mb-3 last:mb-0">
                <div
                  className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider"
                  style={{ color: 'var(--cp-muted)' }}
                >
                  {group}
                </div>
                {items.map(s => {
                  const on = selected === s.id;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => setSelected(s.id)}
                      aria-current={on ? 'page' : undefined}
                      className="w-full text-left px-2 py-1.5 text-xs transition-all duration-200"
                      style={
                        on
                          ? {
                              borderRadius: 12,
                              background: 'var(--cp-primary)',
                              color: 'var(--cp-on-primary)',
                              boxShadow: 'var(--cp-clay)',
                              fontWeight: 600,
                            }
                          : { borderRadius: 12, color: 'var(--cp-muted)', fontWeight: 400 }
                      }
                    >
                      {s.title}
                    </button>
                  );
                })}
              </div>
            ))}

            {/* History is a tab across all eight, not a ninth subsection. It is
                kept out of the server-provided list so the count of eight stays
                authoritative and a scan allowlist keyed on those ids cannot drift. */}
            <div className="pt-2 mt-1" style={{ borderTop: '1px solid rgba(163,177,198,.25)' }}>
              <button
                type="button"
                onClick={() => setSelected('E_HISTORY')}
                aria-current={selected === 'E_HISTORY' ? 'page' : undefined}
                className="w-full text-left px-2 py-1.5 text-xs transition-all duration-200"
                style={
                  selected === 'E_HISTORY'
                    ? {
                        borderRadius: 12,
                        background: 'var(--cp-primary)',
                        color: 'var(--cp-on-primary)',
                        boxShadow: 'var(--cp-clay)',
                        fontWeight: 600,
                      }
                    : { borderRadius: 12, color: 'var(--cp-muted)', fontWeight: 400 }
                }
              >
                Scan history
              </button>
            </div>
          </nav>
        </Card>

        {/* Panel */}
        <div aria-live="polite">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <h2 className="text-base font-semibold" style={{ color: 'var(--cp-text)' }}>
                {selected === 'E_HISTORY' ? 'Scan history' : (current?.title ?? 'Monitoring')}
              </h2>
              <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {selected === 'E_HISTORY'
                  ? 'Every scan verdict, the incident log, and the tool-call audit'
                  : current
                    ? `${current.group} Â· ${current.id}`
                    : 'Loading subsection listâ€¦'}
              </p>
            </div>
            {selected !== 'E_HISTORY' && (
              <ScanButton
                subsection={selected}
                enabled={scanEnabled}
                llmEnabled={scanLlmEnabled}
                scanning={scanning}
                onScan={runScan}
              />
            )}
          </div>

          {lastScan && <ScanOutcome result={lastScan} llmEnabled={scanLlmEnabled} />}

          <PanelBody
            current={current}
            selected={selected}
            overview={overview}
            health={health}
            feedback={feedback}
            history={history}
            monetisation={monetisation}
            loading={loading}
          />
        </div>
      </div>
    </div>
  );
}

interface PanelBodyProps {
  current: MonitoringSubsection | null;
  selected: string;
  overview: ActivityData | null;
  health: HealthData | null;
  feedback: FeedbackData | null;
  history: HistoryData | null;
  monetisation: MonetisationData | null;
  loading: boolean;
}

function PanelBody({
  current,
  selected,
  overview,
  health,
  feedback,
  history,
  monetisation,
  loading,
}: PanelBodyProps) {
  // Scan history is dispatched on `selected`, not `current`.
  //
  // `current` is the server-provided subsection matching the selection, so it is
  // undefined for E_HISTORY - which is exactly why that tab is not in the
  // server's list. Checking `current` first (which this did originally) makes
  // the `case HISTORY_TAB` below unreachable, and the tab renders "Loadingâ€¦"
  // forever with nothing in the console to explain it.
  if (selected === HISTORY_TAB) {
    return <HistoryPanel data={history} loading={loading} />;
  }
  if (!current) return <Loading />;
  const awaiting = isAwaiting(current.group);
  switch (current.id) {
    case 'A_W_HEALTH':
    case 'A_A_HEALTH':
      return <HealthPanel data={health} loading={loading} awaiting={awaiting} />;
    case 'B_W_ACTIVITY':
    case 'B_A_ACTIVITY':
      return (
        <div className="space-y-4">
          <ActivityPanel
            data={overview}
            monetisation={monetisation}
            loading={loading}
            awaiting={awaiting}
          />
          {/* The subsection is titled "User Activity & Monetization", but
              ActivityPanel only carries four summary tiles. The detailed
              revenue / subscription / ad breakdown lived in MonetisationPanel
              and was never rendered anywhere, so it is mounted here to make
              the second half of the subsection actually visible. */}
          <MonetisationPanel data={monetisation} loading={loading} awaiting={awaiting} />
        </div>
      );
    case 'C_W_SECURITY':
    case 'C_A_SECURITY':
      return (
        <SecurityPanel
          data={overview as SecurityData | null}
          loading={loading}
          awaiting={awaiting}
        />
      );
    case 'D_W_FEEDBACK':
    case 'D_A_FEEDBACK':
      return <FeedbackPanel data={feedback} loading={loading} awaiting={awaiting} />;
    default:
      return <Loading />;
  }
}

function Loading() {
  return (
    <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }} aria-live="polite">
      Loadingâ€¦
    </Card>
  );
}

/**
 * "Scan now".
 *
 * `enabled` is the server's SCAN_ENABLED flag, read from the same
 * `/monitoring/subsections` call that supplies the list, so the button is
 * offered exactly when the backend would accept the request. It was previously
 * hardcoded off and blamed the installation, which stayed wrong the moment
 * scanning was switched on.
 */
function ScanButton({
  subsection,
  enabled,
  llmEnabled,
  scanning,
  onScan,
}: {
  subsection: string;
  enabled: boolean;
  llmEnabled: boolean;
  scanning: boolean;
  onScan: () => void;
}) {
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      icon={<ScanLine size={16} strokeWidth={2} aria-hidden />}
      onClick={onScan}
      disabled={!enabled || scanning}
      title={
        !enabled
          ? 'AI scanning is not enabled on this installation (SCAN_ENABLED)'
          : llmEnabled
            ? `Scan ${subsection} with the rule engine and the local LLM. On CPU the model can take minutes.`
            : `Scan ${subsection} with the rule engine only. Every figure comes from measured metrics.`
      }
    >
      {scanning ? 'Scanning…' : 'Scan now'}
    </Button>
  );
}

const SCAN_STATUS_TONES: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  healthy: 'success',
  warning: 'warning',
  critical: 'danger',
  error: 'neutral',
};

/**
 * What the scan just returned.
 *
 * Rendered inline rather than only in the history tab so the answer is where
 * the question was asked. The `model` field is shown verbatim: an admin should
 * be able to see that this verdict came from the rule engine and not from a
 * model, because only one of the two is authoritative on the numbers.
 */
function ScanOutcome({ result, llmEnabled }: { result: ScanResultResponse; llmEnabled: boolean }) {
  const missing = result.confidence?.missing_data ?? [];
  return (
    <Card className="mb-4">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <Badge tone={SCAN_STATUS_TONES[result.status] ?? 'neutral'}>{result.status}</Badge>
        <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          {result.model} · {result.duration_ms} ms · {new Date(result.created_at).toLocaleString()}
        </span>
      </div>
      <p className="text-sm" style={{ color: 'var(--cp-text)' }}>
        {result.summary}
      </p>
      {!llmEnabled && (
        <p className="mt-2 text-xs" style={{ color: 'var(--cp-muted)' }}>
          Rule engine only. The LLM narrative stage is off, so this summary is generated from the
          thresholds rather than written by a model.
        </p>
      )}
      {missing.length > 0 && (
        <p className="mt-1 text-xs" style={{ color: 'var(--cp-muted)' }}>
          Not measured: {missing.join(', ')}
        </p>
      )}
      {result.findings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {result.findings.map((f, i) => (
            <li key={`${f.title}-${i}`} className="text-xs">
              <span style={{ color: 'var(--cp-text)' }}>{f.title}</span>
              <span style={{ color: 'var(--cp-muted)' }}> — {f.severity}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/**
 * How old the newest rollup is.
 *
 * Green under two hours, amber past that. The reason it is always visible, even
 * next to healthy numbers: a dashboard can be confidently correct about data
 * that stopped arriving three days ago, and nothing else on the screen would
 * reveal that.
 */
function FreshnessBadge({ overview }: { overview: ActivityData | null }) {
  const lag = (overview as { data_freshness?: { rollup_lag_minutes?: number | null } } | null)
    ?.data_freshness?.rollup_lag_minutes;
  if (lag === null || lag === undefined) {
    return <Badge tone="neutral">No telemetry received</Badge>;
  }
  const stale = lag > 120;
  return (
    <Badge tone={stale ? 'warning' : 'success'} title="Age of the newest hourly rollup bucket">
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: stale ? 'var(--cp-warning)' : 'var(--cp-success)' }}
        aria-hidden="true"
      />
      {stale ? `Data ${Math.round(lag / 60)}h old` : 'Data current'}
    </Badge>
  );
}
