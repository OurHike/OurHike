import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getWorkerUrl, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { registerMapWorker } from './mapWorker'

// The regression these guard against cost the whole map, on every platform,
// online and off - and looked like nothing at all. maplibre-gl 6 resolves its
// web worker from its own module URL, which after bundling is the app chunk, so
// the shipped app fetched `assets/maplibre-gl-worker.mjs`, which no build ever
// emitted. MapLibre reports no error for that: the style parses, every layer is
// in it, `getStyle()` reads back exactly right, and the map draws nothing but
// its background colour, because the worker is where every tile is parsed.
//
// These tests cover the WIRING - that MapLibre is pointed at a real bundled
// URL rather than left to guess. Whether that URL is really published is a
// question about the build output, which no test running in jsdom can answer;
// scripts/check-build-output.mjs is the other half and runs on the real bundle.

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

beforeEach(() => {
  resetMapLibreMock()
})

describe('registerMapWorker', () => {
  it('points MapLibre at a worker URL instead of leaving it to guess one', () => {
    // Empty is the state that shipped a blank map: MapLibre falls back to a
    // path beside the app chunk, where no bundler publishes anything.
    expect(getWorkerUrl()).toBe('')

    registerMapWorker()

    expect(getWorkerUrl()).not.toBe('')
  })

  it('hands MapLibre the same URL it reports back, so the two cannot drift', () => {
    // What the URL literally says differs between a dev server and a built
    // bundle - `?worker&url` is resolved by Vite either way - so what is
    // asserted is the invariant that holds in both: the app supplies the
    // worker's real location, and that is what MapLibre will fetch. Whether
    // that location is actually published is a fact about the build output,
    // and scripts/check-build-output.mjs is what reads it.
    const url = registerMapWorker()

    expect(url).toMatch(/maplibre-gl-worker/)
    expect(getWorkerUrl()).toBe(url)
  })

  it('is idempotent, so it is safe to call before every map build', () => {
    const first = registerMapWorker()
    const second = registerMapWorker()

    expect(second).toBe(first)
    expect(getWorkerUrl()).toBe(first)
  })
})
