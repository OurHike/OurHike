// The long hike as a set of WINDOWS rather than takeovers (#1329), and the
// map door inside set-up that could not reach a map until they were.
//
// #1317 shipped nine long-hike surfaces in two arrangements - three sheets
// docked to the bottom edge, five screens in App's `flowScreen` chain - and
// a maintainer using it on a desktop found both: a sheet at the foot of a
// 1440px browser, and "having them full screen makes it hard for me to
// remember where I am". `flowScreen` is also what made "Choose on the map"
// impossible: it hides the map subtree and makes it inert, so the door had
// nothing behind it and was wired to close the picker and do nothing.
//
// The SHAPE of the window at each width is desktop.css's and is held by
// test/desktopLayout.test.ts, which can see a stylesheet. What is held here
// is what jsdom can see: that every surface goes through one chrome, that
// the map is inert underneath it and reachable while a point is being
// placed, and that a tap lands as a point on the hike.

import { afterEach, describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, latOfMile, openMapTab } from './test/appHarness'
import { MockMap } from './test/mocks/maplibre-gl'
import { TRIPS_KEY, type TripStore } from './lib/trips'
import { HIKER_MODE_KEY } from './lib/hikerMode'
import { BLAZE_DOTTED_LAYER_ID } from './map/style'

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

const app = appHarness({ navigator: { onLine: false }, objectUrls: true })

/**
 * PUT `matchMedia` BACK, and this is not housekeeping.
 *
 * `onADesktop()` below uses `vi.stubGlobal`, which persists past the test
 * that called it - this project does not set `unstubGlobals`, so the stub
 * outlives the file and reaches whatever the worker runs next. It did:
 * App.loadBudget.test.tsx's "reads the waypoints once when the steps release
 * them" passed alone and failed in the full run, because a leaked desktop
 * makes `mapNeededNow` true from launch (`isDesktop` alone satisfies it) and
 * the launch reads waypoints it would not otherwise read.
 *
 * App.test.tsx has had this line since it started stubbing the viewport. It
 * was missed here, which is how the leak got out - the whole failure mode
 * CLAUDE.md's "run ordering-dependent tests several times before pushing"
 * exists to catch, caught by `scripts/test.sh` rather than by CI, which is
 * where it is cheapest.
 */
afterEach(() => {
  vi.unstubAllGlobals()
})

/** Shelters on the synthetic centerline, with the pipeline's own mile 0.2
 *  above the client index's - App.plan.test.tsx's fixture and its reason:
 *  the anchor correction has to be visible end to end (HIKE_PLANNING.md
 *  Finding 1). */
function shelter(clientMile: number, name: string) {
  return {
    id: `s${clientMile}`,
    type: 'shelter',
    name,
    lat: latOfMile(clientMile),
    lon: -77,
    confidence: 'high',
    mile: clientMile + 0.2,
  }
}

const POIS = [
  shelter(3, 'Front Shelter'),
  shelter(10, 'Middle Shelter'),
  shelter(22, 'Beyond Shelter'),
]

function hikeStore(over: Partial<TripStore> = {}): TripStore {
  return {
    trips: [],
    openId: null,
    groups: [],
    hikes: [
      {
        id: 'hike-1',
        name: 'Springer → Katahdin',
        type: 'thru',
        trailId: 'AT',
        status: 'walking',
        points: [
          { poiId: 's3', name: 'Front Shelter', mile: 3.2 },
          { poiId: 's22', name: 'Beyond Shelter', mile: 22.2 },
        ],
        tripIds: [],
      },
    ],
    activeHikeId: 'hike-1',
    ...over,
  }
}

const windows = () => document.querySelectorAll('.hike-window')

/**
 * A viewport wide enough for the desktop layout (lib/useDesktop.ts).
 *
 * App.test.tsx's helper, and its reason: matched on the query rather than
 * answering `true` to everything, because this shell asks `matchMedia`
 * several other questions - standalone, fine pointer - and a stub that says
 * yes to all of them is testing a browser that does not exist.
 *
 * WITHOUT THIS A TEST IS A PHONE, which is the default every other case in
 * this file deliberately runs as.
 */
