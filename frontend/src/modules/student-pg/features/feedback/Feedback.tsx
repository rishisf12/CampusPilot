import { useEffect, useState, FormEvent, ChangeEvent } from 'react';
import { Send, Paperclip, ChevronDown, TriangleAlert, MailCheck } from 'lucide-react';
import { feedbackApi, profileApi } from '@/api';
import { useAuth } from '@shared/auth/AuthWrapper';
import { useProfile } from '@shared/hooks/useProfile';
import ErrorBanner from '@shared/components/ErrorBanner';
import Spinner from '@shared/components/Spinner';
import { Button, Card, Input, Textarea, Badge } from '@/components/ui';

interface FeedbackSubmission {
  id: number;
  message: string;
  name?: string;
  email?: string;
  phone?: string;
  subject?: string;
  attachment_original?: string;
  created_at?: string;
  replies: FeedbackReply[];
}

interface FeedbackReply {
  id: number;
  message: string;
  created_at?: string;
}

interface IngestStatus {
  configured: boolean;
}

/**
 * Feedback section: text + optional file, then submit.
 *
 * Name, phone and email are fetched automatically from the profile and the
 * account - the student only types them when they are missing or wrong. A
 * phone typed here is saved back to the profile, so next time it is already
 * filled. Submissions land in the backend `feedback` table, which the future
 * admin "feedback responses" view reads via `feedbackApi.responses()`.
 */
