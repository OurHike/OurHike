import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useTappedLinePanel, type TappedLineInput } from './tappedLinePanel'
import { buildTrailIndex } from '../lib/trailPosition'
import { clubTimeline, parseClubSections } from '../lib/clubSections'
import { parseHighlights, NAMED } from '../lib/highlights'
import { STANDARD_PACE } from '../lib/pace'
import type { TappedLine } from '../map/lineTaps'
import type { MergedGraph } from '../lib/trailGraphData'
import { emptyMergedGraph } from '../lib/trailGraphData'
import type { GraphEdge } from '../lib/trailGraph'
import type { ReactElement } from 'react'
import type { LineDetail } from '../lib/lineDetail'

// The climb half is mocked at the fetch rather than at IndexedDB: what is
// under test here is that a TAP is what asks for it, that the answer is
// paired with the graph it was fetched for, and that an undecided answer is
// not recorded as an absence. lib/trailGraphData.ts's own tests own the
// fetching (#1476).
const fetchElevation = vi.hoisted(() => vi.fn())
vi.mock('../lib/trailGraphData', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/trailGraphData')>()),
  fetchTrailGraphElevationCells: fetchElevation,
}))

// #327 moved this feature out of App.tsx whole. One tap asks one question,
// and the answer depends on the zoom and on what was under the finger - that
// precedence is what lived in a nested ternary inside App's `<MapScreen>`
// call and is what these tests are for. The three sheets' own contents belong
// to lib/lineDetail.ts, lib/clubDetail.ts and lib/highlightDetail.ts.

/** Eleven points a mile apart - the shape lib/closureProjection.test.ts
 *  builds and for the reason it gives: `mileOnTrail` snaps to the nearest
 *  vertex, so a two-point line would refuse every tap. */
const MILE_LAT = 1 / 69.05
const TRAIL_INDEX = buildTrailIndex({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline' },
      geometry: {
        type: 'LineString',
        coordinates: Array.from(
          { length: 11 },
          (_, i) => [-77, 39 + i * MILE_LAT] as [number, number],
        ),
      },
    },
  ],
})

const CLUB_SECTIONS = parseClubSections({
  sources: {
    attribution: 'centerline',
    names: 'trail_club_sections',
    miles: 'half_mile_points_from_springer',
  },
  clubs: [
    {
      acronym: 'PATC',
      name: 'Potomac Appalachian Trail Club',
      region: 'MARO',
      stretches: [{ start_mile: 0, end_mile: 20 }],
      miles: 20,
    },
  ],
  unattributed: [],
})

const HIGHLIGHTS = parseHighlights({
  highlights: [
    {
      id: 'mcafee-knob',
      name: 'McAfee Knob',
      bases: [NAMED],
      citations: {
        [NAMED]: { by: 'OurHike', note: 'A ledge.', reviewed: '2026-08-20' },
      },
      legs: [{ trail: 'at', start_mile: 2, end_mile: 4 }],
      club: 'PATC',
    },
  ],
})

/** A tap on the trail two miles up the fixture line. */
const TAP: TappedLine = {
  id: 'at-1',
  source: 'centerline',
  name: 'Appalachian Trail',
  blazeColor: 'White',
  // Null on all three, because this fixture is the corridor's own centerline
  // and the A.T. publishes none of them - #783's nearby-trail facts arrived
  // on `main` while this branch was open, and lib/lineDetail.ts's
  // TappedLineFacts is where the reason each is independently absent lives.
  lengthMiles: null,
  park: null,
  trailStatus: null,
  closureKind: null,
  closureReason: null,
  closureSource: null,
  sharedWith: null,
  badge: false,
  at: [-77, 39 + 2 * MILE_LAT],
}

