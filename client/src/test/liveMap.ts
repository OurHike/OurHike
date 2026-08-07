// Waiting for the map, rather than for the div it will be built in.
//
// This is the third time the same race has been written by hand, so it lives
// in one place now. The rule it encodes:
//
//   `findByRole('region', { name: /trail map/i })` resolves the moment
//   MapView's container div lands in the DOM - which is a commit BEFORE the
//   effect that constructs the map runs.
//
// So `MockMap.live[0]` straight after it is a read of an array that is usually
// full and sometimes empty. It wins on a quiet machine and loses under load,
// which makes it the worst kind of test: green when you push it, red on
// somebody else's merge commit.
//
// It has cost three separate debugging sessions:
//
//  - #86, `Cannot read properties of undefined (reading 'options')` - green on
//    both PR runs, red on the merge.
//  - the light/dark work, where one of the two reads in a single test was
//    wrapped in `waitFor` and the other was not.
//  - #232's map-overlay tests, `Cannot set properties of undefined (setting
//    'sourceIds')`, found by running the whole suite four times in a row
//    (#331).
//
// CLAUDE.md already states the general rule these are all instances of: wait
// on something observable that proves the sequence completed, never on a
// longer timeout. A wider `findByText` window would not have saved any of
// them - the map was absent, not late.

import { expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { MockMap } from './mocks/maplibre-gl'

/**
 * The live map, once MapView's effect has actually built it.
 *
 * `MockMap.live` rather than `MockMap.instances`, deliberately: the map screen
 * builds a NEW map when the trail lines land (a different object URL is a
 * different style), so the first map ever constructed is routinely one that
 * has already been torn down. Touching it would be touching nothing, silently.
 */
export async function liveMap(): Promise<MockMap> {
  await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
  return MockMap.live[0]
}

/**
 * The map screen, up and holding a live map.
 *
 * The pairing almost every test that touches the canvas actually wants: the
 * screen is on, AND the thing it is about exists. Kept together because
 * splitting them is precisely how the first half gets awaited and the second
 * forgotten.
 */
export async function renderedMap(): Promise<MockMap> {
  await screen.findByRole('region', { name: /trail map/i })
  return liveMap()
}
