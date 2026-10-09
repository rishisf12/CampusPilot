import { useEffect, useState, ChangeEvent } from 'react';
import { feedbackApi } from '../../api';
import ErrorBanner from '../../components/ErrorBanner';

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

/**
 * Admin panel (developer): every feedback response with a Respond button.
 *
 * Each response shows the snapshotted name / phone / email, the message and
 * any attachment. "Respond to feedback" opens a text area with Submit; the
 * reply is stored per feedback and appears at the bottom of the student's own
 * feedback entry.
 */
export default function AdminPanel({ onError }: AdminPanelProps) {
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
      <div className="card p-8 text-center text-sm text-gray-500">Loading feedback responses…</div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900">Feedback responses</h2>
        <p className="text-sm text-gray-600 mt-1">
          {items.length} submission{items.length === 1 ? '' : 's'} from students.
        </p>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {items.length === 0 && (
        <div className="card p-8 text-center text-sm text-gray-500">No feedback yet.</div>
      )}

      {items.map(item => (
        <div key={item.id} className="card p-6 space-y-3">
          <p className="text-sm text-gray-800">{item.message}</p>
          <p className="text-xs text-gray-500">
            {item.name} · {item.email}
            {item.phone ? ` · ${item.phone}` : ''}
            {item.attachment_original ? ` · 📎 ${item.attachment_original}` : ''}
          </p>

          {(item.replies || []).map(reply => (
            <div
              key={reply.id}
              className="rounded-lg border border-primary-100 bg-primary-50 p-3 text-sm"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-primary-500">
                Admin response
              </p>
              <p className="mt-1 text-gray-800">{reply.message}</p>
            </div>
          ))}

          {openId === item.id ? (
            <div className="space-y-2">
              <textarea
                value={drafts[item.id] || ''}
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                  setDrafts(prev => ({ ...prev, [item.id]: event.target.value }))
                }
                placeholder="Write your response…"
                rows={3}
                maxLength={5000}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => send(item.id)}
                  disabled={sending || !(drafts[item.id] || '').trim()}
                  className="btn-primary text-sm disabled:opacity-60"
                >
                  {sending ? 'Sending…' : 'Submit'}
                </button>
                <button type="button" onClick={() => setOpenId(null)} className="btn-ghost text-sm">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={() => setOpenId(item.id)} className="btn-ghost text-sm">
              Respond to feedback
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
