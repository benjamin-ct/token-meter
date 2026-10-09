import { atom, read, update } from 'claude-code'
import type { EngineInterface, ModelUsage, Register } from 'claude-code'

import type { ChatRow, Totals, WindowView } from '../types'

// --------------------------------------------------------------- état
const ZERO: Totals = { in: 0, out: 0, cw: 0, cr: 0, turns: 0 }
const chat = atom({ plugin: 'token-meter', key: 'chat' } as const, ZERO)
const windowView = atom({ plugin: 'token-meter', key: 'window' } as const, { tokens: ZERO, start: 0 })
const chats = atom({ plugin: 'token-meter', key: 'chats' } as const, [])

const PANE = 'token-meter'
const HOUR = 3_600_000
const BLOCK = 5 * HOUR
type LogEntry = [number, number, number, number, number] // [ms, in, out, cw, cr]

// --------------------------------------------------------------- calculs
export const sum = (t: Totals) => t.in + t.out + t.cw + t.cr

export function add(t: Totals, u: ModelUsage): Totals {
  return {
    in: t.in + u.input_tokens,
    out: t.out + u.output_tokens,
    cw: t.cw + u.cache_creation_input_tokens,
    cr: t.cr + u.cache_read_input_tokens,
    turns: t.turns + 1,
  }
}

export function fmt(n: number): string {
  for (const [unit, div] of [['G', 1e9], ['M', 1e6], ['k', 1e3]] as const) {
    if (Math.abs(n) >= div) {
      const v = n / div
      return (v < 100 ? v.toFixed(1) : v.toFixed(0)) + unit
    }
  }
  return String(Math.round(n))
}