function panel(overrides: Partial<TappedLineInput> = {}) {
  const onCloseLegend = vi.fn()
  const view = renderHook(
    (props: Partial<TappedLineInput>) =>
      useTappedLinePanel({
        spurs: {},
        pois: [],
        units: 'imperial',
        trailName: 'Appalachian Trail',
        pace: STANDARD_PACE,
        trailSources: {},
        walked: [],
        trailIndex: TRAIL_INDEX,
        belowSeam: false,
        clubSections: CLUB_SECTIONS,
        clubRuns: clubTimeline(CLUB_SECTIONS),
        // No graph and no signal by default: the state every test written
        // before #1476 was in, and the one that must still render the sheet
        // exactly as it did - no climb line, no note about one.
        graphMerged: null,
        online: false,
        highlights: HIGHLIGHTS,
        elevation: null,
        onCloseLegend,
        ...props,
      }),
    { initialProps: overrides },
  )
  return { ...view, onCloseLegend }
}

afterEach(cleanup)

describe('useTappedLinePanel', () => {
  it('shows nothing until something is tapped', () => {
    const { result } = panel()

    expect(result.current.mapScreen.lineSheet).toBeNull()
  })

  it('answers a tap above the seam with the line’s own facts', () => {
    const { result } = panel()

    act(() => result.current.mapScreen.onSelectLine?.(TAP))

    expect(result.current.mapScreen.lineSheet).not.toBeNull()
  })

  it('answers the same tap below the seam with the maintaining club', () => {
    // The whole point of the seam: down here the map is about who looks after
    // the trail, so the club sheet takes the tap and the blaze sheet stands
    // down. Asserted by name because the two sheets are the two answers to
    // one tap and swapping them would be silent otherwise.
    const { result } = panel({ belowSeam: true })

    act(() => result.current.mapScreen.onSelectLine?.(TAP))

    const sheet = result.current.mapScreen.lineSheet as { props: { detail: unknown } }
    expect(sheet.props.detail).toMatchObject({
      heading: 'Potomac Appalachian Trail Club',
    })
  })

  it('lets a tapped mark beat the line under it', () => {
    // A highlight is a small, aimed-at mark sitting ON the corridor, so it
    // wins from either side of the seam - the same rule map/lineTaps.ts
    // applies when a pin beats the line beneath it.
    const { result } = panel({ belowSeam: true })

    act(() => result.current.mapScreen.onSelectLine?.(TAP))
    act(() => result.current.mapScreen.onSelectHighlight?.('mcafee-knob'))

    const sheet = result.current.mapScreen.lineSheet as { props: { detail: unknown } }
    // `heading` rather than a type check: the club sheet's heading is the
    // club's name, so this one assertion says both which sheet won and that
    // it is about the right mark.
    expect(sheet.props.detail).toMatchObject({
      heading: 'McAfee Knob',
      basisLabel: 'On our list',
    })
  })

  it('clears the line when a mark is tapped, so the two can never both stand', () => {
    const { result } = panel()

    act(() => result.current.mapScreen.onSelectLine?.(TAP))
    act(() => result.current.mapScreen.onSelectHighlight?.('mcafee-knob'))
    // Dismissing the mark leaves nothing behind it. Without the clear, the
    // line sheet would reappear over a tap the hiker made two gestures ago.
    act(() => result.current.mapScreen.onSelectHighlight?.(null))

    expect(result.current.mapScreen.lineSheet).toBeNull()
  })

  it('puts the legend away when either tap opens a sheet', () => {
    const { result, onCloseLegend } = panel()

    act(() => result.current.mapScreen.onSelectLine?.(TAP))
    expect(onCloseLegend).toHaveBeenCalledTimes(1)

    act(() => result.current.mapScreen.onSelectHighlight?.('mcafee-knob'))
    expect(onCloseLegend).toHaveBeenCalledTimes(2)
  })

  it('leaves the legend alone on the tap-elsewhere dismissal', () => {
    // The map reports every click, nulls included. A null is a hiker putting
    // the sheet away, and closing the legend on it would shut a sheet they
    // had just opened from the legend itself.
    const { result, onCloseLegend } = panel()

    act(() => result.current.mapScreen.onSelectLine?.(null))
    act(() => result.current.mapScreen.onSelectHighlight?.(null))

    expect(onCloseLegend).not.toHaveBeenCalled()
  })

  it('draws no mark sheet for an id no highlight answers to', () => {
    const { result } = panel()

    act(() => result.current.mapScreen.onSelectHighlight?.('not-a-real-highlight'))

    expect(result.current.mapScreen.lineSheet).toBeNull()
  })
})

