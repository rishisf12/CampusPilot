# PARITY.md — mail feature checklist (Section 6 of the master prompt)

Every row is one feature, marked `not started` until its phase lands and its
test passes. `n/a` means the spec itself marks it optional or deferred, with
the reason. Test reference is filled in as the phase's tests are written.

This file is the acceptance contract: **Phase 12 is not complete until every
row is `done` or `n/a`.**

| ID | Feature | How it works / UX | Edge cases | Status | Test reference |
|---|---|---|---|---|---|

## 6.1 Inbox types and section views

| 6.1-1 | Default inbox type (category tabs) | Settings > Inbox > Inbox type: Default. Category tabs (Primary/Updates/Notices) auto-classified via List-Id, Precedence: bulk, keyword rules; dragging a message to another tab asks "Do this for all future messages from this sender?" | Multiple matching tabs — drag is a filter-like action; undoable | not started | - |
| 6.1-2 | Priority first | Two sections: Priority / Everything else. Instant switch, saved per user. | Empty Priority section renders its own empty state | not started | - |
| 6.1-3 | Unread first | Inbox shows unread messages first. Saved per user. | All-read state | not started | - |
| 6.1-4 | Starred first | Inbox shows starred messages first. Saved per user. | Empty starred state | not started | - |
| 6.1-5 | Priority Inbox | User picks sections such as "Priority and unread", "Starred", "Everything else", or a label. | Custom section selection persisted | not started | - |
| 6.1-6 | Multiple inboxes | Extra panes defined by a search or label; used for the All-sections scope. "Show up to N items" per pane + "See all" link. | Pane count vs screen width; empty panes | not started | - |
| 6.1-7 | Single-section user never sees switcher | A user with access to one section never sees the inbox-type switcher. | Role/section access enforced server-side | not started | - |
| 6.1-8 | Unread counts in subsection tabs | Each Important subsection tab shows its section's unread count. | Zero count hidden or shown as 0 | not started | - |

## 6.2 Message (conversation) list

| 6.2-1 | Row anatomy | Checkbox, star, Priority marker, sender names (bold if unread, "me" for self), thread count in parentheses, subject + grey snippet, attachment chips (type icon + name, Default density), label chips, section badge (All scope), Received-at chip (optional), smart time. | Long sender names truncated with tooltip | not started | - |
| 6.2-2 | Unread styling | Unread rows bold + light background; read rows greyed. | Read/unread toggle persistence | not started | - |
| 6.2-3 | Toolbar | Select-all checkbox with dropdown (All/None/Read/Unread/Starred/Unstarred), Refresh, More (Mark all as read), pagination "1-50 of N", older/newer arrows, page size 25/50/100. | Empty list toolbar state | not started | - |
| 6.2-4 | Two-step select-all | Ticking the header selects the page + banner "All N conversations on this page are selected. Select all N conversations in <view>"; clicking selects the entire result set (background job + progress + Undo). | Result set larger than page; job cancellation | not started | - |
| 6.2-5 | Bulk toolbar | Replaces normal toolbar when rows selected: Archive, Report spam, Delete, Mark read/unread, Snooze, Move to, Label as, More (Mark priority, Mute, Filter like these). | Empty selection reverts toolbar | not started | - |
| 6.2-6 | Hover actions | Right side of row: Archive, Delete, Mark read/unread, Snooze (configurable in Settings). | Disabled per user preference | not started | - |
| 6.2-7 | Drag to label | Row(s) dragged onto a label in the left rail applies that label. | Rail label not visible | not started | - |
| 6.2-8 | Real-time new mail | "N new messages" bar (SSE/WebSocket, polling fallback); scroll position preserved; tab title count; favicon badge. | Network reconnect; duplicate counting | not started | - |
| 6.2-9 | Auto-advance | After archive/delete/mute: Newer / Older / back to list. Setting. | Last message in view | not started | - |
| 6.2-10 | Keyboard cursor | Visible current-row indicator moved with j/k; actions apply to checked rows else cursor row. | Actions on zero rows | not started | - |

