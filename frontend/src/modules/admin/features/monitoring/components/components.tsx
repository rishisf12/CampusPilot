/**
 * Small presentational pieces shared by all eight monitoring subsections.
 *
 * Kept in one file because they exist to make the panels consistent with each
 * other, and consistency is the reason they are shared rather than because
 * any of them is substantial.
 */
import type { ReactNode } from 'react';

type StatusKey = 'healthy' | 'warning' | 'critical' | 'error' | 'unknown';

const STATUS_STYLES: Record<StatusKey, string> = {
  healthy: 'bg-success-50 text-success-700 border-success-200',
  warning: 'bg-warning-50 text-warning-700 border-warning-200',
  critical: 'bg-danger-50 text-danger-700 border-danger-200',
  error: 'bg-gray-100 text-gray-700 border-gray-300',
  unknown: 'bg-gray-50 text-gray-600 border-gray-200',
};

const STATUS_DOTS: Record<StatusKey, string> = {
  healthy: 'bg-success-500',
  warning: 'bg-warning-500',
  critical: 'bg-danger-500',
  error: 'bg-gray-400',
  unknown: 'bg-gray-300',
};

const STATUS_TEXT: Record<StatusKey, string> = {
  healthy: 'Healthy',
  warning: 'Warning',
  critical: 'Critical',
  error: 'Scan failed',
  unknown: 'Not scanned',
};

/**
 * A status pill.
 *
 * `unknown` is a first-class state, not an afterthought. A section that has
 * never been scanned is in a genuinely unknown state, and showing it as
 * "healthy" would be the single most misleading thing this dashboard could do:
 * an admin would read a clean bill of health for a system nobody has measured.
 */
export function StatusPill({ status = 'unknown', label }: { status?: string; label?: string }) {
  const key: StatusKey = status in STATUS_STYLES ? (status as StatusKey) : 'unknown';
  const text = label ?? STATUS_TEXT[key];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${STATUS_STYLES[key]}`}
    >
      <span className={`w-2 h-2 rounded-full ${STATUS_DOTS[key]}`} aria-hidden="true" />
      {text}
    </span>
  );
}

/**
 * One number with an optional change against the previous period.
 *
 * The delta is rendered in words ("up 12%") rather than colour alone. Colour is
 * the only channel a screen reader drops entirely, and "up" is not good news
 * for a crash count - so the direction has to be in text.
 */
export function StatTile({
  label,
  value,
  delta,
  deltaLabel,
  hint,
  invertDelta,
}: {
  label: string;
  value: ReactNode;
  delta?: number | null;
  deltaLabel?: string;
  hint?: ReactNode;
  invertDelta?: boolean;
}) {
  const numeric = typeof delta === 'number' && Number.isFinite(delta);
  const rising = numeric && (delta as number) > 0;
  const good = invertDelta ? !rising : rising;
  const deltaClass = !numeric
    ? 'text-gray-400'
    : Math.abs(delta as number) < 0.05
      ? 'text-gray-500'
      : good
        ? 'text-success-600'
        : 'text-danger-600';

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</div>
      <div className="mt-1 text-2xl font-bold text-gray-900 tabular-nums">{value}</div>
      {numeric && (
        <div className={`mt-1 text-xs font-medium ${deltaClass}`}>
          {rising ? 'up' : (delta as number) < 0 ? 'down' : 'unchanged'}{' '}
          {Math.abs(delta as number).toFixed(1)}%{deltaLabel ? ` ${deltaLabel}` : ''}
        </div>
      )}
      {hint && <div className="mt-1 text-xs text-gray-400">{hint}</div>}
    </div>
  );
}

/** Section shell: title, subtitle, right-hand actions. */
export function Panel({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-gray-100">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

/**
 * The empty state, used wherever a number cannot exist yet.
 *
 * The wording is specific about *why* there is no data. "No data" alone leaves
 * an admin unable to tell a feature that has not been deployed from one that
 * is silently broken, and those need very different responses.
 */
export function EmptyState({
  title = 'No data yet',
  detail,
  action,
}: {
  title?: string;
  detail?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="py-10 text-center">
      <div className="text-sm font-medium text-gray-700">{title}</div>
      {detail && <div className="mx-auto mt-1 max-w-md text-xs text-gray-500">{detail}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/**
 * A "waiting for first data" block for the Android subsections.
 *
 * There is no Android client yet. Rendering an empty dashboard of zeroes would
 * be indistinguishable from a healthy app, so these subsections say what is
 * missing and what to do about it instead.
 */
export function AwaitingData({ what, how }: { what: string; how?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50/60 p-6">
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-2 h-2 mt-1.5 rounded-full bg-gray-400" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-gray-700">Awaiting first data</p>
          <p className="mt-1 text-xs text-gray-600">{what}</p>
          {how && (
            <p className="mt-2 text-xs text-gray-500">
              <span className="font-medium">To start collecting:</span> {how}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/** Format an integer with thousands separators, or an em dash for null. */
export function num(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return Number(value).toLocaleString('en-IN');
}

/** Format micros of minor currency units as a currency string. */
export function money(micros: number | null | undefined, currency = 'INR'): string {
  if (micros === null || micros === undefined) return '--';
  const symbol = currency === 'INR' ? '₹' : '';
  const amount = micros / 1_000_000;
  return `${symbol}${amount.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Percentage change between two periods, guarding the zero baseline.
 *
 * Returns null rather than Infinity when the previous period was empty: "new
 * activity" and "grew by infinity percent" are different statements, and only
 * the first is true.
 */
export function pctChange(
  current: number | null | undefined,
  previous: number | null | undefined
): number | null {
  if (previous === null || previous === undefined) return null;
  if (previous === 0) return (current ?? 0) > 0 ? null : 0;
  return (((current ?? 0) - previous) / previous) * 100;
}

export interface MiniBarDatum {
  value: number;
  label?: string;
}

/** A tiny inline bar chart. Bars are relative to the largest value in the set. */
export function MiniBars({
  data,
  format = num,
  height = 96,
}: {
  data?: MiniBarDatum[] | null;
  format?: (value: number) => string;
  height?: number;
}) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div
      className="flex items-end gap-1"
      style={{ height }}
      role="img"
      aria-label={`Bar chart of ${data.length} values, largest ${format(max)}`}
    >
      {data.map((d, i) => (
        <div
          key={d.label ?? i}
          className="flex-1 min-w-[3px] rounded-t bg-primary-400"
          style={{ height: `${Math.max((d.value / max) * 100, d.value > 0 ? 4 : 1)}%` }}
          title={`${d.label}: ${format(d.value)}`}
        />
      ))}
    </div>
  );
}
