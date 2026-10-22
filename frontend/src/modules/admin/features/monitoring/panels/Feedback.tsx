/**
 * Subsection D: Feedback.
 *
 * Reads aggregates over the existing feedback table. The Feedback Responses
 * feature is deliberately untouched - this is a separate, read-only view that
 * counts and buckets submissions without changing how they are answered.
 */
import { Inbox, MessageCircleWarning, Paperclip, Reply } from 'lucide-react';
import { Panel, StatTile, EmptyState, AwaitingData, MiniBars, num } from '../components/components';
import type { MiniBarDatum } from '../components/components';

const TOPIC_LABELS: Record<string, string> = {
  timetable: 'Timetable & rooms',
  attendance: 'Attendance',
  exams: 'Exams & seating',
  ocr: 'Uploads / OCR',
  teams: 'Teams & hackathons',
  passkey: 'Sign-in & passkeys',
  app_bug: 'Bugs & crashes',
  ui: 'Interface',
  suggestion: 'Feature requests',
};

interface SentimentData {
  available?: boolean;
  positive?: number;
  neutral?: number;
  negative?: number;
  mean?: number | string;
}

export interface FeedbackData {
  total?: number;
  sampled?: number;
  truncated?: boolean;
  sentiment?: SentimentData;
  coverage?: {
    reply_rate_pct?: number;
    answered?: number;
    with_attachment?: number;
  };
  per_day?: Array<{ date: string; count: number }>;
  topics?: Array<{ topic: string; count: number; pct: number }>;
  /**
   * The MCP tool answer behind this panel.
   *
   * The figures above are computed live over the `feedback` table - the
   * actual student submissions, scored with a lexicon and sampled. The tool
   * reads the *rolled-up* analysis the collector recorded, so it answers a
   * different question: how the mix of topics and the sentiment balance
   * moved over the collected windows.
   *
   * They are shown side by side rather than merged, because they are not the
   * same measurement - and a panel that presented one as the other would be
   * confidently wrong half the time.
   */
  mcp?: {
    tools?: string[];
    failed?: Record<string, string>;
    themes?: {
      topics?: Array<{ topic: string; count: number }>;
      total_count?: number;
      sentiment?: {
        positive?: number;
        neutral?: number;
        negative?: number;
        mean?: number;
      };
      windows_covered?: number;
    } | null;
  };
}

interface FeedbackPanelProps {
  data?: FeedbackData | null;
  loading?: boolean;
  awaiting?: boolean;
  platform?: string;
}

const iconProps = {
  size: 20,
  strokeWidth: 2,
  'aria-hidden': true,
  style: { color: 'currentColor' },
} as const;