describe('the tapped line’s climb (#1476)', () => {
  /** A one-edge graph for the trail the fixture tap is on. */
  function merged(overrides: Partial<GraphEdge> = {}): MergedGraph {
    const edge: GraphEdge = {
      from: 0,
      to: 1,
      length_m: 1609.344,
      trail_id: TAP.id,
      source: 'nynjtc_trails',
      name: 'Ramapo–Dunderberg',
      blaze_color: 'Red',
      ...overrides,
    }
    return {
      ...emptyMergedGraph(),
      graph: { nodes: [], edges: [edge] },
      edgeIds: [0],
    }
  }

  afterEach(() => fetchElevation.mockReset())

  /** The detail the rendered sheet was handed. `lineSheet` is the element
   *  itself, which is what MapScreen takes - so the assertion reads it the
   *  way the screen would rather than reaching past the seam for a copy. */
  function detailOf(sheet: unknown): LineDetail {
    return (sheet as ReactElement<{ detail: LineDetail }>).props.detail
  }

  it('asks for nothing until a line is actually tapped', () => {
    panel({ graphMerged: merged(), online: true })

    // A hiker who never opens a sheet never pays for the climb half.
    expect(fetchElevation).not.toHaveBeenCalled()
  })

  it('prints the climb of the tapped line once the half lands', async () => {
    fetchElevation.mockResolvedValue({ kind: 'loaded', data: [[400, 120]] })
    const { result } = panel({ graphMerged: merged(), online: true })

    await act(async () => {
      result.current.mapScreen.onSelectLine?.(TAP)
    })

    expect(detailOf(result.current.mapScreen.lineSheet).climbLine).toBe(
      '+400 ft / −120 ft',
    )
  })

  it('says nothing about climb where the release published none', async () => {
    // A decided absence: the elevation leg is opt-in, so a release without it
    // is ordinary rather than broken, and the sheet must not invent a state.
    fetchElevation.mockResolvedValue({ kind: 'absent' })
    const { result } = panel({ graphMerged: merged(), online: true })

    await act(async () => {
      result.current.mapScreen.onSelectLine?.(TAP)
    })

    expect(detailOf(result.current.mapScreen.lineSheet).climbLine).toBeNull()
    expect(detailOf(result.current.mapScreen.lineSheet).climbNote).toBeNull()
  })

  it('does not record a refused network as an absence', async () => {
    // #1274's distinction, kept: nothing was learned, so the next tap may
    // ask again rather than the sheet settling on "no figures" forever.
    fetchElevation.mockResolvedValue({ kind: 'undecided' })
    const { result } = panel({ graphMerged: merged(), online: true })

    await act(async () => {
      result.current.mapScreen.onSelectLine?.(TAP)
    })
    await act(async () => {
      result.current.mapScreen.onSelectLine?.(null)
    })
    fetchElevation.mockResolvedValue({ kind: 'loaded', data: [[400, 120]] })
    await act(async () => {
      result.current.mapScreen.onSelectLine?.(TAP)
    })

    expect(detailOf(result.current.mapScreen.lineSheet).climbLine).toBe(
      '+400 ft / −120 ft',
    )
  })

  it('refuses a figure for an edge the DEM never covered', async () => {
    fetchElevation.mockResolvedValue({ kind: 'loaded', data: [null] })
    const { result } = panel({ graphMerged: merged(), online: true })

    await act(async () => {
      result.current.mapScreen.onSelectLine?.(TAP)
    })

    expect(detailOf(result.current.mapScreen.lineSheet).climbLine).toBeNull()
    expect(detailOf(result.current.mapScreen.lineSheet).climbNote).toMatch(/not measured/)
  })
})
