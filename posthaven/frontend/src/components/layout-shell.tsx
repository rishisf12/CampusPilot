import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { FolderTree } from "@/features/mailbox/components/folder-tree"
import { MessageList } from "@/features/mailbox/components/message-list"
import { ReadingPane } from "@/features/mailbox/components/reading-pane"
import { useFoldersStore } from "@/features/mailbox/stores/folders"
import { useMessagesStore } from "@/features/mailbox/stores/messages"
import { SidebarHeader } from "@/features/mailbox/components/sidebar-header"
import { accountsApi, type MailAccount } from "@/lib/accounts"
import { foldersApi } from "@/lib/folders"
import { messagesApi } from "@/lib/messages"
import { mailWs } from "@/lib/ws"

function sortFolders(folders: { name: string; special_use?: string | null }[]) {
  return [...folders].sort((a, b) => {
    const aInbox = a.special_use === "\\Inbox" || a.name === "INBOX"
    const bInbox = b.special_use === "\\Inbox" || b.name === "INBOX"
    if (aInbox !== bInbox) return aInbox ? -1 : 1
    return a.name.localeCompare(b.name)
  })
}

export function LayoutShell() {
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [accountsLoading, setAccountsLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState("")
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)

  const {
    selectedFolderId,
    setSelectedFolderId,
    setFolders,
    setLoading: setFoldersLoading,
  } = useFoldersStore()
  const {
    selectedMessageId,
    setSelectedMessageId,
    setMessages,
    setLoading: setMessagesLoading,
  } = useMessagesStore()
  const selectedAccount = accounts.find((a) => a.id === accountId) ?? null
  const accountIdRef = useRef(accountId)
  accountIdRef.current = accountId

  const refreshFolders = useCallback(
    async (accId: string) => {
      setFoldersLoading(true)
      try {
        const folders = await foldersApi.list(accId)
        setFolders(sortFolders(folders))
        const current = useFoldersStore.getState().selectedFolderId
        if (current && folders.some((f) => f.id === current)) return
        const inbox = folders.find(
          (f) => f.special_use === "\\Inbox" || f.name === "INBOX",
        )
        setSelectedFolderId((inbox ?? folders[0])?.id ?? null)
      } finally {
        setFoldersLoading(false)
      }
    },
    [setFolders, setSelectedFolderId, setFoldersLoading],
  )

  const refreshMessages = useCallback(
    async (folderId: string) => {
      setMessagesLoading(true)
      try {
        const res = await messagesApi.list(folderId)
        setMessages(res.messages)
      } finally {
        setMessagesLoading(false)
      }
    },
    [setMessages, setMessagesLoading],
  )

  // reload visible data without triggering a server sync
  const refreshAll = useCallback(
    async (accId: string) => {
      await refreshFolders(accId)
      const fid = useFoldersStore.getState().selectedFolderId
      if (fid) await refreshMessages(fid)
    },
    [refreshFolders, refreshMessages],
  )

  const syncNow = useCallback(
    async (accId: string) => {
      setSyncing(true)
      setSyncError("")
      try {
        const stats = await accountsApi.sync(accId)
        if (stats.errors?.length) setSyncError(stats.errors.join("; "))
        await refreshAll(accId)
        return stats
      } catch (err) {
        setSyncError(err instanceof Error ? err.message : "Sync failed")
        return null
      } finally {
        setSyncing(false)
      }
    },
    [refreshAll],
  )

  // load accounts on mount
  useEffect(() => {
    let cancelled = false
    accountsApi
      .list()
      .then((list) => {
        if (cancelled) return
        setAccounts(list)
        setAccountsLoading(false)
        setAccountId((cur) => cur ?? list[0]?.id ?? null)
      })
      .catch(() => setAccountsLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  // WS: react to server push events (sync:complete refreshes; mail:incoming syncs)
  useEffect(() => {
    if (accounts.length === 0) return
    mailWs.subscribe(accounts.map((a) => a.id))
    const off = mailWs.on((event) => {
      const accId = event.account_id
      if (!accId || accountIdRef.current !== accId) return
      if (event.type === "mail:incoming") {
        // server flagged new mail -> do a full sync (publishes sync:complete)
        syncNow(accId)
      } else if (event.type === "sync:complete" || event.type === "sync:error") {
        // data changed server-side -> only refresh, never re-sync here
        refreshAll(accId)
      }
    })
    return () => {
      off()
    }
  }, [accounts, syncNow, refreshAll])

  // when the selected account changes, sync + load folders
  useEffect(() => {
    if (!accountId) return
    syncNow(accountId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId])

  // refresh messages when folder changes
  useEffect(() => {
    if (!selectedFolderId) return
    refreshMessages(selectedFolderId)
    setSelectedMessageId(null)
  }, [selectedFolderId, refreshMessages, setSelectedMessageId])

  if (accountsLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-50 text-slate-500">
        Loading…
      </div>
    )
  }

  if (accounts.length === 0) {
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-4 bg-slate-50 text-slate-600 px-6 text-center">
        <span className="material-symbols-rounded text-5xl text-slate-400">mail</span>
        <h1 className="text-xl font-semibold text-slate-900">Connect your first mail account</h1>
        <p className="max-w-sm text-sm">
          PostHaven syncs your mail over IMAP and sends via SMTP. Your credentials are
          encrypted at rest.
        </p>
        <button
          onClick={() => navigate("/add-account")}
          className="px-4 py-2 rounded-md bg-slate-900 text-white text-sm font-medium hover:bg-slate-800"
        >
          Add mail account
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-slate-50 text-slate-900 overflow-hidden">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-white shrink-0 z-10">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-2 rounded-md hover:bg-slate-200 text-slate-600"
            aria-label="Toggle sidebar"
          >
            <span className="material-symbols-rounded">menu</span>
          </button>
          <div className="hidden md:flex items-center gap-1 text-slate-900 font-bold text-lg tracking-tight">
            PostHaven
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* account switcher */}
          <div className="relative">
            <button
              onClick={() => setAccountMenuOpen((v) => !v)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-slate-100 text-sm text-slate-700 max-w-[220px]"
              aria-label="Switch account"
            >
              <span className="truncate">{selectedAccount?.username ?? "Select account"}</span>
              <span className="material-symbols-rounded text-base">unfold_more</span>
            </button>
            {accountMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-72 bg-white border border-slate-200 rounded-lg shadow-lg py-2 z-20">
                {accounts.map((acc) => (
                  <button
                    key={acc.id}
                    onClick={() => {
                      setAccountId(acc.id)
                      setAccountMenuOpen(false)
                    }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-slate-50 flex items-center justify-between gap-2"
                  >
                    <span className="truncate">{acc.username}</span>
                    {acc.id === accountId && (
                      <span className="material-symbols-rounded text-base text-blue-600">check</span>
                    )}
                  </button>
                ))}
                <div className="border-t border-slate-100 pt-2 mt-2">
                  <button
                    onClick={() => navigate("/accounts")}
                    className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    Manage accounts…
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* sync now */}
          <button
            onClick={() => accountId && syncNow(accountId)}
            disabled={!accountId || syncing}
            className="p-2 rounded-md hover:bg-slate-200 text-slate-600 disabled:opacity-50"
            aria-label="Sync now"
            title="Sync now"
          >
            <span className={`material-symbols-rounded ${syncing ? "animate-spin" : ""}`}>sync</span>
          </button>

          {/* compose */}
          <button
            onClick={() => navigate("/compose")}
            className="p-2 rounded-md hover:bg-slate-200 text-slate-600"
            aria-label="Compose"
            title="Compose"
          >
            <span className="material-symbols-rounded">edit</span>
          </button>
        </div>
      </header>

      {/* sync error banner */}
      {syncError && (
        <div className="px-4 py-2 bg-red-50 text-red-700 text-xs border-b border-red-200">
          Sync error: {syncError}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {!collapsed && (
          <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0">
            <SidebarHeader />
            <FolderTree selectedFolderId={selectedFolderId} onSelect={setSelectedFolderId} />
          </aside>
        )}

        <div className="flex-1 flex flex-col relative overflow-hidden">
          <div className="flex flex-1 overflow-hidden">
            {/* Message list */}
            <div
              className={`flex flex-col border-r border-slate-200 bg-white ${
                !selectedMessageId ? "w-full" : "w-[45%] min-w-[280px]"
              }`}
            >
              <MessageList folderId={selectedFolderId} />
            </div>
            {/* Reading pane */}
            {selectedMessageId ? (
              <div className="flex flex-col flex-1 min-w-0">
                <ReadingPane
                  messageId={selectedMessageId}
                  onDismiss={() => setSelectedMessageId(null)}
                  onChanged={() => {
                    if (selectedFolderId) refreshMessages(selectedFolderId)
                    if (accountIdRef.current) refreshFolders(accountIdRef.current)
                  }}
                />
              </div>
            ) : (
              <div className="hidden md:flex flex-col flex-1 items-center justify-center text-slate-400 gap-3">
                <span className="material-symbols-rounded text-5xl">drafts</span>
                <p className="text-sm">Select a message to read</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
