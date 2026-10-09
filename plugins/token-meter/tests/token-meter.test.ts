import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { fmt, guessWindowStart, inDelay } from '../hooks/register'

const HOUR = 3_600_000
const NOW = Date.parse('2026-10-09T16:00:00Z')

function engine(on: On, opts: { percent?: number; resetsAt?: string; store?: Record<string, unknown> } = {}) {
  const clock = mock.clock(on, { now: NOW })
  mock.store(on, opts.store)
  const status: (string | undefined)[] = []
  on('session.id', () => ({ value: 'sess-aaaa1111' }))
  on('session.usage', () => ({
    value: {
      startedAt: NOW,
      context: { window: 200_000 },
      rateLimits:
        opts.percent === undefined
          ? []
          : [{ kind: 'five_hour', percentUsed: opts.percent, resetsAt: opts.resetsAt }],
    },
  }))
  on('ui.status', (_, e) => {
    status.push(e.text)
    return { value: undefined }
  })
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.end', (_, e) => ({ sessionId: e.sessionId }))
  on('turn.complete', () => ({ text: '' }))
  return { clock, status }
}

const usage = (i: number, o: number, cw: number, cr: number) => ({
  input_tokens: i,
  output_tokens: o,
  cache_creation_input_tokens: cw,
  cache_read_input_tokens: cr,
  model: 'claude-opus-5-5',
})

const turn = (u: ReturnType<typeof usage>) => ({
  answer: 'ok',
  durationMs: 1000,
  isAborted: false,
  turnId: 't',
  reason: 'answer' as const,
  usage: u,
})

describe('formatage', () => {
  test('fmt', () => {
    expect(fmt(950)).toBe('950')
    expect(fmt(12_340)).toBe('12.3k')
    expect(fmt(2_500_000)).toBe('2.5M')
  })
  test('inDelay', () => {
    expect(inDelay(45 * 60_000)).toBe('45 min')
    expect(inDelay(134 * 60_000)).toBe('2 h 14')
  })
  test('session de 5 h reconstituée', () => {
    const t = NOW - 40 * 60_000
    expect(guessWindowStart([[t, 1, 1, 1, 1]], NOW)).toBe(Math.floor(t / HOUR) * HOUR)
    expect(guessWindowStart([[NOW - 7 * HOUR, 1, 1, 1, 1]], NOW)).toBe(NOW)
  })
})

test('compte les tokens du tchat et de la session de 5 h', async ($, on) => {
  const resetsAt = new Date(NOW + 3 * HOUR).toISOString()
  // un autre tchat a déjà consommé 1000 tokens dans la fenêtre
  const { status } = engine(on, {
    percent: 23.5,
    resetsAt,
    store: { log: [[NOW - HOUR, 100, 200, 300, 400]] },
  })

  await $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })
  await $.turn.complete(turn(usage(50, 800, 2000, 30000)))
  await $.turn.complete(turn(usage(50, 800, 2000, 30000)))

  const last = status[status.length - 1] ?? ''
  expect(last).toContain('Tchat 65.7k')
  expect(last).toContain('Session 5h 66.7k')
  expect(last).toContain('24%')
  expect(last).toContain('reset dans 3 h 00')
})

test('/clear remet le tchat à zéro, pas la session de 5 h', async ($, on) => {
  const { status } = engine(on)
  await $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })
  await $.turn.complete(turn(usage(10, 10, 10, 10)))
  await $.session.end({ reason: 'clear', sessionId: 'sess-aaaa1111', resume: { id: 'sess-aaaa1111' } })
  await $.turn.complete(turn(usage(1, 1, 1, 1)))
  const last = status[status.length - 1] ?? ''
  expect(last).toContain('Tchat 4 ')
  expect(last).toContain('Session 5h 44')
})

test('le panneau s’affiche sur chaque surface', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })
  await $.turn.complete(turn(usage(1000, 1000, 1000, 1000)))
  for (const surface of ['terminal', 'desktop', 'vscode', 'mobile'] as const) {
    const ui = await $.ui.mount({
      plugin: 'token-meter',
      surface,
      component: 'Pane',
      requestId: 'token-meter',
      props: {} as never,
    })
    expect(await ui.find({ text: /Ce tchat : 4\.0k/ })).toBeDefined()
    expect(await ui.find({ text: /Session de 5 h/ })).toBeDefined()
  }
})
