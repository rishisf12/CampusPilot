import { useEffect, useState } from "react"
import { useFoldersStore } from "@/features/mailbox/stores/folders"
import { accountsApi } from "@/lib/accounts"

export function FolderTree({
  selectedFolderId,
  onSelect,
}: {
  selectedFolderId: string | null
  onSelect: (id: string | null) => void
}) {
  const { folders, loading, setFolders, setLoading } = useFoldersStore()
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (initialized) return
    let cancelled = false
    accountsApi.list().then((accounts: any[]) => {
      if (cancelled) return
      // Demo folders per account
      const demoFolders: any[] = []
      accounts.forEach((acc) => {
        const special = ["INBOX", "Sent", "Drafts", "Trash", "Spam", "Archive"]
        special.forEach((name) => {
          demoFolders.push({
            id: `${acc.id}:${name}`,
            account_id: acc.id,
            name,
            special_use: name,
            subscribed: true,
            message_count: 0,
            unread_count: 0,
            synced: true,
          })
        })
      })
      setFolders(demoFolders)
      setLoading(false)
    }).catch(() => setLoading(false))
    setInitialized(true)
    return () => { cancelled = true }
  }, [initialized, setFolders, setLoading])

  if (loading) {
    return (
      <div className="p-3 flex flex-col gap-2">
        <div className="h-4 bg-slate-200 rounded w-1/3"></div>
        <div className="h-4 bg-slate-200 rounded w-1/2"></div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-2 space-y-1">
      {folders.map((folder) => {
        const isUnread = (folder.unread_count || 0) > 0
        const special = folder.special_use
        const iconMap: Record<string, string> = {
          INBOX: "inbox",
          Sent: "send",
          Drafts: "draft",
          Trash: "delete",
          Spam: "report",
          Archive: "archive",
        }
        return (
          <button
            key={folder.id}
            onClick={() => onSelect(folder.id)}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              selectedFolderId === folder.id
                ? "bg-blue-50 text-blue-700 font-medium"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            <span className="material-symbols-rounded w-5 h-5">
              {iconMap[folder.name] || "folder"}
            </span>
            <span className="flex-1 truncate">{folder.name}</span>
            {isUnread && (
              <span className="bg-blue-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {folder.unread_count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
