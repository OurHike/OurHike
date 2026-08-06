import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  clearCompleted,
  completedMarker,
  completedMarkerKeyFor,
  estimateAvailableBytes,
  readPersistence,
  recordCompleted,
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
