// What the map opens on after a reload it did not ask for (#311).
//
// Every case here is about the same trade: a view worth restoring across one
// reload of this tab, and a view that must NOT be restored to someone opening
// the app fresh - which is what makes session storage the design rather than
// an implementation detail.

import { describe, it, expect, afterEach, vi } from 'vitest'
import { CAMERA_MEMORY_KEY, readCamera, writeCamera } from './cameraMemory'

afterEach(() => {
  // Restore BEFORE clearing: one case below mocks the `sessionStorage` getter
  // to throw, and clearing first walks straight into it - failing the teardown
  // of a test whose own assertions passed.
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  window.sessionStorage.clear()
})

describe('cameraMemory', () => {
  it('gives back the view it was handed', () => {
    writeCamera({ center: [-77.2, 41.5], zoom: 13.5 })

    expect(readCamera()).toEqual({ center: [-77.2, 41.5], zoom: 13.5 })
  })

  it('answers null on a fresh tab, which is the whole corridor', () => {
    // Not an edge case - it is every first run, and the caller's null branch
    // is what opens the map on the trail rather than on nowhere.
    expect(readCamera()).toBeNull()
  })

  it('keeps the view in session storage, not beyond it', () => {
    // The design, asserted where it can regress: a durable store would show
    // someone starting in Maine the Georgia view they left last Tuesday.
    writeCamera({ center: [-77, 39], zoom: 12 })

    expect(window.sessionStorage.getItem(CAMERA_MEMORY_KEY)).not.toBeNull()
    expect(window.localStorage.getItem(CAMERA_MEMORY_KEY)).toBeNull()
  })

  it('refuses a stored shape it cannot trust', () => {
    // This value is handed straight to MapLibre as an opening camera, so a
    // half-written entry is not a wrong view - it is a map that fails to
    // build. Each of these is a real way storage comes back wrong.
    for (const bad of [
      'not json at all',
      '{}',
      '{"center":[-77],"zoom":12}',
      '{"center":[-77,39]}',
      '{"center":["west",39],"zoom":12}',
      '{"center":[-77,39],"zoom":null}',
      '{"center":[-77,39],"zoom":"close"}',
    ]) {
      window.sessionStorage.setItem(CAMERA_MEMORY_KEY, bad)
      expect(readCamera()).toBeNull()
    }
  })

  it('rejects a non-finite zoom rather than passing NaN to the map', () => {
    // JSON.stringify writes NaN as null, so this arrives through any path
    // that stored a bad number - and NaN compares false against every guard
    // written with < or >.
    window.sessionStorage.setItem(CAMERA_MEMORY_KEY, '{"center":[-77,39],"zoom":NaN}')

    expect(readCamera()).toBeNull()
  })

  it('survives storage that throws on access, rather than taking the app down', () => {
    // Private browsing and hardened embedders throw when `sessionStorage` is
    // READ, before any get or set. Losing the view is the acceptable failure;
    // failing to render the map is not.
    vi.spyOn(window, 'sessionStorage', 'get').mockImplementation(() => {
      throw new Error('The operation is insecure.')
    })

    expect(() => writeCamera({ center: [-77, 39], zoom: 12 })).not.toThrow()
    expect(readCamera()).toBeNull()
  })
})
