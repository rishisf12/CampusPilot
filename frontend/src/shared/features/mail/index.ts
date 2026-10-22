/**
 * The mail bundle: section inboxes for the Important navigation.
 *
 * A module mounts <MailInbox section={...} /> once per section; the backend
 * scopes every read to the viewer's group, so the same component serves both
 * bundles.
 */
export { default as MailInbox } from './MailInbox';
export { default as MailCompose } from './MailCompose';
export type { ComposeMode } from './MailCompose';
