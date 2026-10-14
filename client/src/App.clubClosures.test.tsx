// Every club closure, end to end through the shell (the maintainer's S6, poll
// of 2026-10-11): conditions/trail_closures.json read at launch with no hike
// planned, crossed out on the canvas, and a tap on one opening its row.
//
// Its own file for App.mapOverlays.test.tsx's reason: it needs lib/config
// mocked as configured, and a fetch that serves the closures file. What only
// this file can catch is the wiring between the modules each suite holds on
// its own - lib/useConditions.ts's read, chrome/noticesPanel.tsx's rule,
// chrome/MapScreen.tsx's pass-through, map/MapView.tsx's lazy chunk and the
// sheet - handing the wrong thing on.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { MockMap } from './test/mocks/maplibre-gl'
import { renderedMap } from './test/liveMap'
import { appHarness, openMapTab } from './test/appHarness'
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

const CLOSURES_URL = 'https://data.example/conditions/trail_closures.json'

// The fetch below is this file's own: the bucket serves the hand-made
// closures file and nothing else.
const app = appHarness({ stubFetch: false })

beforeEach(() => {
  app.onboard()
  app.putTrailData({ miles: 11 })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
    String(input) === CLOSURES_URL
      ? new Response(JSON.stringify(trailClosuresDocument()), { status: 200 })
      : new Response('', { status: 404 }),
  )
})

afterEach(() => vi.restoreAllMocks())

async function renderApp(): Promise<MockMap> {
  const { default: App } = await import('./App')
  render(<App />)
  await openMapTab()
  const map = await renderedMap()
  map.sourceIds = [CLUB_CLOSURE_SOURCE_ID]
  map.emit('load')
  return map
}

function drawnIds(map: MockMap): string[] {
  const data = map.sourceData.get(CLUB_CLOSURE_SOURCE_ID) as
    | { features: Array<{ properties: Record<string, string> }> }
    | undefined
  return (data?.features ?? []).map(
    (feature) => feature.properties[CLUB_CLOSURE_ID_PROPERTY],
  )
}

describe('every club closure on the map, from conditions/trail_closures.json', () => {
  // The first case in its file pays for the whole App's cold start;
  // App.mapOverlays.test.tsx's COLD_START_BUDGET_MS says why 20 s. Above
  // the call for that file's reason too: prettier has no stable place for a
  // comment between a callback and a trailing number.
  const COLD_START_BUDGET_MS = 20_000

  it(
    'crosses out the line, the area’s stretches, the point and the greyed closure, and opens the greyed one’s row from a tap',
    async () => {
      const rows = trailClosureRows()
      const map = await renderApp()

      // LATE, NEVER GONE: both waits are on state that stays once it lands,
      // so a longer window than testing-library's 1 s hides no defect. The
      // marks need the first frame, lib/publishedNotices.ts's chunk, the
      // read, and map/clubClosureTaps.ts's chunk; the sheet needs the whole
      // shell to render again. That passed here alone, and failed 2 batch
      // runs in 3 beside ten other files at a load average near 20
      // (2026-10-14), with the message not kept.
      await waitFor(
        () =>
          expect(drawnIds(map)).toEqual([
            rows.line.notice_id,
            rows.area.notice_id,
            rows.point.notice_id,
            rows.greyed.notice_id,
          ]),
        { timeout: 10_000 },
      )

      map.renderedFeatures.set(CLUB_CLOSURE_LAYER_ID, [
        { properties: { [CLUB_CLOSURE_ID_PROPERTY]: rows.greyed.notice_id } },
      ])
      map.emit('click', { point: { x: 100, y: 100 } })

      const sheet = await screen.findByRole(
        'dialog',
        { name: 'Closure notice' },
        { timeout: 5_000 },
      )
      expect(
        within(sheet).getByText('Example Canyon Trail closed (example)'),
      ).toBeInTheDocument()
      expect(
        within(sheet).getByText('Its source gives no date. It may no longer apply.'),
      ).toBeInTheDocument()
      expect(within(sheet).getByRole('note')).toHaveTextContent(
        /does not work out detours/,
      )
    },
    COLD_START_BUDGET_MS,
  )
})