## 6.3 Conversation view and reading

| 6.3-1 | Threading | Messages grouped by Message-ID/In-Reply-To/References; fallback on normalized subject + participants within a time window. Setting to turn Conversation view off (each message its own row). | Headers missing; subject collisions | not started | - |
| 6.3-2 | Header toolbar | Back to list, Archive, Report spam, Delete, Mark unread, Snooze, Add to Tasks, Move to, Label as, More; previous/next arrows with "N of M". | Single-message thread | not started | - |
| 6.3-3 | Conversation title + label chips | Print / open-in-new-window icons. | Untitled threads | not started | - |
| 6.3-4 | Message cards | Latest + unread expanded; older collapsed to one-line summary; "Expand all"; quoted history behind "..." toggle. | Very long threads | not started | - |
| 6.3-5 | Card header | Avatar (initials/photo), sender name + address, expandable to/cc/bcc/detail (from, reply-to, date, mailed-by, signed-by/auth result, Received at, security), date/time + relative tooltip, star, Reply icon, three-dot menu. | Missing avatars; header-only mail | not started | - |
| 6.3-6 | Routing badge | `Section - matched sender rule "..."` near the title; admins see "Change section". | No matched rule (Unassigned) | not started | - |
| 6.3-7 | Inline reply box | Reply / Reply all / Forward at thread bottom; expands into full compose on pop-out. | Nested replies depth | not started | - |
| 6.3-8 | Smart reply chips | Rule-based suggestions above the reply box; configurable. | No matching suggestions | not started | - |
| 6.3-9 | Attachment strip | Thumbnails, name, size, Preview (PDF/images/text), Download, Download all (ZIP), Add to Downloads library. | Corrupt attachments; oversized | not started | - |
| 6.3-10 | Safe rendering | Sanitized HTML; sandboxed rendering; remote images blocked by default ("Images hidden. Show images / Always show from this sender"); external links show real destination + risky confirmation; display-name vs address mismatch warning; spoof/failed-auth banner. | Mail without HTML body | not started | - |
| 6.3-11 | Unsubscribe | Link/banner when `List-Unsubscribe` header present. | No List-Unsubscribe header | not started | - |
| 6.3-12 | Print / trimmed / plain text | Print view; "Show trimmed content"; plain-text fallback. | HTML-only mail | not started | - |

## 6.4 Message three-dot menu (per message)

| 6.4-1 | Reply / Forward / Filter messages like this / Print | Standard per-message actions; filter pre-fills conditions from the message. | Forward as attachment variant | not started | - |
| 6.4-2 | Delete this message / Block "<sender>" / Report spam / Report phishing | Spam → Spam folder + Undo; phishing → Quarantine review with headers; block → future mail skips Inbox. | Blocked-sender management page | not started | - |
| 6.4-3 | Show original | Raw headers, SPF/DKIM/DMARC results, Delivered-To, routing trace ("matched rule X at time T"); Copy and Download. | Mail ingested without headers | not started | - |
| 6.4-4 | Mark as unread / Add star / Change section (admin) / Copy link / Save attachments | Extras beyond Gmail's menu; Change section guarded to permitted admins. | Read-only sections | not started | - |
| 6.4-5 | Translate message | Optional hook; behind a feature flag. | No translation provider configured | n/a | - |

## 6.5 Labels

| 6.5-1 | Label as a tag | A message can have many labels; nested (Parent/Child); colors; rail show/hide/show-if-unread. Configurable cap (default 500). | Cap reached behavior | not started | - |
| 6.5-2 | Label UX | Menu with search + "Create new" + nested creation; rail context menu (Edit/Remove/Label color/Show/Hide/Add sublabel); drag-drop; Settings > Labels bulk management with counts. | Renaming nested children | not started | - |
| 6.5-3 | Section labels | System-owned, lock icon, cannot be manually added/removed by normal users. | Attempted manual add → 403/400 | not started | - |
| 6.5-4 | Delete label does not delete mail | Confirm + explanation; renaming updates nested children. | Label in use by many messages | not started | - |

