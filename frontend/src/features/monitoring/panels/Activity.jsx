/**
 * Subsection B: User Activity.
 *
 * Every figure here is paired with the period it is compared against. A DAU
 * number on its own is not information — 400 active users is excellent for a
 * campus of 900 and alarming for a campus of 40,000, and the dashboard cannot
 * know which.
 */
import { Panel, StatTile, EmptyState, AwaitingData, MiniBars, num, pctChange } from './components'

export function ActivityPanel({ data, monetisation, loading, awaiting }) {
  if (awaiting) {
    return (
      <div className="space-y-4">
        <Panel title="User activity">
          <AwaitingData
            what="No Android client is sending usage events yet, so there is nothing to count."
            how="Point an Android build at POST /collect/events with a platform of 'android' and a session_start event."
          />
        </Panel>
      </div>
    )
  }
  if (loading) return <Panel title="User activity"><EmptyState title="Loading…" /></Panel>
  if (!data) return <Panel title="User activity"><EmptyState title="Unavailable" detail="The overview endpoint did not answer." /></Panel>

  const a = data.activity || {}
  const dauDelta = pctChange(a.active_users, a.active_users_prev)
  const sessionsDelta = pctChange(a.sessions, a.sessions_prev)
  const nvr = a.new_vs_returning || {}
  const retention = a.retention || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Active users"
          value={num(a.active_users)}
          delta={dauDelta}
          deltaLabel="vs previous period"
          hint="distinct people with a session"
        />
        <StatTile
          label="Sessions"
          value={num(a.sessions)}
          delta={sessionsDelta}
          deltaLabel="vs previous period"
          hint={`${num(a.events)} events`}
        />
        <StatTile
          label="New users"
          value={num(nvr.new)}
          hint="first ever seen in this window"
        />
        <StatTile
          label="Returning"
          value={num(nvr.returning)}
          hint="active, not first-time"
        />
      </div>

      <Panel
        title="Retention"
        subtitle="Day-N, UTC calendar days. Each figure carries the cohort it was measured on — a percentage off a cohort of three is noise."
      >
        {Object.keys(retention).length === 0 || Object.values(retention).every((r) => r.cohort === 0) ? (
          <EmptyState
            title="No cohorts to measure yet"
            detail="Retention needs users whose first session was at least two full days ago. It will populate on its own once the app has a few days of traffic."
          />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {Object.entries(retention).map(([day, r]) => (
              <div key={day} className="rounded-xl border border-gray-200 p-3 text-center">
                <div className="text-[11px] font-medium text-gray-500 uppercase">Day {day}</div>
                <div className="mt-1 text-xl font-bold text-gray-900 tabular-nums">
                  {r.cohort === 0 ? '--' : `${r.pct}%`}
                </div>
                <div className="mt-0.5 text-[11px] text-gray-400">of {num(r.cohort)}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Top countries" subtitle="Coarse ISO country from the edge, never a full IP address.">
          {(a.countries || []).length === 0 ? (
            <EmptyState title="No country data yet" detail="Countries come from the client-supplied edge hint. Nothing has reported one." />
          ) : (
            <DimensionList rows={a.countries} />
          )}
        </Panel>

        <Panel title="App versions" subtitle="Web build versions reported by the client.">
          {(a.versions || []).length === 0 ? (
            <EmptyState title="No version data yet" detail="Versions arrive with the telemetry beacon once it is deployed." />
          ) : (
            <DimensionList rows={a.versions} />
          )}
        </Panel>
      </div>

      <Panel title="Event volume by hour" subtitle="From the hourly rollup, so it stays cheap over long windows.">
        {(a.hourly || []).length === 0 ? (
          <EmptyState title="Rollup has not run" detail="Volume charts read the hourly rollup table. Trigger a rollup from the toolbar above to populate it." />
        ) : (
          <>
            <MiniBars data={a.hourly.map((h) => ({ label: h.hour, value: h.events }))} />
            <div className="mt-2 flex justify-between text-[11px] text-gray-400">
              <span>{a.hourly[0]?.hour}</span>
              <span>{a.hourly[a.hourly.length - 1]?.hour}</span>
            </div>
          </>
        )}
      </Panel>

      {/* Monetization summary (inline in Activity panel) */}
      {monetisation && (
        <Panel title="Monetization summary" subtitle="Verified = store-validated. Unverified = client-claimed.">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatTile
              label="Verified revenue"
              value={num(monetisation.current?.revenue_verified_micros || 0, 0, 1e6)}
              delta={monetisation.changes?.verified_revenue_pct}
              deltaLabel="vs previous period"
              hint="store-validated only"
            />
            <StatTile
              label="Ad revenue"
              value={num(monetisation.current?.ad_revenue_micros || 0, 0, 1e6)}
              delta={monetisation.changes?.ad_revenue_pct}
              deltaLabel="vs previous period"
            />
            <StatTile
              label="Active subscriptions"
              value={num(monetisation.current?.active_subscriptions || 0)}
              delta={monetisation.changes?.subscriptions_pct}
              deltaLabel="vs previous period"
            />
            <StatTile
              label="Total revenue"
              value={num(monetisation.current?.total_revenue_micros || 0, 0, 1e6)}
              delta={monetisation.changes?.total_revenue_pct}
              deltaLabel="vs previous period"
            />
          </div>
        </Panel>
      )}

    </div>
  )
}

function DimensionList({ rows }) {
  const max = Math.max(...rows.map((r) => r.events), 1)
  return (
    <div className="space-y-2">
      {rows.slice(0, 8).map((r) => (
        <div key={r.value}>
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-gray-700">{r.value}</span>
            <span className="tabular-nums text-gray-500">{num(r.events)}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div className="h-full rounded-full bg-primary-400" style={{ width: `${(r.events / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}