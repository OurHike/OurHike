import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set } from 'idb-keyval'
import { enqueue, listQueued, removeQueued, flushOutbox, OUTBOX_KEY } from './outbox'

// TESTING.md item 13, and WIREFRAMES.md's rule that "every write (report,
// thanks, confirmation) queues in an outbox with its authored timestamp and
// syncs later. Nothing blocks on network."
//
// The authored timestamp is the whole point. A report written on Monday and
// flushed on Thursday must still say Monday - see the matching server-side
// change that added `authored_at` to the reports API. If the outbox let the
// send time win, a maintainer would read a three-day-old blowdown as fresh.
//
// Failure handling matters as much: a send that fails must leave the item
// queued, and a flush that runs twice must not create two reports. Both are
// the difference between an outbox and a way to lose someone's report.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn() }))

const mockedGet = vi.mocked(get)
const mockedSet = vi.mocked(set)

/** Backs the mocked idb-keyval with a real in-memory value. */
function withStoredQueue(initial: unknown[] = []) {
  let stored = initial
  mockedGet.mockImplementation(async () => stored)
  mockedSet.mockImplementation(async (_key, value) => {
    stored = value as unknown[]
  })
  return () => stored
}

const DRAFT = {
  type: 'blowdown' as const,
  reporter_type: 'thru' as const,
  note: 'Large tree across the trail near the gap.',
  lat: 35.6,
  lon: -83.5,
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('enqueue', () => {
  it('stores a draft under the outbox key', async () => {
    const read = withStoredQueue()

    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))

    expect(mockedSet).toHaveBeenCalledWith(OUTBOX_KEY, expect.any(Array))
    expect(read()).toHaveLength(1)
  })

  it('records when the report was WRITTEN, not when it will be sent', async () => {
    const read = withStoredQueue()
    const written = new Date('2026-07-27T08:00:00Z')

    await enqueue(DRAFT, written)

    expect((read()[0] as { authoredAt: string }).authoredAt).toBe(written.toISOString())
  })

  it('gives each item a stable id, which is what makes a retry safe', async () => {
    const read = withStoredQueue()

    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))
    await enqueue(DRAFT, new Date('2026-07-27T09:00:00Z'))
    const ids = (read() as Array<{ id: string }>).map((i) => i.id)

    expect(new Set(ids).size).toBe(2)
  })

  it('keeps what is already queued rather than replacing it', async () => {
    const read = withStoredQueue()

    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))
    await enqueue(DRAFT, new Date('2026-07-28T08:00:00Z'))

    expect(read()).toHaveLength(2)
  })
})

describe('listQueued', () => {
  it('returns an empty list on a fresh install rather than throwing', async () => {
    mockedGet.mockResolvedValue(undefined)

    expect(await listQueued()).toEqual([])
  })
})

describe('removeQueued', () => {
  it('deletes an item for good - a later flush must not resurrect it', async () => {
    const read = withStoredQueue()
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))
    const [queued] = read() as Array<{ id: string }>

    await removeQueued(queued.id)
    await flushOutbox(vi.fn().mockResolvedValue(undefined))

    expect(read()).toHaveLength(0)
  })
})

describe('flushOutbox', () => {
  it('sends every queued item, each with its own authored time', async () => {
    withStoredQueue()
    await enqueue(DRAFT, new Date('2026-07-24T08:00:00Z'))
    await enqueue(DRAFT, new Date('2026-07-26T08:00:00Z'))
    await enqueue(DRAFT, new Date('2026-07-28T08:00:00Z'))
    const send = vi.fn().mockResolvedValue(undefined)

    await flushOutbox(send)

    expect(send).toHaveBeenCalledTimes(3)
    expect(send.mock.calls.map(([item]) => item.authoredAt)).toEqual([
      '2026-07-24T08:00:00.000Z',
      '2026-07-26T08:00:00.000Z',
      '2026-07-28T08:00:00.000Z',
    ])
  })

  it('empties the queue once everything has been accepted', async () => {
    const read = withStoredQueue()
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))

    await flushOutbox(vi.fn().mockResolvedValue(undefined))

    expect(read()).toHaveLength(0)
  })

  it('leaves a failed item queued so it can be retried, and says so', async () => {
    const read = withStoredQueue()
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))
    const send = vi.fn().mockRejectedValue(new Error('offline'))

    const result = await flushOutbox(send)

    expect(result).toMatchObject({ sent: 0, failed: 1 })
    expect(read()).toHaveLength(1)
  })

  it('keeps only the failures when some succeed and some do not', async () => {
    const read = withStoredQueue()
    await enqueue({ ...DRAFT, note: 'first' }, new Date('2026-07-24T08:00:00Z'))
    await enqueue({ ...DRAFT, note: 'second' }, new Date('2026-07-26T08:00:00Z'))
    const send = vi
      .fn()
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('offline'))

    await flushOutbox(send)
    const left = read() as Array<{ payload: { note: string } }>

    expect(left).toHaveLength(1)
    expect(left[0].payload.note).toBe('second')
  })

  it('does not send the same report twice when flushed again', async () => {
    withStoredQueue()
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))
    const send = vi.fn().mockResolvedValue(undefined)

    await flushOutbox(send)
    await flushOutbox(send)

    expect(send).toHaveBeenCalledTimes(1)
  })

  it('is a no-op on an empty queue', async () => {
    withStoredQueue()
    const send = vi.fn()

    expect(await flushOutbox(send)).toMatchObject({ sent: 0, failed: 0 })
    expect(send).not.toHaveBeenCalled()
  })
})