## 6.6 Stars and Priority

| 6.6-1 | Star types | Yellow star default; optional extra colors/icons cycled by repeated click; selectable in Settings. | User's chosen star set persisted | not started | - |
| 6.6-2 | Priority flag | Manual toggle + optional automatic marking by rule; used by "Priority first" and "Priority Inbox". | Rule conflicts resolved by precedence | not started | - |
| 6.6-3 | Priority filters | "Always mark as priority" / "Never mark as priority" filter actions. | Conflicting filter actions validated | not started | - |

## 6.7 Archive, mute, snooze, move

| 6.7-1 | Archive | Removes from Inbox; keeps in All Mail and its section; Undo toast; new reply to an archived thread returns it to Inbox. | Thread already archived | not started | - |
| 6.7-2 | Mute | New replies skip the Inbox (stay in All Mail); muted thread shows mute icon; Undo. | Muting an already-muted thread | not started | - |
| 6.7-3 | Snooze | Presets (Later today/Tomorrow/This weekend/Next week) + custom date/time; leaves inbox → Snoozed → returns to top as unread; background job wakes them; notification at wake-up. | Job misses wake-up (server down) → wake on next start | not started | - |
| 6.7-4 | Move to | Folder/label picker (Inbox/Spam/Trash/Archive) with search. | Moving to Trash vs Delete distinction | not started | - |
| 6.7-5 | Send and archive | Option in reply compose (setting). | Compose without send permission | not started | - |

## 6.8 Spam, phishing, blocking, unsubscribe

| 6.8-1 | Report spam / Not spam | Moves to Spam + Undo; Not spam restores and trains per-user safe-sender rule. | Training on already-safe sender | not started | - |
| 6.8-2 | Report phishing | Sends to Spam and flags to admins (Quarantine review) with headers. | Admin Quarantine view | not started | - |
| 6.8-3 | Block sender | Future mail from that address skips Inbox → Spam (per user); manage in Settings > Filters and Blocked addresses; Unblock. | Blocked sender also in a section cluster → cluster wins (official senders never auto-spam) | not started | - |
| 6.8-4 | Spam banner | "Messages in Spam are deleted after 30 days. Delete all spam messages now." | Empty spam folder | not started | - |
| 6.8-5 | Hard rule | Official section senders (registered clusters) are never auto-sent to Spam by heuristics. | Config bypass not exposed | not started | - |

## 6.9 Trash and retention

| 6.9-1 | Delete → Trash | Undo; Trash and Spam auto-purge after 30 days (configurable); "Empty Trash now" / "Delete forever"; both count toward storage. | Purged message in thread → "View deleted messages in conversation" | not started | - |

## 6.10 Search

| 6.10-1 | Search bar + suggestions | Pill-shaped bar; live suggestions (recent searches, contacts, labels, operators). | Empty suggestion set | not started | - |
| 6.10-2 | Advanced search panel | From, To, Subject, Has the words, Doesn't have, Size, Date within, Search in (All Mail/Inbox/Sent/Drafts/Spam & Trash/Starred/Section/Label), Received at (alias), Has attachment; Create filter + Search buttons. | Invalid operator combination validated | not started | - |
| 6.10-3 | Results | Highlighted terms; "Clear search" chip; query shareable in URL. | Zero results empty state | not started | - |
| 6.10-4 | Operators | `from: to: cc: bcc: subject: label: category: section: deliveredto: list: filename: has:attachment has:drive has:document has:spreadsheet has:presentation is:unread/is:read/is:starred/is:important(is:priority)/is:muted/is:snoozed in:inbox/in:sent/in:drafts/in:trash/in:spam/in:archive/in:anywhere before:/after:/older_than:/newer_than:/larger:/smaller:/size: "exact phrase" -exclude OR {a b} AROUND` | `in:anywhere` includes Trash/Spam | not started | - |
| 6.10-5 | Matching semantics | Match at message level, display at thread level (thread can appear for `-is:starred` if any message unstarred — documented). Default scope excludes Trash/Spam; scoped to current section unless All or `section:`. | Cross-section permission filtering | not started | - |
| 6.10-6 | Full-text index | Subject, body, sender, recipients, attachment names; text of text/PDF attachments if feasible; prefix matching. | Non-text attachments | not started | - |
| 6.10-7 | Saved searches | Appear under "Saved searches" rail group; "Create filter" from any search. | Naming collisions | not started | - |

