# ARCHITECTURE.md — how the college webmail is put together

The shape of the system, the data model, and the seams that let a dummy
mailbox be swapped for a real one without touching the code.

---

## 1. The two rules, expressed in the code

| Rule | Where it lives |
|---|---|
| **One common mailbox.** Six receiving ids are aliases of one intake. The address a notice was sent to is stored (`intake_address`) and shown, but it never decides a section. | `features/mail/ingestion/pipeline.py` (one intake per group) and `features/mail/routing/route.py` (routing reads the *sender* only) |
| **Separation by the sender's id.** The admin registers clusters of sender ids per section; mail from a registered sender files under that section, wherever it was posted. | `core.mail_cluster` + `core.mail_sender_rule`, matched by `routing/route.py` |

```
provider ──► ingestion pipeline ──► routing ──► store ──► UI
              (parse, auth,          (sender    (thread,
               dedupe, thread)        rules)     labels,
                                               state)
```

## 2. The backend package

```
backend/app/features/mail/
  routes.py            the HTTP surface (thin: validate, delegate, serialise)
  service.py           the read side: listing, counts, files
  models.py            the tables (SQLModel, core schema)
  schemas.py           request/response shapes
  sections.py          the section ids and labels (shared with the navigation)
  routing/
    route.py           routeMail(message) -> {section, matchedRuleId, reason}
    normalize.py       sender normalisation (display names, tags, case)
    matchers.py        exact / domain / pattern matching, priority order
    retro.py           re-filing the mail of a sender after a rule changes
  ingestion/
    pipeline.py        receive -> parse -> authenticate -> dedupe -> route
    parse.py           headers -> a parsed message
    auth.py            SPF/DKIM/DMARC verdicts
    dedupe.py          Message-ID, with a content hash as the fallback
    threading.py       conversation keys
  providers/
    base.py            InboundProvider / OutboundProvider interfaces
    dummy.py           the simulated server used now
    imap.py            the real one, later
    factory.py         MAIL_PROVIDER -> provider
  compose/
    send.py            building and sending (headers, quoting, threading)
    footer.py          the automatic college footer
    drafts.py          autosave, scheduled sends
  search/
    query.py           the operator parser
  downloads/
    library.py         the attachment library
  seed.py              dummy data for the development database
  jobs.py              the polling worker (APScheduler)
```

## 3. The data model

Every table lives in the `core` schema and is created by an Alembic revision
that matches the model exactly — `test_postgres_migration.py` enforces it.

### 3.1 The foundation (Phase 1)

| Table | Holds |
|---|---|
| `mail_section` | the sections (academics, placement, cultural, technical, sports, other) per group: key, label, order, public flag |
| `mail_section_access` | who may read or manage a section (the "section admin" of the prompt) |
| `mail_cluster` | a named cluster of sender ids, filed under one section |
| `mail_sender_rule` | one member of a cluster: type (exact/domain/pattern), value, section, priority, active flag, notes |
| `mail_thread` | a conversation: subject key, message count, last message at |
| `mail_message` | the mail: headers, `intake_address`, `section`, routing metadata, auth verdicts, status flags |
| `mail_user_message_state` | per-account state: read, starred, important, archived, trashed, snoozed |
| `mail_label` / `mail_message_label` | user labels (multi-tag) and their colours |
| `mail_file` | the attachment bytes, with a hash and a scan status |
| `mail_audit_log` | who changed a rule, re-routed a message, or sent as a section |
| `mail_footer_template` | the college's automatic footer, per section, with a default |
| `mail_signature` | a user's own signature, above the official footer |
| `mail_user_settings` | a user's mail settings (density, reading pane, undo-send delay…) |

### 3.2 Arriving later, with the feature that needs it

| Table | Phase |
|---|---|
| `mail_draft`, `mail_scheduled_send` | 5 (compose) |
| `mail_saved_search`, `mail_user_filter` | 6 (search and rules) |
| `mail_notification` | 6 (notifications) |
| `mail_contact`, `mail_contact_group` | 5 (autocomplete) |
| `mail_auto_reply`, `mail_blocked_sender` | 8 (settings) |

### 3.3 The message, in detail

| Column group | Columns |
|---|---|
| Identity | `id`, `message_id` (the header's Message-ID), `group` |
| Headers | `from_email`, `from_name`, `to_emails`, `cc_emails`, `bcc_emails`, `reply_to`, `reply_to_name`, `subject`, `body_text`, `body_html`, `in_reply_to`, `references` |
| Intake | `intake_address` (which alias it came through), `received_at` |
| Filing | `section`, `cluster_id`, `matched_rule_id`, `routing_reason`, `routed_at`, `routed_by` |
| Trust | `auth_spf`, `auth_dkim`, `auth_dmarc`, `auth_summary` |
| Conversation | `thread_id` |
| Flags | `direction`, `is_important`, `is_quarantined`, `has_attachments` |
| Bookskeeping | `labels`, `attachments` (descriptions), `created_by`, `created_at` |

## 4. The frontend

```
frontend/src/shared/features/mail/
  MailLayout.tsx        the three panes and the state that spans them
  MailSidebar.tsx       compose, section folders with counts, system folders
  MailList.tsx          the list, the selection, the bulk bar
  MailRow.tsx           one row
  ReadingPane.tsx       the conversation, the toolbar, the routing reason
  MailCompose.tsx       the compose window
  FooterPreview.tsx     the official footer, previewed
  useMail.ts            the data hooks
  shortcuts.ts          the keyboard map
```

Three panes on the desktop, one at a time on a phone. The layout follows
MailFlow's anatomy (sidebar → list → reading pane) and the project's own
components and `--cp-*` tokens, so it looks native to the site.

## 5. The provider seam

```python
class InboundProvider:
    def fetch_new(self) -> list[RawMessage]: ...
    def mark_fetched(self, ids: list[str]) -> None: ...

class OutboundProvider:
    def send(self, message: OutgoingMessage) -> SendResult: ...
```

`MAIL_PROVIDER=dummy|imap|graph|gmail|webhook` picks one. The dummy provider
is a database-backed simulated server: it generates realistic mail for every
section and every intake address, with registered and unregistered senders,
spoofed mail, attachments, threads, Cc/Bcc, HTML and plain text — and it can
loop a sent message back in, so replies and threads can be tested without a
mail server. Switching to a real provider is configuration only
(see `PROVIDERS.md`).

## 6. The ingestion pipeline

```
receive → parse → authenticate → dedupe → route → thread → store → index → notify
```

- **receive** — the provider's `fetchNew()`.
- **parse** — headers into a message; the display name is split off the
  address; `+tag` addresses are optionally stripped.
- **authenticate** — SPF/DKIM/DMARC verdicts; a failed-authentication mail
  goes to **Quarantine** when `REQUIRE_AUTH_FOR_ROUTING` is on.
- **dedupe** — by Message-ID, with a content hash as the fallback; a
  re-delivered mail is never stored twice.
- **route** — `routeMail()`, which reads the **sender** and the registered
  rules; an unmatched sender goes to **Unassigned**.
- **thread** — the conversation key (normalised subject, or the parent's
  thread through `In-Reply-To`).
- **store** — the message, its attachments, its routing metadata and the
  audit entry.
- **index** — the search index (the same Postgres, with the columns the
  query parser needs).
- **notify** — the bell, the unread counters, the toast.
