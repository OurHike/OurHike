// The seam that defers the map engine, and the memo that makes it a one-time
// cost (#722).
//
// Separate from `engine.ts` on purpose, and the separation is the whole
// mechanism: `engine.ts` imports `maplibre-gl` statically, so anything
// importing IT statically is back where this started. This module imports it
// only through `import()`, so nothing that reaches this file drags the
// library into the eager chunk.
//
// It is also the seam the tests mock. `vi.mock('maplibre-gl', ...)` does not
// intercept a dynamic `import('maplibre-gl')` of the bare specifier - the real
// library loads in jsdom and throws `GPUInitializationError` - which is the
// trap that stopped this issue the first time it was picked up (recorded on
// #722). Going through a module of our own means the mock has a path to
// attach to.

import type { MapEngine } from './engine'

let pending: Promise<MapEngine> | null = null
let loaded: MapEngine | null = null

/**
 * The engine, loading it if this is the first ask.
 *
 * Memoised on the PROMISE rather than on the result, so two components
 * mounting in the same tick share one load instead of racing two.
 */
export async function loadMapEngine(): Promise<MapEngine> {
  if (loaded !== null) return loaded
  if (pending === null) {
    pending = import('./engine').then((module) => {
      loaded = module.mapEngine()
      return loaded
    })
  }
  return pending
}

/**
 * The engine if it is already here, and null otherwise.
 *
 * This is what keeps the SECOND map synchronous. The deferral is about the
 * first paint of a cold start; once the chunk is parsed, making a returning
 * hiker wait a microtask for a map they already had would be a regression
 * wearing the fix's clothes - and it is what lets `MapView` keep building
 * inside its effect body rather than after an await, on every mount but the
 * first.
 */
export function loadedMapEngine(): MapEngine | null {
  return loaded
}

/** Forgets the memo. Tests only - a module-level cache that survives between
 *  test files is a test that passes because of the one before it. */
export function resetMapEngineForTests(): void {
  pending = null
  loaded = null
}
