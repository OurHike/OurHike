import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  RELEASED_KEY,
  clearCompleted,
  clearReleased,
  completedMarker,
  completedMarkerKeyFor,
  estimateAvailableBytes,
  estimateUsageBytes,
  readPersistence,
  recordCompleted,
  recordReleased,
  requestPersistence,
} from './storageHealth'

// Everything here is best-effort by design, so half these tests are about the
// absent case: no Storage API, a throwing localStorage, a browser that will
// not answer. The honest degradation - "we cannot say" rather than a made-up
// answer - is the behavior worth pinning, because a wrong durability claim is
// exactly what #190 exists to stop.

const KEY = 'ourhike:test-archive'

function stubStorage(storage: unknown): void {
  vi.stubGlobal('navigator', { ...globalThis.navigator, storage })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('requestPersistence', () => {
  it('reports granted when the browser agrees to protect the origin', async () => {
    stubStorage({ persist: () => Promise.resolve(true) })
    expect(await requestPersistence()).toBe('granted')
  })

  it('reports denied when the browser heard the request and said no', async () => {
    stubStorage({ persist: () => Promise.resolve(false) })
    expect(await requestPersistence()).toBe('denied')
  })

  it('reports unsupported where the API does not exist, without throwing', async () => {
    stubStorage(undefined)
    expect(await requestPersistence()).toBe('unsupported')
  })

  it('treats a rejecting persist() as unsupported rather than crashing', async () => {
    stubStorage({ persist: () => Promise.reject(new Error('nope')) })
    expect(await requestPersistence()).toBe('unsupported')
  })
})

describe('readPersistence', () => {
  it('reflects a standing grant without prompting', async () => {
    stubStorage({ persisted: () => Promise.resolve(true) })
    expect(await readPersistence()).toBe('granted')
  })

  it('reports denied while nothing has been granted', async () => {
    stubStorage({ persisted: () => Promise.resolve(false) })
    expect(await readPersistence()).toBe('denied')
  })
})

describe('estimateAvailableBytes', () => {
  it('answers quota minus usage', async () => {
    stubStorage({
      estimate: () => Promise.resolve({ quota: 1_000_000, usage: 250_000 }),
    })
    expect(await estimateAvailableBytes()).toBe(750_000)
  })

  it('never goes negative when usage overshoots the quota', async () => {
    stubStorage({ estimate: () => Promise.resolve({ quota: 100, usage: 250 }) })
    expect(await estimateAvailableBytes()).toBe(0)
  })

  it('answers null where the browser will not say', async () => {
    stubStorage(undefined)
    expect(await estimateAvailableBytes()).toBeNull()

    stubStorage({ estimate: () => Promise.resolve({}) })
    expect(await estimateAvailableBytes()).toBeNull()
  })
})

describe('the completion marker', () => {
  it('remembers when an archive finished, per package key', () => {
    const finished = new Date('2026-08-05T12:00:00Z')
    recordCompleted(KEY, finished)

    expect(completedMarker(KEY)?.toISOString()).toBe(finished.toISOString())
    expect(completedMarker('ourhike:other')).toBeNull()
  })

  it('is cleared with the archive it describes', () => {
    recordCompleted(KEY)
    clearCompleted(KEY)

    expect(completedMarker(KEY)).toBeNull()
  })

  it('lives in localStorage, deliberately outside IndexedDB', () => {
    // The known real-world losses hit IndexedDB specifically; a marker in the
    // same store would vanish with the thing it exists to report on.
    recordCompleted(KEY)

    expect(localStorage.getItem(completedMarkerKeyFor(KEY))).not.toBeNull()
  })

  it('treats an unreadable or garbled marker as no marker', () => {
    localStorage.setItem(completedMarkerKeyFor(KEY), 'not a date')

    // No eviction claim gets made that cannot be backed.
    expect(completedMarker(KEY)).toBeNull()
  })
})

// Crediting space this app deleted that the browser still counts as used
// (#554). Measured in Chromium with `scripts/storage-probe/run.mjs --reclaim`:
// 200 MiB stored as seven segment records, deleted through `deleteArchive` in
// 10 ms and immediately unreadable, and `usage` unmoved at 209,718,780 ten
// seconds later AND after a page reload. So the bytes are free and the
// accounting is not - and "delete this sheet and download again" is the app's
// own printed remedy, which it would otherwise refuse to honour.
describe('crediting a delete the browser has not accounted for', () => {
  it('adds back what was released while usage still counts it', () => {
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 800_000 }) })
    // 300k deleted; usage did not budge, exactly as measured.
    recordReleased(300_000, 800_000)

    // 200k by the browser's arithmetic, 500k in truth.
    return expect(estimateAvailableBytes()).resolves.toBe(500_000)
  })

  it('credits nothing once the browser has caught up', async () => {
    // A browser that reclaims promptly needs no help and must not be
    // double-counted: usage fell by the whole release, so the plain estimate is
    // already right.
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 500_000 }) })
    recordReleased(300_000, 800_000)

    expect(await estimateAvailableBytes()).toBe(500_000)
  })

  it('credits only the part not yet given back', async () => {
    // Half returned, half still miscounted. The credit decays with usage rather
    // than being all-or-nothing, which is what keeps it from ever exceeding the
    // truth.
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 650_000 }) })
    recordReleased(300_000, 800_000)

    expect(await estimateAvailableBytes()).toBe(500_000)
  })

  it('cannot be inflated by usage rising for an unrelated reason', async () => {
    // Another tab filled the origin after the delete. The credit is capped at
    // what was released, so this reports less free space, never more.
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 900_000 }) })
    recordReleased(300_000, 800_000)

    expect(await estimateAvailableBytes()).toBe(400_000)
  })

  it('stops crediting a release older than a day', async () => {
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 800_000 }) })
    localStorage.setItem(
      RELEASED_KEY,
      JSON.stringify({
        bytes: 300_000,
        usageAfter: 800_000,
        at: Date.now() - 25 * 60 * 60 * 1000,
      }),
    )

    // Back to the browser's own answer, and the dead note is cleared rather
    // than re-read on every estimate for the life of the installation.
    expect(await estimateAvailableBytes()).toBe(200_000)
    expect(localStorage.getItem(RELEASED_KEY)).toBeNull()
  })

  it('ignores a garbled note rather than crediting nonsense', async () => {
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 800_000 }) })
    localStorage.setItem(RELEASED_KEY, '{"bytes":"lots"}')

    expect(await estimateAvailableBytes()).toBe(200_000)
  })

  it('credits nothing when nothing was deleted', async () => {
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 800_000 }) })

    expect(await estimateAvailableBytes()).toBe(200_000)
  })

  it('forgets a release once it is cleared', async () => {
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 800_000 }) })
    recordReleased(300_000, 800_000)
    clearReleased()

    expect(await estimateAvailableBytes()).toBe(200_000)
  })

  it('reports raw usage unadjusted, since that is the credit’s own baseline', async () => {
    // If this applied the credit, the note would decay against itself.
    stubStorage({ estimate: () => Promise.resolve({ quota: 1_000_000, usage: 800_000 }) })
    recordReleased(300_000, 800_000)

    expect(await estimateUsageBytes()).toBe(800_000)
  })

  it('says nothing about usage where the browser will not', async () => {
    stubStorage({})

    expect(await estimateUsageBytes()).toBeNull()
  })
})
