import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  MAX_CACHED_BYTES,
  conditionsCacheKey,
  recallPublished,
  rememberPublished,
} from './conditionsCache'
import { PUBLISHED_CLOSURES_KEY } from './publishedConditions'

// config.ts reads VITE_DATA_BASE_URL once at module load and it is unset
// under test, so the reading half is imported fresh against a stubbed env -
// publishedConditions.test.ts's own convention, and the only way to exercise
// a configured bucket at all.
async function configured() {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', 'https://data.example.org')
  return import('./publishedConditions')
}

// #447: the baseline helped a phone whose backend was down and not a phone
// with no signal, which is the one a hiker is actually holding. What these
// cases hold:
//
//  1. **Offline reads the kept copy and fires no request.** Both halves
//     matter - `App.trailData.test.tsx` asserts this app does not fire a
//     fetch it knows cannot work, and #447 exists because that left the
//     honest answer as "unavailable".
//  2. **A kept copy is validated on the way out**, not trusted because it
//     was ours. An older build may have written a shape this one refuses.
//  3. **Failing to keep a copy never fails the read.** The bytes already
//     arrived; a full disk must not turn that into nothing.

vi.mock('idb-keyval', () => {
  const store = new Map<string, unknown>()
  return {
    get: vi.fn(async (key: string) => store.get(key)),
    __clear: () => store.clear(),
    set: vi.fn(async (key: string, value: unknown) => void store.set(key, value)),
    del: vi.fn(async (key: string) => void store.delete(key)),
    __store: store,
  }
})

const CLOSURES = {
  generated_at: '2026-07-20T06:00:00Z',
  closures: [
    {
      id: 'closure-1',
      reason_type: 'storm_damage',
      note: 'Bridge out',
      status: 'closed',
      start_mile_marker: 1408.6,
      end_mile_marker: 1411.0,
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(async () => {
  // The store is the mock's own Map, cleared directly: nothing in the app
  // wipes these keys (deleting one map must not cost a hiker the closure
  // list), so there is no production function for a test to borrow.
  const store = (await import('idb-keyval')) as unknown as { __clear(): void }
  store.__clear()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('the kept baseline', () => {
  it('keeps one key per artifact rather than one record for all six', async () => {
    await rememberPublished(PUBLISHED_CLOSURES_KEY, CLOSURES)

    // Six artifacts arrive concurrently. One shared record would make every
    // arrival a read-modify-write over one key - #288's hazard in the
    // outbox, where two writes interleave and the loser vanishes.
    expect(vi.mocked(set)).toHaveBeenCalledWith(
      conditionsCacheKey(PUBLISHED_CLOSURES_KEY),
      expect.objectContaining({ document: CLOSURES }),
    )
  })

  it('refuses to keep an artifact past the size ceiling, and drops the old one', async () => {
    await rememberPublished(PUBLISHED_CLOSURES_KEY, CLOSURES)
    const huge = {
      generated_at: '2026-07-21T06:00:00Z',
      closures: [{ note: 'x'.repeat(MAX_CACHED_BYTES) }],
    }

    await rememberPublished(PUBLISHED_CLOSURES_KEY, huge)

    // Dropped rather than truncated: half a JSON document is not a smaller
    // baseline, it is an unparseable one. And the previous copy goes with
    // it rather than sitting there ageing while this build refuses to
    // refresh it.
    expect(await recallPublished(PUBLISHED_CLOSURES_KEY)).toBeNull()
  })

  it('does not fail the read when the store will not take it', async () => {
    vi.mocked(set).mockRejectedValueOnce(new Error('QuotaExceededError'))

    // The bytes already arrived. A phone in private mode, or one out of
    // disk, must not turn a successful read into a failed one.
    await expect(
      rememberPublished(PUBLISHED_CLOSURES_KEY, CLOSURES),
    ).resolves.toBeUndefined()
  })

  it('refuses a stored shape this build cannot read', async () => {
    await set(conditionsCacheKey(PUBLISHED_CLOSURES_KEY), {
      document: 'not an object',
      storedAt: '2026-07-20T06:00:00Z',
    })

    expect(await recallPublished(PUBLISHED_CLOSURES_KEY)).toBeNull()
  })

  it('survives a store that throws on read', async () => {
    vi.mocked(get).mockRejectedValueOnce(new Error('no IndexedDB here'))

    expect(await recallPublished(PUBLISHED_CLOSURES_KEY)).toBeNull()
  })
})

describe('reading a published baseline offline', () => {
  it('serves the kept copy and asks the radio for nothing', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    await rememberPublished(PUBLISHED_CLOSURES_KEY, CLOSURES)

    const { fetchPublishedClosures } = await configured()
    const published = await fetchPublishedClosures(undefined, { online: false })

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(published?.items).toHaveLength(1)
    // The age travels with the data, so a month-old list reads as a month
    // old rather than as whatever time the phone read it back.
    expect(published?.generatedAt.toISOString()).toBe('2026-07-20T06:00:00.000Z')
  })

  it('says nothing rather than something when no copy was ever kept', async () => {
    const { fetchPublishedClosures } = await configured()
    const published = await fetchPublishedClosures(undefined, { online: false })

    // The state this leaves is `unavailable`, which the strip says out loud.
    // An empty list would render as a trail with no closures on it.
    expect(published).toBeNull()
  })

  it('falls back to the kept copy when the bucket refuses a live read', async () => {
    await rememberPublished(PUBLISHED_CLOSURES_KEY, CLOSURES)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)

    const { fetchPublishedClosures } = await configured()
    const published = await fetchPublishedClosures()

    // A phone with signal and a bucket that 404s is the other half of the
    // same failure, and it was equally unhandled before.
    expect(published?.items).toHaveLength(1)
  })

  it('keeps what a live read brought back', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => CLOSURES,
    } as Response)

    const { fetchPublishedClosures } = await configured()
    await fetchPublishedClosures()

    await vi.waitFor(async () =>
      expect(await recallPublished(PUBLISHED_CLOSURES_KEY)).not.toBeNull(),
    )
  })

  it('does not overwrite a good copy with bytes it cannot parse', async () => {
    await rememberPublished(PUBLISHED_CLOSURES_KEY, CLOSURES)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      // No `generated_at`: refused on the way in, for the reason the whole
      // path exists - conditions with no age render as fresh.
      json: async () => ({ closures: [] }),
    } as Response)

    const { fetchPublishedClosures } = await configured()
    const published = await fetchPublishedClosures()

    expect(published?.generatedAt.toISOString()).toBe('2026-07-20T06:00:00.000Z')
    expect(await recallPublished(PUBLISHED_CLOSURES_KEY)).not.toBeNull()
  })
})