## 6.11 Filters (user level)

| 6.11-1 | Conditions | From, To, Subject, Has the words, Doesn't have, Has attachment, Size, Delivered-to (alias). | Empty condition → validation error | not started | - |
| 6.11-2 | Actions | Skip Inbox (Archive), Mark as read, Star it, Apply label, Forward to (verified only, capped), Delete it, Never send to Spam, Always/Never mark Priority, Categorize as (tab), Also apply filter to N matching conversations (count before applying). | Forwarding loop protection | not started | - |
| 6.11-3 | Entry points | Search options > Create filter; message menu > Filter messages like this; Settings; confirmation toast after saving. | Duplicate filter detection | not started | - |
| 6.11-4 | Processing order | Ingest → system section routing → user filters (in order) → notifications; a user filter can never change the Section label. | Filter reordering respected | not started | - |
| 6.11-5 | Filters list | Edit/Delete; Export/Import (JSON). | Corrupt import file | not started | - |

## 6.12 Compose

| 6.12-1 | Window model | Floating window docked bottom-right titled "New Message"; Minimize / Full screen / Pop-out / Close (saves draft); multiple windows stack; oldest minimizes when space runs out; Ctrl+./Ctrl+, cycle windows; Esc saves and closes. | Window restore after refresh | not started | - |
| 6.12-2 | Fields | From (identity dropdown), To, Cc/Bcc toggle links (remembered state), Subject. | Default identity per user | not started | - |
| 6.12-3 | Recipients | Chips with suggestions (contacts/groups/directory/recently used); `,` `;` Space/Enter commits; paste many; drag chips between To/Cc/Bcc; invalid red + tooltip; click chip to edit/remove/copy; groups expand with count; `+name`/`@name` in body adds recipient; warnings (external on official addresses, duplicates across To/Cc/Bcc, cap, Bcc tooltip). | Very large paste; international addresses | not started | - |
| 6.12-4 | Body editor | Formatting bar ("A" button): undo/redo, font family/size, bold/italic/underline, colors, align, lists, indent/outdent, quote, strikethrough, remove formatting, link, emoji, inline image, table, horizontal rule, code block; shortcuts; paste cleanup; plain-text mode; spell check. | Pasting rich HTML from the web | not started | - |
| 6.12-5 | Smart Compose | Optional module behind an interface; inline grey suggestion accepted with Tab; toggle in Settings. | No model configured → never shows | n/a | - |
| 6.12-6 | Bottom bar | Send (split button → Schedule send), Formatting (A), Attach files, Insert link, Insert emoji, Insert from Downloads library, Insert photo, Templates, Signature, Confidential mode (optional), More options, Discard. | Confidential mode unavailable → hidden | n/a | - |
| 6.12-7 | Draft autosave | Debounced ~3s after typing stops + on blur/minimize; "Saving.../Saved" indicator; drafts in Drafts; refresh restores open compose; crash recovery. | Concurrent tab edits | not started | - |
| 6.12-8 | Send behaviors | Send; Undo send toast (configurable 5/10/20/30s); Schedule send presets + custom (Scheduled, editable, cancellable); Send and archive; priority flag; optional read receipt; Ctrl+Enter or Tab+Enter sends. | Undo window elapsed | not started | - |
| 6.12-9 | Pre-send checks | Empty subject confirm; attachment-mentioned-but-none warning; invalid recipients; external recipient on official address; attachments still uploading. | User overrides warnings | not started | - |
| 6.12-10 | Attachments | Drag-drop anywhere, picker, per-file progress/cancel, thumbnails, remove; 25 MB default limit (configurable); over-limit → Downloads library link ("File too large, sent as link"); blocked types; virus-scan hook; inline images. | Virus scan failure → blocked | not started | - |
| 6.12-11 | Reply / Reply all / Forward | Inline at thread bottom or popped out; recipients prefilled (Reply-To then From; reply all excludes self + my aliases); Re:/Fwd: without stacking; quoted original with attribution; In-Reply-To/References headers; forward inline or as .eml; signature placement above quoted text (setting). | Forwarding a forwarded message (quote stacking) | not started | - |
| 6.12-12 | Templates | Save current draft as template; insert; overwrite; delete. | Template with attachments | not started | - |
| 6.12-13 | Signature | Multiple signatures; defaults for new mail and for replies. | Signature longer than body | not started | - |

