# MASTER PROMPT FOR OPENCODE: Rebuild the "Important" Mail System (IIITDM Jabalpur)

You are a senior full-stack engineer. Your job is to **completely replace** the existing mail logic in the "Important" section of this website with a new, professional, college-specific webmail system. Work like an experienced developer: plan, build in phases, verify every phase, fix bugs before moving on.

---

## 0. OPERATING RULES (read first, obey always)

1. **Adapt this prompt to the project before building.**
   - Inspect the repo: framework, language, package manager, routing, state management, styling/design system, auth, database/ORM, existing API layer, env handling, test setup.
   - Write `docs/mail/ADAPTATION.md` listing: detected stack, how each requirement below maps onto it, and any change you made to this prompt so it merges cleanly. **Use the project's existing stack, conventions, naming, folder style, UI components, theme tokens, and auth.** Do not introduce a new framework unless the project has no suitable option, and justify it in ADAPTATION.md.
   - Where this prompt suggests a library or structure and the project already has an equivalent, use the project's.
2. **Do not compromise anything else.** All existing features, pages, UI, styles, routes, and data outside the old mail module must keep working exactly as before. Run the existing build/lint/tests before starting (baseline) and after every phase.
3. **Replace, don't coexist.** Inventory the old mail code (routes, components, services, models, styles, tests, env vars, seed data). After the new system reaches feature parity (Phase 10), **delete the old implementation fully**: dead files, unused routes, unused dependencies, stale env vars, orphan styles. Migrate any useful existing data first.
4. **Work on a git branch** (`feature/mail-rebuild`), commit at the end of each phase with a clear message.
5. **Every phase ends with**: (a) a Verification checklist run, (b) a Bug-fix pass, (c) a short report appended to `docs/mail/PHASE_REPORTS.md` (what was done, what was tested, bugs found and fixed, known issues). Do not start the next phase until the current one passes.
6. **Dummy mode now, real mail later.** Everything must run end-to-end with simulated mail. Real mail servers plug in later by configuration only, with no code rewrites (see provider adapters).
7. Never hardcode secrets. Use env vars with a documented `.env.example`.
8. Don't copy proprietary code from Gmail/Outlook. Use them only as feature references; write original code.
9. If something is ambiguous, choose the most sensible option, record it in ADAPTATION.md under "Assumptions", and continue. Don't stop to ask unless truly blocked.

---

## 1. PRODUCT CONTEXT

The website has an **Important** section with subsections:
**Academics, Placement Cell, Cultural, Technical, Sports, Other, Downloads.**

It is a purpose-built **college webmail hub**. Official mail addresses all feed into **one common mailbox/pipeline**, and each incoming mail is automatically sorted into a section **by who sent it, not by which address it was sent to.**

### Receiving addresses (all land in ONE common intake)
- ug-placement@iiitdmj.ac.in
- registrar@iiitdmj.ac.in
- ug-cultural@iiitdmj.ac.in
- ug-technical@iiitdmj.ac.in
- ug-sports@iiitdmj.ac.in
- ug-other@iiitdmj.ac.in

Treat these as **aliases of one intake**. The "to" address is stored as metadata only (and shown in the UI) and **must never decide the section.**

*(Assumption to record: `registrar@` is the Academics-related address. Section is still decided only by sender.)*

---

## 2. CORE HYBRID LOGIC: SENDER-BASED ROUTING (most important part)

### 2.1 Sender Clusters
- Admin registers **clusters of sender email IDs per section** (Academics, Placement Cell, Cultural, Technical, Sports, Other).
- A cluster contains: exact emails, and optionally **domain rules** (e.g. `@placementcell.iiitdmj.ac.in`) and **wildcard/pattern rules**. Each rule has: type, value, section, priority, active flag, created by/at, notes.
- Include a **Downloads** behavior (see 6.7); it is a files hub, not a sender-routed inbox.

### 2.2 Routing Engine (pure, well-tested function)
`routeMail(message) -> { section, matchedRuleId, reason }`

Algorithm:
1. Normalize the sender: trim, lowercase, extract address from `Name <addr>`, optionally strip `+tag` (configurable), handle `Sender`/`From`/`Reply-To` according to a documented policy (use `From` after authentication check; see 2.4).
2. Match priority: **exact email > domain rule > pattern rule**. Within the same type, higher `priority` number wins, then oldest rule.
3. If the sender is in clusters of **multiple sections** → conflict resolution by priority; log the conflict; surface it in the admin "Conflicts" view.
4. If **no match** → route to an **"Unassigned / Review"** queue (visible to admins only). Admin can assign the sender to a cluster in one click, which then routes this and optionally all past mail from that sender (**retro-apply** with audit log).
5. Store `section`, `matchedRuleId`, `routedAt`, `routedBy` (system/admin) on the message. Allow **manual re-route** with audit trail.
6. Re-routing must never duplicate or lose messages (idempotent).

