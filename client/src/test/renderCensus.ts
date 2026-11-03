// Counts how many times a component renders, for tests that are about the
// shape of the component tree rather than about what it draws.
//
// WHY A COUNT AND NOT A DURATION
//
// The same reason App.loadBudget.test.tsx gives for counting operations
// rather than milliseconds, and it is worth restating because this file is
// where the next person will be tempted: a render count is a structural fact
// about the tree. It is the same number on a CI runner, on a maintainer's
// laptop and on a phone in the Smokies, because it is decided by where state
// lives and which components sit beneath it - not by how fast anything runs.
//
// React's own `<Profiler>` reports `actualDuration` alongside the commit, and
// in jsdom that number is meaningless: no compositor, no WebGL, no paint, and
// `maplibre-gl` mocked outright (TESTING.md §19). A duration asserted here
// would be the flaky test CLAUDE.md warns about, and worse, it would look like
// evidence. Profiler is not used for that reason - it answers per-commit, and
// the question is per-component.
//
// WHAT THE COUNT MEANS, EXACTLY
//
// `counting(name, Component)` returns a wrapper that increments `name` and
// then renders `Component` with the same props. The wrapper re-renders exactly
// when React would have re-rendered the original - it adds a layer to the tree
// but changes nothing about how re-renders propagate through it, because the
// wrapper is not memoised and neither is anything in this client (zero
// `React.memo` at 3ce30bdd, #1422). So the count IS the component's render
// count.
//
// That equivalence is the one thing here that would quietly stop being true:
// wrap a component that IS memoised and the wrapper re-renders when the
// original would not have, over-reporting. If `React.memo` ever arrives, this
// file needs `memo()` applied to the wrapper to match - and the census will be
// measuring the memoisation, which is then the interesting question anyway.

import { createElement, type ComponentType } from 'react'

const counts = new Map<string, number>()

/** Wrap a component so every render of it is counted under `name`. */
export function counting<P extends object>(
  name: string,
  Component: ComponentType<P>,
): ComponentType<P> {
  function Counted(props: P) {
    counts.set(name, (counts.get(name) ?? 0) + 1)
    return createElement(Component, props)
  }
  Counted.displayName = `Counted(${name})`
  return Counted
}

/**
 * Zero every counter.
 *
 * Called after the screen has settled and before the interaction under
 * measurement, so the count is the interaction's and does not carry the
 * mount's renders in it.
 */
export function resetCensus(): void {
  counts.clear()
}

/** What has rendered since the last reset, by name. */
export function census(): Record<string, number> {
  return Object.fromEntries([...counts].sort(([a], [b]) => a.localeCompare(b)))
}

/**
 * Run effects until nothing is rendering any more, then zero the counters.
 *
 * The map screen does not stop rendering when `renderedMap()` resolves: reads
 * of preferences, trail data and the archive land as promises and each settles
 * into its own commit. A census taken straight after landing therefore counts
 * the tail of the mount as though it were the interaction - measured while
 * writing this: one render of all six instrumented components, arriving after
 * the map was live.
 *
 * So: flush, and keep flushing until a flush produces nothing. `rounds` is a
 * ceiling rather than a target - it throws instead of looping forever if the
 * shell has an effect that re-triggers itself, which is a real defect and
 * should be loud rather than a hang.
 */
export async function settle(
  act: (fn: () => Promise<void>) => Promise<void>,
  rounds = 20,
): Promise<void> {
  for (let i = 0; i < rounds; i++) {
    resetCensus()
    await act(async () => {
      await Promise.resolve()
    })
    if (Object.keys(census()).length === 0) {
      resetCensus()
      return
    }
  }
  throw new Error(
    `the shell was still rendering after ${rounds} flushes: ${JSON.stringify(census())}`,
  )
}
