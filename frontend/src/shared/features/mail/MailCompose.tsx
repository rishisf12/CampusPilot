/**
 * A compose box: a new message, a reply, or a forward.
 *
 * A reply pre-fills the sender as the recipient; a forward quotes the
 * original in the body, which is what "forward" means to a student - the
 * text they can edit before it goes. The backend marks the thread with
 * the message being answered, so the mail server keeps the conversation
 * together.
 */
import { useState } from 'react';
import { Button, Card, Input, Textarea } from '@/components/ui';
import { mailApi } from '../../../api';
import type { MailMessageResponse } from '../../types/api';

export type ComposeMode = 'new' | 'reply' | 'forward';

interface MailComposeProps {
  mode: ComposeMode;
  original?: MailMessageResponse | null;
  onSent?: (message: MailMessageResponse) => void;
  onCancel?: () => void;
}

/** The quoted block a forward (and a reply, visibly) carries. */
function quote(message: MailMessageResponse): string {
  const from = message.from_name
    ? `${message.from_name} <${message.from_email}>`
    : message.from_email;
  const when = message.received_at ? new Date(message.received_at).toLocaleString() : '';
  const lines = [
    '---------- Forwarded message ----------',
    `From: ${from}`,
    `Subject: ${message.subject || '(no subject)'}`,
    when ? `Date: ${when}` : '',
  ].filter(Boolean);
  const body = (message.body_text || '(no text)')
    .split('\n')
    .map(line => `> ${line}`)
    .join('\n');
  return `${lines.join('\n')}\n\n${body}`;
}

/** One Re:, not a stack of them. */
function withPrefix(subject: string | null | undefined, prefix: 'Re:' | 'Fwd:'): string {
  const text = (subject ?? '').trim();
  return text.startsWith(prefix) ? text : `${prefix} ${text}`.trim();
}

export default function MailCompose({ mode, original, onSent, onCancel }: MailComposeProps) {
  const prefilled = mode !== 'new' && original ? quote(original) : '';
  const [to, setTo] = useState(mode === 'reply' && original ? original.from_email : '');
  const [subject, setSubject] = useState(() => {
    if (mode === 'new') return '';
    if (!original) return '';
    return withPrefix(original.subject, mode === 'reply' ? 'Re:' : 'Fwd:');
  });
  const [body, setBody] = useState(prefilled);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    if (!to.trim()) {
      setError('Who is it for?');
      return;
    }
    setSending(true);
    try {
      const thread: Record<string, number> = {};
      if (mode === 'reply' && original) thread.reply_of = original.id;
      if (mode === 'forward' && original) thread.forward_of = original.id;
      const message = await mailApi.compose({
        to,
        subject,
        body,
        ...thread,
      });
      onSent?.(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The message did not go out.');
    } finally {
      setSending(false);
    }
  };

  const heading = mode === 'reply' ? 'Reply' : mode === 'forward' ? 'Forward' : 'New mail';

  return (
    <Card className="p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">{heading}</h3>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="text-xs"
            style={{ color: 'var(--cp-muted)' }}
          >
            Cancel
          </button>
        )}
      </div>
      {mode === 'reply' && original && (
        <p className="text-xs mb-3" style={{ color: 'var(--cp-muted)' }}>
          To <span style={{ color: 'var(--cp-text, #0f172a)' }}>{original.from_email}</span>
          {' · '}
          {original.is_read ? '' : 'marked read when you opened it'}
        </p>
      )}
      <div className="flex flex-col gap-2">
        {<Input type="email" placeholder="To" value={to} onChange={e => setTo(e.target.value)} />}
        <Input
          type="text"
          placeholder="Subject"
          value={subject}
          onChange={e => setSubject(e.target.value)}
        />
        <Textarea
          rows={8}
          placeholder="Write your message"
          value={body}
          onChange={e => setBody(e.target.value)}
        />
        {error && (
          <p className="text-xs" style={{ color: 'var(--cp-danger, #b91c1c)' }}>
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="primary" disabled={sending} onClick={() => void submit()}>
            {sending ? 'Sending…' : 'Send'}
          </Button>
        </div>
      </div>
    </Card>
  );
}
