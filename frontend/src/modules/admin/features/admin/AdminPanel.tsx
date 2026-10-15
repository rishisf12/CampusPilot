import { useEffect, useState, ChangeEvent, lazy } from 'react';
import {
  MessageSquareReply,
  Paperclip,
  Send,
  Settings,
  Shield,
  BarChart3,
  FileText,
  Wrench,
  Users,
  AlertTriangle,
  TrendingUp,
  Search,
} from 'lucide-react';
import { feedbackApi } from '@/api';
import { Badge, Button, Card, Tabs, Textarea } from '@/components/ui';
import ErrorBanner from '@shared/components/ErrorBanner';
import ReinforcementPatterns from './ReinforcementPatterns';
import UsersModule from './Users';
import DataManager from './DataManager';

// Lazy-load new admin tabs
const Control = lazy(() => import('./Control').then(m => ({ default: m.default })));
const MonitoringLive = lazy(() => import('./MonitoringLive').then(m => ({ default: m.default })));
const Errors = lazy(() => import('./Errors').then(m => ({ default: m.default })));
const Analytics = lazy(() => import('./Analytics').then(m => ({ default: m.default })));
const User360 = lazy(() => import('./User360').then(m => ({ default: m.default })));
const Security = lazy(() => import('./Security').then(m => ({ default: m.default })));
const Audit = lazy(() => import('./Audit').then(m => ({ default: m.default })));
const SettingsTab = lazy(() => import('./SettingsTab').then(m => ({ default: m.default })));

interface FeedbackResponse {
  id: number;
  message: string;
  name?: string;
  email?: string;
  phone?: string;
  subject?: string;
  attachment_original?: string;
  replies: FeedbackReply[];
}

interface FeedbackReply {
  id: number;
  message: string;
}

interface AdminPanelProps {
  onError?: (message: string) => void;
}

const SUB_TABS = [
  {
    id: 'feedback',
    label: 'Feedback Responses',
    icon: <MessageSquareReply size={16} strokeWidth={2} />,
  },
  { id: 'patterns', label: 'Reinforcement Patterns', icon: <Wrench size={16} strokeWidth={2} /> },
  { id: 'users', label: 'Users', icon: <Users size={16} strokeWidth={2} /> },
  { id: 'data', label: 'Data', icon: <FileText size={16} strokeWidth={2} /> },
  { id: 'control', label: 'Control', icon: <Settings size={16} strokeWidth={2} /> },
  { id: 'monitoring', label: 'Monitoring Live', icon: <BarChart3 size={16} strokeWidth={2} /> },
  { id: 'errors', label: 'Errors', icon: <AlertTriangle size={16} strokeWidth={2} /> },
  { id: 'analytics', label: 'Analytics', icon: <TrendingUp size={16} strokeWidth={2} /> },
  { id: 'user360', label: 'User 360', icon: <Users size={16} strokeWidth={2} /> },
  { id: 'security', label: 'Security', icon: <Shield size={16} strokeWidth={2} /> },
  { id: 'audit', label: 'Audit', icon: <Search size={16} strokeWidth={2} /> },
  { id: 'settings', label: 'Settings', icon: <Settings size={16} strokeWidth={2} /> },
] as const;

type SubTab = (typeof SUB_TABS)[number]['id'];

/**
 * Admin panel (developer): every feedback response with a Respond button.
 *
 * Each response shows the snapshotted name / phone / email, the message and
 * any attachment. "Respond to feedback" opens a text area with Submit; the
 * reply is stored per feedback and appears at the bottom of the student's own
 * feedback entry.
 */