export function inDelay(ms: number): string {
  if (ms <= 0) return 'maintenant'
  const m = Math.round(ms / 60_000)
  return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}` : `${m} min`
}

/** Début de la session de 5 h quand l'API ne la donne pas : comme ccusage. */
export function guessWindowStart(log: LogEntry[], now: number): number {
  let start = 0
  for (const [t] of [...log].sort((a, b) => a[0] - b[0])) {
    if (!start || t >= start + BLOCK) start = Math.floor(t / HOUR) * HOUR
  }
  return start && start + BLOCK > now ? start : now
}

export function totalsSince(log: LogEntry[], since: number): Totals {
  let t = ZERO
  for (const [ts, i, o, cw, cr] of log) {
    if (ts >= since) t = { in: t.in + i, out: t.out + o, cw: t.cw + cw, cr: t.cr + cr, turns: t.turns + 1 }
  }
  return t
}

export function line(c: Totals, w: WindowView, now: number): string {
  let s = `💬 Tchat ${fmt(sum(c))} (↑${fmt(c.in + c.cw)} ↓${fmt(c.out)} ⟲${fmt(c.cr)})`
  s += ` │ ⏱ Session 5h ${fmt(sum(w.tokens))}`
  if (w.percent !== undefined) s += ` · ${Math.round(w.percent)}%`
  if (w.end) s += ` · reset dans ${inDelay(w.end - now)}`
  return s
}

// --------------------------------------------------------------- stockage (entre sessions)
async function getLog($: EngineInterface): Promise<LogEntry[]> {
  const v = await $.store.get('log')
  return Array.isArray(v) ? (v as LogEntry[]) : []
}

async function refresh($: EngineInterface) {
  const now = await $.clock.now()
  const log = await getLog($)
  const { rateLimits } = await $.session.usage()
  const five = rateLimits.find(r => r.kind === 'five_hour')
  const week = rateLimits.find(r => r.kind === 'seven_day')
  const resets = five?.resetsAt ? Date.parse(five.resetsAt) : NaN

  let start: number
  let end: number | undefined
  if (!Number.isNaN(resets)) {
    end = resets
    start = resets - BLOCK
  } else {
    start = guessWindowStart(log, now)
    end = start < now ? start + BLOCK : undefined
  }
  const view: WindowView = { tokens: totalsSince(log, start), start, end }
  if (five) view.percent = five.percentUsed
  if (week) view.weekPercent = week.percentUsed
  await update($, windowView, () => view)
  $.ui.status(line(await read($, chat), view, now))
}

// --------------------------------------------------------------- hooks
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'token-meter',
      description: 'Ouvre le panneau des tokens (tchat, session de 5 h, derniers tchats)',
    })
    // reprise d'un tchat déjà compté par le mod
    const id = await $.session.id()
    const saved = ((await $.store.get('chats')) as ChatRow[] | undefined) ?? []
    const mine = saved.find(r => r.id === id)
    if (mine) await update($, chat, () => mine.tot)
    await update($, chats, () => saved)
    await refresh($)
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    const u = e.usage
    if (!u) return result

    const now = await $.clock.now()
    const id = await $.session.id()
    const tot = await update($, chat, t => add(t, u))

    // journal partagé entre toutes les sessions (6 h gardées)
    const log = (await getLog($)).filter(([t]) => t > now - BLOCK - HOUR)
    log.push([now, u.input_tokens, u.output_tokens, u.cache_creation_input_tokens, u.cache_read_input_tokens])
    await $.store.set('log', log)

    // historique par tchat (30 derniers)
    const saved = ((await $.store.get('chats')) as ChatRow[] | undefined) ?? []
    const rows = [{ id, last: now, tot }, ...saved.filter(r => r.id !== id)].slice(0, 30)
    await $.store.set('chats', rows)
    await update($, chats, () => rows)

    await refresh($)
    return result
  })

  // le % de limite bouge aussi entre deux tours (autres tchats, claude.ai…)
  on('session.measure', async ($, e, next) => {
    if (e.changed.includes('rateLimits')) await refresh($)
    return next(e)
  })

  // /clear : nouveau tchat, compteur remis à zéro
  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') await update($, chat, () => ZERO)
    return next(e)
  })

  on('command.run', { command: 'token-meter' }, async $ => {
    await refresh($)
    await $.ui.open({ id: PANE, title: 'Tokens' })
    const now = await $.clock.now()
    return { text: line(await read($, chat), await read($, windowView), now) }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const c = await read($, chat)
    const w = await read($, windowView)
    const list = await read($, chats)
    const now = await $.clock.now()
    const room = Math.max(1, (e.viewport?.rows ?? 24) - 14)
    const id = await $.session.id()

    return (
      <Box flexDirection="column">
        <Text bold>💬 Ce tchat : {fmt(sum(c))} tokens</Text>
        <Text dimColor>
          entrée {fmt(c.in)} · sortie {fmt(c.out)} · cache écrit {fmt(c.cw)} · cache lu {fmt(c.cr)} · {c.turns} réponses
        </Text>
        <Text> </Text>
        <Text bold>⏱ Session de 5 h : {fmt(sum(w.tokens))} tokens</Text>
        <Text dimColor>
          {w.percent !== undefined ? `${Math.round(w.percent)} % de la limite` : 'limite : pas encore de relevé'}
          {w.end ? ` · reset dans ${inDelay(w.end - now)}` : ''}
          {w.weekPercent !== undefined ? ` · semaine ${Math.round(w.weekPercent)} %` : ''}
        </Text>
        <Text dimColor>
          entrée {fmt(w.tokens.in)} · sortie {fmt(w.tokens.out)} · cache écrit {fmt(w.tokens.cw)} · cache lu {fmt(w.tokens.cr)}
        </Text>
        <Text> </Text>
        <Text bold>Derniers tchats</Text>
        {list.length === 0 && <Text dimColor>Aucun tchat compté pour l'instant.</Text>}
        {list.slice(0, room).map(r => (
          <Text dimColor={r.id !== id}>
            {r.id === id ? '● ' : '  '}
            {r.id.slice(0, 8)} · {now - r.last < 60_000 ? "à l'instant" : `il y a ${inDelay(now - r.last)}`} · {fmt(sum(r.tot))} tokens ({r.tot.turns} rép.)
          </Text>
        ))}
      </Box>
    )
  })
}