## 6.13 Automatic official footer

| 6.13-1 | Server-side footer | Appended at send time (HTML + plain text), after user signature and quoted-text rules. Institute name, section/department, sender name+designation, official contact, server/portal link (deep link to sent message or section page), confidentiality disclaimer. | Footer on every outgoing mail, no exceptions | not started | - |
| 6.13-2 | Template variables | `{{sender_name}} {{sender_email}} {{designation}} {{section}} {{institute}} {{server_url}} {{message_link}} {{date}}`; all escaped. | Missing variable → empty value | not started | - |
| 6.13-3 | Admin editor | Per-section footer templates with default fallback + live preview; users cannot remove. | Section without template → group default | not started | - |
| 6.13-4 | Compose preview | Read-only footer preview line ("Official footer will be added when sent"). | Compose in plain-text mode | not started | - |
| 6.13-5 | No duplication | Older footers in quoted text detected and collapsed on reply/forward. | Quoted text without footer | not started | - |

## 6.14 Mailbox footer

| 6.14-1 | Footer content | Storage ("X GB of Y GB used" + Manage → Storage settings with per-section usage); Terms/Privacy/Program policies links; Mail server status (green/amber/red, provider name, last successful fetch; "Simulated server" in dummy); "Powered by IIITDM Jabalpur Mail"; "Last account activity: N minutes ago - Details". | Storage near limit | not started | - |
| 6.14-2 | Activity dialog | Recent activity table (access type web/mobile/API/SMTP, IP, approximate location, date-time); concurrent sessions table; current IP; "Sign out of all other sessions"; alert preference for unusual activity. | No other sessions | not started | - |

## 6.15 Downloads subsection

| 6.15-1 | Attachment library | All attachments from permitted sections, auto-indexed on ingest, deduped by hash, linked to source mail and section. Admin-uploaded documents (circulars, forms, notices) with title, description, category/section, tags, version, expiry. | Attachment with no source mail | not started | - |
| 6.15-2 | Views and filters | Grid/list; filters (section, type, date, sender, size); search by name/content; sort. | Empty library | not started | - |
| 6.15-3 | Preview and download | In-app preview (PDF/images/text); single and bulk ZIP; "Open source mail"; "Attach to new mail"; download counts; per-section permissions; admin upload/replace/delete; scan-status badge. | Bulk ZIP of zero files | not started | - |

## 6.16 Contacts and groups

| 6.16-1 | Contact list | Search; labels/groups (distribution lists, e.g. "CSE 2022 batch"); auto-collected "Other contacts" from sent/received; merge duplicates; import/export CSV and vCard; college directory source (admin CSV; later LDAP). | Duplicate merge conflicts | not started | - |
| 6.16-2 | Contact card | On hover over sender: name, email, recent mail, "Add to contacts", "Block". Used for compose autocomplete. | Sender without recent mail | not started | - |

## 6.17 Notifications

| 6.17-1 | Notification surface | Bell dropdown, unread badge, desktop notifications (opt-in per section: all/priority only/off), sound toggle, tab title count, favicon badge, optional daily digest, mute per section, quiet hours. | Notification permission denied | not started | - |

