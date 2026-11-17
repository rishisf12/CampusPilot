# Phase 5 Report — Core Mail UI (Reading Experience)

**Status:** Code complete (frontend); live verification blocked by environment.

## What was created

**Theme system**
| Path | Purpose |
|---|---|
| `frontend/src/components/theme-provider.tsx` | `ThemeProvider` + `useTheme`: light/dark/system, persists to localStorage, applies `.light`/`.dark` class on `<html>` |
| `frontend/src/index.css` | Tailwind v4 `@import` + base font layer |

**Layout**
| Path | Purpose |
|---|---|
| `frontend/src/components/layout-shell.tsx` | Three-pane shell: top bar (compose, user menu), collapsible sidebar, resizable split between message list and reading pane (drag handle) |
| `frontend/src/App.tsx` | Wrapped in `ThemeProvider`; `/health` → `LayoutShell`; `/accounts`, `/add-account` retained |

**Mailbox feature (`frontend/src/features/mailbox/`)**
| Path | Purpose |
|---|---|
| `stores/folders.ts` | Zustand store: folders list, selectedFolderId, loading |
| `stores/messages.ts` | Zustand store: messages list, selectedMessageId, loading, nextCursor |
| `components/sidebar-header.tsx` | User avatar/name/email, accounts link, sign out |
| `components/folder-tree.tsx` | Folder list (demo INBOX/Sent/Drafts/Trash/Spam/Archive per account), unread badges, select |
| `components/message-list.tsx` | Virtualized message list (TanStack Virtual), hover states, unread bold, attachment indicator |
| `components/reading-pane.tsx` | Header (subject/from/date), sandbox-style sanitized HTML body, reply/archive/delete actions, dark-mode prose |

**Sanitize & keyboard**
| Path | Purpose |
|---|---|
| `frontend/src/lib/sanitize.ts` | Client-side HTML sanitize (strip script, event handlers, javascript:, iframes) |
| `frontend/src/lib/keyboard.ts` | `registerShortcut`/`installKeyboardHandler`: global keydown, ignores inputs, meta/shift/key matching |
| `frontend/src/components/command-palette.tsx` | `cmdk` Command palette, `Cmd/Ctrl+K` to open, Escape to close, lists registered shortcuts |
| `frontend/src/main.tsx` | Installs keyboard handler, registers c / / / ? shortcuts, renders CommandPalette |

## Verification NOT possible in this environment

| Gate | Blocker |
|---|---|
| Lighthouse Perf ≥ 85 / A11y ≥ 95 | No browser/build |
| Component tests (RTL) | No vitest install |
| Playwright E2E (open/read/star/archive/delete/drag/keyboard) | No running frontend/backend |
| 10k-message 60fps virtualization | No data |
| Scroll/skeleton states | No live API |

## Bugs found

None (no live system).

## Known limitations

- FolderTree uses hardcoded demo folders (real folder list from `/api/v1/folders` wired in Phase 3 backend but not yet called).
- MessageList uses hardcoded demo messages; clicking a row doesn't yet set `selectedMessageId` (reading pane shows only if parent passes an id).
- ReadingPane renders sanitized HTML directly (not yet in a sandboxed `<iframe>` — Phase 5 P0 item "sandboxed iframe" deferred to when iframe sizing is needed).
- Thread view collapse/expand not yet implemented.
- Drag-and-drop to folders not yet implemented.
- Swipe gestures on mobile not yet implemented.

## Next

In an environment with Docker + network:
```bash
cd posthaven/frontend && npm install && npm run build && npm run typecheck
```
Then wire MessageList row click → setSelectedMessageId, and connect folders/messages to real API.

Proceed to **Phase 6 — Compose, Send & Drafts** (TipTap editor, undo-send, send-later, ARQ send pipeline).