### 2.3 Required unit tests (table-driven)
Exact match; case differences; display-name formats; `+tag` addresses; domain rule; pattern rule; precedence between types; priority ties; multi-cluster conflict; no match; disabled rule; recipient address changing must NOT change the section (assert the same sender to each of the 6 addresses yields the same section); retro-apply; idempotency.

### 2.4 Sender trust (production-readiness)
- Parse and store SPF/DKIM/DMARC results from headers. Add setting `REQUIRE_AUTH_FOR_ROUTING` (default on in real mode, off in dummy mode). Mails that fail authentication go to a **Quarantine** view (admin) instead of being auto-routed, to prevent spoofed senders from entering official sections.
- Dummy provider can simulate pass/fail for testing.

---

## 3. ARCHITECTURE: PROVIDER ADAPTERS

Create a clean abstraction so dummy and real mail are interchangeable via `MAIL_PROVIDER=dummy|imap|graph|gmail|webhook`:

- `InboundProvider`: `fetchNew()`, `markFetched()`, optional webhook handler for push delivery.
- `OutboundProvider`: `send(message)` (SMTP/API), returns provider message ID and status.
- **DummyProvider (default now)**: in-memory/DB-backed simulated server with:
  - Seed script generating realistic sample mails for every section, every receiving address, multiple senders (registered, unregistered, spoofed/failed-auth), with attachments, threads, CC/BCC, HTML and plain text.
  - A **Developer Tools panel** (admin only, hidden when `MAIL_PROVIDER` ≠ dummy): "Simulate incoming mail" form (from, to, subject, body, attachments) to test routing live.
  - Dummy outbound: "sent" mail is stored and optionally looped back as inbound to test replies and threads.
