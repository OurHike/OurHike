// What the shell puts on the canvas once the reads land (#232).
//
// Its own file for the reason App.outboxRetry.test.tsx and
// App.trailData.test.tsx each have one: this needs BOTH lib/api and lib/config
// mocked as configured, and either would change the subject of every test in
// App.test.tsx, which deliberately runs unconfigured.
//
// The seam being covered is App's own: `closureBands` and `isSeriousWarning`
// are tested where they live, and MapScreen's pass-through is tested in
// chrome/MapScreen.test.tsx. What only this file can catch is the shell
// handing the wrong array to either - a normal report drawn as a serious
// warning, or a closure placed against the wrong index.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MockMap } from './test/mocks/maplibre-gl'
import { renderedMap } from './test/liveMap'
import { appHarness } from './test/appHarness'
import { CLOSURE_SOURCE_ID } from './map/closureLayers'
import { WARNING_SOURCE_ID } from './map/warningLayers'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))
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

const CLOSURE = {
  id: 'c1',
  reason_type: 'storm_damage' as const,
  note: null,
  status: 'closed' as const,
  start_mile_marker: 2,
  end_mile_marker: 4,
  reported_at: '2026-08-01T10:00:00Z',
  verified_at: '2026-08-02T10:00:00Z',
}

const REPORT = {
  reporter_type: 'thru',
  status: 'verified' as const,
  poi_id: null,
  note: null,
  timestamp: '2026-08-01T10:00:00Z',
}

const REPORTS = [
  {
    ...REPORT,
    id: 'serious-1',
    type: 'animals',
    severity: 'serious' as const,
    lat: 39.05,
    lon: -77,
  },
  // Not escalated. Every report on the trail would be a pin if the shell
  // filtered on nothing, and the pin is supposed to mean a moderator acted.
  {
    ...REPORT,
    id: 'normal-1',
    type: 'blowdown',
    severity: 'normal' as const,
    lat: 39.06,
    lon: -77,
  },
  // Serious, and nowhere - a report filed against a POI rather than a
  // position. There is no honest place to draw this.
  {
    ...REPORT,
    id: 'serious-nowhere',
    type: 'water',
    severity: 'serious' as const,
    lat: null,
    lon: null,
  },
]

vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => [CLOSURE]),
  fetchReports: vi.fn(async () => REPORTS),
}))

// No fetch stub: this file mocks lib/api and lib/config, so nothing here
// reaches the network, and a stub would only hide it if something did.
const app = appHarness({ stubFetch: false })

beforeEach(() => {
  app.onboard()
  // Already on the phone, so nothing is fetched and the centerline index is
  // built from exactly this geometry - eleven miles, one vertex each.
  app.putTrailData({ miles: 11 })
})

// restore, not just clear - see App.trailData.test.tsx's own note.
afterEach(() => vi.restoreAllMocks())

async function renderApp(): Promise<MockMap> {
  const { default: App } = await import('./App')
  render(<App />)

  // `renderedMap`, not `findByRole` then `MockMap.live[0]`. The container div
  // commits before the effect that builds the map runs, so reading the array
  // straight after the div is a race - it passed here every time and failed on
  // the fourth consecutive full-suite run with `Cannot set properties of
  // undefined (setting 'sourceIds')` (#331). See test/liveMap.ts.
  const map = await renderedMap()

  // Real MapLibre holds its sources by the time `load` fires; the mock has to
  // be told. Emitted after the first render so the attach helpers exercise
  // their wait-for-the-style path, which is the one that actually runs.
  map.sourceIds = [CLOSURE_SOURCE_ID, WARNING_SOURCE_ID]
  map.emit('load')
  return map
}

function featuresIn(map: MockMap, sourceId: string) {
  const data = map.sourceData.get(sourceId) as
    { features: Array<{ id: string }> } | undefined
  return data?.features ?? []
}

