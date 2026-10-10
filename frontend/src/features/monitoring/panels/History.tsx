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
import { Panel, StatTile, StatusPill, EmptyState, num } from '../components/components';

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
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Scans recorded" value={num(scans.length)} />
        <StatTile label="Open incidents" value={num(open.length)} invertDelta />
        <StatTile label="Total incidents" value={num(incidents.length)} />
        <StatTile
          label="Tool calls audited"
          value={num(toolCalls.length)}
          hint="every scan tool invocation"
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
                className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="text-xs font-medium text-gray-800">{inc.subsection}</div>
                  <div className="text-[11px] text-gray-500">
                    started {inc.started_at}
                    {inc.ended_at ? ` · cleared ${inc.ended_at}` : ' · not cleared yet'}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <StatusPill status={inc.status} />
                  <span className="text-xs tabular-nums text-gray-500">
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
              <div key={s.scan_id} className="rounded-lg border border-gray-200 px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium text-gray-800">{s.subsection}</span>
                  <StatusPill status={s.status} />
                </div>
                {s.summary && <p className="mt-1 text-xs text-gray-600">{s.summary}</p>}
                <div className="mt-1 text-[11px] text-gray-400">
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
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-left text-gray-500">
                <tr>
                  <th className="py-1.5 pr-3 font-medium">Scan</th>
                  <th className="py-1.5 pr-3 font-medium">Tool</th>
                  <th className="py-1.5 pr-3 font-medium">Metric key</th>
                  <th className="py-1.5 pr-3 font-medium text-right">Rows</th>
                  <th className="py-1.5 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {toolCalls.slice(0, 40).map((t, i) => (
                  <tr key={`${t.scan_id}-${i}`} className="border-t border-gray-100">
                    <td className="py-1.5 pr-3 font-mono text-gray-500">{t.scan_id.slice(0, 8)}</td>
                    <td className="py-1.5 pr-3 text-gray-800">{t.tool}</td>
                    <td className="py-1.5 pr-3 font-mono text-gray-500">{t.metric_key || '--'}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums text-gray-700">
                      {num(t.row_count)}
                    </td>
                    <td className="py-1.5 text-gray-500">{t.at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
