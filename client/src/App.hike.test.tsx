// What a declared hike buys, at the level a hiker experiences it (#335).
//
// Its own file for the reason App.mapOverlays.test.tsx has one: this needs
// lib/api mocked as CONFIGURED so there are closures to warn about, and that
// would change the subject of every test in App.test.tsx, which deliberately
// runs unconfigured.
//
// The assertion that matters is the FIRST one. lib/hikeDirection.ts will not
// commit to NOBO or SOBO until a quarter mile has been walked in one
// direction - deliberately, so a GPS wandering under tree cover at a lunch
// stop does not flip the header - and until it does, "ahead" has no meaning
// and the banners say nothing. That quarter mile is exactly the stretch a
// hiker walks leaving a trailhead, which is where a closure two miles up the
// trail most needs saying.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { appHarness } from './test/appHarness'
import { PLANNED_HIKE_KEY } from './lib/plannedHike'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))

/** Closed from mile 8 to 9 - two and a bit miles north of where the fix below
 *  puts the hiker, and behind a southbound one. */
const CLOSURE = {
  id: 'c1',
  reason_type: 'storm_damage' as const,
  note: null,
  status: 'closed' as const,
  start_mile_marker: 8,
  end_mile_marker: 9,
  reported_at: '2026-08-01T10:00:00Z',
  verified_at: '2026-08-02T10:00:00Z',
}

vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => [CLOSURE]),
  fetchFieldNotes: vi.fn(async () => []),
  // Disputes ride the same read as the notes they are computed from (#876).
  fetchDisputes: vi.fn(async () => []),
  fetchReports: vi.fn(async () => []),
}))

// onLine because the map's own reads are gated on it (App.tsx): a navigator
// without it is `undefined`, which is falsy, so no closure ever arrives and
// every banner assertion below would pass by being vacuously silent.
const app = appHarness({
  navigator: { onLine: true, geolocation: true },
  objectUrls: true,
})
const store = app.store

beforeEach(() => {
  app.onboard({ location_permission_requested: true })
  app.putTrailData()
})

/**
 * ONE fix, five miles up the trail, and deliberately only one.
 *
 * A second fix a quarter mile further on is what makes `hikeDirection.ts`
 * commit. Sending only this one holds the app in exactly the state this
 * feature exists for: a hiker who is somewhere, and about whom nothing is yet
 * known regarding which way they are pointed.
 */
const reportOneFix = () => app.reportFixAtMile(5)

async function renderApp() {
  render(<App />)
  await screen.findByRole('region', { name: /trail map/i })
}

// Imported after the mocks above are in place.
const { default: App } = await import('./App')

/** The visible safety band. Queried by its container since #315 — it no longer
 *  carries `role="alert"`, because its text ends in a distance the shell
 *  recomputes on every GPS fix, so a live role meant an assertive screen-reader
 *  interruption per jitter tick. What gets ANNOUNCED is a separate hidden line
 *  that names the lanes without the number; chrome/MapScreen.test.tsx pins that. */
async function safetyBand(): Promise<HTMLElement> {
  return (await screen.findByText(/trail closed|serious warning|advisory/i)).closest(
    '.map-screen__alerts',
  ) as HTMLElement
}

/** Whether any safety line is on screen at all. */
function noSafetyBand(): boolean {
  return document.querySelector('.map-screen__alerts') === null
}

describe('a hiker who has said which way they are walking', () => {
  it('is warned about the closure ahead without walking a step', async () => {
    // The payoff. Northbound from the southern terminus, one GPS fix, no
    // movement - and the closure two miles up the trail is on screen.
    store.set(PLANNED_HIKE_KEY, { startMile: 0, endMile: 30 })

    await renderApp()
    await reportOneFix()

    expect(await safetyBand()).toHaveTextContent(/trail closed/i)
  })

  it('reads that warning in the units they chose in Settings (#619)', async () => {
    // The whole thread, end to end: a stored preference, read by the shell,
    // handed to lib/closureBanner.ts, on screen in the one line a hiker sees
    // without tapping anything. Every other test of this reaches one seam;
    // this one proves the seams are joined.
    //
    // Mile 5, closure at 8: three miles ahead is 4.8 km. The mile-marker range
    // in the same sentence stays as the trail has it, which is the exception
    // lib/units.ts exists to keep visible.
    app.onboard({ location_permission_requested: true, unit_system: 'metric' })
    store.set(PLANNED_HIKE_KEY, { startMile: 0, endMile: 30 })

    await renderApp()
    await reportOneFix()

    const banner = await safetyBand()
    expect(banner).toHaveTextContent('4.8 km ahead')
    expect(banner).toHaveTextContent('mi 8.0 – 9.0')
  })

  it('is told nothing about a closure behind them', async () => {
    // Southbound past the same closure. "Ahead" is the entire content of the
    // banner, and getting it backwards would be worse than silence - it would
    // warn about trail already walked while saying nothing about what is
    // coming.
    store.set(PLANNED_HIKE_KEY, { startMile: 30, endMile: 0 })

    await renderApp()
    await reportOneFix()

    expect(noSafetyBand()).toBe(true)
  })
})

describe('a hiker who has not', () => {
  it('gets no closure banner until the GPS works out which way they are going', async () => {
    // The gap this feature closes, asserted rather than described - without
    // it, the test above would pass for the wrong reason.
    await renderApp()
    await reportOneFix()

    expect(noSafetyBand()).toBe(true)
  })

  it('still has a working app, because a hike is optional', async () => {
    await renderApp()
    await reportOneFix()

    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()
  })
})

describe('setting one', () => {
  it('goes from More, and shows up as a summary afterwards', async () => {
    const user = userEvent.setup()
    await renderApp()

    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    await user.click(
      await screen.findByRole('button', { name: /say where you are walking/i }),
    )
    await user.click(
      await screen.findByRole('button', { name: /whole trail, northbound/i }),
    )
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    expect(
      await screen.findByRole('button', { name: /northbound · mi/i }),
    ).toBeInTheDocument()
  })

  it('survives the app being closed, because it is written to the phone', async () => {
    const user = userEvent.setup()
    await renderApp()

    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    await user.click(
      await screen.findByRole('button', { name: /say where you are walking/i }),
    )
    await user.click(
      await screen.findByRole('button', { name: /whole trail, northbound/i }),
    )
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => expect(store.get(PLANNED_HIKE_KEY)).toBeDefined())
    // The end is the trail's own measured length rather than a round number:
    // the shortcut reads `trailIndex.totalMiles`, which is haversine over the
    // real geometry, so 40 vertices a mile apart come to a little over 39.
    const saved = store.get(PLANNED_HIKE_KEY) as { startMile: number; endMile: number }
    expect(saved.startMile).toBe(0)
    expect(saved.endMile).toBeCloseTo(39, 1)
  })

  it('can be cleared back to having none', async () => {
    const user = userEvent.setup()
    store.set(PLANNED_HIKE_KEY, { startMile: 0, endMile: 30 })

    await renderApp()

    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    await user.click(await screen.findByRole('button', { name: /northbound · mi/i }))
    await user.click(await screen.findByRole('button', { name: /clear this hike/i }))

    await waitFor(() => expect(store.has(PLANNED_HIKE_KEY)).toBe(false))
    expect(
      await screen.findByRole('button', { name: /say where you are walking/i }),
    ).toBeInTheDocument()
  })
})
