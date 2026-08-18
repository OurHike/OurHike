import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set, update } from 'idb-keyval'
import {
  enqueue,
  listQueued,
  removeQueued,
  retryQueued,
  flushOutbox,
  OUTBOX_KEY,
} from './outbox'
import { BUILD_INFO } from './buildInfo'

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

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), update: vi.fn() }))

const mockedGet = vi.mocked(get)
const mockedSet = vi.mocked(set)
const mockedUpdate = vi.mocked(update)

/** Backs the mocked idb-keyval with a real in-memory value. The mocked
 *  update() applies its updater synchronously against the stored value,
 *  mirroring the real one's single-transaction semantics: there is no gap
 *  between the read and the write for another mutator to interleave into. */
function withStoredQueue(initial: unknown[] = []) {
  let stored = initial
  mockedGet.mockImplementation(async () => stored)
  mockedSet.mockImplementation(async (_key, value) => {
    stored = value as unknown[]
  })
  mockedUpdate.mockImplementation(async (_key, updater) => {
    stored = updater(stored) as unknown[]
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

    expect(mockedUpdate).toHaveBeenCalledWith(OUTBOX_KEY, expect.any(Function))
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

// --- Delivery guarantees (#243) -----------------------------------------
//
// The header promises "a flush that half-succeeds neither loses the
// successes nor drops the failures - and flushing twice cannot file the
// same report twice." These are the three ways that was not true.

describe('a report written while a flush is running', () => {
  it('is not overwritten by the flush finishing', async () => {
    // The bug: flushOutbox read the queue, awaited every send, then wrote
    // the whole key back from its own stale snapshot. Anything enqueued in
    // between was appended to the key and then erased by that final write -
    // gone from IndexedDB without ever being sent, which is the one thing an
    // outbox exists to prevent.
    const read = withStoredQueue([
      {
        id: 'first',
        authoredAt: '2026-06-01T00:00:00.000Z',
        payload: { type: 'blowdown' },
      },
    ])

    await flushOutbox(async () => {
      // Mid-flight, exactly like a hiker writing a second report while the
      // first is uploading.
      await enqueue({ type: 'trash', reporter_type: 'day' })
    })

    expect(
      read().map((item) => (item as { payload: { type: string } }).payload.type),
    ).toEqual(['trash'])
  })
})

describe('a permanently refused report', () => {
  const REFUSED = [
    {
      id: 'doomed',
      authoredAt: '2026-06-01T00:00:00.000Z',
      payload: { type: 'blowdown' },
    },
  ]

  it('is kept, marked, and reported as stuck', async () => {
    const read = withStoredQueue([...REFUSED])

    const result = await flushOutbox(
      async () => {
        throw new Error('422')
      },
      () => 'The server would not accept it.',
    )

    expect(result).toEqual({ sent: 0, failed: 1, stuck: 1 })
    const stored = read()[0] as { failure?: { reason: string } }
    // Kept, not deleted: it is still the only copy of what someone wrote.
    expect(stored.failure?.reason).toBe('The server would not accept it.')
  })

  it('is not retried on the next flush', async () => {
    withStoredQueue([...REFUSED])
    const classify = () => 'nope'
    await flushOutbox(async () => {
      throw new Error('422')
    }, classify)

    const send = vi.fn()
    const second = await flushOutbox(send, classify)

    // Retrying would spend signal to be refused again, and would keep
    // resetting a failure the hiker is currently being shown.
    expect(send).not.toHaveBeenCalled()
    expect(second).toEqual({ sent: 0, failed: 1, stuck: 1 })
  })

  it('goes again once its failure is cleared', async () => {
    // The escape hatch for the cause a hiker can fix: a wrong phone clock
    // has every report refused, and once it is right nothing is wrong with
    // them.
    withStoredQueue([...REFUSED])
    await flushOutbox(
      async () => {
        throw new Error('422')
      },
      () => 'nope',
    )

    await retryQueued('doomed')
    const send = vi.fn()
    await flushOutbox(send)

    expect(send).toHaveBeenCalledTimes(1)
  })

  it('records which build gave up on it', async () => {
    // #412: the verdict belongs to a build, not to the report, so the build
    // has to be part of the record for a later one to overturn it.
    const read = withStoredQueue([...REFUSED])

    await flushOutbox(
      async () => {
        throw new Error('422')
      },
      () => 'nope',
    )

    const stored = read()[0] as { failure?: { build?: string } }
    expect(stored.failure?.build).toBe(BUILD_INFO.commit)
  })

  it('is retried once by a different build', async () => {
    // The whole point. A 422 on a field the previous build did not send is
    // fixed by the build that sends it - and a hiker who never opens More
    // and presses "Try again" would otherwise lose the report to a verdict
    // that has stopped being true.
    const read = withStoredQueue([...REFUSED])
    await flushOutbox(
      async () => {
        throw new Error('422')
      },
      () => 'nope',
    )

    // The same stored queue, now read by a build with a different commit.
    const stored = read()[0] as { failure: { build?: string } }
    stored.failure.build = 'a0000000000000000000000000000000000000ff'

    const send = vi.fn()
    const result = await flushOutbox(send)

    expect(send).toHaveBeenCalledTimes(1)
    expect(result.sent).toBe(1)
  })

  it('is not retried again by the build that re-marked it', async () => {
    // Bounded to one retry per update: the rule is "a different build may
    // disagree", not "keep resetting a failure the hiker is being shown".
    const read = withStoredQueue([...REFUSED])
    const refuse = async () => {
      throw new Error('422')
    }
    await flushOutbox(refuse, () => 'nope')

    const stored = read()[0] as { failure: { build?: string } }
    stored.failure.build = 'a0000000000000000000000000000000000000ff'

    // The new build tries, is refused, and re-marks it under its own commit.
    await flushOutbox(refuse, () => 'nope')
    const send = vi.fn()
    const third = await flushOutbox(send, () => 'nope')

    expect(send).not.toHaveBeenCalled()
    expect(third).toEqual({ sent: 0, failed: 1, stuck: 1 })
  })

  it('retries a failure stored before builds were recorded', async () => {
    // The shape on a phone that upgraded into this change: `failure` with no
    // `build`. Absent is not this build, so it gets the same single retry an
    // older build's verdict would - see storedShapes.fixtures.ts, which
    // carries exactly this item.
    withStoredQueue([
      {
        ...REFUSED[0],
        failure: { reason: 'Refused by an older build.', at: '2026-07-30T08:00:00.000Z' },
      },
    ])

    const send = vi.fn()
    await flushOutbox(send)

    expect(send).toHaveBeenCalledTimes(1)
  })
})

describe('a transient failure', () => {
  it('is left alone, with no failure recorded', async () => {
    const read = withStoredQueue([
      {
        id: 'waiting',
        authoredAt: '2026-06-01T00:00:00.000Z',
        payload: { type: 'blowdown' },
      },
    ])

    const result = await flushOutbox(
      async () => {
        throw new Error('offline')
      },
      // The classifier's "retry this" answer.
      () => null,
    )

    expect(result).toEqual({ sent: 0, failed: 1, stuck: 0 })
    expect((read()[0] as { failure?: unknown }).failure).toBeUndefined()
  })

  it('is the default when no classifier is given', async () => {
    // A caller with no opinion must not accidentally strand a report.
    const read = withStoredQueue([
      {
        id: 'waiting',
        authoredAt: '2026-06-01T00:00:00.000Z',
        payload: { type: 'blowdown' },
      },
    ])

    const result = await flushOutbox(async () => {
      throw new Error('anything at all')
    })

    expect(result.stuck).toBe(0)
    expect((read()[0] as { failure?: unknown }).failure).toBeUndefined()
  })
})

// --- Carrying the photo, not a link to one (#234) -------------------------

describe('a report queued with a photo', () => {
  const BYTES = new Blob([new Uint8Array([1, 2, 3])], { type: 'image/jpeg' })

  // Its own empty store per test. The global `beforeEach` clears calls but
  // not implementations, so without this the queue is whatever the previous
  // describe left behind.
  beforeEach(() => {
    withStoredQueue()
  })

  it('stores the bytes beside the report', async () => {
    // Not `payload.photo_url`, which is the shape for a photo already
    // uploaded. Out here the report is usually written with no signal at all
    // and flushes days later, so the image has to survive in IndexedDB.
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'), BYTES)

    const [item] = await listQueued()
    expect(item.photo).toBe(BYTES)
  })

  it('leaves the key off entirely when there is no photo', async () => {
    // An explicit `photo: undefined` is a difference that reads as one to
    // every comparison and rewrite the queue goes through.
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))

    const [item] = await listQueued()
    expect('photo' in item).toBe(false)
  })

  it('hands the photo to the sender along with the report', async () => {
    // The send is what turns bytes into an upload; the outbox's only job is
    // that they are still there when it runs.
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'), BYTES)
    const send = vi.fn().mockResolvedValue(undefined)

    await flushOutbox(send)

    expect(send.mock.calls[0][0].photo).toBe(BYTES)
  })

  it('keeps the photo when the send fails and the item stays queued', async () => {
    // The retry has to carry the same bytes; losing them on the first failed
    // flush would mean the photo only ever survived a first-try success,
    // which on this trail is the uncommon case.
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'), BYTES)

    await flushOutbox(vi.fn().mockRejectedValue(new Error('no signal')))

    const [item] = await listQueued()
    expect(item.photo).toBe(BYTES)
  })
})

describe('atomicity of the mutators (#288)', () => {
  it('every mutator goes through update(), never a separate get-then-set', async () => {
    // The whole fix: get+put inside ONE readwrite transaction. A mutator
    // that re-grew its own `get` → transform → `set` would reopen the
    // sub-millisecond window where two overlapping mutators lose a write -
    // and a queued report is often the only copy of something written with
    // no signal. flushOutbox is exercised with a failing-then-classified
    // send so markFailed's path runs too.
    const read = withStoredQueue()
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))
    await enqueue(DRAFT, new Date('2026-07-27T09:00:00Z'))
    const [first, second] = read() as Array<{ id: string }>

    mockedGet.mockClear()
    mockedSet.mockClear()

    await removeQueued(first.id)
    await retryQueued(second.id)
    await flushOutbox(
      vi.fn().mockRejectedValue(new Error('rejected')),
      () => 'The server will never accept this.',
    )

    expect(mockedSet).not.toHaveBeenCalled()
    // flushOutbox legitimately reads the queue once to iterate it; what must
    // never happen is a WRITE built from that separate read.
    expect(mockedUpdate).toHaveBeenCalled()
  })

  it("an item enqueued between a flush's read and its removals survives", async () => {
    const read = withStoredQueue()
    await enqueue(DRAFT, new Date('2026-07-27T08:00:00Z'))

    // The send resolves only after a new report lands in the queue -
    // exactly the overlap that used to lose whichever write went first.
    const send = vi.fn().mockImplementation(async () => {
      await enqueue(DRAFT, new Date('2026-07-27T09:00:00Z'))
    })
    await flushOutbox(send)

    const remaining = read() as Array<{ authoredAt: string }>
    expect(remaining.map((item) => item.authoredAt)).toEqual(['2026-07-27T09:00:00.000Z'])
  })
})
