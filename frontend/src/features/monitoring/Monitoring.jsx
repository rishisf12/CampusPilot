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
import { useCallback, useEffect, useMemo, useState } from 'react'

import { monitoringApi } from '../../api'
import { ActivityPanel } from './Activity'
import { FeedbackPanel } from './Feedback'
import { HealthPanel } from './Health'
import { HistoryPanel } from './History'
import { SecurityPanel } from './Security'
import { StatusPill } from './components'

const RANGES = [
  { days: 1, label: '24h' },
  { days: 7, label: '7d' },
  { days: 30, label: '30d' },
  { days: 90, label: '90d' },
]

/** Rendered when a platform has never reported anything. */
function isAwaiting(group) {
  return group === 'Android App Monitoring'
}

/**
 * Scan history is a tab across all eight subsections, not a ninth one.
 *
 * Kept out of the server-provided list so the count of eight stays
 * authoritative and the backend's scan allowlist cannot drift from what the UI
 * offers.
 */
const HISTORY_TAB = 'E_HISTORY'

export default function Monitoring({ platformGroup }) {
  const [subsections, setSubsections] = useState([])
  const [selected, setSelected] = useState('A_W_HEALTH')
  const [days, setDays] = useState(7)
  const [overview, setOverview] = useState(null)
  const [health, setHealth] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [rolling, setRolling] = useState(false)

  useEffect(() => {
    let cancelled = false
    monitoringApi.subsections()
      .then((r) => { if (!cancelled) setSubsections(r.subsections || []) })
      .catch(() => { if (!cancelled) setError('Could not load the subsection list.') })
    return () => { cancelled = true }
  }, [])

  const current = useMemo(
    () => subsections.find((s) => s.id === selected) || null,
    [subsections, selected],
  )

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
    if (!platformGroup) return
    if (selected === HISTORY_TAB) return
    const wanted = subsections.filter((s) => s.group === platformGroup).map((s) => s.id)
    if (wanted.length && !wanted.includes(selected)) {
      setSelected(wanted[0])
    }
  }, [platformGroup, subsections, selected])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const platform = current?.platform ?? 'web'
    // Android has no client, so asking for its numbers would only ever produce
    // zeros. Fetch anyway so the moment a client starts reporting, the panel is
    // already wired to it.
    const results = await Promise.allSettled([
      monitoringApi.overview(days, platform),
      monitoringApi.health(days, platform),
      monitoringApi.feedback(days),
      monitoringApi.history(selected),
    ])
    if (results[0].status === 'fulfilled') setOverview(results[0].value)
    if (results[1].status === 'fulfilled') setHealth(results[1].value)
    if (results[2].status === 'fulfilled') setFeedback(results[2].value)
    if (results[3].status === 'fulfilled') setHistory(results[3].value)

    const failures = results.filter((r) => r.status === 'rejected')
    if (failures.length === results.length) {
      setError('The monitoring endpoints did not answer. Is the API running?')
    }
    setLoading(false)
  }, [days, current, selected])

  useEffect(() => { load() }, [load])

  async function runRollup() {
    setRolling(true)
    try {
      await monitoringApi.rollup(48)
      await load()
    } catch {
      setError('The rollup could not be triggered.')
    } finally {
      setRolling(false)
    }
  }

  const groups = useMemo(() => {
    const out = new Map()
    for (const s of subsections) {
      if (platformGroup && s.group !== platformGroup) continue
      if (!out.has(s.group)) out.set(s.group, [])
      out.get(s.group).push(s)
    }
    return [...out.entries()]
  }, [subsections, platformGroup])

  return (
    <div className="space-y-4">
      {/* Toolbar: range, freshness, manual rollup */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white border border-gray-200 rounded-xl px-4 py-3">
        <div className="flex items-center gap-1" role="group" aria-label="Date range">
          {RANGES.map((r) => (
            <button
              key={r.days}
              type="button"
              onClick={() => setDays(r.days)}
              aria-pressed={days === r.days}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors ${
                days === r.days
                  ? 'bg-primary-500 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <FreshnessBadge overview={overview} />
          <button
            type="button"
            onClick={runRollup}
            disabled={rolling}
            className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            title="Recompute the hourly rollup now instead of waiting for the timer"
          >
            {rolling ? 'Rolling up…' : 'Rebuild rollup'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-danger-200 bg-danger-50 px-4 py-3 text-xs text-danger-800">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4">
        {/* Subsection nav */}
        <nav className="bg-white border border-gray-200 rounded-xl p-2 h-fit" aria-label="Monitoring subsections">
          {groups.map(([group, items]) => (
            <div key={group} className="mb-3 last:mb-0">
              <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-gray-400">
                {group}
              </div>
              {items.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelected(s.id)}
                  aria-current={selected === s.id ? 'page' : undefined}
                  className={`w-full text-left px-2 py-1.5 rounded-lg text-xs transition-colors ${
                    selected === s.id
                      ? 'bg-primary-50 text-primary-700 font-semibold'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {s.title}
                </button>
              ))}
            </div>
          ))}

          {/* History is a tab across all eight, not a ninth subsection. It is
              kept out of the server-provided list so the count of eight stays
              authoritative and a scan allowlist keyed on those ids cannot drift. */}
          <div className="border-t border-gray-100 pt-2 mt-1">
            <button
              type="button"
              onClick={() => setSelected('E_HISTORY')}
              aria-current={selected === 'E_HISTORY' ? 'page' : undefined}
              className={`w-full text-left px-2 py-1.5 rounded-lg text-xs transition-colors ${
                selected === 'E_HISTORY'
                  ? 'bg-primary-50 text-primary-700 font-semibold'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              Scan history
            </button>
          </div>
        </nav>

        {/* Panel */}
        <div>
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <h2 className="text-base font-semibold text-gray-900">
                {selected === 'E_HISTORY' ? 'Scan history' : current?.title ?? 'Monitoring'}
              </h2>
              <p className="text-xs text-gray-500">
                {selected === 'E_HISTORY'
                  ? 'Every scan verdict, the incident log, and the tool-call audit'
                  : current
                    ? `${current.group} · ${current.id}`
                    : 'Loading subsection list…'}
              </p>
            </div>
            {selected !== 'E_HISTORY' && <ScanButton subsection={selected} enabled={false} />}
          </div>

          <PanelBody
            current={current}
            selected={selected}
            overview={overview}
            health={health}
            feedback={feedback}
            history={history}
            loading={loading}
          />
        </div>
      </div>
    </div>
  )
}

function PanelBody({ current, selected, overview, health, feedback, history, loading }) {
  // Scan history is dispatched on `selected`, not `current`.
  //
  // `current` is the server-provided subsection matching the selection, so it is
  // undefined for E_HISTORY - which is exactly why that tab is not in the
  // server's list. Checking `current` first (which this did originally) makes
  // the `case HISTORY_TAB` below unreachable, and the tab renders "Loading…"
  // forever with nothing in the console to explain it.
  if (selected === HISTORY_TAB) {
    return <HistoryPanel data={history} loading={loading} />
  }
  if (!current) return <Loading />
  const awaiting = isAwaiting(current.group)
  switch (current.id) {
    case 'A_W_HEALTH':
    case 'A_A_HEALTH':
      return <HealthPanel data={health} loading={loading} awaiting={awaiting} />
    case 'B_W_ACTIVITY':
    case 'B_A_ACTIVITY':
      return <ActivityPanel data={overview} loading={loading} awaiting={awaiting} />
    case 'C_W_SECURITY':
    case 'C_A_SECURITY':
      return <SecurityPanel data={overview} loading={loading} awaiting={awaiting} />
    case 'D_W_FEEDBACK':
    case 'D_A_FEEDBACK':
      return <FeedbackPanel data={feedback} loading={loading} awaiting={awaiting} />
    default:
      return <Loading />
  }
}

function Loading() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-400">
      Loading…
    </div>
  )
}

/**
 * "Scan now" placeholder.
 *
 * Disabled on purpose in this phase. It is rendered rather than omitted so the
 * shape of the UI is settled, and it says why it is off — a permanently greyed
 * button with no explanation is worse than no button.
 */
function ScanButton({ subsection, enabled }) {
  return (
    <button
      type="button"
      disabled={!enabled}
      title={
        enabled
          ? 'Run a read-only AI scan of this subsection'
          : 'AI scanning is not enabled on this installation (SCAN_ENABLED)'
      }
      className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 text-gray-400 cursor-not-allowed"
    >
      Scan now
    </button>
  )
}

/**
 * How old the newest rollup is.
 *
 * Green under two hours, amber past that. The reason it is always visible, even
 * next to healthy numbers: a dashboard can be confidently correct about data
 * that stopped arriving three days ago, and nothing else on the screen would
 * reveal that.
 */
function FreshnessBadge({ overview }) {
  const lag = overview?.data_freshness?.rollup_lag_minutes
  if (lag === null || lag === undefined) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-1 rounded-full border border-gray-200 bg-gray-50 text-gray-600">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-400" aria-hidden="true" />
        No telemetry received
      </span>
    )
  }
  const stale = lag > 120
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-1 rounded-full border ${
        stale
          ? 'bg-warning-50 border-warning-200 text-warning-800'
          : 'bg-success-50 border-success-200 text-success-700'
      }`}
      title="Age of the newest hourly rollup bucket"
    >
      <span className={`w-1.5 h-1.5 rounded-full ${stale ? 'bg-warning-500' : 'bg-success-500'}`} aria-hidden="true" />
      {stale ? `Data ${Math.round(lag / 60)}h old` : 'Data current'}
    </span>
  )
}