describe('what the shell draws once the reads land', () => {
  it('places the closure on the trail, from its mile markers', async () => {
    // The only place the two halves meet: the backend sends mile markers, the
    // phone holds the centerline, and neither on its own can put a band on the
    // map.
    const map = await renderApp()

    await waitFor(() => {
      expect(featuresIn(map, CLOSURE_SOURCE_ID)).toHaveLength(1)
    })
    expect(featuresIn(map, CLOSURE_SOURCE_ID)[0].id).toBe('c1')
  })

  it('draws only the reports a moderator escalated', async () => {
    const map = await renderApp()

    await waitFor(() => {
      expect(featuresIn(map, WARNING_SOURCE_ID).map((f) => f.id)).toEqual(['serious-1'])
    })
  })

  it('draws a warning even before the app knows which way anyone is walking', async () => {
    // There is no GPS fix in this test and no direction, so the alert strip
    // says nothing - `closureAhead` and `warningsAhead` both need a heading.
    // The canvas is what a hiker has until then, which is the whole reason
    // these are separate props.
    const map = await renderApp()

    await waitFor(() => {
      expect(featuresIn(map, WARNING_SOURCE_ID)).toHaveLength(1)
    })
    expect(screen.queryByRole('alert')).toBe(null)
  })
})

// The ATC's notices, end to end (#461 and features/ATC_TRAIL_UPDATES.md).
//
// Only this file can catch what is being asserted here, because the gap it
// covers is a gap BETWEEN modules: `atcBandCandidates` drops a non-obstructing
// range, `closureBands` drops anything over `MAX_BAND_MILES`, `atcPointNotices`
// keeps only single-mile notices, and `atcUpdateLanes` shows at most two and
// only ahead of the hiker. Each is right where it lives. Their intersection is
// a notice the ATC published that a hiker using this app could not read
// anywhere at all, and no unit test has a vantage point on an intersection.

/** ATC's Helene advisory at this harness's scale: a range, over the band
 *  ceiling, obstructing nothing, and with no GPS fix there is no banner
 *  either. Before the notice list this reached the hiker through nothing. */
const UNDRAWN_UPDATE = {
  atc_id: 'hurricane-helene-storm-damage',
  title: 'Hurricane Helene Storm Damage',
  category: 'Alert' as const,
  states: ['NC', 'TN'],
  start_mile_marker: 1,
  end_mile_marker: 9,
  obstructs_trail: false,
  updated_at: '2026-06-02T00:00:00Z',
  source_url: 'https://appalachiantrail.org/trail-updates/helene/',
}

/** A single mile, so the map draws a dot for it. */
const DRAWN_UPDATE = {
  atc_id: 'harpers-ferry-footbridge-closure',
  title: 'Harpers Ferry: Footbridge Closure',
  category: 'Detour' as const,
  states: ['MD', 'WV'],
  start_mile_marker: 6,
  end_mile_marker: 6,
  obstructs_trail: true,
  updated_at: '2026-07-31T19:54:12Z',
  source_url: 'https://appalachiantrail.org/trail-updates/harpers-ferry/',
}

/** Answers the one published read this file cares about and 404s the rest, so
 *  the closures and reports baselines stay exactly as the tests above found
 *  them - both come from the mocked `lib/api` here, not from the bucket. */
function serveAtcUpdates(updates: unknown[]): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (!url.endsWith('conditions/atc_updates.json')) {
        return new Response(null, { status: 404 })
      }
      return new Response(
        JSON.stringify({
          generated_at: '2026-08-12T00:00:00Z',
          reviewed_at: '2026-08-12T00:00:00Z',
          atc_updates: updates,
        }),
        { status: 200 },
      )
    }),
  )
}

