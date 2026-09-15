// A SPIKE (#1423): what does opening a sheet actually re-render?
//
// THE QUESTION
//
// The client holds per-sheet UI state in the root component - `legendOpen`,
// `searchOpen`, `downloadsOpen`, `dayListOpen`, `tripsOpen`, `placeSheetOpen`,
// `stepPickerOpen` - and has zero `React.memo` and no React Compiler (#1422).
// It follows on paper that flipping one of those booleans re-renders every
// component beneath the root. Nothing had checked, which is the whole of why
// this file exists: the claim was a reading of the code, and a reading is not
// a finding.
//
// It was not obviously true either. `MapView` keeps its map in a ref and
// drives it through 48 narrowly-keyed effects, so a React re-render does not
// redraw the canvas - the cost could have been absorbed there.
//
// THE ANSWER, measured here at 3ce30bdd and re-verified after merging main
// in for #1426's fix, where every figure this file rests on is unmoved:
// App.tsx 10,627 lines with 33 `useState` and 161 `useCallback`,
// `MapScreenProps` 170 fields, and still zero `React.memo` and zero
// `createContext` in the whole client.
//
// Opening the legend renders all six instrumented components exactly once
// each, `MapView` and `MapAttribution` included. Neither has any part in the
// legend; both re-render because they sit under a root whose state changed.
// There is no boundary anywhere in the tree - the re-render reaches whatever
// is mounted, and what is mounted is the map screen entire.
//
// What that does NOT say, and the distinction is the useful part:
//
//   - It is ONE render each, not a storm. The tap reaches three setState
//     calls (`setInViewOpen` in MapScreen, `setLegendOpen` and
//     `setSelectedPoiId` in App) and they arrive as a single commit. Which
//     part of that is React batching them and which is two of the three
//     being no-ops against their current value was not isolated here - the
//     measurement is the one commit, not the mechanism behind it.
//   - `MapView` re-rendering is not the map redrawing. The map instance lives
//     in a ref and its effects are keyed on props the legend does not touch,
//     so this is a function call and a reconciliation, not a tile fetch and
//     not a paint.
//   - Nothing here is a millisecond. See test/renderCensus.ts for why this
//     counts renders instead, which is the same argument
//     App.loadBudget.test.tsx makes about counting operations.
//
// So the honest summary is: the structure is exactly as described, the blast
// radius is the whole mounted tree, and the per-render cost is unmeasured and
// is NOT measurable here. Whether one extra render of `MapView` costs a hiker
// anything on a mid-range Android WebView needs a throttled Chromium against a
// deployment, the way client/scripts/measure-first-run.mjs does it. This file
// establishes the multiplier; it cannot establish the unit.
//
// WHY THE CONTROLS ARE HALF THE FILE
//
// A census that reported "everything re-rendered" would look identical
// whether it were measuring the interaction or measuring its own background
// noise. Two controls separate them, and both were earned rather than
// assumed - the idle control caught a real post-mount render tail on the
// first run, which is why `settle()` exists.
//
// THIS IS A SPIKE, NOT A BUDGET. The assertions below are deliberately loose:
// they assert the SHAPE (everything, or nothing), not a total. A tightened
// count here would fail on any innocent change to what the map screen mounts,
// which is the flaky gate CLAUDE.md warns about. Whether any of this becomes a
// standing budget in the manner of App.loadBudget.test.tsx is a separate
// decision that #1423 does not make.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { appHarness, openMapTab } from './test/appHarness'
import { renderedMap } from './test/liveMap'
import { census, settle } from './test/renderCensus'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))
vi.mock('./map/protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
  CORRIDOR_ARCHIVE_URL: 'pmtiles://ourhike-corridor',
}))
vi.mock('./lib/config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
  archiveUrl: () => 'https://data.example/corridor.pmtiles',
}))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  fetchDisputes: vi.fn(async () => []),
  fetchReports: vi.fn(async () => []),
}))

