// The trailhead door, "Your day hikes near here" (frame D8), never over a
// sheet a hiker opened by tapping the map (App.tsx's `lowerThirdTaken`).
//
// The door is the one occupant of the map's lower third nobody asked for,
// and it renders in exactly the state where the map's taps are live; it sits
// last in the canvas, so at equal z-index it would cover whatever sheet a
// tap had just opened. A hazard area's sheet (decision 67) and a club
// closure's (the maintainer's S6, 2026-10-11) were not counted, so the door
// could cover either, both of them about what a hiker is walking into.
//
// Its own file for App.clubClosures.test.tsx's reason, plus a GPS fix: the
// door asks for a located hiker near a planned hike's start.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MockMap } from './test/mocks/maplibre-gl'
import { renderedMap } from './test/liveMap'
import { appHarness, latOfMile, openMapTab } from './test/appHarness'
import { DAY_HIKES_KEY } from './lib/dayHikes'
import { HAZARD_ADVISORIES, HAZARD_ID_PROPERTY } from './lib/hazardAreas'
import { HAZARD_FILL_LAYER_ID, HAZARD_SOURCE_ID } from './map/hazardAreaLayers'
import { CLUB_CLOSURE_ID_PROPERTY } from './map/closureLayers'
import { CLUB_CLOSURE_SOURCE_ID } from './map/clubClosureLayers'
import { CLUB_CLOSURE_LAYER_ID } from './map/styleIds'
import {
  trailClosureRows,
  trailClosuresDocument,
} from '../preview-shots/fixtures/clubClosures.mjs'

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

/** The door as it first appears: chrome/DayHikesHere.tsx's pill, before a
 *  tap opens it into the "Your day hikes near here" region. */
const DOOR = 'A day hike starts here'
const HUNTING_ID = 'oprhp_hunting_areas:fixture'

/** A planned day hike starting at mile 2 of the harness's centerline, where
 *  the fix below lands, so the door offers it. */
const PLANNED_HIKE = {
  id: 'planned-1',
  name: 'Fixture loop',
  date: '2026-08-29',
  segments: [
    [
      { coord: [-77, latOfMile(2)], poiId: null },
      { coord: [-77, latOfMile(3)], poiId: null },
    ],
  ],
  figures: {
    miles: 1,
    legs: [{ name: 'Fixture Trail', source: 'centerline', blaze_color: null, miles: 1 }],
  },
  looped: false,
  recorded: 'planned',
}

/** conditions/hazard_areas.json with one invented hunting area, which the
 *  centerline crosses between miles 4.5 and 5.5, so it draws. */
const HAZARD_DOCUMENT = {
  generated_at: '2026-10-14T09:00:00Z',
  notices: [
    {
      notice_id: HUNTING_ID,
      source_key: 'oprhp_hunting_areas',
      title: 'Fixture hunting area (example)',
      hazard: 'hunting',
      obstructs_trail: false,
      place: {
        kind: 'geometry',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-77.01, latOfMile(4.5)],
              [-76.99, latOfMile(4.5)],
              [-76.99, latOfMile(5.5)],
              [-77.01, latOfMile(5.5)],
              [-77.01, latOfMile(4.5)],
            ],
          ],
        },
      },
    },
  ],
}

const FILES: Record<string, unknown> = {
  'https://data.example/conditions/hazard_areas.json': HAZARD_DOCUMENT,
  'https://data.example/conditions/trail_closures.json': trailClosuresDocument(),
}

const app = appHarness({
  navigator: { onLine: true, geolocation: true },
  objectUrls: true,
  stubFetch: false,
})

beforeEach(() => {
  app.onboard({ location_permission_requested: true })
  app.putTrailData({ miles: 11 })
  app.store.set(DAY_HIKES_KEY, { hikes: [PLANNED_HIKE], openId: null })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const file = FILES[String(input)]
    return file === undefined
      ? new Response('', { status: 404 })
      : new Response(JSON.stringify(file), { status: 200 })
  })
})

afterEach(() => vi.restoreAllMocks())

function featuresIn(map: MockMap, sourceId: string): unknown[] {
  const data = map.sourceData.get(sourceId) as { features: unknown[] } | undefined
  return data?.features ?? []
}

describe('the day hikes here door and the sheets a tap on the map opens', () => {
  // The first case in its file pays for the whole App's cold start;
  // App.mapOverlays.test.tsx's COLD_START_BUDGET_MS says why 20 s.
  const COLD_START_BUDGET_MS = 20_000

  it(
    'stays off an open hazard-area sheet and an open club closure sheet, and comes back between them',
    async () => {
      const { default: App } = await import('./App')
      render(<App />)
      await openMapTab()
      const map = await renderedMap()
      map.sourceIds = [HAZARD_SOURCE_ID, CLUB_CLOSURE_SOURCE_ID]
      map.emit('load')

      // At the planned hike's start, the door offers it.
      await app.reportFixAtMile(2)
      await screen.findByRole('button', { name: DOOR }, { timeout: 5_000 })

      // A touch on the drawn hunting area opens its sheet, and the door goes.
      // The waits are on state that stays once it lands (the area needs the
      // hazard file and two chunks), so a long window hides no defect.
      await waitFor(() => expect(featuresIn(map, HAZARD_SOURCE_ID)).toHaveLength(1), {
        timeout: 10_000,
      })
      map.renderedFeatures.set(HAZARD_FILL_LAYER_ID, [
        { properties: { [HAZARD_ID_PROPERTY]: HUNTING_ID } },
      ])
      map.emit('click', { point: { x: 100, y: 100 } })
      const hazardSheet = await screen.findByRole(
        'dialog',
        { name: HAZARD_ADVISORIES.hunting.heading },
        { timeout: 5_000 },
      )
      expect(screen.queryByRole('button', { name: DOOR })).toBeNull()

      // Closing the sheet gives the lower third back to the door.
      fireEvent.click(within(hazardSheet).getByRole('button', { name: 'Close' }))
      await screen.findByRole('button', { name: DOOR }, { timeout: 5_000 })

      // And a touch on a club closure's crossed-out line takes it away again.
      await waitFor(
        () => expect(featuresIn(map, CLUB_CLOSURE_SOURCE_ID)).toHaveLength(4),
        {
          timeout: 10_000,
        },
      )
      map.renderedFeatures.delete(HAZARD_FILL_LAYER_ID)
      map.renderedFeatures.set(CLUB_CLOSURE_LAYER_ID, [
        {
          properties: { [CLUB_CLOSURE_ID_PROPERTY]: trailClosureRows().greyed.notice_id },
        },
      ])
      map.emit('click', { point: { x: 100, y: 100 } })
      await screen.findByRole('dialog', { name: 'Closure notice' }, { timeout: 5_000 })
      expect(screen.queryByRole('button', { name: DOOR })).toBeNull()
    },
    COLD_START_BUDGET_MS,
  )
})
