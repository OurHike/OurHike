// The refuse-if-unmeasurable gate, past hike creation (#1357).
//
// #1317 stopped a Hike being CREATED on a trail with no published mile axis,
// and lib/hikeText.ts says why in one sentence - "a figure on any other trail
// would be an A.T. mileage wearing somebody else's name". Nothing carried that
// refusal past creation. lib/trailPosition.ts, lib/elevationProfile.ts and
// lib/route.ts's legFigures() do not consult trail identity at all; they are
// hardcoded to the one axis the pipeline publishes, right down to
// `axisProjection` measuring against Springer and Katahdin by name. So a hike
// on a second trail would have gone on being answered in A.T. miles, under
// that trail's name, on the position and elevation paths CLAUDE.md lists among
// the four ways this app can hurt somebody.
//
// WHY THIS FILE HAS TO SEED THE STORE RATHER THAN DRIVE THE UI. No hiker can
// reach this state today: `trailHasMileAxis` is `trailId === DEFAULT_TRAIL_ID`
// and `setupRefusal` blocks creating any other, so the shell has no door to
// walk through to an unmeasurable hike. The gate is written before that door
// opens - before a second axis is published (#768) or the predicate is
// relaxed - and seeding the trip store is the only thing that can reach it.
// That is the point of the gate, not a shortcut around testing it.
//
// The A.T. case in each pair is not decoration: it is what proves the gate is
// a gate and not a wall.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'
import { appHarness, openMapTab } from './test/appHarness'
import { TRIPS_KEY, type TripStore } from './lib/trips'
import { HIKER_MODE_KEY } from './lib/hikerMode'
import { ELEVATION_STORE_KEY } from './lib/trailData'
import { parseProfile } from './lib/elevationProfile'

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
vi.mock('./lib/api', () => ({
  API_CONFIGURED: false,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  fetchDisputes: vi.fn(async () => []),
  fetchReports: vi.fn(async () => []),
}))

const app = appHarness({
  navigator: { onLine: true, geolocation: true },
  objectUrls: true,
})

/**
 * Forty-one samples over the harness's forty-mile centerline, climbing
 * steadily so the ribbon has something to draw.
 *
 * SEEDED HERE RATHER THAN IN `appHarness.putTrailData`, which stores no
 * profile: 380 test files call that helper, and giving all of them terrain
 * they did not ask for is a wide change to make for one file's assertion.
 * The store holds the PARSED profile rather than its bytes (lib/trailData.ts
 * commits `ElevationProfile` under this key), so this parses it the same way
 * the download would.
 */
const PROFILE = parseProfile(
  JSON.stringify(
    Array.from({ length: 41 }, (_, i) => ({
      distance_mi: i,
      elevation_ft: 1000 + i * 50,
    })),
  ),
)

beforeEach(() => {
  app.onboard({ location_permission_requested: true })
  app.putTrailData()
  app.store.set(ELEVATION_STORE_KEY, PROFILE)
})

/** An active long hike on `trailId`, walking. Two ends, so `isUsableHike`
 *  holds and nothing refuses it for a reason other than the one under test. */
function hikeOn(trailId: string): TripStore {
  return {
    trips: [],
    openId: null,
    groups: [],
    hikes: [
      {
        id: 'hike-1',
        name: trailId === 'AT' ? 'Springer → Katahdin' : 'The Long Path',
        type: 'thru',
        trailId,
        status: 'walking',
        points: [
          { name: 'Start', mile: 0 },
          { name: 'End', mile: 20 },
        ],
        tripIds: [],
      },
    ],
    activeHikeId: 'hike-1',
  }
}

/**
 * Launch on a hike on `trailId`, open the map, and put one fix five miles up
 * the centerline.
 *
 * THE MAP TAB IS NOT OPTIONAL: the position line renders in the map screen's
 * header, so a test that only rendered would assert against a screen the line
 * is not on and pass for the wrong reason - which is what the A.T. controls
 * below caught on the first run of this file.
 */
async function walkingOn(trailId: string) {
  app.store.set(TRIPS_KEY, hikeOn(trailId))
  app.store.set(HIKER_MODE_KEY, 'long')
  render(<App />)
  await openMapTab()
  await screen.findByRole('region', { name: /trail map/i })
  await app.reportFixAtMile(5)
}

describe('the mile a hiker reads, on a trail this build cannot measure', () => {
  it('prints the mile when the hike IS on the measured trail', async () => {
    // The control. Without it the case below could pass because the fix never
    // arrived, which would prove nothing at all.
    await walkingOn('AT')

    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()
  })

  it('prints no mile, and names the trail, when it is not', async () => {
    await walkingOn('LP')

    expect(await screen.findByText('No miles on the L.P.')).toBeInTheDocument()
  })

  it('never prints an A.T. mile under the other trail’s name', async () => {
    // THE ASSERTION THIS FILE EXISTS FOR, stated as an absence because the
    // defect is a presence. The fix is at client mile 5 on the seeded
    // centerline; the failure mode is that number appearing anyway, measured
    // on an axis that does not run under this hiker's feet.
    await walkingOn('LP')
    await screen.findByText('No miles on the L.P.')

    expect(screen.queryByText(/mi 5\./)).toBeNull()
    expect(screen.queryByText(/^mi /)).toBeNull()
  })

  it('does not report a missing download from a phone that has one', async () => {
    // The wrong degrade, and an easy one to ship by accident: withholding the
    // index makes `trailReady` false unless the position line is told which
    // question it is answering. "No trail data" would send a hiker to the
    // downloads screen to fix something that is not broken.
    await walkingOn('LP')
    await screen.findByText('No miles on the L.P.')

    expect(screen.queryByText('No trail data')).toBeNull()
  })

  it('does not accuse the hiker of being off their trail', async () => {
    // The other wrong degrade, and the one that reaches safety: this hiker may
    // be standing squarely on the Long Path.
    await walkingOn('LP')
    await screen.findByText('No miles on the L.P.')

    expect(screen.queryByText('Off the trail')).toBeNull()
  })

  it('draws the elevation ribbon on the measured trail', async () => {
    // The control for the pair below. Without a seeded profile the ribbon is
    // absent for BOTH trails and the next assertion would prove nothing -
    // which is the trap this file already fell into once, on the mile.
    await walkingOn('AT')

    expect(
      await screen.findByRole('img', { name: /elevation profile/i }),
    ).toBeInTheDocument()
  })

  it('draws no ribbon at all rather than another trail’s terrain', async () => {
    // The second computation locus. `ribbonView` already answers undefined on
    // a null profile and MapScreen omits the block entirely - its own
    // docstring says an empty ribbon "reads as 'no terrain here'" - so
    // withholding the profile reuses a degrade that was designed for a
    // download with no terrain in it. The climb, the grade and the
    // walking-time estimate built on this profile all go with it.
    await walkingOn('LP')
    await screen.findByText('No miles on the L.P.')

    expect(screen.queryByRole('img', { name: /elevation profile/i })).toBeNull()
  })

  it('leaves a hiker with no long hike on the A.T. shell, unchanged', async () => {
    // No active hike is MEASURABLE, not unmeasurable - the app is the A.T.'s
    // whether or not a hike has been set up, which is today's behaviour and
    // the thing this change must not quietly alter.
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await app.reportFixAtMile(5)

    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()
  })
})