## 6.18 Accounts, aliases and identities

| 6.18-1 | Receiving addresses | Six aliases listed with status, last received, delivery health; enable/disable (admin). | Admin-only toggle | not started | - |
| 6.18-2 | Send mail as | Personal address + section addresses (if permitted); verification for new identities (dummy: auto-verified); per-identity signature/reply-to; default identity; "Reply from the address the message was sent to" via Delivered-To. | Identity without verification | not started | - |
| 6.18-3 | Delegation | Section admin can delegate send/read rights to another user with audit logging (optional). | Delegate revocation audit | n/a | - |
| 6.18-4 | Forwarding | Forward-all or filter-based forward to verified address; choices for original (keep in inbox / mark read / archive / delete); disabled by default. | Forwarding loop protection | not started | - |

## 6.19 Keyboard shortcuts

| 6.19-1 | Navigation | `g i`/`g s`/`g t`/`g d`/`g a`/`g c`/`g l`; `/` search; `j`/`k`; `o`/Enter open; `u` back to list; `n`/`p` next/prev in thread; `Esc` leave field/close. | Sequences time out after ~1.5s | not started | - |
| 6.19-2 | Selection | `x` select; `* a/n/r/u/s/t` all/none/read/unread/starred/unstarred. | Selection on zero rows | not started | - |
| 6.19-3 | Actions | `e` archive; `#` delete; `!` report spam; `s` star; `+`/`=` priority; `m` mute; `b` snooze; `l` label; `v` move; `.` more; `r`/`a`/`f` reply/all/forward; `Shift+i/u` read/unread; `Shift+n` refresh; `z` undo; `c`/`d`/`Shift+c` compose variants. | Shortcuts inert inside inputs | not started | - |
| 6.19-4 | Compose shortcuts | Ctrl+Enter/Tab+Enter send; Ctrl+Shift+D discard; Ctrl+Shift+C/B Cc/Bcc; Ctrl+K link; Ctrl+./Ctrl+, switch windows; formatting shortcuts. | Compose not focused | not started | - |
| 6.19-5 | Help | `?` opens shortcut help; on-screen hint after first key of a sequence. | Help modal accessibility | not started | - |

## 6.20 Tasks and events (optional module)

| 6.20-1 | Tasks | "Add to Tasks" from toolbar/message menu; task linked to message (title, due date, done); Tasks panel in right side panel. | Feature flag off → hidden | n/a | - |
| 6.20-2 | Events | "Create event" → .ics download / college calendar hook. | Calendar provider not configured | n/a | - |

## 6.21 Global Undo system

| 6.21-1 | UndoManager | All reversible actions through one system: toast with Undo (~8s), `z` shortcut, bulk-action undo restores server-side state. Send has its own delay window. | Undo window elapsed → irreversible | not started | - |

## Hybrid engine (Section 7 / Section 2.4 worked examples)

| H-1 | Six aliases → one mailbox | Delivered-To chip; `deliveredto:` operator; one message stored once even when addressed to several aliases. | Multi-alias dedupe | not started | - |
| H-2 | Sender clusters | Exact / domain / pattern rules; priority; active flag; notes; CSV import/export; "Test a sender"; "Apply to existing mail" with preview count; change history. | Duplicate rule registration | not started | - |
| H-3 | routeMail() precedence | exact > domain > pattern; within a type higher priority wins, then oldest; quarantine on failed auth; conflicts logged; recipients are not inputs. | Sender registered in two sections → conflict view | not started | - |
| H-4 | Unassigned / Quarantine | Unknown sender → Unassigned queue (admin only); failed auth → Quarantine; one-click resolve with optional retro-apply. | Retro-apply idempotency | not started | - |
| H-5 | Manual re-route | Admin changes message section with reason; audit logged; overrides survive retro-apply unless reset. | Re-routing to invalid section | not started | - |
| H-6 | Section label protection | Section labels are system-owned; user filters/labels can never remove or change them. | Filter attempt → validation error | not started | - |
| H-7 | Server-side authorization | Every endpoint authorized; section isolation enforced server-side. | Cross-section access attempt → 403/404 | not started | - |
| H-8 | Provider abstraction | dummy now; imap/graph/gmail/webhook later by configuration only (`MAIL_PROVIDER`). | Switching provider requires config only | not started | - |

