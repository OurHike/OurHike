import { beforeEach, describe, expect, it, vi } from 'vitest'
import { get, set, update } from 'idb-keyval'

import { accessToken, apiFetch } from './api'
import { accountTag } from './accountTag'
import {
  clearUsage,
  DEFAULT_WAIT_MS,
  EMPTY_USAGE,
  flushUsage,
  MAX_QUEUED,
  MAX_WAIT_MS,
  SEND_TIMEOUT_MS,
  readUsage,
  resumeUsage,
  sendUsageBatch,
  type SendResult,
  unlinkWaitingRows,
  type UsageStore,
  withRows,
} from './usageQueue'
import type { QueuedUsageRow, UsageRow } from './usageEvents'

// Where usage rows wait for signal (#1902). The promises pinned here: the
// queue never grows past its cap, a refused batch is not retried for ever,
// rows recorded under a yes are never linked after a no, a row is never sent
// with another account's token, and switching measurement off empties
// everything that was waiting.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), update: vi.fn() }))
vi.mock('./api', () => ({
  accessToken: vi.fn(async () => 'token'),
  apiFetch: vi.fn(),
  API_CONFIGURED: true,
  ApiError: class ApiError extends Error {},
}))

let stored: unknown = undefined
beforeEach(() => {
  stored = undefined
  vi.mocked(get).mockImplementation(async () => stored)
  vi.mocked(set).mockImplementation(async (_key, value) => {
    stored = value
  })
  vi.mocked(update).mockImplementation(async (_key, updater) => {
    stored = updater(stored)
  })
})

function row(id: string): UsageRow {
  return {
    id,
    event: 'session',
    local_date: '2026-10-27',
    platform: 'web',
    week_first: false,
    month_first: false,
    ever_first: false,
    club_firsts: [],
    kind_month_first: false,
    month_returning: false,
    signed_in: false,
  }
}

const ALICE = 'tag-alice'
const BOB = 'tag-bob'
const NONE = { full: 0, refused: 0 }

function queued(id: string, linkedTo: string | null = null): QueuedUsageRow {
  return { row: row(id), linkedTo }
}

async function seed(rows: QueuedUsageRow[]) {
  stored = { ...EMPTY_USAGE, rows, initialized: true } satisfies UsageStore
}

describe('withRows', () => {
  it('drops the oldest rows once the queue passes its cap', () => {
    const full = withRows(
      EMPTY_USAGE,
      Array.from({ length: MAX_QUEUED }, (_, i) => queued(`old-${i}`)),
    )
    const after = withRows(full, [queued('newest')])

    expect(after.rows).toHaveLength(MAX_QUEUED)
    expect(after.rows[0].row.id).toBe('old-1')
    expect(after.rows.at(-1)?.row.id).toBe('newest')
  })

  it("keeps a phone's first row of the month when the cap drops a row, so a long stretch offline does not lose the phone from the month", () => {
    const first: QueuedUsageRow = {
      row: { ...row('month-first'), week_first: true, month_first: true },
      linkedTo: null,
    }
    const full = withRows(EMPTY_USAGE, [
      first,
      ...Array.from({ length: MAX_QUEUED - 1 }, (_, i) => queued(`plain-${i}`)),
    ])

    const after = withRows(full, [queued('newest')])

    expect(after.rows).toHaveLength(MAX_QUEUED)
    expect(after.rows[0].row.id).toBe('month-first')
    expect(after.dropped.full).toBe(1)
    expect(after.rows.map((queued) => queued.row.id)).not.toContain('plain-0')
  })

  it('keeps a $0 support answer when the cap drops a row, because no later row counts it again', () => {
    const answer: QueuedUsageRow = {
      row: { ...row('support'), event: 'support_chosen', support_cents: 0 },
      linkedTo: null,
    }
    const full = withRows(EMPTY_USAGE, [
      answer,
      ...Array.from({ length: MAX_QUEUED - 1 }, (_, i) => queued(`plain-${i}`)),
    ])

    const after = withRows(full, [queued('newest')])

    expect(after.rows[0].row.id).toBe('support')
    expect(after.rows.map((queued) => queued.row.id)).not.toContain('plain-0')
  })

  it('takes no rows while "Share usage statistics" is off in the shared store', () => {
    const off = { ...EMPTY_USAGE, off: true }

    expect(withRows(off, [queued('a')]).rows).toEqual([])
  })
})