// The instrumented six: everything the map screen mounts that is worth naming.
// Each mock spreads the real module and replaces one export with a counting
// wrapper, so nothing else about the module changes and the component that
// renders is the real one.
//
// `Legend` is here as the positive control - it is the thing being opened, so
// a census in which IT did not render would mean the harness was broken rather
// than the tree insulated. `MapView` and `MapAttribution` are the subjects:
// neither has anything to do with the legend.
vi.mock('./chrome/MapScreen', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./chrome/MapScreen')>()
  const { counting } = await import('./test/renderCensus')
  return { ...actual, MapScreen: counting('MapScreen', actual.MapScreen) }
})
vi.mock('./map/MapView', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./map/MapView')>()
  const { counting } = await import('./test/renderCensus')
  return { ...actual, MapView: counting('MapView', actual.MapView) }
})
vi.mock('./chrome/Legend', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./chrome/Legend')>()
  const { counting } = await import('./test/renderCensus')
  return { ...actual, Legend: counting('Legend', actual.Legend) }
})
vi.mock('./chrome/TabBar', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./chrome/TabBar')>()
  const { counting } = await import('./test/renderCensus')
  return { ...actual, TabBar: counting('TabBar', actual.TabBar) }
})
vi.mock('./chrome/Header', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./chrome/Header')>()
  const { counting } = await import('./test/renderCensus')
  return { ...actual, Header: counting('Header', actual.Header) }
})
vi.mock('./chrome/MapAttribution', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./chrome/MapAttribution')>()
  const { counting } = await import('./test/renderCensus')
  return {
    ...actual,
    MapAttribution: counting('MapAttribution', actual.MapAttribution),
  }
})

/** Every component this file instruments, so "all of them" is one name. */
const INSTRUMENTED = [
  'Header',
  'Legend',
  'MapAttribution',
  'MapScreen',
  'MapView',
  'TabBar',
] as const

// No fetch stub: lib/api and lib/config are mocked, so nothing reaches the
// network, and a stub would only hide it if something did.
const app = appHarness({ stubFetch: false })

beforeEach(() => {
  app.onboard()
  app.putTrailData({ miles: 11 })
})

afterEach(() => vi.restoreAllMocks())

/**
 * Land on the map screen with the counters zeroed and the shell quiet.
 *
 * `settle` is the load-bearing half. `renderedMap()` resolves when the map is
 * live, which is BEFORE the shell has finished settling - so without it the
 * first census in each test carries the mount's tail and every number is one
 * too high. The idle control below is what catches that if it regresses.
 */
async function landOnTheMap(): Promise<void> {
  const { default: App } = await import('./App')
  render(<App />)
  await openMapTab()
  await renderedMap()
  await settle(act)
}

const legendButton = () => screen.getByRole('button', { name: 'Legend' })

describe('what a root-held sheet toggle re-renders (#1423, a spike)', () => {
  it('re-renders nothing at all while the shell sits still', async () => {
    await landOnTheMap()

    await act(async () => {
      await Promise.resolve()
    })

    // The control that makes every other number in this file mean something:
    // an idle app renders nothing, so a census taken after an interaction is
    // reading the interaction.
    expect(census()).toEqual({})
  })

  it('re-renders nothing for a tap that changes no state', async () => {
    await landOnTheMap()

    // Open it, settle, then tap the same control again. `setLegendOpen(true)`
    // over `true` is a no-op and React bails out of the whole subtree, so this
    // is a tap that reaches a handler and still costs nothing.
    await act(async () => {
      fireEvent.click(legendButton())
    })
    await settle(act)

    await act(async () => {
      fireEvent.click(legendButton())
    })

    // The second control, and the sharper one: it proves the census counts
    // state changes rather than events. Without it, "everything re-renders on
    // a tap" could just as well have meant "everything re-renders, always".
    expect(census()).toEqual({})
  })

  it('re-renders every mounted component, the map included, for one boolean', async () => {
    await landOnTheMap()

    await act(async () => {
      fireEvent.click(legendButton())
    })

    const counted = census()

    // The finding. Not one of the six is insulated from a boolean that
    // concerns exactly one of them: `MapView` and `MapAttribution` re-render
    // for a legend they have no part in, because there is no boundary between
    // the root's state and them.
    expect(Object.keys(counted).sort()).toEqual([...INSTRUMENTED])

    // Once each, not a storm - the tap's three setState calls arrive as one
    // commit. Asserted per component rather than as a total so that mounting
    // one more thing on the map screen does not fail this file.
    for (const name of INSTRUMENTED) expect(counted[name]).toBe(1)
  })

  it('re-renders all of them again to close it, so the round trip is two each', async () => {
    await landOnTheMap()

    await act(async () => {
      fireEvent.click(legendButton())
    })
    await settle(act)

    // The legend's own close button, not the control that opened it -
    // `onOpenLegend` sets `true` rather than toggling, which is what the
    // no-op control above is measuring.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Close legend' }))
    })

    // Closing is not cheaper than opening: the same boolean moves the other
    // way and the same tree answers for it. A hiker who opens the legend to
    // check a symbol and closes it again has re-rendered the map screen twice.
    const counted = census()
    expect(Object.keys(counted).sort()).toEqual([...INSTRUMENTED])
    for (const name of INSTRUMENTED) expect(counted[name]).toBe(1)
  })
})
