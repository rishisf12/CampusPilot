/**
 * One section's inbox.
 *
 * The Important navigation mounts this once per section; `section` is the
 * mailbox subsection (academics, placement, ...). Every read is scoped to
 * the viewer's group by the backend, so this component only picks the
 * section and nothing else.
 */
import { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Card, Input } from '@/components/ui';
import Spinner from '../../components/Spinner';
import { isUnauthorized, mailApi } from '../../../api';
import type { MailMessageResponse } from '../../types/api';

interface MailInboxProps {
  section: string;
  onError?: (message: string) => void;
}

const SECTION_LABELS: Record<string, string> = {
  academics: 'Academics',
  placement: 'Placement Cell',
  cultural: 'Cultural',
  technical: 'Technical',
  sports: 'Sports',
  other: 'Other',
};

/** A compact "when" for the list: today shows the clock, else the date. */
function listWhen(iso?: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString([], { day: 'numeric', month: 'short' });
}

export default function MailInbox({ section, onError }: MailInboxProps) {
  const [messages, setMessages] = useState<MailMessageResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [openId, setOpenId] = useState<number | null>(null);
  const [onlyStarred, setOnlyStarred] = useState(false);

  const label = SECTION_LABELS[section] ?? 'Important';

  const load = useCallback(
    async (query = '', starred = false) => {
      setLoading(true);
      setError('');
      try {
        const data = await mailApi.list({
          section,
          search: query || undefined,
          starred: starred || undefined,
        });
        setMessages(data.messages);
      } catch (err) {
        if (!isUnauthorized(err)) {
          const message = err instanceof Error ? err.message : 'Could not load mail';
          setError(message);
          onError?.(message);
        }
      } finally {
        setLoading(false);
      }
    },
    [section, onError]
  );

  useEffect(() => {
    void load(search, onlyStarred);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section]);

  const open = async (message: MailMessageResponse) => {
    if (openId === message.id) {
      setOpenId(null);
      return;
    }
    setOpenId(message.id);
    if (message.is_read) return;
    // Optimistic: read the pane now, keep the list in step.
    setMessages(list => list.map(m => (m.id === message.id ? { ...m, is_read: true } : m)));
    try {
      await mailApi.markRead(message.id);
    } catch {
      // The next load will correct the flag; not worth a banner.
    }
  };

  const toggleStar = async (message: MailMessageResponse) => {
    setMessages(list =>
      list.map(m => (m.id === message.id ? { ...m, is_starred: !m.is_starred } : m))
    );
    try {
      await mailApi.toggleStar(message.id);
    } catch {
      setMessages(list =>
        list.map(m => (m.id === message.id ? { ...m, is_starred: m.is_starred } : m))
      );
    }
  };

  return (
    <Card className="p-0 overflow-hidden">
      {/* Section header + search */}
      <div
        className="flex flex-wrap items-center gap-3 p-4 border-b"
        style={{ borderColor: 'rgba(15,23,42,.08)' }}
      >
        <div className="flex-1 min-w-[10rem]">
          <h2 className="text-lg font-semibold">{label}</h2>
          <p className="text-xs" style={{ color: 'var(--cp-muted)' }}>
            {messages.length} message{messages.length === 1 ? '' : 's'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            type="search"
            placeholder="Search mail"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') void load(search, onlyStarred);
            }}
            className="w-40 sm:w-56"
          />
          <Button
            variant={onlyStarred ? 'primary' : 'secondary'}
            onClick={() => {
              const next = !onlyStarred;
              setOnlyStarred(next);
              void load(search, next);
            }}
            aria-pressed={onlyStarred}
          >
            ★ Starred
          </Button>
          <Button variant="secondary" onClick={() => void load(search, onlyStarred)}>
            Refresh
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center">
          <Spinner />
        </div>
      ) : error ? (
        <div className="p-6 text-center text-sm" style={{ color: 'var(--cp-danger, #b91c1c)' }}>
          {error}
        </div>
      ) : messages.length === 0 ? (
        <div className="py-16 text-center" style={{ color: 'var(--cp-muted)' }}>
          <p className="text-sm">No mail in {label.toLowerCase()} yet.</p>
          <p className="mt-1 text-xs">Notices sent to this section appear here.</p>
        </div>
      ) : (
        <ul className="divide-y" style={{ borderColor: 'rgba(15,23,42,.06)' }}>
          {messages.map(message => {
            const open_ = openId === message.id;
            return (
              <li key={message.id}>
                <button
                  type="button"
                  onClick={() => void open(message)}
                  className="w-full text-left px-4 py-3 flex gap-3 hover:bg-black/[.03] transition-colors"
                  style={{ fontStyle: message.is_read ? 'normal' : 'normal' }}
                >
                  <span
                    aria-hidden
                    className="mt-1.5 self-start rounded-full flex-shrink-0"
                    style={{
                      width: 8,
                      height: 8,
                      background: message.is_read ? 'transparent' : 'var(--cp-accent, #2f7a6d)',
                      border: message.is_read ? '1px solid rgba(15,23,42,.15)' : 'none',
                    }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span
                        className="truncate font-medium"
                        style={{ fontWeight: message.is_read ? 400 : 600, fontSize: '0.95rem' }}
                      >
                        {message.from_name || message.from_email}
                      </span>
                      <span
                        className="text-xs whitespace-nowrap"
                        style={{ color: 'var(--cp-muted)' }}
                      >
                        {listWhen(message.received_at)}
                      </span>
                    </div>
                    <p className="truncate text-sm" style={{ color: 'var(--cp-text, #0f172a)' }}>
                      {message.subject || '(no subject)'}
                    </p>
                    {!open_ && message.snippet && (
                      <p className="truncate text-xs" style={{ color: 'var(--cp-muted)' }}>
                        {message.snippet}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 self-start">
                    {message.has_attachments && <Badge title="Has attachments">📎</Badge>}
                    <span
                      role="button"
                      tabIndex={0}
                      aria-label={message.is_starred ? 'Unstar' : 'Star'}
                      onClick={e => {
                        e.stopPropagation();
                        void toggleStar(message);
                      }}
                      onKeyDown={e => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.stopPropagation();
                          e.preventDefault();
                          void toggleStar(message);
                        }
                      }}
                      className="cursor-pointer select-none text-base"
                      style={{ opacity: message.is_starred ? 1 : 0.35 }}
                    >
                      {message.is_starred ? '★' : '☆'}
                    </span>
                  </div>
                </button>
                {open_ && (
                  <div
                    className="px-4 pb-4 pt-1 text-sm"
                    style={{ color: 'var(--cp-text, #0f172a)' }}
                  >
                    <div className="text-xs mb-2" style={{ color: 'var(--cp-muted)' }}>
                      From {message.from_email}
                      {message.to_email ? ` · to ${message.to_email}` : ''} ·{' '}
                      {message.received_at ? new Date(message.received_at).toLocaleString() : ''}
                    </div>
                    {message.body_text ? (
                      <pre className="whitespace-pre-wrap break-words font-sans">
                        {message.body_text}
                      </pre>
                    ) : (
                      <p style={{ color: 'var(--cp-muted)' }}>This message has no text body.</p>
                    )}
                    {message.attachments.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {message.attachments.map((a, i) => (
                          <Badge key={i}>
                            📎 {a.filename}
                            {a.size ? ` (${Math.max(1, Math.round(a.size / 1024))} kB)` : ''}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