describe('flushUsage', () => {
  it('sends anonymous and linked rows in separate batches, the token only with the linked one', async () => {
    await seed([queued('a'), queued('b', ALICE)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send, ALICE)

    expect(send).toHaveBeenCalledWith([row('a')], null, NONE)
    expect(send).toHaveBeenCalledWith([row('b')], ALICE, NONE)
    expect((await readUsage()).rows).toEqual([])
  })

  it('never sends one account’s rows with another account’s token', async () => {
    // Alice linked and recorded, her session expired with the app closed,
    // and Bob signed in on the same phone before the queue had gone.
    await seed([queued('alice-1', ALICE), queued('bob-1', BOB)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send, BOB)

    expect(send).toHaveBeenCalledWith([row('alice-1')], null, NONE)
    expect(send).toHaveBeenCalledWith([row('bob-1')], BOB, NONE)
  })

  it('sends rows recorded before a sign-out without any account, rather than losing them', async () => {
    await seed([queued('a', ALICE)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send, null)

    expect(send).toHaveBeenCalledTimes(1)
    expect(send).toHaveBeenCalledWith([row('a')], null, NONE)
  })

  it('drops a refused batch rather than retrying it for ever', async () => {
    await seed([queued('a')])

    await flushUsage(async () => 'refused')

    expect((await readUsage()).rows).toEqual([])
  })

  it('keeps everything for later when there is no signal', async () => {
    await seed([queued('a'), queued('b', ALICE)])
    const send = vi.fn(async (): Promise<SendResult> => 'later')

    await flushUsage(send, ALICE)

    expect(send).toHaveBeenCalledTimes(1)
    expect((await readUsage()).rows).toHaveLength(2)
  })

  it('shares one flush between two calls that overlap', async () => {
    await seed([queued('a')])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await Promise.all([flushUsage(send), flushUsage(send)])

    expect(send).toHaveBeenCalledTimes(1)
  })

  it('stops between batches when sharing is switched off during the first, so the linked batch never leaves', async () => {
    await seed([queued('a'), queued('b', ALICE)])
    let release: () => void = () => {}
    const send = vi.fn(
      (): Promise<SendResult> =>
        new Promise((resolve) => {
          release = () => resolve('sent')
        }),
    )

    const flushing = flushUsage(send, ALICE)
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(1))
    await clearUsage()
    release()
    await flushing

    expect(send).toHaveBeenCalledTimes(1)
    expect(send).toHaveBeenCalledWith([row('a')], null, NONE)
  })

  it('sends a row unlinked when the hiker said no while the first batch was on its way', async () => {
    await seed([queued('a'), queued('b', ALICE)])
    let release: () => void = () => {}
    const send = vi.fn(
      (): Promise<SendResult> =>
        new Promise((resolve) => {
          release = () => resolve('sent')
        }),
    )

    const flushing = flushUsage(send, ALICE)
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(1))
    await unlinkWaitingRows()
    release()
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(2))
    release()
    await flushing

    expect(send).toHaveBeenLastCalledWith([row('b')], null, NONE)
  })

  it('sends nothing more until the wait the server asked for has passed', async () => {
    await seed([queued('a')])
    const send = vi.fn(async (): Promise<SendResult> => ({ waitMs: 60_000 }))

    await flushUsage(send)
    await flushUsage(send)

    expect(send).toHaveBeenCalledTimes(1)
    expect((await readUsage()).rows).toHaveLength(1)

    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 60_001)
    try {
      await flushUsage(vi.fn(async (): Promise<SendResult> => 'sent'))
    } finally {
      vi.mocked(Date.now).mockRestore()
    }
    expect((await readUsage()).rows).toEqual([])
  })

  it('ignores a wait further ahead than any it would honour, set by a clock since moved back', async () => {
    await seed([queued('a')])
    stored = { ...(stored as UsageStore), notBefore: Date.now() + MAX_WAIT_MS * 10 }
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send)

    expect(send).toHaveBeenCalledTimes(1)
  })

  it('holds linked rows while a consent answer given here has not reached the account, and sends the rest', async () => {
    await seed([queued('a'), queued('b', ALICE)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send, ALICE, async () => true)

    expect(send).toHaveBeenCalledTimes(1)
    expect(send).toHaveBeenCalledWith([row('a')], null, NONE)
    expect((await readUsage()).rows).toEqual([queued('b', ALICE)])
  })

  it('sends what the phone dropped with the next batch, and takes it off once the batch is answered', async () => {
    await seed([queued('a')])
    stored = { ...(stored as UsageStore), dropped: { full: 4, refused: 2 } }
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send)

    expect(send).toHaveBeenCalledWith([row('a')], null, { full: 4, refused: 2 })
    expect((await readUsage()).dropped).toEqual(NONE)
  })

  it('keeps what the phone dropped when the batch carrying it was not delivered', async () => {
    await seed([queued('a')])
    stored = { ...(stored as UsageStore), dropped: { full: 4, refused: 0 } }

    await flushUsage(async () => 'later')

    expect((await readUsage()).dropped).toEqual({ full: 4, refused: 0 })
  })

  it('counts the rows of a refused batch as dropped, for the server to hear of with the next one', async () => {
    await seed([queued('a'), queued('b')])

    await flushUsage(async () => 'refused')

    expect((await readUsage()).dropped).toEqual({ full: 0, refused: 2 })
  })

  it('offers each row once per flush even when the store will not let a sent batch be removed', async () => {
    await seed([queued('a')])
    vi.mocked(update).mockImplementation(async () => {
      throw new Error('quota')
    })
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send)

    expect(send).toHaveBeenCalledTimes(1)
  })
})