function onADesktop() {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: query.includes('min-width: 900px'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  )
}

describe('every long-hike surface goes through one window', () => {
  it('opens the pick sheet in the window chrome, not welded to the screen', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('radio', { name: 'Long hike' }))
    expect(
      await screen.findByRole('dialog', { name: 'Which long hike?' }),
    ).toBeInTheDocument()

    const dock = windows()
    expect(dock).toHaveLength(1)
    expect(dock[0]?.className).toContain('hike-window--sheet')
  })

  it('opens set-up in the same chrome rather than as a screen of its own', async () => {
    // Set-up was a `flowScreen` - the arrangement that replaces the screen
    // and unmounts the map. Whether the map behind is INERT is asserted in
    // the map-door test below, where there is a map to assert it about: a
    // launch that stays on Today builds none, deliberately (the entry
    // budget), so there is nothing to be inert here.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('radio', { name: 'Long hike' }))
    await user.click(await screen.findByRole('button', { name: /A new long hike/ }))

    const setUp = windows()
    expect(setUp).toHaveLength(1)
    expect(setUp[0]?.className).toContain('hike-window--screen')
    expect(screen.getByRole('heading', { name: 'A new long hike' })).toBeInTheDocument()
    // The sheet that opened it is gone rather than waiting underneath: one
    // window at a time, so closing set-up does not land on a second modal.
    expect(screen.queryByRole('dialog', { name: 'Which long hike?' })).toBeNull()
  })
})

describe('choosing a hike point on the map (#1329)', () => {
  it('arms a real tap, refuses off-trail out loud, and places the point', async () => {
    // The door was wired to `() => setHikePointAt(null)`: it closed the
    // picker and placed nothing, because a `flowScreen` had unmounted the
    // map it was offering.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('radio', { name: 'Long hike' }))
    await user.click(await screen.findByRole('button', { name: /A new long hike/ }))
    await user.click(
      await screen.findByRole('button', { name: /Add a point on the way/ }),
    )

    const picker = await screen.findByRole('dialog', { name: 'Choose a stop' })
    await user.click(within(picker).getByRole('button', { name: 'Choose on the map' }))

    // The bar is up, and the window has stood aside rather than closed - the
    // draft it holds is not something one tap may cost somebody.
    expect(
      await screen.findByText('Tap the trail where this stop goes.'),
    ).toBeInTheDocument()
    expect(document.querySelector('.hike-window--stood-aside')).not.toBeNull()
    // ...and the map is reachable again, because it is what the hiker is
    // aiming at.
    expect(document.querySelector('.map-screen')?.closest('[inert]')).toBeNull()

    await waitFor(() => {
      expect(MockMap.live).toHaveLength(1)
      expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
    })
    const map = MockMap.live[0]

    // Four degrees west of the centerline, far past the 3-mile gate.
    // Refused where the finger landed, and the bar stays open.
    await act(async () => {
      map.emit('click', { lngLat: { lng: -81, lat: latOfMile(10) } })
    })
    expect(await screen.findByText(/no honest mile/)).toBeInTheDocument()

    // An on-trail tap at client mile 10 lands on Middle Shelter, whose
    // PIPELINE mile is 10.2 - the anchor correction, carried end to end.
    await act(async () => {
      map.emit('click', { lngLat: { lng: -77, lat: latOfMile(10) } })
    })
    const back = await screen.findByRole('heading', { name: 'A new long hike' })
    expect(back).toBeInTheDocument()
    expect(document.querySelector('.hike-window--stood-aside')).toBeNull()
    expect(screen.getByText('Middle Shelter')).toBeInTheDocument()
    expect(screen.getByText(/mi 10\.2/)).toBeInTheDocument()
    // ...and the map goes back behind the modal it came out from.
    expect(document.querySelector('.map-screen')?.closest('[inert]')).not.toBeNull()
  })
})

