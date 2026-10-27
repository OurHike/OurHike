import { beforeEach, describe, expect, it, vi } from 'vitest'
import { get, set, update } from 'idb-keyval'

import {
  clearUsage,
  EMPTY_USAGE,
  flushUsage,
  forgetLinkedRows,
  MAX_QUEUED,
  readUsage,
  type SendResult,
  type UsageStore,
  withRows,
} from './usageQueue'
import type { QueuedUsageRow, UsageRow } from './usageEvents'

// Where usage rows wait for signal (#1902). The promises pinned here: the
// queue never grows past its cap, a refused batch is not retried for ever,
// rows recorded under a yes do not outlive a no, and switching measurement
// off empties everything that was waiting.

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
  }
}

function queued(id: string, linked = false): QueuedUsageRow {
  return { row: row(id), linked }
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
    await seed([queued('a'), queued('b', true)])
    const send = vi.fn(async (): Promise<SendResult> => 'sent')

    await flushUsage(send)

    expect(send).toHaveBeenCalledWith([row('a')], false)
    expect(send).toHaveBeenCalledWith([row('b')], true)
    expect((await readUsage()).rows).toEqual([])
  })

  it('drops a refused batch rather than retrying it for ever', async () => {
    await seed([queued('a')])

    await flushUsage(async () => 'refused')

    expect((await readUsage()).rows).toEqual([])
  })

  it('keeps everything for later when there is no signal', async () => {
    await seed([queued('a'), queued('b', true)])
    const send = vi.fn(async (): Promise<SendResult> => 'later')

    await flushUsage(send)

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
    await seed([queued('a'), queued('b', true)])

    await clearUsage()

    const after = await readUsage()
    expect(after.rows).toEqual([])
    expect(after.initialized).toBe(true)
  })

  it('drops rows recorded under a yes when the hiker says no, and keeps the rest', async () => {
    await seed([queued('anonymous'), queued('linked', true)])

    await forgetLinkedRows()

    expect((await readUsage()).rows.map((q) => q.row.id)).toEqual(['anonymous'])
  })
})