export default function AdminPanel({ onError }: AdminPanelProps) {
  const [tab, setTab] = useState<SubTab>('feedback');
  const [items, setItems] = useState<FeedbackResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Which feedback is being answered, and the draft text per feedback.
  const [openId, setOpenId] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [sending, setSending] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setItems(await feedbackApi.responses());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load feedback');
      onError?.(err instanceof Error ? err.message : 'Failed to load feedback');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = async (id: number) => {
    const text = (drafts[id] || '').trim();
    if (!text) return;
    setSending(true);
    try {
      const reply = await feedbackApi.reply(id, text);
      setItems(prev =>
        prev.map(item =>
          item.id === id ? { ...item, replies: [...(item.replies || []), reply] } : item
        )
      );
      setDrafts(prev => ({ ...prev, [id]: '' }));
      setOpenId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reply');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
        Loading feedback responses…
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Tabs
        tabs={SUB_TABS.map(item => ({ id: item.id, label: item.label, icon: item.icon }))}
        active={tab}
        onChange={id => setTab(id as SubTab)}
      />

      {tab === 'feedback' && (
        <>
          <Card>
            <h2 className="text-lg font-semibold" style={{ color: 'var(--cp-text)' }}>
              Feedback responses
            </h2>
            <p className="text-sm mt-1" style={{ color: 'var(--cp-muted)' }}>
              {items.length} submission{items.length === 1 ? '' : 's'} from students.
            </p>
          </Card>

          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          {items.length === 0 && (
            <Card className="text-center text-sm" style={{ color: 'var(--cp-muted)' }}>
              No feedback yet.
            </Card>
          )}

          {items.map(item => (
            <Card key={item.id} className="space-y-3" aria-live="polite">
              <p className="text-sm" style={{ color: 'var(--cp-text)' }}>
                {item.message}
              </p>
              <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                {item.name} · {item.email}
                {item.phone ? ` · ${item.phone}` : ''}
              </p>
              {item.attachment_original && (
                <Badge tone="neutral">
                  <Paperclip size={12} strokeWidth={2} aria-hidden />
                  {item.attachment_original}
                </Badge>
              )}

              {(item.replies || []).map(reply => (
                <div
                  key={reply.id}
                  className="p-3 text-sm"
                  style={{
                    borderRadius: 12,
                    border: '1px solid rgba(163,177,198,.3)',
                    background: 'var(--cp-bg)',
                    boxShadow: 'var(--cp-neu-inset)',
                  }}
                >
                  <p
                    className="text-xs font-semibold uppercase tracking-wide"
                    style={{ color: 'var(--cp-primary)' }}
                  >
                    Admin response
                  </p>
                  <p className="mt-1" style={{ color: 'var(--cp-text)' }}>
                    {reply.message}
                  </p>
                </div>
              ))}

              {openId === item.id ? (
                <div className="space-y-2">
                  <Textarea
                    value={drafts[item.id] || ''}
                    onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                      setDrafts(prev => ({ ...prev, [item.id]: event.target.value }))
                    }
                    placeholder="Write your response…"
                    rows={3}
                    maxLength={5000}
                    aria-label="Response text"
                  />
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      icon={<Send size={16} strokeWidth={2} aria-hidden />}
                      loading={sending}
                      disabled={sending || !(drafts[item.id] || '').trim()}
                      onClick={() => send(item.id)}
                    >
                      Submit
                    </Button>
                    <Button type="button" variant="ghost" size="sm" onClick={() => setOpenId(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  icon={<MessageSquareReply size={16} strokeWidth={2} aria-hidden />}
                  onClick={() => setOpenId(item.id)}
                >
                  Respond to feedback
                </Button>
              )}
            </Card>
          ))}
        </>
      )}

      {tab === 'patterns' && <ReinforcementPatterns onError={(msg: string) => setError(msg)} />}
      {tab === 'users' && <UsersModule onError={(msg: string) => setError(msg)} />}
      {tab === 'data' && <DataManager onError={(msg: string) => setError(msg)} />}
      {tab === 'control' && <Control onError={(msg: string) => setError(msg)} />}
      {tab === 'monitoring' && <MonitoringLive onError={(msg: string) => setError(msg)} />}
      {tab === 'errors' && <Errors onError={(msg: string) => setError(msg)} />}
      {tab === 'analytics' && <Analytics onError={(msg: string) => setError(msg)} />}
      {tab === 'user360' && <User360 onError={(msg: string) => setError(msg)} />}
      {tab === 'security' && <Security onError={(msg: string) => setError(msg)} />}
      {tab === 'audit' && <Audit onError={(msg: string) => setError(msg)} />}
      {tab === 'settings' && <SettingsTab onError={(msg: string) => setError(msg)} />}
    </div>
  );
}