describe('renaming the hike, through the real shell (#1344)', () => {
  it('names the hike while making it, which is where a hiker looks first', async () => {
    // THE REPORT THIS SECOND PASS CAME FROM: "I can't edit the name of the
    // hike." The first pass put a rename on the Plan room and nowhere else -
    // an 11px link on a screen you have to already be in - while set-up,
    // where a hiker is literally making the thing, printed
    // "A new long hike" as a heading and offered no field at all.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('radio', { name: 'Long hike' }))
    await user.click(await screen.findByRole('button', { name: /A new long hike/ }))

    const field = await screen.findByLabelText('Its name')
    expect(field).toHaveValue('A new long hike')
    await user.clear(field)
    await user.type(field, 'Georgia, a bit at a time')

    // The band above the field is showing it, which is the whole reason the
    // field is here rather than behind a "rename".
    expect(
      screen.getByRole('heading', { level: 1, name: 'Georgia, a bit at a time' }),
    ).toBeInTheDocument()

    // And it survives a trip into the stop picker and back, like the points.
    await user.click(screen.getByRole('button', { name: /Add a point on the way/ }))
    const picker = await screen.findByRole('dialog', { name: 'Choose a stop' })
    await user.type(within(picker).getByLabelText('Search for a stop'), 'front')
    await user.click(
      await within(
        await screen.findByRole('dialog', { name: 'Choose a stop' }),
      ).findByRole('button', { name: /Front Shelter/ }),
    )

    expect(await screen.findByLabelText('Its name')).toHaveValue(
      'Georgia, a bit at a time',
    )
  })

  it('types a new name and keeps it', async () => {
    // THE TEST THAT WAS MISSING. PlanHome.test.tsx renames against a mocked
    // `onRenameHike`, which proves the button calls something and nothing
    // about whether the store ever hears it.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: /Rename/ }))

    const field = await screen.findByLabelText('New name for Springer → Katahdin')
    await user.clear(field)
    await user.type(field, 'Georgia to Maine')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    // On screen...
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Georgia to Maine' }),
    ).toBeInTheDocument()
    // ...and in the store, which is the half a mocked handler cannot show.
    await waitFor(() => {
      const store = app.store.get(TRIPS_KEY) as TripStore
      expect(store.hikes[0]?.name).toBe('Georgia to Maine')
    })
  })
})

describe('a section moves both ways (#1367)', () => {
  const withSection = () =>
    hikeStore({
      trips: [
        {
          id: 'trip-1',
          name: 'Damascus → Atkins',
          plan: {
            target: { miles: 12 },
            stops: [
              { mile: 3.2, resupply: false },
              { mile: 22.2, resupply: false },
            ],
            days: [{ id: 'd1', pinned: false, generated: true }],
          },
        },
      ],
    })

  it('takes a section out of the hike without touching the section', async () => {
    // `unassignTrip` has been in the store since #788 with no caller, so the
    // only way out was "Forget this hike", which ungroups EVERY section in
    // it - a sledgehammer for a one-row mistake.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, {
      ...withSection(),
      hikes: [{ ...withSection().hikes[0], tripIds: ['trip-1'] }],
    })
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    expect(await screen.findByText('Sections in this hike')).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: /Take Damascus/ }))

    await waitFor(() => {
      const store = app.store.get(TRIPS_KEY) as TripStore
      expect(store.hikes[0]?.tripIds).toEqual([])
      // THE HALF THAT MATTERS: ungrouping is not deleting.
      expect(store.trips).toHaveLength(1)
      expect(store.trips[0]?.name).toBe('Damascus → Atkins')
    })
    expect(await screen.findByText('Your other sections')).toBeInTheDocument()
  })

  it('puts one back, which is what makes the two shelves a control', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, withSection())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: /Add Damascus/ }))

    await waitFor(() => {
      const store = app.store.get(TRIPS_KEY) as TripStore
      expect(store.hikes[0]?.tripIds).toEqual(['trip-1'])
    })
  })
})

