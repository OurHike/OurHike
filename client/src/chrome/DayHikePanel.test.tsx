// Tests for chrome/DayHikePanel.tsx - the builder's rail and top panel
// (#1194).
//
// The claims worth pinning are the ones a redesign could quietly break, and
// two of them are about what the panel must NOT say:
//
//   IT DRAWS NO ELEVATION PROFILE. The samples that would draw one are not
//   published for network trails (pipeline/export_network_elevation.py), so a
//   silhouette here would be a picture of ground nobody measured. The panel
//   says so where the chart would have been, and this asserts the saying.
//
//   IT NEVER PRICES A DETOUR. A stop's distance off the walk is shown; the
//   minutes to get there are not invented.
//
// And one about what it must not CONTAIN: the action buttons stayed on
// chrome/DayHikePickBar.tsx at the foot of the canvas. That was the
// instruction, and the reason is thumb reach on a trail.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { DayHikePanel } from './DayHikePanel'
import type { DraftStatus, DayHikeDraft } from '../lib/dayHikeDraft'
import type { DayHikeStop } from '../lib/dayHikeStops'
import type { GraphPoint, RouteLeg } from '../lib/trailGraph'

// This repository's convention rather than a global: chrome/DayHikePickBar.tsx's
// suite does the same, and without it one render's DOM is still mounted under
// the next test's queries.
afterEach(() => {
  cleanup()
})

function leg(name: string, miles: number): RouteLeg {
  return {
    name,
    source: 'oprhp_trails',
    blaze_color: 'blue',
    trail_id: `oprhp_trails:${name}`,
    miles,
  }
}

function tap(): GraphPoint {
  return {
    edgeIndex: 0,
    fraction: 0.5,
    at: { lon: -74.1, lat: 41.25 },
    offNetworkFeet: 0,
  }
}

const DRAFT: DayHikeDraft = {
  segments: [[tap(), tap(), tap()]],
  refusal: null,
  looped: false,
  droppedMiles: 0,
}

const ROUTED: DraftStatus = {
  kind: 'routed',
  stretches: [],
  miles: 3.6,
  legs: [leg('Pine Meadow Trail', 1.4), leg('Seven Hills Trail', 2.2)],
  legsBySource: [{ source: 'oprhp_trails', legs: 2 }],
  climb: { gainFt: 1180, lossFt: 940 },
  gapMiles: 0,
}

const SHELTER: DayHikeStop = {
  poiId: 'tom-jones',
  type: 'shelter',
  name: 'Tom Jones Shelter',
  lat: 41.25,
  lon: -74.1,
  mile: 1.4,
  offCourseFeet: 220,
}

/** A shelter a long way up a spur - the case the panel says out loud. */
const FAR_SHELTER: DayHikeStop = { ...SHELTER, poiId: 'far', offCourseFeet: 3200 }

function panel(overrides: Partial<Parameters<typeof DayHikePanel>[0]> = {}) {
  const props = {
    draft: DRAFT,
    status: ROUTED,
    stops: [] as readonly DayHikeStop[],
    units: 'imperial' as const,
    walking: { minutes: 135, text: '≈2h 15m', relativeLine: null },
    hiddenLabels: {},
    onToggleLabel: vi.fn(),
    onRemoveStop: vi.fn(),
    onRemoveTurn: vi.fn(),
    detailsOpen: true,
    onToggleDetails: vi.fn(),
    ...overrides,
  }
  render(<DayHikePanel {...props} />)
  return props
}

describe('what the panel says about the walk', () => {
  it('prints the distance, the climb and the walking time', () => {
    panel()

    expect(screen.getByText('3.6 mi')).toBeInTheDocument()
    expect(screen.getByText('1,180 ft')).toBeInTheDocument()
    expect(screen.getByText('≈2h 15m')).toBeInTheDocument()
  })

  it('names the route from the trails it uses, never a guessed destination', () => {
    panel()

    expect(
      screen.getByRole('heading', { name: 'Pine Meadow Trail to Seven Hills Trail' }),
    ).toBeInTheDocument()
  })

  it('summarises the legs and the stops, omitting a clause at zero', () => {
    panel({ stops: [SHELTER] })

    expect(screen.getByText('2 legs · 1 shelter')).toBeInTheDocument()
  })

  it('says the climb is unknown rather than printing a zero', () => {
    // A walk crossing an edge nobody measured. `ascentFt: 0` would be a
    // flat-ground claim on real ground.
    panel({ status: { ...ROUTED, climb: null }, walking: null })

    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.queryByText('0 ft')).not.toBeInTheDocument()
  })
})

