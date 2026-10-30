import { CalendarDays, Trophy, GraduationCap, Sparkles, Music } from 'lucide-react';
import { Card, Badge } from '@/components/ui';

/**
 * Events streams — Jagrati, Cultural, Technical and Sports.
 *
 * Purely presentational: the sub-tab row lives in the layout shells (attached
 * to the main nav, toggling on repeated Events clicks, exactly like the
 * Classroom sub-nav), so this component only renders the stream for the tab
 * the shell says is active. One component serves students and faculty on
 * mobile and desktop.
 */

export type EventTabId = 'jagrati' | 'cultural' | 'technical' | 'sports';

const EVENT_TAB_META: Record<EventTabId, { icon: React.ReactNode; blurb: string }> = {
  jagrati: {
    icon: <Sparkles size={16} strokeWidth={2} aria-hidden />,
    blurb: 'Jagrati - the institute cultural festival.',
  },
  cultural: {
    icon: <Music size={16} strokeWidth={2} aria-hidden />,
    blurb: 'Cultural events - clubs, competitions and celebrations.',
  },
  technical: {
    icon: <GraduationCap size={16} strokeWidth={2} aria-hidden />,
    blurb: 'Technical events - hackathons, workshops and tech fests.',
  },
  sports: {
    icon: <Trophy size={16} strokeWidth={2} aria-hidden />,
    blurb: 'Sports events - tournaments, tryouts and meets.',
  },
};

interface EventsProps {
  /** Active stream id ('jagrati' | 'cultural' | 'technical' | 'sports'). */
  tab?: string;
}

export default function Events({ tab = 'jagrati' }: EventsProps) {
  const meta =
    EVENT_TAB_META[(tab as EventTabId) in EVENT_TAB_META ? (tab as EventTabId) : 'jagrati'];

  return (
    <div className="space-y-4">
      <Card className="text-center py-12">
        <div
          className="mx-auto flex items-center justify-center rounded-full mb-4"
          style={{
            width: 44,
            height: 44,
            color: 'var(--cp-primary)',
            background: 'var(--cp-bg)',
            boxShadow: 'var(--cp-neu-inset)',
          }}
        >
          <CalendarDays size={20} strokeWidth={2} aria-hidden />
        </div>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
          {tab.charAt(0).toUpperCase() + tab.slice(1)} events
        </h3>
        <p className="mt-2 text-sm" style={{ color: 'var(--cp-muted)' }}>
          {meta.blurb}
        </p>
        <div className="mt-4 flex justify-center">
          <Badge tone="neutral">Coming soon</Badge>
        </div>
      </Card>
    </div>
  );
}
