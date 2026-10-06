/**
 * Match score.
 *
 * Two parts, because "85%" on its own is not actionable:
 *
 *   fill     - the share of the team's remaining gap this candidate closes.
 *              This is the signal that decides the ranking.
 *   overlap  - familiarity with the team's existing stack. Tie-break only.
 *
 * The bar markup mirrors the per-subject attendance bar in CampusPilot's
 * Attendance.jsx: a `h-1 rounded-full` track with an inline width and a
 * transition. The percentage is always rendered as text so the score is never
 * communicated by colour alone.
 */
import { toneFor } from '../../constants.js'

const TONE_BAR = {
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  danger: 'bg-danger-500',
}

const TONE_TEXT = {
  success: 'text-success-600',
  warning: 'text-warning-600',
  danger: 'text-danger-600',
}

function clamp(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 0
  return Math.round(Math.max(0, Math.min(100, number)) * 10) / 10
}

export default function MatchScore({
  score,
  fillPct,
  overlapPct,
  sameBranch = false,
  branchBonus = 0,
}) {
  if (score === null || score === undefined) return null

  const tone = toneFor(score)
  const width = clamp(score)
  const fill = clamp(fillPct ?? 0)
  const overlap = clamp(overlapPct ?? 0)

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">Match</span>
        <span className="flex items-center gap-2">
          {sameBranch && (
            <span className="px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 text-[10px] font-semibold uppercase">
              Same branch +{branchBonus}
            </span>
          )}
          <span className={`text-sm font-bold ${TONE_TEXT[tone]}`}>{score}%</span>
        </span>
      </div>

      <div
        className="w-full h-1 rounded-full bg-gray-200 mt-1"
        role="progressbar"
        aria-valuenow={width}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Match ${score} percent: closes ${fill} percent of their gap`}
      >
        <div
          className={`h-1 rounded-full ${TONE_BAR[tone]} transition-all`}
          style={{ width: `${width}%` }}
        />
      </div>

      <p className="text-[11px] text-gray-400 mt-1">
        Closes {fill}% of their gap
        {overlap > 0 && ` · knows ${overlap}% of their stack`}
      </p>
    </div>
  )
}

/**
 * Breakdown used on the detail view.
 *
 * Two independent bars rather than one segmented track: the two signals are
 * each measured 0-100 on their own, so stacking them on a shared track would
 * imply a proportion that does not exist (100% gap + 20% stack overflows the
 * track and flex-shrinks into something that contradicts its own labels).
 */
export function ScoreBreakdown({ fillPct = 0, overlapPct = 0 }) {
  const rows = [
    { label: 'Closes their gap', value: clamp(fillPct), track: 'bg-primary-500' },
    { label: 'Knows their stack', value: clamp(overlapPct), track: 'bg-gray-300' },
  ]

  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <div key={row.label}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-gray-500">{row.label}</span>
            <span className="text-[11px] font-semibold text-gray-700">{row.value}%</span>
          </div>
          <div
            className="w-full h-1 rounded-full bg-gray-100 mt-1"
            role="progressbar"
            aria-valuenow={row.value}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${row.label}: ${row.value} percent`}
          >
            <div className={`h-1 rounded-full ${row.track}`} style={{ width: `${row.value}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}