describe('the elevation slot', () => {
  it('says a profile is not drawn here, and claims nothing about the data', () => {
    // THE CLAIM THAT WAS WRONG, pinned so it cannot come back. This line used
    // to read "these trails publish how much they climb, not the shape of it"
    // - false on the day it was written: export_network_profile.py publishes
    // trail_graph_profile.json, and lib/walkProfile.ts already reads it
    // (#1119, closing #1045). A panel may say what IT does not draw; it may
    // not say what the pipeline does not publish, because that is a claim
    // about the bucket and this screen cannot see the bucket.
    panel()

    expect(screen.getByText('No profile drawn here yet.')).toBeInTheDocument()
    expect(screen.queryByText(/not the shape of it/i)).toBeNull()
    expect(screen.queryByText(/publish/i)).toBeNull()
  })

  it('prints the gain and the loss, which ARE published', () => {
    panel()

    // Matched with their arrows: the gain also appears in the stats row
    // above, and a bare /1,180 ft/ would find both and fail on the ambiguity
    // rather than on the claim.
    expect(screen.getByText('\u2191 1,180 ft')).toBeInTheDocument()
    expect(screen.getByText('\u2193 940 ft')).toBeInTheDocument()
  })
})

describe('the route order', () => {
  it('numbers the legs and gives each a cumulative mile range', () => {
    panel()

    expect(screen.getByText('01')).toBeInTheDocument()
    expect(screen.getByText('02')).toBeInTheDocument()
    expect(screen.getByText(/mile 1.4–3.6/)).toBeInTheDocument()
  })

  it('folds a stop in where the walk reaches it', () => {
    panel({ stops: [SHELTER] })

    expect(screen.getByText('Tom Jones Shelter')).toBeInTheDocument()
    expect(screen.getByText(/Shelter · mile 1.4/)).toBeInTheDocument()
  })

  it('says when a stop is a long way off the walk, and prices no detour', () => {
    panel({ stops: [FAR_SHELTER] })

    expect(screen.getByText(/off the walk/)).toBeInTheDocument()
    // The stopping figure counts stops, never distance - one stop is one
    // stop's worth of minutes however far off the line it sits.
    expect(screen.getByText(/Stops add about 15 min/)).toBeInTheDocument()
  })

  it('prints the capacity and the water distance a stop was chosen on', () => {
    // #1198. The whole point: a hiker comparing two shelters reads both rows
    // at once rather than opening and closing two cards.
    panel({ stops: [{ ...SHELTER, capacity: 8, waterDistanceFt: 350 }] })

    expect(screen.getByText(/sleeps 8/)).toBeInTheDocument()
    expect(screen.getByText(/water 350 ft/)).toBeInTheDocument()
  })

  it('omits each figure where nobody published it, and never prints a zero', () => {
    // Absent capacity is not "sleeps 0" and absent water is not "water 0 ft",
    // which would be the app inventing about the thing being decided.
    panel({ stops: [SHELTER] })

    expect(screen.queryByText(/sleeps/)).toBeNull()
    expect(screen.queryByText(/water/)).toBeNull()
  })

  it('floors a stated water distance so it never reads as zero', () => {
    // lib/units.ts's MIN_STATED_FEET, the same floor chrome/PoiCard.tsx
    // applies to the same published column - one home since #1198.
    panel({ stops: [{ ...SHELTER, waterDistanceFt: 0 }] })

    expect(screen.queryByText(/water 0 ft/)).toBeNull()
    expect(screen.getByText(/water 3 ft/)).toBeInTheDocument()
  })

  it('says how far off the walk a stop is without pricing the detour', () => {
    panel({ stops: [{ ...FAR_SHELTER, capacity: 6 }] })

    expect(screen.getByText(/off the walk/)).toBeInTheDocument()
    expect(screen.getByText(/sleeps 6/)).toBeInTheDocument()
    // One stop is one stop's worth of minutes, however far off the line.
    expect(screen.getByText(/Stops add about 15 min/)).toBeInTheDocument()
  })

  it('removes a stop when its × is pressed', async () => {
    const props = panel({ stops: [SHELTER] })

    await userEvent.click(screen.getByRole('button', { name: /Remove Tom Jones/ }))

    expect(props.onRemoveStop).toHaveBeenCalledWith('tom-jones')
  })

  it('offers no delete on a leg, which nobody chose', () => {
    // lib/dayHikeRows.ts's argument: a leg is what the router made of two
    // taps, so "delete this leg" has no defined effect. A control that looked
    // pressable and did nothing would be worse than its absence.
    panel()
    const legRow = screen.getByText('Pine Meadow Trail').closest('li')

    expect(legRow).not.toBeNull()
    expect(within(legRow as HTMLElement).queryByRole('button')).toBeNull()
  })

  it('invites the first tap when there is nothing yet', () => {
    panel({ status: { kind: 'empty' }, walking: null })

    expect(
      screen.getByText(/Tap a trail on the map to start walking it/),
    ).toBeInTheDocument()
  })
})