export default function Feedback() {
  const { user } = useAuth();
  const { profile, refresh } = useProfile();

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [mine, setMine] = useState<FeedbackSubmission[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [ingestStatus, setIngestStatus] = useState<IngestStatus | null>(null);
  const [checkingMail, setCheckingMail] = useState(false);

  // Auto-fill from the profile/account as soon as they arrive.
  useEffect(() => {
    const full = [profile?.first_name, profile?.last_name].filter(Boolean).join(' ').trim();
    if (!name) {
      if (full) setName(full);
      else if (user?.full_name) setName(user.full_name);
      else if (user?.username) setName(user.username);
    }
    if (!phone && profile?.phone) setPhone(profile.phone);
    if (!email && user?.email) setEmail(user.email);
    // Only run when the source data first arrives, not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.first_name, profile?.last_name, profile?.phone, user?.email, user?.full_name]);

  useEffect(() => {
    feedbackApi
      .mine()
      .then(setMine)
      .catch(() => {});
    // Check mail ingestion status
    feedbackApi
      .ingestStatus()
      .then(setIngestStatus)
      .catch(() => {});
  }, []);

  const checkMail = async () => {
    setCheckingMail(true);
    try {
      // Trigger mail check by calling the ingest status endpoint which may trigger a check
      // Or we can add a dedicated endpoint for triggering mail check
      const status = await feedbackApi.ingestStatus();
      setIngestStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check mail');
    } finally {
      setCheckingMail(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!message.trim()) {
      setError('Please write your feedback first.');
      return;
    }
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      // Keep the phone on the profile so it auto-fills next time.
      if (phone.trim() && phone.trim() !== (profile?.phone || '')) {
        try {
          await profileApi.update({ phone: phone.trim() });
          refresh?.();
        } catch {
          // A failed phone save must not block the feedback itself.
        }
      }
      const saved = await feedbackApi.submit({
        message: message.trim(),
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim(),
        subject: subject.trim(),
        file,
      });
      setMine(prev => [saved, ...prev]);
      setMessage('');
      setFile(null);
      (event.target as HTMLFormElement).reset?.();
      setDone('Thanks - your feedback is recorded.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit feedback');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <p className="text-sm max-w-xl" style={{ color: 'var(--cp-muted)' }}>
          Please give us feedback to improve this app and make more convenient for you to use
        </p>
      </Card>

      {ingestStatus && (
        <Card>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--cp-warning)' }}>
              <TriangleAlert size={20} strokeWidth={2} aria-hidden />
              <span>
                Mail ingestion is off. Set FEED_IMAP_USER and FEED_IMAP_PASSWORD in .env (repo root)
                to switch it on. Items already in the feed still show.
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={
                  checkingMail ? (
                    <Spinner size={16} />
                  ) : (
                    <MailCheck size={16} strokeWidth={2} aria-hidden />
                  )
                }
                onClick={checkMail}
                disabled={checkingMail}
                loading={checkingMail}
              >
                Check mail
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() =>
                  feedbackApi
                    .ingestStatus()
                    .then(setIngestStatus)
                    .catch(() => {})
                }
              >
                Refresh
              </Button>
            </div>
          </div>
        </Card>
      )}

      <ErrorBanner message={error} onDismiss={() => setError(null)} />
      {done && (
        <div
          className="p-3 rounded-2xl border text-sm"
          style={{ borderColor: 'rgba(163,177,198,.3)', color: 'var(--cp-success)' }}
        >
          {done}
        </div>
      )}

      <Card>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid sm:grid-cols-3 gap-4">
            <label className="block">
              <span
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: 'var(--cp-muted)' }}
              >
                Name
              </span>
              <Input
                type="text"
                value={name}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setName(event.target.value)}
                placeholder="Your name"
                className="mt-1 w-full"
              />
            </label>
            <label className="block">
              <span
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: 'var(--cp-muted)' }}
              >
                Phone number
              </span>
              <Input
                type="tel"
                value={phone}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setPhone(event.target.value)}
                placeholder="Your phone number"
                className="mt-1 w-full"
              />
            </label>
            <label className="block">
              <span
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: 'var(--cp-muted)' }}
              >
                Email id
              </span>
              <Input
                type="email"
                value={email}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setEmail(event.target.value)}
                placeholder="you@iiitdmj.ac.in"
                className="mt-1 w-full"
              />
            </label>
          </div>

          <label className="block">
            <span
              className="text-xs font-semibold uppercase tracking-wide"
              style={{ color: 'var(--cp-muted)' }}
            >
              Subject
            </span>
            <Input
              type="text"
              value={subject}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setSubject(event.target.value)}
              placeholder="Subject / title"
              className="mt-1 w-full"
            />
          </label>

          <label className="block">
            <span
              className="text-xs font-semibold uppercase tracking-wide"
              style={{ color: 'var(--cp-muted)' }}
            >
              Feedback
            </span>
            <Textarea
              value={message}
              onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setMessage(event.target.value)}
              placeholder="What should we improve?"
              rows={4}
              maxLength={5000}
              className="mt-1 w-full"
            />
          </label>

          <label className="block">
            <span
              className="text-xs font-semibold uppercase tracking-wide"
              style={{ color: 'var(--cp-muted)' }}
            >
              Upload file (optional)
            </span>
            <Input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.csv"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setFile(event.target.files?.[0] || null)
              }
              className="mt-1 w-full"
            />
            <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
              PDF, image, TXT or CSV, up to the upload limit.
            </span>
          </label>

          <Button
            type="submit"
            variant="primary"
            size="sm"
            icon={<Send size={16} strokeWidth={2} aria-hidden />}
            disabled={busy}
            loading={busy}
          >
            Submit
          </Button>
        </form>
      </Card>

      {mine.length > 0 && (
        <Card className="space-y-3">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--cp-text)' }}>
            Your feedback
          </h3>
          {mine.map(item => (
            <div
              key={item.id}
              className="neu-raised-sm p-3 text-sm"
              style={{ borderRadius: 16, background: 'var(--cp-surface)' }}
            >
              <button
                type="button"
                onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                aria-expanded={expandedId === item.id}
                className="w-full flex items-center justify-between text-left"
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold" style={{ color: 'var(--cp-text)' }}>
                    {item.subject || 'Feedback'}
                  </span>
                  {item.attachment_original && (
                    <Badge tone="primary">
                      <Paperclip size={14} strokeWidth={2} aria-hidden />
                      {item.attachment_original}
                    </Badge>
                  )}
                </div>
                <ChevronDown
                  size={16}
                  strokeWidth={2}
                  aria-hidden
                  className={`transition-transform ${expandedId === item.id ? 'rotate-180' : ''}`}
                  style={{ color: 'var(--cp-muted)' }}
                />
              </button>

              {expandedId === item.id && (
                <div
                  className="mt-3 space-y-2 pt-3 animate-slide-down"
                  style={{ borderTop: '1px solid rgba(163,177,198,.25)' }}
                >
                  <p className="whitespace-pre-wrap" style={{ color: 'var(--cp-text)' }}>
                    {item.message}
                  </p>
                  <div
                    className="grid sm:grid-cols-2 gap-2 text-xs"
                    style={{ color: 'var(--cp-muted)' }}
                  >
                    <span>
                      {item.name} · {item.email}
                    </span>
                    {item.phone && <span>{item.phone}</span>}
                    {item.created_at && (
                      <span>Submitted: {new Date(item.created_at).toLocaleString()}</span>
                    )}
                  </div>
                  {(item.replies || []).map(reply => (
                    <div
                      key={reply.id}
                      className="mt-2 p-2.5"
                      style={{
                        borderRadius: 12,
                        background: 'var(--cp-bg)',
                        boxShadow: 'var(--cp-neu-inset)',
                      }}
                    >
                      <p
                        className="text-[11px] font-semibold uppercase tracking-wide"
                        style={{ color: 'var(--cp-primary)' }}
                      >
                        Admin response
                      </p>
                      <p className="mt-0.5" style={{ color: 'var(--cp-text)' }}>
                        {reply.message}
                      </p>
                      {reply.created_at && (
                        <p className="mt-1 text-[10px]" style={{ color: 'var(--cp-muted)' }}>
                          {new Date(reply.created_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