describe('the Map tab names the hike and can change it (#1367)', () => {
  it('puts the hike on the plate and the switch beside it', async () => {
    // Every other screen had a door; this was the one that did not, because
    // the plate is read-only (chrome/Header.tsx) and nobody had looked at
    // the actions row next to it.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Map' }))
    await waitFor(() => {
      expect(document.querySelector('.map-plate__eyebrow')?.textContent).toBe(
        'Springer → Katahdin',
      )
    })

    await user.click(await screen.findByRole('button', { name: /Change which hike/ }))
    expect(
      await screen.findByRole('dialog', { name: 'Which hike are you on?' }),
    ).toBeInTheDocument()
  })

  it('leaves the plate naming the trail when there is no hike', async () => {
    // The eyebrow is not a hike slot - it answers "what am I looking at",
    // and off a long hike the trail is still that answer.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Map' }))
    await waitFor(() => {
      expect(document.querySelector('.map-plate__eyebrow')?.textContent).toMatch(
        /Appalachian Trail/,
      )
    })
    expect(screen.queryByRole('button', { name: /Change which hike/ })).toBeNull()
  })
})

describe('the switch is on every screen (#1344)', () => {
  it('carries the hike in the sidebar, whichever tab is up', async () => {
    // `Switch hike ›` lived on the Plan band and nowhere else, so a hiker on
    // Today, the map or Settings had no way to change hike. The sidebar is
    // already on all four and already holds the mode, so it is where the
    // same question one level down belongs.
    //
    // THE SIDEBAR IS A DESKTOP THING, so this case says so. jsdom leaves
    // `matchMedia` answering false, which is a phone - the default the rest
    // of this file runs as, and the layout with no sidebar to put this in.
    const user = userEvent.setup()
    onADesktop()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    for (const tab of ['Today', 'Map', 'Plan', 'More'] as const) {
      await user.click(await screen.findByRole('tab', { name: tab }))
      const chip = await waitFor(() => {
        const found = document.querySelector('.tab-bar__hike')
        expect(found, `no hike switch on ${tab}`).not.toBeNull()
        return found as HTMLElement
      })
      expect(chip).toHaveTextContent('Springer → Katahdin')
    }

    await user.click(document.querySelector('.tab-bar__hike') as HTMLElement)
    expect(
      await screen.findByRole('dialog', { name: 'Which hike are you on?' }),
    ).toBeInTheDocument()
  })

  it('shows no hike chip when the app is not on a hike', async () => {
    const user = userEvent.setup()
    onADesktop()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    expect(document.querySelector('.tab-bar__hike')).toBeNull()
  })
})