describe('the taps', () => {
  it('lists one removable mark per tap, numbered as the map numbers them', () => {
    panel()

    expect(screen.getByRole('button', { name: /Remove tap 2/ })).toBeInTheDocument()
  })

  it('removes the tap by its ordinal, not its label', async () => {
    const props = panel()

    await userEvent.click(screen.getByRole('button', { name: /Remove tap 2/ }))

    // Label 2 is ordinal 1 - `removeTap` indexes draftPoints.
    expect(props.onRemoveTurn).toHaveBeenCalledWith(1)
  })
})

describe('the label toggles', () => {
  it('shows every class as pressed by default, because absent means on', () => {
    panel()

    expect(screen.getByRole('button', { name: /Parking/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('reads as off for a class the hiker switched off', () => {
    panel({ hiddenLabels: { roads: true } })

    expect(screen.getByRole('button', { name: /Roads/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('toggles by key', async () => {
    const props = panel()

    await userEvent.click(screen.getByRole('button', { name: /Shelters/ }))

    expect(props.onToggleLabel).toHaveBeenCalledWith('shelters')
  })

  it('stays reachable while the details are shut', async () => {
    // The one place this panel departs from the handoff's phone frame, and
    // deliberately: the label row is how a hiker finds what to tap next, so
    // it has to work in the state the redesign puts them in by default - map
    // at its tallest, details closed.
    panel({ detailsOpen: false })

    expect(screen.getByRole('button', { name: /Parking/ })).toBeInTheDocument()
  })
})

describe('what the panel is not', () => {
  it('holds none of the builder’s actions - those stay at the bottom', () => {
    // The instruction behind #1194: information at the top, buttons within
    // thumb reach. Undo, Close the loop, Draw instead, Done and Cancel all
    // live on chrome/DayHikePickBar.tsx, and a redesign that quietly moved
    // one up here would cost a hiker the one-handed use the bar exists for.
    panel()

    for (const label of ['Undo', 'Cancel', 'Done', 'Close the loop', 'Draw instead']) {
      expect(screen.queryByRole('button', { name: label })).toBeNull()
    }
  })

  it('scores nothing and compares nothing', () => {
    // Plan.test.tsx's standing negative assertion, carried onto a new
    // surface: no "behind", no "ahead", no verdict on the hiker.
    panel({ stops: [SHELTER] })

    for (const word of [/behind/i, /ahead/i, /on track/i, /difficulty/i, /score/i]) {
      expect(screen.queryByText(word)).toBeNull()
    }
  })

  it('prints no arrival clock, only a walking duration', () => {
    panel()

    expect(screen.queryByText(/back by/i)).toBeNull()
    expect(screen.queryByText(/finish at/i)).toBeNull()
  })
})

describe('the details toggle', () => {
  it('hides the body when shut, and says so to a screen reader', () => {
    panel({ detailsOpen: false })
    const toggle = screen.getByRole('button', { name: 'Details' })

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Pine Meadow Trail')).not.toBeVisible()
  })

  it('calls back when pressed', async () => {
    const props = panel({ detailsOpen: false })

    await userEvent.click(screen.getByRole('button', { name: 'Details' }))

    expect(props.onToggleDetails).toHaveBeenCalled()
  })
})
