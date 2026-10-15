/**
 * Subsection E: History.
 *
 * The scan history and the incident log. Phase 1 records the structure and the
 * read path but has no scanner running yet, so this renders an honest
 * "nothing has been scanned" state rather than an empty chart.
 *
 * The incident log derives duration from status transitions instead of storing
 * it, which is why an open incident shows "ongoing" and no number: it has no end
 * time yet, and inventing a duration would mean rewriting rows every time a
 * later scan closed it.
 */
import { ClipboardList, History, Siren, Wrench } from 'lucide-react';
import { Panel, StatTile, StatusPill, EmptyState, num } from '../components/components';
import { Table } from '@/components/ui';

interface ScanRow {
  scan_id: string;
  subsection: string;
  status: string;
  summary?: string | null;
  created_at: string;
  duration_ms?: number | null;
  model?: string | null;
  window?: { start?: string | null; end?: string | null };
}

interface IncidentRow {
  subsection: string;
  status: string;
  started_at: string;
  ended_at?: string | null;
  open: boolean;
  duration_s?: number | null;
}

interface ToolCallRow {
  scan_id: string;
  tool: string;
  metric_key?: string | null;
  row_count?: number | null;
  at: string;
}

export interface HistoryData {
  scans?: ScanRow[];
  incidents?: IncidentRow[];
  tool_calls?: ToolCallRow[];
}

interface HistoryPanelProps {
  data?: HistoryData | null;
  loading?: boolean;
  selected?: string | null;
  onSelect?: (subsection: string | null) => void;
}

const iconProps = {
  size: 20,
  strokeWidth: 2,
  'aria-hidden': true,
  style: { color: 'currentColor' },
} as const;

export function HistoryPanel({ data, loading }: HistoryPanelProps) {
  if (loading)
    return (
      <Panel title="Scan history">
        <EmptyState title="Loading…" />
      </Panel>
    );

  const scans = data?.scans || [];
  const incidents = data?.incidents || [];
  const toolCalls = data?.tool_calls || [];
  const open = incidents.filter(i => i.open);

  return (
    <div className="space-y-4" aria-live="polite">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Scans recorded"
          value={num(scans.length)}
          hue="indigo"
          icon={<History {...iconProps} />}
        />
        <StatTile
          label="Open incidents"
          value={num(open.length)}
          invertDelta
          hue="coral"
          icon={<Siren {...iconProps} />}
        />
        <StatTile
          label="Total incidents"
          value={num(incidents.length)}
          hue="amber"
          icon={<ClipboardList {...iconProps} />}
        />
        <StatTile
          label="Tool calls audited"
          value={num(toolCalls.length)}
          hint="every scan tool invocation"
          hue="sky"
          icon={<Wrench {...iconProps} />}
        />
      </div>

      <Panel
        title="Incident log"
        subtitle="Derived from status transitions. An incident runs from the scan that raised it to the scan that cleared it."
      >
        {incidents.length === 0 ? (
          <EmptyState
            title="No incidents recorded"
            detail="An incident appears here the first time a scan returns Warning or Critical."
          />
        ) : (
          <div className="space-y-2">
            {incidents.map((inc, i) => (
              <div
                key={`${inc.subsection}-${inc.started_at}-${i}`}
                className="flex items-center justify-between gap-3 px-3 py-2 transition-colors"
                style={{
                  borderRadius: 12,
                  border: '1px solid rgba(163,177,198,.3)',
                  background: 'var(--cp-surface)',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'var(--cp-bg)';
                  e.currentTarget.style.boxShadow = 'var(--cp-neu-inset)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'var(--cp-surface)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div className="min-w-0">
                  <div className="text-xs font-medium" style={{ color: 'var(--cp-text)' }}>
                    {inc.subsection}
                  </div>
                  <div className="text-[11px]" style={{ color: 'var(--cp-muted)' }}>
                    started {inc.started_at}
                    {inc.ended_at ? ` · cleared ${inc.ended_at}` : ' · not cleared yet'}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <StatusPill status={inc.status} />
                  <span className="text-xs tabular-nums" style={{ color: 'var(--cp-muted)' }}>
                    {inc.open ? 'ongoing' : formatDuration(inc.duration_s)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Scan history"
        subtitle="Every verdict is kept. A scan that errored is not the same as one that found a problem."
      >
        {scans.length === 0 ? (
          <EmptyState
            title="No scans have run yet"
            detail="Each subsection gets its own Scan now button. Scans are read-only and never change the data they measure."
          />
        ) : (
          <div className="space-y-2">
            {scans.map(s => (
              <div
                key={s.scan_id}
                className="px-3 py-2"
                style={{
                  borderRadius: 12,
                  border: '1px solid rgba(163,177,198,.3)',
                  background: 'var(--cp-surface)',
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium" style={{ color: 'var(--cp-text)' }}>
                    {s.subsection}
                  </span>
                  <StatusPill status={s.status} />
                </div>
                {s.summary && (
                  <p className="mt-1 text-xs" style={{ color: 'var(--cp-muted)' }}>
                    {s.summary}
                  </p>
                )}
                <div className="mt-1 text-[11px]" style={{ color: 'var(--cp-muted)' }}>
                  {s.created_at} · {s.duration_ms} ms · window {s.window?.start?.slice(0, 16)} →{' '}
                  {s.window?.end?.slice(0, 16)}
                  {s.model ? ` · ${s.model}` : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Tool call audit" subtitle="What each scan actually asked the database for.">
        {toolCalls.length === 0 ? (
          <EmptyState
            title="No tool calls recorded"
            detail="Every scan records each tool it calls here, which is what makes 'the scan never invented a number' a checkable claim rather than an assertion."
          />
        ) : (
          <Table
            head={['Scan', 'Tool', 'Metric key', 'Rows', 'When']}
            rows={toolCalls.slice(0, 40).map((t, i) => [
              <span key={`s-${i}`} className="font-mono" style={{ color: 'var(--cp-muted)' }}>
                {t.scan_id.slice(0, 8)}
              </span>,
              <span key={`t-${i}`} style={{ color: 'var(--cp-text)' }}>
                {t.tool}
              </span>,
              <span key={`m-${i}`} className="font-mono" style={{ color: 'var(--cp-muted)' }}>
                {t.metric_key || '--'}
              </span>,
              <span
                key={`r-${i}`}
                className="tabular-nums"
                style={{ color: 'var(--cp-text)', textAlign: 'right', display: 'block' }}
              >
                {num(t.row_count)}
              </span>,
              <span key={`w-${i}`} style={{ color: 'var(--cp-muted)' }}>
                {t.at}
              </span>,
            ])}
          />
        )}
      </Panel>
    </div>
  );
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '--';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}
