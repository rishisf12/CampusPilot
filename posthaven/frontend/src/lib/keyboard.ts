export type Shortcut = {
  key: string
  meta?: boolean // Cmd/Ctrl
  shift?: boolean
  description: string
  handler: () => void
}

const SHORTCUTS: Shortcut[] = []

export function registerShortcut(shortcut: Shortcut) {
  SHORTCUTS.push(shortcut)
}

export function getShortcuts() {
  return SHORTCUTS
}

let installed = false

export function installKeyboardHandler() {
  if (installed) return
  installed = true
  document.addEventListener("keydown", (e) => {
    // Ignore when typing in inputs
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || (e.target as HTMLElement).isContentEditable)
      return
    const meta = e.metaKey || e.ctrlKey
    const shift = e.shiftKey
    const key = e.key.toLowerCase()
    for (const s of SHORTCUTS) {
      if ((!!s.meta === !!meta || !s.meta) && (!!s.shift === !!shift || !s.shift) && s.key.toLowerCase() === key) {
        e.preventDefault()
        s.handler()
        break
      }
    }
  })
}
