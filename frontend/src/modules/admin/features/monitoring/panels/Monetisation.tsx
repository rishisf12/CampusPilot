/**
 * Subsection B (Monetization): Revenue, subscriptions, ads.
 *
 * All figures are paired with the previous period. Revenue is split into
 * verified (store-validated) and unverified (client-claimed) so an admin
 * can distinguish auditable revenue from claims.
 */
import { BadgeCheck, CreditCard, Megaphone, Wallet } from 'lucide-react';
import { Panel, StatTile, EmptyState, AwaitingData, num } from '../components/components';

interface RevenueBucket {
  revenue_verified_micros?: number;
  revenue_unverified_micros?: number;
  ad_revenue_micros?: number;
  total_revenue_micros?: number;
  active_subscriptions?: number;
}

export interface MonetisationData {
  current?: RevenueBucket;
  previous?: RevenueBucket;
  changes?: {
    verified_revenue_pct?: number | null;
    ad_revenue_pct?: number | null;
    total_revenue_pct?: number | null;
    subscriptions_pct?: number | null;
  };
  ad_metrics?: {
    impressions?: number;
    clicks?: number;
    ecpm_micros?: number;
  };
  breakdowns?: {
    by_product?: Array<{ product: string; revenue_micros: number }>;
    by_country?: Array<{ country: string; revenue_micros: number }>;
  };
  note?: string;
}

interface MonetisationPanelProps {
  data?: MonetisationData | null;
  loading?: boolean;
  awaiting?: boolean;
}

const iconProps = {
  size: 20,
  strokeWidth: 2,
  'aria-hidden': true,
  style: { color: 'currentColor' },
} as const;

export function MonetisationPanel({ data, loading, awaiting }: MonetisationPanelProps) {
  if (awaiting) {
    return (
      <div className="space-y-4">
        <Panel title="Monetization">
          <AwaitingData
            what="No Android client is reporting purchase or ad events yet."
            how="POST to /collect/events with purchase_completed, ad_impression or ad_click events from the Android build."
          />
        </Panel>
      </div>
    );
  }
  if (loading)
    return (
      <Panel title="Monetization">
        <EmptyState title="Loading…" />
      </Panel>
    );
  if (!data)
    return (
      <Panel title="Monetization">
        <EmptyState title="Unavailable" detail="The monetisation endpoint did not answer." />
      </Panel>
    );

  const m = data.current || {};
  const p = data.previous || {};
  const c = data.changes || {};
  const ad = data.ad_metrics || {};
  const br = data.breakdowns || {};

  return (
    <div className="space-y-4" aria-live="polite">
      {/* Revenue overview */}
      <Panel
        title="Revenue overview"
        subtitle="Verified = store-validated. Unverified = client-claimed."
      >
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile
            label="Verified revenue"
            value={num(m.revenue_verified_micros)}
            delta={c.verified_revenue_pct ?? null}
            deltaLabel="vs previous period"
            hint="store-validated only"
            hue="mint"
            icon={<BadgeCheck {...iconProps} />}
          />
          <StatTile
            label="Unverified claims"
            value={num(m.revenue_unverified_micros)}
            delta={null}
            deltaLabel="not audited"
            hint="client-reported only"
            invertDelta
            hue="amber"
            icon={<CreditCard {...iconProps} />}
          />
          <StatTile
            label="Ad revenue"
            value={num(m.ad_revenue_micros)}
            delta={c.ad_revenue_pct ?? null}
            deltaLabel="vs previous period"
            hue="sky"
            icon={<Megaphone {...iconProps} />}
          />
          <StatTile
            label="Total revenue"
            value={num(m.total_revenue_micros)}
            delta={c.total_revenue_pct ?? null}
            deltaLabel="vs previous period"
            hue="indigo"
            icon={<Wallet {...iconProps} />}
          />
        </div>
      </Panel>

      {/* Subscriptions */}
      <Panel title="Subscriptions" subtitle="Active subscriptions from store-validated purchases.">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <StatTile
            label="Active subscriptions"
            value={num(m.active_subscriptions)}
            delta={c.subscriptions_pct ?? null}
            deltaLabel="vs previous period"
            hue="indigo"
          />
          <StatTile
            label="New this period"
            value={num(Math.max(0, (m.active_subscriptions || 0) - (p.active_subscriptions || 0)))}
            hint="net growth"
            hue="mint"
          />
        </div>
      </Panel>

      {/* Ad performance */}
      <Panel
        title="Ad performance"
        subtitle="Impressions, clicks and eCPM (revenue per 1000 impressions)."
      >
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label="Impressions" value={num(ad.impressions)} hue="sky" />
          <StatTile label="Clicks" value={num(ad.clicks)} hue="sky" />
          <StatTile
            label="CTR"
            value={
              ad.impressions ? `${(((ad.clicks ?? 0) / ad.impressions) * 100).toFixed(2)}%` : '--'
            }
            hint="clicks / impressions"
          />
          <StatTile label="eCPM" value={num(ad.ecpm_micros)} hint="revenue per 1000 impressions" />
        </div>
      </Panel>

      {/* Revenue by product */}
      <Panel title="Revenue by product" subtitle="Verified revenue only.">
        {(br.by_product || []).length === 0 ? (
          <EmptyState
            title="No product data yet"
            detail="Verified purchases arrive when ENABLE_STORE_VERIFY=true and a store receipt is validated."
          />
        ) : (
          <DimensionList
            rows={(br.by_product || []).map(r => ({ value: r.product, events: r.revenue_micros }))}
          />
        )}
      </Panel>

      {/* Revenue by country */}
      <Panel
        title="Revenue by country"
        subtitle="Verified revenue only. Country from the edge, never a full IP."
      >
        {(br.by_country || []).length === 0 ? (
          <EmptyState
            title="No country data yet"
            detail="Countries come from the client-supplied edge hint."
          />
        ) : (
          <DimensionList
            rows={(br.by_country || []).map(r => ({ value: r.country, events: r.revenue_micros }))}
          />
        )}
      </Panel>

      {/* Note about unverified */}
      <Panel title="Data quality">
        <p className="text-sm" style={{ color: 'var(--cp-muted)' }}>
          {data.note ||
            'Unverified purchases are labelled as claims, not revenue. Enable ENABLE_STORE_VERIFY to validate receipts with the app store.'}
        </p>
      </Panel>
    </div>
  );
}

function DimensionList({ rows }: { rows: Array<{ value: string; events: number }> }) {
  const max = Math.max(...rows.map(r => r.events), 1);
  return (
    <div className="space-y-2">
      {rows.slice(0, 8).map(r => (
        <div key={r.value}>
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium" style={{ color: 'var(--cp-text)' }}>
              {r.value}
            </span>
            <span className="tabular-nums" style={{ color: 'var(--cp-muted)' }}>
              {num(r.events)}
            </span>
          </div>
          <div
            className="mt-1 h-1.5 rounded-full overflow-hidden"
            style={{ background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
          >
            <div
              className="h-full rounded-full"
              style={{ width: `${(r.events / max) * 100}%`, background: 'var(--cp-primary)' }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