describe('every ATC notice is readable, drawn or not', () => {
  // #687 moved the way to open this list from a permanent button on the map
  // screen into the legend, so every test below opens the legend first - the
  // list itself, and what it shows once open, are otherwise unchanged.

  it('offers a way to read all of them as soon as any arrive', async () => {
    serveAtcUpdates([UNDRAWN_UPDATE, DRAWN_UPDATE])
    await renderApp()

    // No fix and no direction in this harness, so there is no banner at all -
    // which is exactly the state the legend row has to survive.
    expect(screen.queryByRole('alert')).toBe(null)

    await userEvent.click(await screen.findByRole('button', { name: 'Legend' }))

    expect(
      await screen.findByRole('button', { name: 'Read all 2 ATC trail updates' }),
    ).toBeInTheDocument()
  })

  it('shows the notice that reaches the hiker through nothing else', async () => {
    serveAtcUpdates([UNDRAWN_UPDATE, DRAWN_UPDATE])
    await renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Legend' }))
    await userEvent.click(
      await screen.findByRole('button', { name: /ATC trail updates/ }),
    )

    const list = screen.getByRole('dialog', {
      name: /Appalachian Trail Conservancy/,
    })
    expect(within(list).getByText('Hurricane Helene Storm Damage')).toBeInTheDocument()
    expect(
      within(list).getByText('Harpers Ferry: Footbridge Closure'),
    ).toBeInTheDocument()
  })

  it('tells the hiker which one has no mark on the map to look for', async () => {
    // Read off what the canvas is actually drawing rather than re-derived, so
    // a notice whose mile falls off this build's centerline is reported
    // honestly too. The dot for mile 6 is on the eleven-vertex centerline this
    // file builds; the 8-mile range is over the band ceiling and is not.
    serveAtcUpdates([UNDRAWN_UPDATE, DRAWN_UPDATE])
    await renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Legend' }))
    await userEvent.click(
      await screen.findByRole('button', { name: /ATC trail updates/ }),
    )

    const items = screen.getAllByRole('listitem')
    const helene = items.find((item) =>
      within(item).queryByText('Hurricane Helene Storm Damage'),
    )
    const footbridge = items.find((item) =>
      within(item).queryByText('Harpers Ferry: Footbridge Closure'),
    )

    expect(helene).toHaveTextContent(/Not drawn on the map/)
    expect(footbridge).not.toHaveTextContent(/Not drawn on the map/)
  })

  it('offers nothing to open when the bucket has no reviewed file', async () => {
    // The 404 the pipeline serves while nobody has reviewed the source. An
    // empty list would render as "the ATC reports nothing", which is the one
    // thing export_atc_updates.py publishes nothing in order to avoid.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 404 })),
    )
    await renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Legend' }))

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /ATC trail update/ })).toBe(null)
    })
  })
})

describe('the bottom banner for new ATC alerts, end to end (#687)', () => {
  // chrome/MapScreen.test.tsx and lib/atcAlertsBanner.test.ts cover the
  // banner's own rendering and the 72-hour gate in isolation. What only this
  // file can catch is the wiring between them: App.tsx's real clock
  // (lib/useClock.ts) and the real localStorage watermark actually meeting
  // what the shell fetched.

  function recentUpdate() {
    // An hour old, which is comfortably inside the 72-hour window without
    // touching its boundary - the exact edge is lib/atcAlertsBanner.test.ts's
    // job, under a frozen clock where "exact" is possible.
    return {
      ...DRAWN_UPDATE,
      updated_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    }
  }

  it('appears once ATC has posted something in the last 72 hours', async () => {
    serveAtcUpdates([UNDRAWN_UPDATE, recentUpdate()])
    await renderApp()

    expect(
      await screen.findByRole('button', { name: 'ATC · New alert issued' }),
    ).toBeInTheDocument()
  })

  it('stays quiet when everything ATC holds is old news', async () => {
    // UNDRAWN_UPDATE and DRAWN_UPDATE's own dates (2026-06-02, 2026-07-31)
    // are what most of this describe block already renders against - this
    // pins that the banner agrees with the legend row about what "old" means.
    serveAtcUpdates([UNDRAWN_UPDATE, DRAWN_UPDATE])
    await renderApp()

    await userEvent.click(await screen.findByRole('button', { name: 'Legend' }))
    await screen.findByRole('button', { name: 'Read all 2 ATC trail updates' })

    expect(screen.queryByRole('button', { name: /new alerts? issued/i })).toBe(null)
  })

  it('silences on its own, without opening the full list', async () => {
    serveAtcUpdates([recentUpdate()])
    await renderApp()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Silence new ATC alerts' }),
    )

    expect(screen.queryByRole('button', { name: /new alerts? issued/i })).toBe(null)
    expect(screen.queryByRole('dialog', { name: /Appalachian Trail Conservancy/ })).toBe(
      null,
    )
  })

  it('is also silenced by reading the full list instead', async () => {
    serveAtcUpdates([recentUpdate()])
    await renderApp()

    await userEvent.click(
      await screen.findByRole('button', { name: 'ATC · New alert issued' }),
    )

    expect(screen.queryByRole('button', { name: /new alerts? issued/i })).toBe(null)
    expect(
      screen.getByRole('dialog', { name: /Appalachian Trail Conservancy/ }),
    ).toBeInTheDocument()
  })
})
