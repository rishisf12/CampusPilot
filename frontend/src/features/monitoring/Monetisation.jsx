/**
 * Subsection B (Monetization): Revenue, subscriptions, ads.
 *
 * All figures are paired with the previous period. Revenue is split into
 * verified (store-validated) and unverified (client-claimed) so an admin
 * can distinguish auditable revenue from claims.
 */
import { Panel, StatTile, EmptyState, AwaitingData, num, pctChange, pct } from './components'

export function MonetisationPanel({ data, loading, awaiting }) {
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
    )
  }
  if (loading) return <Panel title="Monetization"><EmptyState title="Loading…" /></Panel>
  if (!data) return <Panel title="Monetization"><EmptyState title="Unavailable" detail="The monetisation endpoint did not answer." /></Panel>

  const m = data.current || {}
  const p = data.previous || {}
  const c = data.changes || {}
  const ad = data.ad_metrics || {}
  const br = data.breakdowns || {}

  return (
    <div className="space-y-4">
      {/* Revenue overview */}
      <Panel title="Revenue overview" subtitle="Verified = store-validated. Unverified = client-claimed.">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile
            label="Verified revenue"
            value={num(m.revenue_verified_micros, 0, 1e6)}
            delta={c.verified_revenue_pct}
            deltaLabel="vs previous period"
            hint="store-validated only"
          />
          <StatTile
            label="Unverified claims"
            value={num(m.revenue_unverified_micros, 0, 1e6)}
            delta={null}
            deltaLabel="not audited"
            hint="client-reported only"
            invertDelta
          />
          <StatTile
            label="Ad revenue"
            value={num(m.ad_revenue_micros, 0, 1e6)}
            delta={c.ad_revenue_pct}
            deltaLabel="vs previous period"
          />
          <StatTile
            label="Total revenue"
            value={num(m.total_revenue_micros, 0, 1e6)}
            delta={c.total_revenue_pct}
            deltaLabel="vs previous period"
          />
        </div>
      </Panel>

      {/* Subscriptions */}
      <Panel title="Subscriptions" subtitle="Active subscriptions from store-validated purchases.">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <StatTile
            label="Active subscriptions"
            value={num(m.active_subscriptions)}
            delta={c.subscriptions_pct}
            deltaLabel="vs previous period"
          />
          <StatTile
            label="New this period"
            value={num(Math.max(0, (m.active_subscriptions || 0) - (p.active_subscriptions || 0)))}
            hint="net growth"
          />
        </div>
      </Panel>

      {/* Ad performance */}
      <Panel title="Ad performance" subtitle="Impressions, clicks and eCPM (revenue per 1000 impressions).">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile
            label="Impressions"
            value={num(ad.impressions)}
          />
          <StatTile
            label="Clicks"
            value={num(ad.clicks)}
          />
          <StatTile
            label="CTR"
            value={ad.impressions ? `${((ad.clicks / ad.impressions) * 100).toFixed(2)}%` : '--'}
            hint="clicks / impressions"
          />
          <StatTile
            label="eCPM"
            value={num(ad.ecpm_micros, 0, 1e6)}
            hint="revenue per 1000 impressions"
          />
        </div>
      </Panel>

      {/* Revenue by product */}
      <Panel title="Revenue by product" subtitle="Verified revenue only.">
        {(br.by_product || []).length === 0 ? (
          <EmptyState title="No product data yet" detail="Verified purchases arrive when ENABLE_STORE_VERIFY=true and a store receipt is validated." />
        ) : (
          <DimensionList rows={br.by_product.map(r => ({ value: r.product, events: r.revenue_micros }))} valueFormatter={v => num(v, 0, 1e6)} />
        )}
      </Panel>

      {/* Revenue by country */}
      <Panel title="Revenue by country" subtitle="Verified revenue only. Country from the edge, never a full IP.">
        {(br.by_country || []).length === 0 ? (
          <EmptyState title="No country data yet" detail="Countries come from the client-supplied edge hint." />
        ) : (
          <DimensionList rows={br.by_country.map(r => ({ value: r.country, events: r.revenue_micros }))} valueFormatter={v => num(v, 0, 1e6)} />
        )}
      </Panel>

      {/* Note about unverified */}
      <Panel title="Data quality">
        <p className="text-sm text-gray-600">
          {data.note || 'Unverified purchases are labelled as claims, not revenue. Enable ENABLE_STORE_VERIFY to validate receipts with the app store.'}
        </p>
      </Panel>
    </div>
  )
}

function DimensionList({ rows, valueFormatter = num }) {
  const max = Math.max(...rows.map((r) => r.events), 1)
  return (
    <div className="space-y-2">
      {rows.slice(0, 8).map((r) => (
        <div key={r.value}>
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-gray-700">{r.value}</span>
            <span className="tabular-nums text-gray-500">{valueFormatter(r.events)}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div className="h-full rounded-full bg-primary-400" style={{ width: `${(r.events / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}