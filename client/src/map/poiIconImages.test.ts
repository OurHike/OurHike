// The pin images have to exist. That is the whole of what this file holds.
//
// Which thread builds them is a performance question (#857, and the header of
// poiIconImages.ts has the measurement). Whether they arrive at all is not: a
// map with no pin artwork draws no waypoints, the legend goes on counting
// them, and a hiker looking for the next water source is told nothing. So
// every way the worker can fail ends here with the images the synchronous
// build produces.
//
// Each case imports the module fresh, because it caches the build across
// callers on purpose - two maps attaching in one tick must share one worker,
// which also means one test's build would otherwise be every later test's
// answer.

import { describe, it, expect, vi, afterEach } from 'vitest'

// The rasteriser stands in for itself here, and deliberately. What every case
// below is about is WHICH path produced the images, not what they look like -
// map/poiIcons.test.ts owns the artwork - and the real build is seconds of
// scanline rasterising per call in jsdom, which is the cost this whole module
// exists to move rather than something to pay four more times in a suite.
const BUILT_HERE = [
  { id: 'poi-water-verified', image: 'built on this thread', pixelRatio: 2 },
]
vi.mock('./poiIcons', () => ({ buildPoiIcons: vi.fn(() => BUILT_HERE) }))

/** A fresh module, with its cache empty. */
async function loadModule() {
  vi.resetModules()
  return await import('./poiIconImages')
}

/**
 * A stand-in for a dedicated worker.
 *
 * jsdom has no `Worker` at all, which is itself one of the cases below - so
 * the constructor is installed as a global rather than spied on an existing
 * one. `reply` decides what this worker does with the message it is sent:
 * answer it, or fail.
 */
function stubWorker(reply: 'answer' | 'error') {
  const terminated: string[] = []
  const constructed: string[] = []
  const answer = [
    { id: 'poi-worker-water-verified', image: 'from the worker', pixelRatio: 2 },
  ]

  class FakeWorker {
    onmessage: ((event: { data: unknown }) => void) | null = null
    onerror: (() => void) | null = null

    constructor(url: URL | string) {
      constructed.push(String(url))
    }

    postMessage() {
      // A tick later, like a real one: the caller has to have returned before
      // anything comes back, which is the property attachPoiIcons is written
      // against.
      queueMicrotask(() => {
        if (reply === 'answer') this.onmessage?.({ data: answer })
        if (reply === 'error') this.onerror?.()
      })
    }

    terminate() {
      terminated.push('terminated')
    }
  }

  vi.stubGlobal('Worker', FakeWorker)
  return { terminated, constructed, answer }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('where the pin images are built', () => {
  it('uses a worker when the browser has one, and lets it go afterwards', async () => {
    const worker = stubWorker('answer')
    const { poiIconImages } = await loadModule()

    await expect(poiIconImages()).resolves.toEqual(worker.answer)
    expect(worker.constructed).toHaveLength(1)
    expect(worker.terminated).toHaveLength(1)
  })

  it('builds them here when there is no Worker at all', async () => {
    // jsdom, and any browser old enough that MapLibre could not draw for it
    // either - see the module header for why that second case is theoretical.
    vi.stubGlobal('Worker', undefined)
    const { poiIconImages } = await loadModule()

    await expect(poiIconImages()).resolves.toBe(BUILT_HERE)
  })

  it('builds them here when the worker cannot be constructed', async () => {
    // A Content-Security-Policy that refuses workers, or an asset that did not
    // ship. The pins are not optional, so this ends with them anyway.
    vi.stubGlobal(
      'Worker',
      class {
        constructor() {
          throw new Error('Refused to create a worker')
        }
      },
    )
    const { poiIconImages } = await loadModule()

    await expect(poiIconImages()).resolves.toBe(BUILT_HERE)
  })

  it('builds them here when the worker fails on its way through', async () => {
    stubWorker('error')
    const { poiIconImages } = await loadModule()

    await expect(poiIconImages()).resolves.toBe(BUILT_HERE)
  })

  it('builds once however many maps ask, so a second map costs nothing', async () => {
    // Every trip to the More tab and back builds a new map, and each one
    // attaches its icons. Two workers for one answer would be the bill this
    // module exists to remove, paid twice.
    const worker = stubWorker('answer')
    const { poiIconImages } = await loadModule()

    const [first, second] = await Promise.all([poiIconImages(), poiIconImages()])

    expect(first).toBe(second)
    expect(worker.constructed).toHaveLength(1)
  })

  it('asks for the worker entry beside it, which is what Vite emits as an asset', async () => {
    // The URL is the contract with the bundler: `new URL('./poiIconWorker.ts',
    // import.meta.url)` is what makes Vite emit the worker as a real hashed
    // asset and put it in the service worker's precache. Spelled any other way
    // it resolves to nothing at runtime, silently, and every launch falls back
    // to the main thread - the bug this module was written to end, restored
    // and invisible.
    const worker = stubWorker('answer')
    const { poiIconImages } = await loadModule()

    await poiIconImages()

    expect(worker.constructed[0]).toMatch(/poiIconWorker/)
  })
})
