/**
 * One section's inbox.
 *
 * The Important navigation mounts this once per section; `section` is the
 * mailbox subsection (academics, placement, ...). Every read is scoped to
 * the viewer's group by the backend, so this component only picks the
 * section and nothing else.
 *
 * Alongside the list sit the three things the mail app is for: a compose
 * box (or a reply or forward of what is open), a Files panel - the
 * download icon, which holds every attachment the mailbox has carried -
 * and the download button on each listed file.
 */
import { useCallback, useEffect, useState } from 'react';
import { Download, Pencil, RefreshCw } from 'lucide-react';
import { Badge, Button, Card, Input } from '@/components/ui';
import Spinner from '../../components/Spinner';
import { isUnauthorized, mailApi } from '../../../api';
import type { MailFileInfo, MailMessageResponse } from '../../types/api';
import MailCompose, { type ComposeMode } from './MailCompose';

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

/** A file size the way a file list shows it. */
function fileSize(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** What a download button does to the browser. */
async function saveFile(messageId: number, fileId: number, filename: string) {
  const blob = await mailApi.download(messageId, fileId);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || 'attachment';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

type Panel =
  | null
  | { kind: 'compose'; mode: ComposeMode; original?: MailMessageResponse | null }
  | { kind: 'files' };

export default function MailInbox({ section, onError }: MailInboxProps) {
  const [messages, setMessages] = useState<MailMessageResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [openId, setOpenId] = useState<number | null>(null);
  const [onlyStarred, setOnlyStarred] = useState(false);
  const [panel, setPanel] = useState<Panel>(null);
  const [files, setFiles] = useState<MailFileInfo[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [downloading, setDownloading] = useState<number | null>(null);

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

  const loadFiles = useCallback(async () => {
    setFilesLoading(true);
    try {
      setFiles(await mailApi.files());
    } catch (err) {
      if (!isUnauthorized(err)) {
        const message = err instanceof Error ? err.message : 'Could not load the files';
        onError?.(message);
      }
    } finally {
      setFilesLoading(false);
    }
  }, [onError]);

  const openFiles = () => {
    if (panel?.kind === 'files') {
      setPanel(null);
      return;
    }
    setPanel({ kind: 'files' });
    void loadFiles();
  };

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

  const grabFile = async (messageId: number, fileId: number, filename: string) => {
    setDownloading(fileId);
    try {
      await saveFile(messageId, fileId, filename);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Could not download the file');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Card className="p-0 overflow-hidden">
      {/* Section header + compose, files (downloads), search */}
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
          <Button
            variant={panel?.kind === 'compose' ? 'primary' : 'secondary'}
            onClick={() => setPanel({ kind: 'compose', mode: 'new', original: null })}
            aria-label="New mail"
            title="New mail"
          >
            <Pencil size={16} aria-hidden /> Compose
          </Button>
          <Button
            variant={panel?.kind === 'files' ? 'primary' : 'secondary'}
            onClick={openFiles}
            aria-label="Files, the download icon holds every attachment the mail brought"
            title="Files: every attachment in this mailbox"
          >
            <Download size={16} aria-hidden /> Files
          </Button>
          <Input
            type="search"
            placeholder="Search mail"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') void load(search, onlyStarred);
            }}
            className="w-32 sm:w-48"
          />
          <Button
            variant={onlyStarred ? 'primary' : 'secondary'}
            onClick={() => {
              const next = !onlyStarred;
              setOnlyStarred(next);
              void load(search, next);
            }}
            aria-pressed={onlyStarred}
            title="Only the starred messages"
          >
            ★
          </Button>
          <Button
            variant="secondary"
            aria-label="Refresh"
            onClick={() => void load(search, onlyStarred)}
          >
            <RefreshCw size={15} aria-hidden />
          </Button>
        </div>
      </div>

      {/* Compose / reply / forward */}
      {panel?.kind === 'compose' ? (
        <div className="p-4">
          <MailCompose
            mode={panel.mode}
            original={panel.original}
            onCancel={() => setPanel(null)}
            onSent={message => {
              setPanel(null);
              void load(search, onlyStarred);
              setMessages(list =>
                message.section === section && !list.some(m => m.id === message.id)
                  ? [message, ...list]
                  : list
              );
            }}
          />
        </div>
      ) : panel?.kind === 'files' ? (
        <div className="border-b p-4" style={{ borderColor: 'rgba(15,23,42,.06)' }}>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold">Files in this mailbox</h3>
            <button
              type="button"
              className="text-xs"
              style={{ color: 'var(--cp-muted)' }}
              onClick={() => setPanel(null)}
            >
              Close
            </button>
          </div>
          {filesLoading ? (
            <div className="py-8 flex justify-center">
              <Spinner />
            </div>
          ) : files.length === 0 ? (
            <p className="py-4 text-sm text-center" style={{ color: 'var(--cp-muted)' }}>
              No files have come with the mail yet. Put a download marker on a file and it stays
              here.
            </p>
          ) : (
            <ul className="divide-y" style={{ borderColor: 'rgba(15,23,42,.06)' }}>
              {files.map(file => (
                <li key={file.id} className="py-2 flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">
                      {file.filename}
                      <span className="ml-2 text-xs" style={{ color: 'var(--cp-muted)' }}>
                        {fileSize(file.size)}
                      </span>
                    </p>
                    <p className="text-xs truncate" style={{ color: 'var(--cp-muted)' }}>
                      From {file.from_name || file.from_email} · {listWhen(file.received_at)} ·{' '}
                      {SECTION_LABELS[file.section] ?? file.section}
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    aria-label={`Download ${file.filename}`}
                    disabled={downloading === file.id}
                    onClick={() => void grabFile(file.message_id, file.id, file.filename)}
                  >
                    {downloading === file.id ? (
                      <Spinner size={14} />
                    ) : (
                      <Download size={15} aria-hidden />
                    )}
                    Download
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

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
                    {message.has_attachments && (
                      <Badge title="Has attachments">
                        📎 {message.attachments.length > 1 ? message.attachments.length : ''}
                      </Badge>
                    )}
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
                      <div className="mt-3 flex flex-col gap-2">
                        {message.attachments.map((a, i) => (
                          <div
                            key={a.id ?? i}
                            className="flex items-center gap-3 rounded-lg px-3 py-2"
                            style={{
                              background: 'var(--cp-surface, #fff)',
                              border: '1px solid rgba(15,23,42,.08)',
                            }}
                          >
                            <span aria-hidden>📎</span>
                            <span className="truncate text-xs flex-1">
                              {a.filename}
                              {a.size ? ` · ${fileSize(a.size)}` : ''}
                            </span>
                            {a.id ? (
                              <Button
                                variant="secondary"
                                aria-label={`Download ${a.filename}`}
                                disabled={downloading === a.id}
                                onClick={() =>
                                  void grabFile(message.id, a.id as number, a.filename)
                                }
                              >
                                {downloading === a.id ? (
                                  <Spinner size={14} />
                                ) : (
                                  <Download size={15} aria-hidden />
                                )}
                                Download
                              </Button>
                            ) : (
                              <span className="text-xs" style={{ color: 'var(--cp-muted)' }}>
                                Not available
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-3 flex gap-2">
                      {message.direction === 'inbox' && (
                        <>
                          <Button
                            variant="secondary"
                            onClick={() =>
                              setPanel({ kind: 'compose', mode: 'reply', original: message })
                            }
                          >
                            Reply
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() =>
                              setPanel({ kind: 'compose', mode: 'forward', original: message })
                            }
                          >
                            Forward
                          </Button>
                        </>
                      )}
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setOpenId(null);
                        }}
                      >
                        Close
                      </Button>
                    </div>
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
