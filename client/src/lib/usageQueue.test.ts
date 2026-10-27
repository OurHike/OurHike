import { beforeEach, describe, expect, it, vi } from 'vitest'
import { get, set, update } from 'idb-keyval'

import {
  clearUsage,
  EMPTY_USAGE,
  flushUsage,
  MAX_QUEUED,
  readUsage,
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
})

describe('flushUsage', () => {
  it('sends anonymous and linked rows in separate batches, the token only with the linked one', async () => {
    await seed([queued('a'), queued('b', ALICE)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send, ALICE)

    expect(send).toHaveBeenCalledWith([row('a')], false)
    expect(send).toHaveBeenCalledWith([row('b')], true)
    expect((await readUsage()).rows).toEqual([])
  })

  it('never sends one account’s rows with another account’s token', async () => {
    // Alice linked and recorded, her session expired with the app closed,
    // and Bob signed in on the same phone before the queue had gone.
    await seed([queued('alice-1', ALICE), queued('bob-1', BOB)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send, BOB)

    expect(send).toHaveBeenCalledWith([row('alice-1')], false)
    expect(send).toHaveBeenCalledWith([row('bob-1')], true)
  })

  it('sends rows recorded before a sign-out without any account, rather than losing them', async () => {
    await seed([queued('a', ALICE)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send, null)

    expect(send).toHaveBeenCalledTimes(1)
    expect(send).toHaveBeenCalledWith([row('a')], false)
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
})

describe('the two switches', () => {
  it('empties the queue when measurement is switched off', async () => {
    await seed([queued('a'), queued('b', ALICE)])

    await clearUsage()

    const after = await readUsage()
    expect(after.rows).toEqual([])
    expect(after.initialized).toBe(true)
  })

  it('unlinks rows recorded under a yes when the hiker says no, and still counts them', async () => {
    await seed([queued('anonymous'), queued('linked', ALICE)])

    await unlinkWaitingRows()

    expect((await readUsage()).rows).toEqual([queued('anonymous'), queued('linked')])
  })

  it('reads a row queued before rows were bound to an account as unlinked', async () => {
    stored = { ...EMPTY_USAGE, rows: [{ row: row('old'), linked: true }] }

    expect((await readUsage()).rows).toEqual([queued('old')])
  })
})
