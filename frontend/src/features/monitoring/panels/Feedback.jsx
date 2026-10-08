/**
 * Subsection D: Feedback.
 *
 * Reads aggregates over the existing feedback table. The Feedback Responses
 * feature is deliberately untouched - this is a separate, read-only view that
 * counts and buckets submissions without changing how they are answered.
 */
import { Panel, StatTile, EmptyState, AwaitingData, MiniBars, num, pctChange } from './components'

const TOPIC_LABELS = {
  timetable: 'Timetable & rooms',
  attendance: 'Attendance',
  exams: 'Exams & seating',
  ocr: 'Uploads / OCR',
  teams: 'Teams & hackathons',
  passkey: 'Sign-in & passkeys',
  app_bug: 'Bugs & crashes',
  ui: 'Interface',
  suggestion: 'Feature requests',
}

export function FeedbackPanel({ data, loading, awaiting, platform }) {
  if (awaiting) {
    return (
      <Panel title="Feedback">
        <AwaitingData
          what="Android-side feedback has not been wired up yet."
          how="Send a feedback_submitted event to /collect/events with platform 'android'."
        />
      </Panel>
    )
  }
  if (loading) return <Panel title="Feedback"><EmptyState title="Loading…" /></Panel>
  if (!data) return <Panel title="Feedback"><EmptyState title="Unavailable" detail="The feedback analysis endpoint did not answer." /></Panel>

  if (data.total === 0) {
    return (
      <Panel title="Feedback">
        <EmptyState
          title="No submissions in this window"
          detail="Widen the date range, or submit a test message to confirm the pipeline end to end."
        />
      </Panel>
    )
  }

  const s = data.sentiment || {}
  const cov = data.coverage || {}
  const perDay = (data.per_day || []).map((d) => ({ label: d.date, value: d.count }))
  const negativeShare = s.available && data.sampled
    ? (s.negative / data.sampled) * 100
    : null

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Submissions" value={num(data.total)} hint={`${num(data.sampled)} analysed`} />
        <StatTile
          label="Negative"
          value={s.available ? num(s.negative) : '--'}
          hint={negativeShare === null ? 'sentiment unavailable' : `${negativeShare.toFixed(0)}% of analysed`}
          invertDelta
        />
        <StatTile label="Reply rate" value={`${cov.reply_rate_pct}%`} hint={`${num(cov.answered)} answered`} />
        <StatTile label="With attachment" value={num(cov.with_attachment)} hint="screenshots, PDFs" />
      </div>

      {data.truncated && (
        <p className="rounded-lg bg-gray-50 border border-gray-200 px-3 py-2 text-xs text-gray-600">
          Showing the {num(data.sampled)} most recent of {num(data.total)} submissions.
          Sentiment and topics are computed on that sample, not on all of them.
        </p>
      )}

      <Panel title="Volume over time">
        <MiniBars data={perDay} height={110} />
        <div className="mt-2 flex justify-between text-[11px] text-gray-400">
          <span>{perDay[0]?.label}</span>
          <span>{perDay[perDay.length - 1]?.label}</span>
        </div>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel
          title="Sentiment"
          subtitle="Lexicon-based (VADER). Fast and local; it under-reads sarcasm and reads short factual complaints as neutral."
        >
          {!s.available ? (
            <EmptyState title="Sentiment unavailable" detail="vaderSentiment is not installed in this environment." />
          ) : (
            <div className="space-y-3">
              <SentimentBar sentiment={s} sampled={data.sampled} />
              <p className="text-xs text-gray-500">
                Mean compound polarity {s.mean}. This is a lexicon score, not a
                judgement about the product.
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Topics" subtitle="Keyword buckets. A message matching none appears under no topic rather than being forced into one.">
          {(data.topics || []).length === 0 ? (
            <EmptyState title="No topics matched" detail="None of the submissions matched a known topic keyword." />
          ) : (
            <div className="space-y-2">
              {data.topics.map((t) => (
                <div key={t.topic} className="flex items-center justify-between text-xs">
                  <span className="font-medium text-gray-700">{TOPIC_LABELS[t.topic] || t.topic}</span>
                  <span className="tabular-nums text-gray-500">{num(t.count)} · {t.pct}%</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="What this is not">
        <p className="text-xs text-gray-600">
          This panel counts and classifies submissions. It does not change how
          feedback is stored, displayed or answered — the Feedback Responses view
          is exactly as it was. Individual message text is not returned by this
          endpoint; only aggregates are.
        </p>
      </Panel>
    </div>
  )
}

function SentimentBar({ sentiment, sampled }) {
  const total = sampled || 1
  const segments = [
    { key: 'positive', label: 'Positive', value: sentiment.positive, cls: 'bg-success-400' },
    { key: 'neutral', label: 'Neutral', value: sentiment.neutral, cls: 'bg-gray-300' },
    { key: 'negative', label: 'Negative', value: sentiment.negative, cls: 'bg-danger-400' },
  ]
  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden bg-gray-100">
        {segments.map((s) =>
          s.value > 0 ? (
            <div key={s.key} className={s.cls} style={{ width: `${(s.value / total) * 100}%` }}
                 title={`${s.label}: ${s.value}`} />
          ) : null
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-3">
        {segments.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span className={`w-2.5 h-2.5 rounded-sm ${s.cls}`} aria-hidden="true" />
            {s.label} <span className="tabular-nums font-medium">{num(s.value)}</span>
          </span>
        ))}
      </div>
    </div>
  )
}