describe('planning a section without leaving the room (#1344)', () => {
  it('names two ends in place, lays out the days there, and puts it on the hike', async () => {
    // "Plan the next section should be 'Plan a section', and that content
    // should live on the same page." The route builder used to take the Map
    // tab outright (`sweepForBuilder` opens with `setActiveTab('map')`).
    //
    // This also closes the gap #1329's body named and left open: nothing put
    // a PLANNED section into a hike, so one laid out from this very room
    // landed nowhere near it.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: 'Plan a section' }))

    // Still on Plan - the whole point. The panel is in the column, and the
    // Plan tab is still the selected one.
    expect(await screen.findByRole('button', { name: /From/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Plan' })).toHaveAttribute(
      'aria-selected',
      'true',
    )

    for (const [end, place] of [
      ['From', 'Front Shelter'],
      ['To', 'Beyond Shelter'],
    ] as const) {
      // Anchored, and not "Today": the phone's bar now carries a "Today I’m…"
      // read-out (#1373, lib/navigator.ts), and an unanchored /To/ matched
      // it too. The field's own name runs its two spans together
      // ("ToChoose a place ›"), so a word boundary would miss it.
      await user.click(screen.getByRole('button', { name: new RegExp(`^${end}(?!day)`) }))
      const picker = await screen.findByRole('dialog', { name: 'Choose a stop' })
      await user.type(within(picker).getByLabelText('Search for a stop'), place)
      await user.click(
        await within(
          await screen.findByRole('dialog', { name: 'Choose a stop' }),
        ).findByRole('button', { name: new RegExp(place) }),
      )
    }

    // Both ends named, so the SAME slot becomes the target sheet - the form
    // that already turns two ends into a plan (planDaysVia + buildPlan).
    await user.click(await screen.findByRole('button', { name: /^Lay out \d+ days?$/ }))

    // Kept AND on the hike.
    await waitFor(() => {
      const store = app.store.get(TRIPS_KEY) as TripStore
      expect(store.trips).toHaveLength(1)
      expect(store.hikes[0]?.tripIds).toEqual([store.trips[0].id])
    })
    expect(await screen.findByText('Sections in this hike')).toBeInTheDocument()
  })

  it('hands the map job to the route builder rather than doing it here', async () => {
    // Tapping the trail is the one part that genuinely needs a canvas, so
    // the door is explicit and goes to the builder that owns it - never a
    // second route builder on the Plan page.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: 'Plan a section' }))
    await user.click(
      await screen.findByRole('button', { name: 'Draw it on the map instead' }),
    )

    expect(
      await screen.findByRole('dialog', { name: 'Plan a route' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Map' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })
})

describe('the hike a hiker is on, in Plan (#1329)', () => {
  it('names the hike in the band and offers the way onto another', async () => {
    // "When I save a long hike, it is not displaying anywhere." Half of that
    // report was this: the Plan tab's band read "Sections" and the room
    // showed a generic list, so nothing said which hike.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Springer → Katahdin' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Switch hike/ }))
    // Named for what it is doing: the dialog's label and its heading are one
    // string, so the sheet announces itself as the switch it is rather than
    // as the first pick it was written for.
    expect(
      await screen.findByRole('dialog', { name: 'Which hike are you on?' }),
    ).toBeInTheDocument()
  })

  it('closing the switch keeps the hike, rather than reverting to Day hike', async () => {
    // The handoff's deliberate exception is about the sheet's FIRST job.
    // Reverting a hiker who looked at their other hike and decided to stay
    // would be the app punishing them for looking.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: /Switch hike/ }))
    await user.click(await screen.findByRole('button', { name: 'Close' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Springer → Katahdin' }),
    ).toBeInTheDocument()
    expect(windows()).toHaveLength(0)
  })
})

describe('the hike a hiker is on is what the map takes (#1352)', () => {
  /** The dotted side's filter, as map/nearbyTrails.ts builds it: the
   *  negation of a membership test, so an EMPTY membership dots every line
   *  and a non-empty one dots everything outside it. */
  async function dottedFilter(): Promise<string> {
    await openMapTab()
    await waitFor(() => expect(MockMap.live.length).toBe(1))
    const style = MockMap.live[0].options.style as {
      layers: Array<{ id: string; filter?: unknown }>
    }
    return JSON.stringify(
      style.layers.find((layer) => layer.id === BLAZE_DOTTED_LAYER_ID)?.filter,
    )
  }

  it('draws the A.T. solid when the active hike is on it, with no preference to set', async () => {
    // The whole point of the merge: nothing wrote `chosen_trail_id` here.
    // The hike says AT, so the map is about the A.T. - one state, read in
    // two places, rather than two states that can disagree.
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    expect(await dottedFilter()).toContain('centerline')
  })

  it('takes nothing when the active hike is on a trail this build has no lines for', async () => {
    // THE HONEST-DEGRADE PATH, and the reason Part 1 could be shipped before
    // Part 2. `chosenSystemSources()` answers an empty list for every trail
    // but the A.T. (map/nearbyTrails.ts), so a hike on the Long Path leaves
    // the map in its all-dotted state rather than picking a system it cannot
    // stand behind. No crash, no wrong trail drawn solid - the same shape as
    // first launch, which is the truthful one until #1307's successor
    // publishes a second trail's sources.
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(
      TRIPS_KEY,
      hikeStore({ hikes: [{ ...hikeStore().hikes[0], trailId: 'LP' }] }),
    )
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    expect(await dottedFilter()).toContain('"literal",[]')
  })
})