export function FeedbackPanel({ data, loading, awaiting }: FeedbackPanelProps) {
  if (awaiting) {
    return (
      <Panel title="Feedback">
        <AwaitingData
          what="Android-side feedback has not been wired up yet."
          how="Send a feedback_submitted event to /collect/events with platform 'android'."
        />
      </Panel>
    );
  }
  if (loading)
    return (
      <Panel title="Feedback">
        <EmptyState title="Loading…" />
      </Panel>
    );
  if (!data)
    return (
      <Panel title="Feedback">
        <EmptyState title="Unavailable" detail="The feedback analysis endpoint did not answer." />
      </Panel>
    );

  if (data.total === 0) {
    return (
      <Panel title="Feedback">
        <EmptyState
          title="No submissions in this window"
          detail="Widen the date range, or submit a test message to confirm the pipeline end to end."
        />
      </Panel>
    );
  }

  const s = data.sentiment || {};
  const cov = data.coverage || {};
  const perDay: MiniBarDatum[] = (data.per_day || []).map(d => ({ label: d.date, value: d.count }));
  const negativeShare =
    s.available && data.sampled ? ((s.negative ?? 0) / data.sampled) * 100 : null;

  return (
    <div className="space-y-4" aria-live="polite">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Submissions"
          value={num(data.total)}
          hint={`${num(data.sampled)} analysed`}
          hue="indigo"
          icon={<Inbox {...iconProps} />}
        />
        <StatTile
          label="Negative"
          value={s.available ? num(s.negative) : '--'}
          hint={
            negativeShare === null
              ? 'sentiment unavailable'
              : `${negativeShare.toFixed(0)}% of analysed`
          }
          invertDelta
          hue="coral"
          icon={<MessageCircleWarning {...iconProps} />}
        />
        <StatTile
          label="Reply rate"
          value={`${cov.reply_rate_pct}%`}
          hint={`${num(cov.answered)} answered`}
          hue="mint"
          icon={<Reply {...iconProps} />}
        />
        <StatTile
          label="With attachment"
          value={num(cov.with_attachment)}
          hint="screenshots, PDFs"
          hue="sky"
          icon={<Paperclip {...iconProps} />}
        />
      </div>

      {data.truncated && (
        <p
          className="px-3 py-2 text-xs"
          style={{
            borderRadius: 12,
            background: 'var(--cp-bg)',
            boxShadow: 'var(--cp-neu-inset)',
            color: 'var(--cp-muted)',
          }}
        >
          Showing the {num(data.sampled)} most recent of {num(data.total)} submissions. Sentiment
          and topics are computed on that sample, not on all of them.
        </p>
      )}

      <Panel title="Volume over time">
        <MiniBars data={perDay} height={110} />
        <div className="mt-2 flex justify-between text-[11px]" style={{ color: 'var(--cp-muted)' }}>
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
            <EmptyState
              title="Sentiment unavailable"
              detail="vaderSentiment is not installed in this environment."
            />
          ) : (
            <div className="space-y-3">
              <SentimentBar sentiment={s} sampled={data.sampled ?? 0} />
              <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                Mean compound polarity {s.mean}. This is a lexicon score, not a judgement about the
                product.
              </p>
            </div>
          )}
        </Panel>

        <Panel
          title="Topics"
          subtitle="Keyword buckets. A message matching none appears under no topic rather than being forced into one."
        >
          {(data.topics || []).length === 0 ? (
            <EmptyState
              title="No topics matched"
              detail="None of the submissions matched a known topic keyword."
            />
          ) : (
            <div className="space-y-2">
              {(data.topics || []).map(t => (
                <div key={t.topic} className="flex items-center justify-between text-xs">
                  <span className="font-medium" style={{ color: 'var(--cp-text)' }}>
                    {TOPIC_LABELS[t.topic] || t.topic}
                  </span>
                  <span className="tabular-nums" style={{ color: 'var(--cp-muted)' }}>
                    {num(t.count)} · {t.pct}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <McpThemesPanel mcp={data.mcp} />

      <Panel title="What this is not">
        <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
          This panel counts and classifies submissions. It does not change how feedback is stored,
          displayed or answered — the Feedback Responses view is exactly as it was. Individual
          message text is not returned by this endpoint; only aggregates are.
        </p>
      </Panel>
    </div>
  );
}

/**
 * The collected topic mix and sentiment balance, as the MCP tool reports them.
 *
 * A different source from the panel above. The live analysis scores the
 * `feedback` rows themselves with a lexicon; the tool reads the rolled-up
 * windows the collector recorded, so its topic counts and sentiment balance
 * cover the collected history rather than the newest sample.
 *
 * Shown separately on purpose: the two measure different things over
 * different windows, and a reader who saw one number and assumed it was the
 * other would draw the wrong conclusion.
 */
function McpThemesPanel({ mcp }: { mcp?: FeedbackData['mcp'] }) {
  const themes = mcp?.themes;
  const failed = Object.keys(mcp?.failed ?? {});

  if (!themes || !themes.topics || themes.topics.length === 0) {
    return (
      <Panel
        title="Collected mix (MCP)"
        subtitle="The topic mix and sentiment balance from the collector's own windows."
      >
        <EmptyState
          title="No collected windows"
          detail="The collector has not written a feedback analysis window for this range. The panel above still shows the live analysis."
        />
      </Panel>
    );
  }

  const sentiment = themes.sentiment ?? {};
  const total = sentiment.positive ?? 0 + (sentiment.neutral ?? 0) + (sentiment.negative ?? 0);

  return (
    <Panel
      title="Collected mix (MCP)"
      subtitle="The topic mix and sentiment balance across the collector's own windows - a different source from the live analysis above."
      actions={
        failed.length > 0 ? (
          <span className="text-xs" style={{ color: 'var(--cp-warning)' }}>
            {failed.join(', ')} refused
          </span>
        ) : undefined
      }
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Analysed"
          value={num(themes.total_count)}
          hint="across the collected windows"
        />
        <StatTile
          label="Windows"
          value={num(themes.windows_covered)}
          hint="analysis windows in range"
        />
        <StatTile
          label="Positive"
          value={num(sentiment.positive)}
          hint={`mean polarity ${sentiment.mean ?? 0}`}
          hue="mint"
        />
        <StatTile
          label="Negative"
          value={num(sentiment.negative)}
          hint="of the collected windows"
          invertDelta
          hue="coral"
        />
      </div>

      <div className="mt-4 space-y-2">
        {themes.topics.map(t => (
          <div key={t.topic} className="flex items-center justify-between text-xs">
            <span className="font-medium" style={{ color: 'var(--cp-text)' }}>
              {TOPIC_LABELS[t.topic] || t.topic}
            </span>
            <span className="tabular-nums" style={{ color: 'var(--cp-muted)' }}>
              {num(t.count)}
            </span>
          </div>
        ))}
      </div>
      {total === 0 && (
        <p className="mt-3 text-xs" style={{ color: 'var(--cp-muted)' }}>
          No sentiment was recorded in these windows.
        </p>
      )}
    </Panel>
  );
}

function SentimentBar({ sentiment, sampled }: { sentiment: SentimentData; sampled: number }) {
  const total = sampled || 1;
  const segments = [
    { key: 'positive', label: 'Positive', value: sentiment.positive ?? 0, bg: 'var(--cp-success)' },
    { key: 'neutral', label: 'Neutral', value: sentiment.neutral ?? 0, bg: 'var(--cp-muted)' },
    { key: 'negative', label: 'Negative', value: sentiment.negative ?? 0, bg: 'var(--cp-danger)' },
  ];
  return (
    <div>
      <div
        className="flex h-3 rounded-full overflow-hidden"
        style={{ background: 'var(--cp-bg)', boxShadow: 'var(--cp-neu-inset)' }}
      >
        {segments.map(s =>
          s.value > 0 ? (
            <div
              key={s.key}
              style={{ width: `${(s.value / total) * 100}%`, background: s.bg }}
              title={`${s.label}: ${s.value}`}
            />
          ) : null
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-3">
        {segments.map(s => (
          <span
            key={s.key}
            className="flex items-center gap-1.5 text-xs"
            style={{ color: 'var(--cp-muted)' }}
          >
            <span
              className="w-2.5 h-2.5 rounded-sm"
              style={{ background: s.bg }}
              aria-hidden="true"
            />
            {s.label} <span className="tabular-nums font-medium">{num(s.value)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
