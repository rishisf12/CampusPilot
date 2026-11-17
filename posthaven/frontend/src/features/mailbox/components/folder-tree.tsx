import { useFoldersStore, type Folder } from "@/features/mailbox/stores/folders"

const ICON_BY_NAME: Record<string, string> = {
  INBOX: "inbox",
  Sent: "send",
  Drafts: "draft",
  Trash: "delete",
  Junk: "report",
  Spam: "report",
  Archive: "archive",
}

function iconFor(folder: Folder): string {
  const special = folder.special_use ?? ""
  if (special.includes("Sent")) return "send"
  if (special.includes("Drafts")) return "draft"
  if (special.includes("Trash")) return "delete"
  if (special.includes("Junk")) return "report"
  if (special.includes("Archive")) return "archive"
  return ICON_BY_NAME[folder.name] ?? "folder"
}

export function FolderTree({
  selectedFolderId,
  onSelect,
}: {
  selectedFolderId: string | null
  onSelect: (id: string | null) => void
}) {
  const { folders, loading } = useFoldersStore()

  if (loading) {
    return (
      <div className="p-3 flex flex-col gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-8 bg-slate-100 rounded animate-pulse" />
        ))}
      </div>
    )
  }

  if (folders.length === 0) {
    return (
      <div className="p-4 text-sm text-slate-500">
        No folders yet. Hit the sync button above to fetch your mail.
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-2 space-y-1">
      {folders.map((folder) => {
        const isUnread = (folder.unread_count || 0) > 0
        return (
          <button
            key={folder.id}
            onClick={() => onSelect(folder.id)}
            className={`flex w-full items-center gap-3 px-3 py-2 rounded-lg text-sm ${
              selectedFolderId === folder.id
                ? "bg-blue-50 text-blue-700 font-medium"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            <span className="material-symbols-rounded w-5 h-5">
              {iconFor(folder)}
            </span>
            <span className="flex-1 truncate text-left">{folder.name}</span>
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