describe('sendUsageBatch', () => {
  function tokenFor(email: string): string {
    const payload = btoa(JSON.stringify({ email })).replace(/=+$/, '')
    return `header.${payload}.signature`
  }

  it("holds a linked batch whose session belongs to another account, rather than sending it with that account's token", async () => {
    vi.mocked(accessToken).mockResolvedValueOnce(tokenFor('bob@example.org'))
    vi.mocked(apiFetch).mockClear()

    const result = await sendUsageBatch([row('a')], accountTag('alice@example.org'))

    expect(result).toBe('later')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('holds a linked batch when the token could not be refreshed, rather than storing it unlinked for good', async () => {
    // An hour offline expires the access token; one bar too weak to refresh
    // it still carries the POST. Sent without the token, the rows were stored
    // unlinked, and the resend with a fresh one was only ever a duplicate
    // (#1903's second review).
    vi.mocked(accessToken).mockResolvedValueOnce(null)
    vi.mocked(apiFetch).mockClear()

    const result = await sendUsageBatch([row('a')], accountTag('alice@example.org'))

    expect(result).toBe('later')
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('sends an anonymous batch without asking for a token at all', async () => {
    vi.mocked(accessToken).mockClear()
    vi.mocked(apiFetch).mockResolvedValueOnce(new Response(null, { status: 202 }))

    expect(await sendUsageBatch([row('a')], null)).toBe('sent')

    expect(accessToken).not.toHaveBeenCalled()
    const init = vi.mocked(apiFetch).mock.calls.at(-1)?.[1] as RequestInit
    expect(init.headers).not.toHaveProperty('Authorization')
    expect(JSON.parse(init.body as string)).toEqual({
      identified: false,
      events: [row('a')],
    })
  })

  it('carries what the phone dropped, and nothing when it dropped nothing', async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce(new Response(null, { status: 202 }))

    await sendUsageBatch([row('a')], null, { full: 3, refused: 0 })

    const init = vi.mocked(apiFetch).mock.calls.at(-1)?.[1] as RequestInit
    expect(JSON.parse(init.body as string)).toMatchObject({
      dropped: { full: 3, refused: 0 },
    })
  })

  function refusedWith(status: number, retryAfter: string | null = null) {
    return Object.assign(new Error(`failed: ${status}`), { status, retryAfter })
  }

  it.each([
    ['the server’s own 503, which says an hour', 503, '3600', 3_600_000],
    ['a 503 that says nothing', 503, null, DEFAULT_WAIT_MS],
    ['a 429', 429, '120', 120_000],
    ['a wait longer than any honoured', 503, '999999', MAX_WAIT_MS],
  ])('waits as asked after %s', async (_name, status, retryAfter, waitMs) => {
    vi.mocked(apiFetch).mockRejectedValueOnce(refusedWith(status, retryAfter))

    expect(await sendUsageBatch([row('a')], null)).toEqual({ waitMs })
  })

  it.each([404, 405, 422])(
    'waits rather than drops after a %i, the answer of a server older than this build',
    async (status) => {
      vi.mocked(apiFetch).mockRejectedValueOnce(refusedWith(status))

      expect(await sendUsageBatch([row('a')], null)).toEqual({ waitMs: DEFAULT_WAIT_MS })
    },
  )

  it.each([400, 413])('drops a batch the server will never take (%i)', async (status) => {
    vi.mocked(apiFetch).mockRejectedValueOnce(refusedWith(status))

    expect(await sendUsageBatch([row('a')], null)).toBe('refused')
  })

  it('gives up on a request that never answers, for the next chance', async () => {
    vi.useFakeTimers()
    try {
      vi.mocked(apiFetch).mockImplementationOnce(
        (_path, init) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () =>
              reject(new DOMException('The operation was aborted.', 'AbortError')),
            )
          }),
      )

      const sending = sendUsageBatch([row('a')], null)
      await vi.advanceTimersByTimeAsync(SEND_TIMEOUT_MS)

      expect(await sending).toBe('later')
    } finally {
      vi.useRealTimers()
    }
  })

  it('attaches it when the session is the same account', async () => {
    vi.mocked(accessToken).mockResolvedValueOnce(tokenFor('Alice@Example.org'))
    vi.mocked(apiFetch).mockResolvedValueOnce(new Response(null, { status: 202 }))

    await sendUsageBatch([row('a')], accountTag('alice@example.org'))

    const init = vi.mocked(apiFetch).mock.calls.at(-1)?.[1] as RequestInit
    expect(init.headers).toHaveProperty('Authorization')
    expect(JSON.parse(init.body as string)).toMatchObject({ identified: true })
  })
})

