const WS_BASE = import.meta.env.VITE_WS_BASE ?? (typeof window !== "undefined" ? (window.location.protocol === "https:" ? "wss:" : "ws:") + "//" + window.location.host : "")

export type WsEvent = {
  type: string
  account_id?: string
  payload?: any
  ts: string
}

export class MailWs {
  private ws: WebSocket | null = null
  private reconnectTimer: any = null
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private listeners: Set<(e: WsEvent) => void> = new Set()
  private subscribedAccountIds: string[] = []
  private connecting = false
  private closed = false
  private enabled = false

  constructor() {}

  enable() {
    this.enabled = true
    this.connect()
  }

  disable() {
    this.enabled = false
    this.disconnect()
  }

  private connect() {
    if (!this.enabled) return
    if (this.connecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) return
    this.connecting = true
    const url = `${WS_BASE}/ws`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.connecting = false
      this.reconnectDelay = 1000
      this.subscribedAccountIds = []
      this.send({ type: "subscribe", account_ids: this.subscribedAccountIds })
    }

    this.ws.onmessage = (event) => {
      try {
        const parsed: WsEvent = JSON.parse(event.data)
        this.listeners.forEach((cb) => cb(parsed))
      } catch {
        // ignore malformed
      }
    }

    this.ws.onclose = () => {
      this.connecting = false
      this.ws = null
      if (!this.closed) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      if (this.ws) this.ws.close()
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
      this.connect()
    }, this.reconnectDelay)
  }

  subscribe(accountIds: string[]) {
    this.subscribedAccountIds = accountIds
    this.send({ type: "subscribe", account_ids: accountIds })
  }

  ping() {
    this.send({ type: "ping", ts: Date.now() })
  }

  send(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  on(event: (e: WsEvent) => void) {
    this.listeners.add(event)
    return () => this.listeners.delete(event)
  }

  disconnect() {
    this.closed = true
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.listeners.clear()
  }
}

export const mailWs = new MailWs()
