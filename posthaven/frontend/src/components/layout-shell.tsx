import { useState } from "react"
import { FolderTree } from "@/features/mailbox/components/folder-tree"
import { MessageList } from "@/features/mailbox/components/message-list"
import { ReadingPane } from "@/features/mailbox/components/reading-pane"
import { useFoldersStore } from "@/features/mailbox/stores/folders"
import { useMessagesStore } from "@/features/mailbox/stores/messages"
import { SidebarHeader } from "@/features/mailbox/components/sidebar-header"

export function LayoutShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [paneSplit, setPaneSplit] = useState(50) // percent for list vs reading

  const { selectedFolderId, setSelectedFolderId } = useFoldersStore()
  const { selectedMessageId, setSelectedMessageId } = useMessagesStore()

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
          <button className="p-2 rounded-md hover:bg-slate-200 text-slate-600" aria-label="Compose">
            <span className="material-symbols-rounded">edit</span>
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {!collapsed && (
          <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0">
            <SidebarHeader />
            <FolderTree selectedFolderId={selectedFolderId} onSelect={setSelectedFolderId} />
          </aside>
        )}

        {/* Resizable split between list and reading pane */}
        <div className="flex-1 flex flex-col relative">
          <div
            className={`absolute left-0 top-0 bottom-0 w-1 cursor-ew bg-transparent hover:bg-blue-200/30`}
            onMouseDown={(e) => {
              e.preventDefault()
              const startX = e.clientX
              const start = paneSplit
              const onMove = (ev: MouseEvent) => {
                const dx = ev.clientX - startX
                setPaneSplit(Math.min(Math.max(start + dx, 25), 85))
              }
              const onUp = () => {
                window.removeEventListener("mousemove", onMove)
                window.removeEventListener("mouseup", onUp)
              }
              window.addEventListener("mousemove", onMove)
              window.addEventListener("mouseup", onUp, { once: true })
            }}
          />
          <div className="flex flex-1 overflow-hidden">
            {/* Message list */}
            <div
              className={`flex flex-col border-r border-slate-200 bg-white ${!selectedMessageId ? "w-full" : `w-[${paneSplit}%]`}`}
            >
              <MessageList folderId={selectedFolderId} />
            </div>
            {/* Reading pane */}
            {selectedMessageId && (
              <div className={`flex flex-col ${paneSplit === 0 ? "hidden" : "block"}`}>
                <ReadingPane messageId={selectedMessageId} onDismiss={() => setSelectedMessageId(null)} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