describe('the two switches', () => {
  it('empties the queue when measurement is switched off', async () => {
    await seed([queued('a'), queued('b', ALICE)])

    await clearUsage()

    const after = await readUsage()
    expect(after.rows).toEqual([])
    expect(after.initialized).toBe(true)
    expect(after.off).toBe(true)
  })

  it('keeps which weeks and months were counted when switched off, so off and on again is not a new phone, and forgets the clubs', async () => {
    stored = {
      ...EMPTY_USAGE,
      initialized: true,
      heartbeat: {
        weeks: ['2026-W44'],
        months: ['2026-10'],
        ever: true,
        clubs: { '2026-10': ['NYNJTC'] },
        kinds: { '2026-10': ['session'] },
      },
    }

    await clearUsage()
    await resumeUsage()

    const after = await readUsage()
    expect(after.off).toBe(false)
    expect(after.heartbeat.ever).toBe(true)
    expect(after.heartbeat.weeks).toEqual(['2026-W44'])
    expect(after.heartbeat.months).toEqual(['2026-10'])
    expect(after.heartbeat.kinds).toEqual({ '2026-10': ['session'] })
    expect(after.heartbeat.clubs).toEqual({})
  })

  it('unlinks rows recorded under a yes when the hiker says no, and still counts them', async () => {
    await seed([queued('anonymous'), queued('linked', ALICE)])

    await unlinkWaitingRows()

    expect((await readUsage()).rows).toEqual([queued('anonymous'), queued('linked')])
  })

  it('unlinks the visit still in progress too, so it cannot end linked to the account that said no', async () => {
    stored = {
      ...EMPTY_USAGE,
      initialized: true,
      session: {
        startedAt: 1,
        lastSeenAt: 2,
        pageviews: 3,
        linkedTo: ALICE,
        signedIn: true,
      },
    } satisfies UsageStore

    await unlinkWaitingRows()

    expect((await readUsage()).session).toEqual({
      startedAt: 1,
      lastSeenAt: 2,
      pageviews: 3,
      linkedTo: null,
      signedIn: true,
    })
  })

  it('reads a row queued before rows were bound to an account as unlinked', async () => {
    stored = { ...EMPTY_USAGE, rows: [{ row: row('old'), linked: true }] }

    expect((await readUsage()).rows).toEqual([queued('old')])
  })
})
