export type Totals = { in: number; out: number; cw: number; cr: number; turns: number }
export type WindowView = { tokens: Totals; start: number; end?: number; percent?: number; weekPercent?: number }
export type ChatRow = { id: string; last: number; tot: Totals }

declare module 'claude-code' {
  interface PluginState {
    'token-meter': { chat: Totals; window: WindowView; chats: ChatRow[] }
  }
}