## Worked examples (Section 2.4 — must become automated tests)

| W-1 | hr@acme.com → ug-placement@ | Placement Cell | | not started | - |
| W-2 | hr@acme.com → ug-sports@ | Placement Cell | | not started | - |
| W-3 | hr@acme.com → registrar@ & ug-cultural@ | Placement Cell, ONE stored message | | not started | - |
| W-4 | dean.acad@iiitdmj.ac.in → ug-placement@ | Academics | | not started | - |
| W-5 | coach@iiitdmj.ac.in → registrar@ | Sports | | not started | - |
| W-6 | unknown@gmail.com → ug-sports@ | Unassigned | | not started | - |
| W-7 | HR@Acme.com → any | Placement Cell | case-insensitive sender | not started | - |
| W-8 | "HR Team" <hr@acme.com> → any | Placement Cell | display-name parsing | not started | - |
| W-9 | hr+jobs@acme.com (plus-strip on) → any | Placement Cell | tag stripping setting | not started | - |
| W-10 | spoofed hr@acme.com failing auth → any | Quarantine | auth verdict | not started | - |

## Summary

| Group | Rows | done | in progress | not started | n/a |
|---|---|---|---|---|---|
| 6.1 Inbox types | 8 | 0 | 0 | 8 | 0 |
| 6.2 Message list | 10 | 0 | 0 | 10 | 0 |
| 6.3 Conversation/reading | 12 | 0 | 0 | 12 | 0 |
| 6.4 Three-dot menu | 5 | 0 | 0 | 5 | 0 |
| 6.5 Labels | 4 | 0 | 0 | 4 | 0 |
| 6.6 Stars/Priority | 3 | 0 | 0 | 3 | 0 |
| 6.7 Archive/mute/snooze/move | 5 | 0 | 0 | 5 | 0 |
| 6.8 Spam/phishing/block | 5 | 0 | 0 | 5 | 0 |
| 6.9 Trash/retention | 1 | 0 | 0 | 1 | 0 |
| 6.10 Search | 6 | 0 | 0 | 6 | 0 |
| 6.11 Filters | 5 | 0 | 0 | 5 | 0 |
| 6.12 Compose | 13 | 0 | 0 | 13 | 0 |
| 6.13 Footer | 5 | 0 | 0 | 5 | 0 |
| 6.14 Mailbox footer | 2 | 0 | 0 | 2 | 0 |
| 6.15 Downloads | 3 | 0 | 0 | 3 | 0 |
| 6.16 Contacts | 2 | 0 | 0 | 2 | 0 |
| 6.17 Notifications | 1 | 0 | 0 | 1 | 0 |
| 6.18 Accounts/aliases | 4 | 0 | 0 | 4 | 0 |
| 6.19 Shortcuts | 5 | 0 | 0 | 5 | 0 |
| 6.20 Tasks/events | 2 | 0 | 0 | 0 | 2 |
| 6.21 Undo | 1 | 0 | 0 | 1 | 0 |
| Hybrid engine | 8 | 0 | 0 | 8 | 0 |
| Worked examples | 10 | 0 | 0 | 10 | 0 |
| **Total** | **~119** | **0** | **0** | **~117** | **2** |

### How to use this file
- Update `Status` and `Test reference` at the end of each phase.
- A row becomes `done` only when its feature is implemented AND its test passes AND it is verified in the UI walkthrough.
- `n/a` rows need a reason (shown above for Smart Compose, Confidential mode, Tasks/events, delegation).
- Phase 12 is complete only when every row is `done` or `n/a`.