- Ingestion pipeline (single path for all providers): `receive -> parse -> authenticate -> dedupe (Message-ID) -> route (2.2) -> thread -> store -> index -> notify`.
- Background job/worker (or the project's equivalent scheduler) with retry and dead-letter handling. Poll interval configurable.

---

## 4. DATA MODEL (adapt to the project's ORM/DB)

Entities (at minimum):
`User`, `Role/Permission`, `SectionAccess`, `Section`, `SenderCluster`, `SenderRule`, `Message` (headers, from, to[], cc[], bcc[], replyTo, subject, bodyText, bodyHtml, receivedAt, intakeAddress, section, routing metadata, authResults, messageId, inReplyTo, references, status flags), `Thread`, `Attachment` (name, mime, size, hash, storageKey, section, scanStatus), `Label`, `MessageLabel`, `UserMessageState` (read, starred, important, archived, trashed, snoozed per user), `Draft`, `ScheduledSend`, `Contact`, `ContactGroup`, `Filter/Rule`, `UserSettings`, `FooterTemplate`, `Signature`, `AutoReply`, `BlockedSender`, `AuditLog`, `Notification`.
Add indexes for: section+receivedAt, sender, threadId, full-text on subject/body, attachment hash. Provide migrations and seeds.

---

## 5. ROLES & ACCESS

- **Super Admin**: everything, manages clusters, quarantine, unassigned, providers, audit log, footer templates.
- **Section Admin / Moderator** (per section): manages that section's clusters, re-routes within permission, sees section mail, can send official mail as the section.
- **Member**: reads permitted sections, personal labels/stars/settings.
- **Student/Viewer**: read-only access to sections marked public.
Use the project's existing authentication; add authorization middleware/guards on every API route. Section visibility enforced **server-side**.

---

## 6. FEATURE SET (full webmail feature parity, tailored to college)

### 6.1 Layout & navigation
- Three-pane layout (sidebar | message list | reading pane) on desktop; stacked single-pane on mobile; configurable reading pane (right/bottom/off).
- Sidebar: Compose button; **section folders** (Academics, Placement Cell, Cultural, Technical, Sports, Other, Downloads) with **unread counts**; system folders (All Mail, Starred, Important, Sent, Drafts, Scheduled, Archive, Spam, Trash); user labels; admin-only (Unassigned/Review, Quarantine, Conflicts, Dev Tools).
- Top bar: global search, filters dropdown, settings, theme toggle, user menu, notification bell.
- Follow the project's existing design system, colors, fonts, spacing, and components. The mail UI must look native to the site.
- Empty, loading (skeletons), and error states everywhere. Fully responsive. Accessible (ARIA, focus management, keyboard navigation, contrast).

### 6.2 Message list
- Sender, subject, snippet, time, attachment icon, section badge, label chips, unread bold, star, importance marker.
- Select checkbox, select all/page/all-matching, bulk actions: mark read/unread, archive, delete, move/re-route (admin), label, star, report spam.
- Pagination or infinite scroll, sort (newest/oldest/sender/subject), density (compact/comfortable), conversation view toggle.

### 6.3 Reading pane
- Conversation/thread view with collapsible messages; headers (from, to, cc, bcc if sender, date, intake address, routing reason badge: "Routed to Placement Cell because sender X matches cluster rule Y").
- **Safe HTML rendering**: sanitize server-side and client-side; sandboxed rendering; block remote images by default with "Load images" control; link safety warning for external links; show the real URL.
- Plain text fallback, view original/headers, print, download as .eml, attachment list with preview (PDF/image) and download.
- Actions: reply, reply all, forward, archive, delete, star, mark unread, snooze, label, move, report spam, block sender.

### 6.4 Compose (advanced, must be polished)
- Compose as a docked window (minimize / maximize / full screen / pop-out), multiple compose windows, plus a full-page compose route.
- **From**: selectable official identity (e.g., the section address) based on user permission.
- **To / Cc / Bcc**: chip inputs with show/hide Cc/Bcc toggles, email validation, paste multiple addresses, drag chips between fields, **autocomplete from contacts, contact groups, and registered college directory**, warnings for external recipients, duplicate detection, max recipient limit.
- Subject (warn on empty), **rich text editor** (bold, italic, underline, lists, links, headings, alignment, color, quote, code, tables, clear formatting), plain-text mode, emoji, inline images, spell check.
- **Attachments**: drag-drop + picker, progress, size/type limits (configurable), remove, virus-scan hook, large-file warning, inline preview.
- **Autosave drafts** (debounced) with "Saved" indicator; discard confirm; restore unsent compose after refresh.
- **Send options**: Send, **Undo send** (configurable 5-30s), **Schedule send**, save draft, priority/importance flag, read-receipt request (optional).
- Reply / Reply all / Forward with proper quoting, `In-Reply-To`/`References` headers, subject prefixes (Re:/Fwd:), thread continuity.
- Templates / canned responses for common official notices.

### 6.5 Automatic college footer (advanced feature handled by the mail system itself)
- Every outgoing mail automatically gets a **server-managed footer** appended, in both HTML and plain-text, containing: institute name (Indian Institute of Information Technology, Design and Manufacturing, Jabalpur), department/section name, sender name and designation, official contact, **link back to the mail server/portal** (`PORTAL_MAIL_URL`, e.g. the section's page in the Important area), disclaimer/confidentiality text, and optional unsubscribe/notification-preferences link.
- Footer is a **template with variables**: `{{sender_name}}`, `{{sender_email}}`, `{{section}}`, `{{portal_url}}`, `{{message_link}}`, `{{date}}`, `{{institute}}`.
- Admin-editable **per-section footer templates** with live preview and a default fallback. Users may add a personal **signature** above the footer; they cannot remove the official footer.
- Footer is added server-side at send time (not editable in compose body), never duplicated in replies or forwards (strip/collapse old footers in quoted text), and escapes variables safely.
- Each sent mail gets a deep link so recipients inside the portal can open the same message.

### 6.6 Search & organization
- Full-text search with operators: `from:`, `to:`, `cc:`, `subject:`, `has:attachment`, `filename:`, `section:`, `label:`, `is:unread|starred|important`, `before:`, `after:`, `larger:`. Saved searches, search suggestions, highlight matches.
- User **filters/rules** (if from X / subject contains Y → label / star / archive / mark read), labels with colors, nested labels, snooze, mute thread, pin.

### 6.7 Downloads section
- Central library of all **attachments across sections plus admin-uploaded documents** (forms, circulars, notices).
- Filters by section, file type, date, sender; search by filename; sort; grid/list view; in-browser preview for PDF/images; single and **bulk ZIP download**; duplicate detection by hash; link back to the source mail; storage usage; per-section permission; admin upload and delete; download counts.

### 6.8 Notifications
- In-app bell, unread badge, browser notification (opt-in), optional email digest per section, mute per section, new-mail toast, real-time updates via SSE/WebSocket or polling fallback.

### 6.9 Settings (detailed, tabbed page)
- **General**: display name, language, time zone/date format, density, theme, reading pane, conversation view, page size, keyboard shortcuts on/off.
- **Compose**: default From, default reply behavior, undo-send duration, default font, signature editor, show Cc/Bcc by default, spell check.
- **Footer & Signature**: preview of the official footer for the user's section.
- **Sections & Sender Clusters (admin)**: manage clusters and rules (add/edit/delete/disable, bulk import via CSV, export, test tool: "enter a sender email → see which section it routes to and why"), conflicts list, unassigned queue, retro-apply.
- **Intake Addresses (admin)**: list the six aliases, enable/disable, health status, last received, provider config status.
- **Filters & Labels**, **Contacts & Groups** (import/export CSV/vCard).
- **Blocked senders / Spam**, **Auto-reply (vacation responder)** with date range, **Notifications**, **Storage & quota**, **Data export**, **Retention** (auto-delete trash after N days, archive policy).
- **Security**: active sessions, remote image policy, external-link warnings.
- **Audit Log (admin)**: who changed rules, re-routed, deleted, sent as section; filterable and exportable.
- **Keyboard shortcuts** (c compose, r reply, a reply all, f forward, e archive, # delete, s star, / search, j/k navigate, ? help).

---

## 7. SECURITY & QUALITY REQUIREMENTS
- Server-side authorization on every endpoint; per-section data isolation.
- HTML sanitization (DOMPurify or server equivalent), CSP headers, CSRF protection, input validation, parameterized queries, rate limiting on send/search/login, upload validation (type, size, magic bytes), filename sanitization, no path traversal.
- Header injection protection in outgoing mail; escape template variables.
- Audit logging for admin and routing actions. Secrets only via env.
- Performance: pagination, indexes, lazy loading, attachment streaming, caching of cluster rules (invalidate on change).
- Tests: unit (routing, footer rendering, parsing), integration (ingestion pipeline, send flow, permissions), UI/e2e for core flows. Maintain lint/type-check green.

---

## 8. PROPOSED DIRECTORY STRUCTURE (adapt names to the project's conventions)

```
backend/
  src/
    modules/mail/
      controllers/         # messages, compose, drafts, sections, clusters, downloads, settings, admin
      routes/
      services/
        routing/           # routeMail.ts, normalizeSender.ts, ruleMatcher.ts, retroApply.ts
        ingestion/         # pipeline.ts, parser.ts, authCheck.ts, dedupe.ts, threading.ts
        compose/           # sendService.ts, draftService.ts, scheduler.ts, footerService.ts
        search/            # indexer.ts, queryParser.ts
        downloads/         # attachmentLibrary.ts, zipService.ts
        notifications/
      providers/
        inbound/           # dummy.ts, imap.ts, graph.ts, gmail.ts, webhook.ts
        outbound/          # dummy.ts, smtp.ts
        index.ts           # factory by MAIL_PROVIDER
      models/ or schema/
      middleware/          # authz, rateLimit, validate, sanitize
      jobs/                # pollInbound, sendScheduled, retention, digests
      seeds/               # dummyMail.ts, sections.ts, clusters.ts, footers.ts
      tests/
    config/mail.config.ts
frontend/
  src/features/mail/
    pages/                 # MailLayout, SectionInbox, Thread, ComposePage, Settings/*, Admin/*
    components/            # Sidebar, MessageList, MessageRow, ReadingPane, ComposeWindow,
                           # RecipientInput, RichEditor, AttachmentUploader, SearchBar,
                           # SectionBadge, RoutingReason, FooterPreview, BulkToolbar
    hooks/                 # useMessages, useCompose, useShortcuts, useRealtime
    api/  store/  types/  utils/  styles/
docs/mail/                 # ADAPTATION.md, PHASE_REPORTS.md, ARCHITECTURE.md, ROUTING.md,
                           # PROVIDERS.md (how to switch dummy -> real), MIGRATION.md, USER_GUIDE.md
.env.example
```

---

## 9. PHASED PLAN (each phase: Build -> Verify -> Fix bugs -> Report)

**Phase 0: Discovery, Baseline & Adaptation**
- Audit repo and old mail module; inventory features/data to preserve; capture baseline build/test status and screenshots of existing pages; write ADAPTATION.md and a feature-parity checklist.
- *Verify:* baseline passes; checklist reviewed. *Fix:* any pre-existing build errors that block work (document them).

**Phase 1: Foundation (config, data model, auth/roles, seeds)**
- Schema + migrations, config, env, role guards, section seed, sample users per role.
- *Verify:* migrations up/down work; guards deny unauthorized access (test each role vs each section). *Fix:* schema/index issues.

**Phase 2: Sender-based Routing Engine**
- Clusters/rules CRUD, `routeMail`, conflict handling, unassigned queue, retro-apply, audit.
- *Verify:* full test table from 2.3 passes; prove recipient address never affects routing; performance check with 10k rules. *Fix:* all failing cases.

**Phase 3: Provider layer + Ingestion pipeline (dummy)**
- Provider interfaces, DummyProvider, seed generator, pipeline, dedupe, threading, auth-results, quarantine, dev tools simulator.
- *Verify:* 6 aliases + many senders -> correct sections; duplicates ignored; spoofed -> quarantine; threads group correctly. *Fix:* parser/threading bugs.

**Phase 4: Read-side API & UI shell**
- Layout, sidebar with counts, message list, reading pane, safe HTML, labels/stars/read state, bulk actions, section permissions, responsive.
- *Verify:* manual + e2e for each section/role; XSS test with malicious HTML; mobile view. *Fix:* UI and permission bugs.

**Phase 5: Compose, send & automatic footer**
- Compose window, To/Cc/Bcc chips + autocomplete, rich editor, attachments, drafts autosave, reply/reply all/forward, undo send, schedule send, footer service with templates.
- *Verify:* sent mail has correct headers (Cc visible, Bcc hidden from others), threading headers, footer present once in HTML and text, not duplicated on reply; header-injection tests; large/blocked attachments. *Fix:* all failures.

**Phase 6: Search, filters, labels, notifications, real-time**
- Operators, saved searches, user rules, snooze, bell, SSE/polling.
- *Verify:* operator test matrix; filter rules apply on ingestion; notification counts accurate. *Fix.*

**Phase 7: Downloads section**
- Attachment library, preview, ZIP, upload, permissions, hash dedupe.
- *Verify:* every attachment from ingested mail appears under the right section; permissions respected; ZIP integrity. *Fix.*

**Phase 8: Settings & Admin console**
- All tabs from 6.9, cluster manager with CSV import and "test a sender" tool, intake address status, footer editor with live preview, audit log, retention, auto-reply.
- *Verify:* every setting persists and takes effect; admin-only pages blocked for others; CSV import edge cases. *Fix.*

**Phase 9: Security, performance & accessibility hardening**
- CSP, CSRF, rate limits, sanitization review, a11y audit, keyboard shortcuts, load test with large dummy dataset.
- *Verify:* security checklist from section 7; Lighthouse/a11y results; no console errors. *Fix.*

**Phase 10: Legacy removal & migration**
- Migrate old mail data if any, redirect old routes, **delete old mail code, styles, deps, env vars**, update navigation.
- *Verify:* repo-wide search for old mail identifiers returns nothing; full build, lint, tests pass; all non-mail pages visually and functionally unchanged vs Phase 0 baseline. *Fix.*

**Phase 11: Final QA, docs & real-mail readiness**
- Full regression, e2e of the complete scenario below, docs (ARCHITECTURE, ROUTING, PROVIDERS with step-by-step "switch from dummy to real IMAP/SMTP/Graph/Gmail"), `.env.example`, final report.
- *Verify:* acceptance criteria (section 10). *Fix* remaining issues.

---

## 10. ACCEPTANCE CRITERIA (the system is done only when all are true)
1. Mail sent to **any** of the six addresses enters one common intake.
2. Section assignment depends **only** on the sender's registered cluster. Same sender to different addresses -> same section. Different senders to the same address -> different sections.
3. Unregistered senders go to Unassigned; failed-auth senders go to Quarantine; admin can resolve both in one click, with optional retro-apply.
4. Compose supports To/Cc/Bcc, attachments, rich text, drafts, undo/schedule send, reply/reply all/forward, and always adds the correct automatic footer with the server/portal link.
5. Downloads shows all attachments organized by section with preview and bulk download.
6. Settings and admin console are complete, per section 6.9.
7. Roles and section visibility are enforced server-side.
8. UI matches the existing site design, is responsive and accessible.
9. All tests pass; old mail implementation is fully removed; no other site feature regressed.
10. Switching `MAIL_PROVIDER` from `dummy` to a real provider requires **configuration only**, documented in PROVIDERS.md.

---

## 11. FINAL DELIVERABLES
- Working code on `feature/mail-rebuild` with per-phase commits.
- `docs/mail/*` documents listed above.
- Test suite and seed/dummy data.
- A final summary: features delivered, assumptions made, known limitations, and recommended next steps for connecting real email.

**Start now with Phase 0. After Phase 0, post the ADAPTATION.md summary, then proceed phase by phase without skipping verification.**
