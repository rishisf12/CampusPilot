import { useState, useEffect, useRef } from "react"
import { Command } from "cmdk"
import { getShortcuts } from "@/lib/keyboard"

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      inputRef.current?.focus()
    }
  }, [open])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen(true)
      }
      if (open && e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open])

  return (
    <Command
      open={open}
      onOpenChange={setOpen}
      loader={(value) => {
        const shortcuts = getShortcuts()
        return shortcuts
          .filter((s) =>
            value ? s.description.toLowerCase().includes(value.toLowerCase()) : true
          )
          .map((s) => ({
            id: `${s.key}:${s.description}`,
            name: s.description,
            shortcut: (s.meta ? "⌘" : "") + s.key.toUpperCase(),
            onSelect: s.handler,
          }))
      }}
    >
      <Command.Empty>No shortcuts found</Command.Empty>
      <Command.Input ref={inputRef} placeholder="Search shortcuts…" />
      <Command.List />
    </Command>
  )
}
