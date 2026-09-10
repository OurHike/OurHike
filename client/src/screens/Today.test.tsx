import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Today, type LongHikeToday, type TodayProps } from './Today'
import { STANDARD_PACE } from '../lib/pace'

// The Today screen's honesty contract, asserted where it renders: the mode
// switch never collapses, "AHEAD" is only claimed with a direction, the
// greeting never reads as an arrival clock, the closure entry carries a next
// step, and nothing on the screen counts or scores anybody.

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const MORNING = new Date(2026, 7, 26, 7, 12)

const POIS = [
  { id: 'w1', name: 'Sartain Spring', type: 'water', mile: 713.8 },
  { id: 's1', name: 'Bailey Gap Shelter', type: 'shelter', mile: 720.8 },
]

/** Ten miles of profile around the fix, so the greeting's estimate is
 *  computable the honest way - from measured ascent. */
const SAMPLES = Array.from({ length: 11 }, (_, i) => ({
  mile: 712 + i,
  elevationFt: 2100 + i * 100,
}))

function props(overrides: Partial<TodayProps> = {}): TodayProps {
  return {
    now: MORNING,
    position: 'mi 712.4 · NOBO',
    online: false,
    hasGpsFix: true,
    lastSyncedAt: new Date(2026, 7, 23),
    mode: 'long',
    onChangeMode: vi.fn(),
    pois: POIS,
    currentMile: 712.4,
    direction: 'NOBO',
    onOpenPoi: vi.fn(),
    onShowOnMap: vi.fn(),
    elevation: {
      samples: SAMPLES,
      currentMile: 712.4,
      source: 'ahead',
      axis: 'trail',
      domain: { startMile: 712, endMile: 722 },
    },
    units: 'imperial',
    pace: STANDARD_PACE,
    opportunities: [],
    opportunitiesAsOf: MORNING,
    onOpenVolunteer: vi.fn(),
    passedPlaces: [],
    queuedReportCount: 0,
    onStartReport: vi.fn(),
    onSayThanks: vi.fn(),
    dayHikes: [],
    onOpenDayHike: vi.fn(),
    hasDownload: true,
    ...overrides,
  }
}

describe('the pine header', () => {
  it('splits the located position into the big mile and its unit', () => {
    render(<Today {...props()} />)

    expect(screen.getByText('712.4')).toBeInTheDocument()
    expect(screen.getByText('mi · NOBO')).toBeInTheDocument()
  })

  it('prints the no-position states as the sentences they are', () => {
    render(<Today {...props({ position: 'Location is off' })} />)

    expect(screen.getByText('Location is off')).toBeInTheDocument()
  })

  it('carries the status flags, same wording as the map screen', () => {
    render(<Today {...props({ online: false, hasGpsFix: false })} />)

    expect(screen.getByText('Offline')).toBeInTheDocument()
    expect(screen.getByText('No GPS fix')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders all three mode segments, always', () => {
    render(<Today {...props()} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
  })

  it('reports a mode change', async () => {
    const onChangeMode = vi.fn()
    const user = userEvent.setup()
    render(<Today {...props({ onChangeMode })} />)

    await user.click(screen.getByRole('radio', { name: 'Volunteer' }))

    expect(onChangeMode).toHaveBeenCalledWith('volunteer')
  })

  it('greets with the next shelter and a duration, never an arrival clock', () => {
    render(<Today {...props()} />)

    const greeting = screen.getByText(/Bailey Gap Shelter is 8\.4 miles ahead/)
    expect(greeting.textContent).toMatch(/≈/)
    expect(greeting.textContent).not.toMatch(/\d{1,2}:\d{2}/)
  })

  it('says the distance alone when the ascent is not measurable', () => {
    // No profile window means no time - pricing unmeasured climbs at zero
    // would understate the walk.
    render(<Today {...props({ elevation: undefined })} />)

    const greeting = screen.getByText(/Bailey Gap Shelter is 8\.4 miles ahead/)
    expect(greeting.textContent).not.toMatch(/≈/)
  })
})

describe('the journal column', () => {
  it('lists what is ahead in walking order, with the miles in the gutter', () => {
    render(<Today {...props()} />)

    expect(screen.getByText('AHEAD')).toBeInTheDocument()
    const names = [...document.querySelectorAll('.today__entry-name')].map(
      (name) => name.textContent,
    )
    expect(names).toEqual(['Sartain Spring', 'Bailey Gap Shelter'])
    expect(screen.getByText('1.4')).toBeInTheDocument()
    expect(screen.getByText('8.4')).toBeInTheDocument()
  })

  it('says NEARBY, not AHEAD, while the direction is unsettled', () => {
    render(<Today {...props({ direction: undefined })} />)

    expect(screen.getByText('NEARBY')).toBeInTheDocument()
    expect(screen.queryByText('AHEAD')).not.toBeInTheDocument()
  })

  it('opens an entry the way a search result opens - on the map', async () => {
    const onOpenPoi = vi.fn()
    const user = userEvent.setup()
    render(<Today {...props({ onOpenPoi })} />)

    await user.click(screen.getByRole('button', { name: /sartain spring/i }))

    expect(onOpenPoi).toHaveBeenCalledWith('w1')
  })

  it('lets the staleness words ride only where the pixels do', () => {
    render(
      <Today
        {...props({
          stalenessFor: (id) =>
            id === 'w1'
              ? {
                  treatment: {
                    ring: 'faint-invite',
                    opacity: 1,
                    borderStyle: 'solid',
                  },
                  words: 'No recent word',
                }
              : {
                  treatment: { ring: 'none', opacity: 1, borderStyle: 'solid' },
                  words: 'Never confirmed',
                },
        })}
      />,
    )

    expect(screen.getAllByText(/No recent word/).length).toBeGreaterThan(0)
    // The shelter's neutral state stays quiet rather than reading "Never
    // confirmed" down the column (WIREFRAMES.md §11's channel rule).
    expect(screen.queryByText(/Never confirmed/)).not.toBeInTheDocument()
  })

  it('renders honestly with no position at all', () => {
    render(<Today {...props({ currentMile: undefined, position: 'No GPS signal' })} />)

    expect(
      screen.getByText(/nothing here claims to know where you are/i),
    ).toBeInTheDocument()
  })

  it('carries the closure sentence and its next step', async () => {
    const onShowOnMap = vi.fn()
    const user = userEvent.setup()
    render(
      <Today
        {...props({
          closureAhead: 'Trail closed 2.1 mi ahead — storm damage — mi 714.5 – 715.5',
          onShowOnMap,
        })}
      />,
    )

    expect(screen.getByText(/trail closed 2\.1 mi ahead/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'See it on the map' }))
    expect(onShowOnMap).toHaveBeenCalled()
  })
})

describe('the volunteer card', () => {
  it('renders in every mode - that is the deal the tab removal was made on', () => {
    for (const mode of ['day', 'long', 'volunteer'] as const) {
      const { unmount } = render(<Today {...props({ mode })} />)
      expect(
        screen.getByText('Volunteer', { selector: '.today__volunteer-eyebrow' }),
      ).toBeInTheDocument()
      unmount()
    }
  })

  it('leads the column in volunteer mode', () => {
    render(<Today {...props({ mode: 'volunteer' })} />)

    const paper = document.querySelector('.today__paper')!
    const sections = [...paper.querySelectorAll('.today__section')]
    const volunteerAt = sections.findIndex(
      (section) => section.querySelector('.today__card--volunteer') !== null,
    )
    const journalAt = sections.findIndex(
      (section) => section.textContent?.includes('Sartain Spring') ?? false,
    )
    expect(volunteerAt).toBeGreaterThanOrEqual(0)
    expect(volunteerAt).toBeLessThan(journalAt)
  })

  it('says "could not check" differently from "no club has asked"', () => {
    const { unmount } = render(<Today {...props({ opportunities: null })} />)
    expect(screen.getByText(/needs signal/i)).toBeInTheDocument()
    unmount()

    render(<Today {...props({ opportunities: [] })} />)
    expect(screen.getByText(/no workdays are posted/i)).toBeInTheDocument()
  })

  it('never counts, scores, or compares', () => {
    const { container } = render(<Today {...props()} />)

    expect(container.textContent).not.toMatch(
      /\d+ (places|of \d+|answered|skipped|left)/i,
    )
  })
})

describe('the rest of the column', () => {
  it('offers the download as a starting point when nothing is on the phone', async () => {
    const onOpenDownloads = vi.fn()
    const user = userEvent.setup()
    render(<Today {...props({ hasDownload: false, onOpenDownloads })} />)

    await user.click(screen.getByRole('button', { name: 'Download' }))

    expect(onOpenDownloads).toHaveBeenCalled()
  })

  it('says what the sheet weighs on the notice when the manifest has said, and only what still works when it has not', () => {
    const { rerender } = render(
      <Today
        {...props({
          hasDownload: false,
          onOpenDownloads: vi.fn(),
          downloadSize: '458.4 MB',
        })}
      />,
    )
    expect(screen.getByText('The topo sheet is not on this phone')).toBeInTheDocument()
    expect(
      screen.getByText('458.4 MB. Trails and waypoints work without it.'),
    ).toBeInTheDocument()

    rerender(<Today {...props({ hasDownload: false, onOpenDownloads: vi.fn() })} />)
    expect(screen.getByText('Trails and waypoints work without it.')).toBeInTheDocument()
    expect(screen.queryByText(/MB/)).toBeNull()
  })

  it('surfaces saved day hikes first in day mode', () => {
    render(
      <Today
        {...props({
          mode: 'day',
          dayHikes: [
            {
              id: 'h1',
              name: 'Reeves Meadow loop',
              date: null,
              segments: [[]],
              figures: { miles: 3.4, legs: [] },
              looped: true,
              recorded: 'planned',
              note: '',
            },
          ],
        })}
      />,
    )

    const paper = document.querySelector('.today__paper')!
    const sections = [...paper.querySelectorAll('.today__section')]
    const hikesAt = sections.findIndex(
      (section) => section.textContent?.includes('Reeves Meadow loop') ?? false,
    )
    const journalAt = sections.findIndex(
      (section) => section.textContent?.includes('Sartain Spring') ?? false,
    )
    expect(hikesAt).toBeGreaterThanOrEqual(0)
    expect(hikesAt).toBeLessThan(journalAt)
  })

  it('offers both halves of the crew relationship, at equal weight', async () => {
    // THIS USED TO BE ONE BUTTON (#1133), reading "Note something for the
    // crew", and saying thanks was the seventh row inside the problem picker
    // under a list of hazards. Reporting a problem and thanking a maintainer
    // are two sides of the same relationship - the volunteer card is directly
    // above this row - and burying one under the other was costing it.
    const onStartReport = vi.fn()
    const onSayThanks = vi.fn()
    const user = userEvent.setup()
    render(<Today {...props({ onStartReport, onSayThanks })} />)

    await user.click(screen.getByRole('button', { name: 'Report a problem' }))
    expect(onStartReport).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Say thanks' }))
    expect(onSayThanks).toHaveBeenCalled()
  })

  it('gives the two buttons the same width to share', () => {
    // The design handoff's own implementation note asked for this to be
    // CHECKED rather than assumed: `flex: 1` did nothing in its prototype,
    // because the Button copy there swallowed the style prop, and the two came
    // out 176px against 129px. This app's Button spreads `style` last, so it
    // lands - and this is the assertion that says so, because jsdom does no
    // layout and a rendered-width check is not available here.
    //
    // Equal weight is the design intent; equal WIDTH is how a row of two
    // solid fills actually delivers it.
    render(<Today {...props()} />)

    for (const name of ['Report a problem', 'Say thanks']) {
      expect(screen.getByRole('button', { name })).toHaveStyle({ flex: '1' })
    }
  })

  it('says what is waiting, and gives it somewhere to go', () => {
    // The line existed before and was a paragraph: it said something a hiker
    // might want to act on, with nowhere to act. It now opens the volunteer
    // page, which is where a queued report is already surfaced and retried -
    // rather than a second destination, which would be a second answer to
    // "where are my reports".
    const onOpenVolunteer = vi.fn()
    render(<Today {...props({ queuedReportCount: 1, onOpenVolunteer })} />)

    const line = screen.getByTestId('today-outbox')
    expect(line).toHaveTextContent('1 note waiting to send')
    fireEvent.click(line)
    expect(onOpenVolunteer).toHaveBeenCalled()
  })

  it('pluralises, and says nothing at all when the outbox is empty', () => {
    // No "0 notes waiting to send". An empty outbox is not news, and a line
    // that reports it is a scoreboard for a number that should be zero -
    // which is the anti-gamification rule DATA_NUDGES.md states four times.
    const { rerender } = render(<Today {...props({ queuedReportCount: 2 })} />)
    expect(screen.getByTestId('today-outbox')).toHaveTextContent(
      '2 notes waiting to send',
    )

    rerender(<Today {...props({ queuedReportCount: 0 })} />)
    expect(screen.queryByTestId('today-outbox')).toBeNull()
  })

  it('keeps the offline promise on screen', () => {
    render(<Today {...props()} />)

    expect(screen.getByText('Everything here works with no signal.')).toBeInTheDocument()
  })
})

describe('the suggested hikes (#1284)', () => {
  const NJ = { lon: -74.6, lat: 41.2 }
  const suggestion = (id: string, overrides: Record<string, unknown> = {}) => ({
    id,
    name: id,
    miles: 6.2,
    climb: { gainFt: 980, lossFt: 980 },
    difficulty: 'moderate' as const,
    author: { kind: 'club' as const, name: 'NY-NJ Trail Conference' },
    segments: [
      [
        { coord: [NJ.lon, NJ.lat] as [number, number], poiId: null },
        { coord: [NJ.lon + 0.01, NJ.lat] as [number, number], poiId: null },
      ],
    ],
    ...overrides,
  })
  const SUGGESTED = [
    suggestion('Sunrise Mtn loop', {
      transit: { line: 'NJT 197', toStop: 'Culvers Gap', walkMiles: 0.3, source: 'NJT' },
    }),
    suggestion('Angels Rest', {
      difficulty: 'strenuous',
      author: { kind: 'guidebook', name: 'L. Adkins' },
    }),
    suggestion('Pochuck boardwalk', { difficulty: 'easy' }),
    suggestion('Terrace Pond circular'),
    suggestion('Wapiti to Docs Knob', { climb: null }),
  ]

  it('renders in every mode - mode re-ranks, it never hides', () => {
    for (const mode of ['day', 'long', 'volunteer'] as const) {
      const { unmount } = render(
        <Today {...props({ mode, suggestedHikes: SUGGESTED, onFindHike: vi.fn() })} />,
      )
      expect(screen.getByText('Suggested hikes')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /find a hike/i })).toBeInTheDocument()
      unmount()
    }
  })

  it('leads the column in day mode, and sits last in the other two', () => {
    const at = (mode: 'day' | 'long' | 'volunteer') => {
      const { unmount } = render(
        <Today {...props({ mode, suggestedHikes: SUGGESTED, onFindHike: vi.fn() })} />,
      )
      const sections = [
        ...document.querySelectorAll('.today__paper .today__section'),
      ].filter((section) => section.childElementCount > 0)
      const index = sections.findIndex(
        (section) => section.querySelector('.today__suggested-rail') !== null,
      )
      const journal = sections.findIndex(
        (section) => section.textContent?.includes('Sartain Spring') ?? false,
      )
      unmount()
      return { index, journal, last: sections.length - 1 }
    }
    expect(at('day').index).toBeLessThan(at('day').journal)
    expect(at('long').index).toBe(at('long').last)
    expect(at('volunteer').index).toBe(at('volunteer').last)
  })

  it('renders no rule and no gap when there is nothing to suggest', () => {
    render(<Today {...props({ suggestedHikes: [], onFindHike: vi.fn() })} />)

    expect(screen.queryByText('Suggested hikes')).not.toBeInTheDocument()
    expect(document.querySelector('.today__suggested-rail')).toBeNull()
    // The slot is there and empty, which .today__section:empty collapses.
    expect(screen.queryByRole('button', { name: /find a hike/i })).not.toBeInTheDocument()
  })

  it('shows three on the shelf and counts the rest on the way to them', async () => {
    const onFindHike = vi.fn()
    const user = userEvent.setup()
    render(<Today {...props({ suggestedHikes: SUGGESTED, onFindHike })} />)

    expect(document.querySelectorAll('.today__suggested-card')).toHaveLength(3)
    const find = screen.getByRole('button', { name: /find a hike/i })
    expect(find).toHaveTextContent('2 more ›')
    await user.click(find)
    expect(onFindHike).toHaveBeenCalled()
  })

  it('prints a walking duration from the cached climb, and no time without one', () => {
    render(
      <Today
        {...props({
          suggestedHikes: [SUGGESTED[0], SUGGESTED[4]],
          onFindHike: vi.fn(),
        })}
      />,
    )

    expect(screen.getByText('6.2 mi · ≈2h 30m')).toBeInTheDocument()
    expect(screen.getByText('6.2 mi · no time — climb unmeasured')).toBeInTheDocument()
    // A duration, never an arrival clock - the status strip's own clock is
    // outside the rail, which is why the check is scoped to it.
    const rail = document.querySelector('.today__suggested-rail')!
    expect(rail.textContent).not.toMatch(/\d{1,2}:\d{2}/)
  })

  it('marks transit only where it was published, and names who wrote each route', () => {
    render(
      <Today
        {...props({ suggestedHikes: SUGGESTED.slice(0, 2), onFindHike: vi.fn() })}
      />,
    )

    expect(
      screen.getAllByRole('img', { name: 'Reachable by public transport' }),
    ).toHaveLength(1)
    expect(screen.getByText(/NJT 197 → Culvers Gap/)).toBeInTheDocument()
    expect(screen.getByText('NY-NJ Trail Conference')).toBeInTheDocument()
    expect(screen.getByText('Guidebook route · L. Adkins')).toBeInTheDocument()
    expect(screen.getByText('Strenuous')).toBeInTheDocument()
  })

  it('renders the cards as things to read until there is a detail to open', () => {
    // Wireframe 1g is not designed; a card that looked pressable and went
    // nowhere would be a dead control.
    render(
      <Today
        {...props({ suggestedHikes: SUGGESTED.slice(0, 1), onFindHike: vi.fn() })}
      />,
    )

    expect(screen.queryByRole('button', { name: /sunrise mtn loop/i })).toBeNull()
    expect(screen.getByRole('article', { name: 'Sunrise Mtn loop' })).toBeInTheDocument()
  })

  it('keeps the provenance note under the row', () => {
    render(<Today {...props({ suggestedHikes: SUGGESTED, onFindHike: vi.fn() })} />)

    expect(
      screen.getByText('Routes from community contributions. Check before traveling.'),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// The long hike leading Today (#1317).

const LONG_HIKE: LongHikeToday = {
  name: 'Springer → Katahdin',
  figures: '412.0 mi walked · 1,785.4 mi to go',
  dayNumber: 6,
  awayLine: null,
  resume: null,
  day: {
    title: 'Pine Swamp Branch → Bailey Gap',
    planned: '11.2 mi planned',
    resupply: 'Resupply: Pearisburg, 31.6 mi on',
    last: false,
    onOpen: vi.fn(),
    onTakeZero: vi.fn(),
    onSeeOnMap: vi.fn(),
  },
}

describe('the long hike leading Today', () => {
  it('puts the hike’s name and its two figures under the readout', () => {
    render(<Today {...props({ mode: 'long', longHike: LONG_HIKE })} />)

    expect(screen.getByText('Springer → Katahdin')).toBeInTheDocument()
    expect(screen.getByText('412.0 mi walked · 1,785.4 mi to go')).toBeInTheDocument()
  })

  it('makes the name the door to a different hike, when there is one', async () => {
    // #1344: the hiker reading their hike's name on the morning screen is the
    // one most likely to want a different hike, and the only door was the
    // Plan tab's band.
    const user = userEvent.setup()
    const onSwitch = vi.fn()
    render(<Today {...props({ mode: 'long', longHike: { ...LONG_HIKE, onSwitch } })} />)

    await user.click(screen.getByRole('button', { name: /Springer → Katahdin/ }))
    expect(onSwitch).toHaveBeenCalled()
  })

  it('leaves the name as text where there is nowhere to switch to', () => {
    // LineSheet's rule: never a control that looks pressable and is not.
    render(<Today {...props({ mode: 'long', longHike: LONG_HIKE })} />)

    expect(screen.getByText('Springer → Katahdin')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Springer → Katahdin/ })).toBeNull()
  })

  it('adds the day of the hike to the date eyebrow', () => {
    render(<Today {...props({ mode: 'long', longHike: LONG_HIKE })} />)
    expect(document.querySelector('.today__eyebrow')?.textContent).toMatch(/· DAY 6$/)
  })

  it('says the date alone when nothing in the hike is dated', () => {
    // A day number nothing supports would be worse than no day number.
    render(
      <Today {...props({ mode: 'long', longHike: { ...LONG_HIKE, dayNumber: null } })} />,
    )
    expect(document.querySelector('.today__eyebrow')?.textContent).not.toMatch(/DAY/)
  })

  it('leads the paper column with the hike’s day, and still renders the alerts', () => {
    // Mode re-ranks; nothing disappears (lib/hikerMode.ts).
    render(
      <Today
        {...props({
          mode: 'long',
          longHike: LONG_HIKE,
          closureAhead: 'A closure 3 mi ahead',
        })}
      />,
    )

    const sections = [
      ...document.querySelectorAll('.today__paper .today__section'),
    ].filter((section) => section.childElementCount > 0)
    const card = sections.findIndex(
      (section) => section.querySelector('.today__card--hike') !== null,
    )

    expect(card).toBe(0)
    expect(screen.getByText('A closure 3 mi ahead')).toBeInTheDocument()
  })

  it('renders no hike card in the other two modes', () => {
    for (const mode of ['day', 'volunteer'] as const) {
      const { unmount } = render(<Today {...props({ mode, longHike: LONG_HIKE })} />)
      expect(document.querySelector('.today__card--hike')).toBeNull()
      unmount()
    }
  })

  it('renders no hike card when nothing is planned for today', () => {
    // Planning as you walk is the ordinary way to walk a long trail, so this
    // is not a degraded state and nothing nags about it.
    render(<Today {...props({ mode: 'long', longHike: { ...LONG_HIKE, day: null } })} />)

    expect(document.querySelector('.today__card--hike')).toBeNull()
    expect(screen.getByText('Springer → Katahdin')).toBeInTheDocument()
  })

  it('changes tone DOWN on the last of it - no countdown, no bar, no confetti', () => {
    const { container } = render(
      <Today
        {...props({
          mode: 'long',
          longHike: {
            ...LONG_HIKE,
            day: { ...LONG_HIKE.day!, last: true },
          },
        })}
      />,
    )

    expect(screen.getByText('The last of it')).toBeInTheDocument()
    expect(screen.getByText(/Nothing here counts down for you/)).toBeInTheDocument()
    expect(container.querySelector('progress')).toBeNull()
    expect(container.textContent).not.toMatch(/%|to go until|congratulations/i)
  })

  it('prints no percentage, nothing behind and nothing on track', () => {
    const { container } = render(
      <Today {...props({ mode: 'long', longHike: LONG_HIKE })} />,
    )
    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })
})

// --- The setup screens and the pinned bar (#1373, F2) ---------------------------

describe('Today before anything is loaded (#1373, F2)', () => {
  const NJ = { lon: -74.6, lat: 41.2 }
  const walk = (name: string) => ({
    id: name,
    name,
    miles: 4.2,
    difficulty: 'easy' as const,
    author: { kind: 'club' as const, name: 'NY-NJ Trail Conference' },
    segments: [
      [
        { coord: [NJ.lon, NJ.lat] as [number, number], poiId: null },
        { coord: [NJ.lon + 0.01, NJ.lat] as [number, number], poiId: null },
      ],
    ],
  })

  it('day mode with nothing planned leads with the setup head, ranked from the kept place', () => {
    render(
      <Today
        {...props({
          mode: 'day',
          suggestedHikes: [walk('Pine Meadow Lake loop')],
          near: NJ,
          placeName: 'Harriman State Park',
          onFindHike: vi.fn(),
          onPlanHike: vi.fn(),
        })}
      />,
    )

    const sections = [
      ...document.querySelectorAll('.today__paper .today__section'),
    ].filter((section) => section.childElementCount > 0)
    expect(sections[0]).toHaveTextContent('Nothing planned today')
    expect(sections[0]).toHaveTextContent(
      'Published walks, nearest Harriman State Park first, and a builder if none of them is yours.',
    )
    expect(screen.getByText('Hikes near you')).toBeInTheDocument()
  })

  it('says "nearest you" from a fix, "to pick from" with neither, and names the builder alone with nothing published', () => {
    const { rerender } = render(
      <Today
        {...props({
          mode: 'day',
          suggestedHikes: [walk('A')],
          near: NJ,
          onFindHike: vi.fn(),
        })}
      />,
    )
    expect(screen.getByText(/nearest you first/)).toBeInTheDocument()

    rerender(
      <Today
        {...props({ mode: 'day', suggestedHikes: [walk('A')], onFindHike: vi.fn() })}
      />,
    )
    expect(screen.getByText(/Published walks to pick from/)).toBeInTheDocument()
    expect(screen.getByText('Suggested hikes')).toBeInTheDocument()

    rerender(<Today {...props({ mode: 'day', suggestedHikes: [] })} />)
    expect(screen.getByText(/A builder for a route of your own/)).toBeInTheDocument()
  })

  it('a planned day hike is the loaded state: no setup head', () => {
    render(
      <Today
        {...props({
          mode: 'day',
          dayHikes: [
            {
              id: 'd1',
              name: 'Reeves Meadow → Tuxedo',
              figures: { miles: 6.4 },
            } as unknown as TodayProps['dayHikes'][number],
          ],
        })}
      />,
    )

    expect(screen.queryByText('Nothing planned today')).toBeNull()
  })

  it('long mode with no hike says what a long hike is and offers the map, then the way back to day mode', async () => {
    const onStartLongHike = vi.fn()
    const user = userEvent.setup()
    render(<Today {...props({ mode: 'long', longHike: null, onStartLongHike })} />)

    expect(
      screen.getByRole('heading', { name: 'You have no hike yet' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/A long hike is one trail, broken into days\. Pick the trail/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Pick a trail on the map ›' }))
    expect(onStartLongHike).toHaveBeenCalled()
    expect(
      screen.getByText(/Switch to Day hike above — nothing here is lost/),
    ).toBeInTheDocument()
  })

  it('carries the pinned bar on every state, emphasising Plan only while nothing is loaded', () => {
    const onFindHike = vi.fn()
    const onPlanHike = vi.fn()
    const { rerender } = render(
      <Today {...props({ mode: 'day', onFindHike, onPlanHike })} />,
    )

    const bar = screen.getByRole('group', { name: 'Find or plan a hike' })
    expect(bar.querySelector('.pinned-bar__button--primary')).toHaveTextContent(
      'Plan a hike',
    )

    fireEvent.click(screen.getByRole('button', { name: 'Plan a hike' }))
    expect(onPlanHike).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Find a hike' }))
    expect(onFindHike).toHaveBeenCalledWith()

    rerender(<Today {...props({ mode: 'volunteer', onFindHike, onPlanHike })} />)
    expect(
      screen
        .getByRole('group', { name: 'Find or plan a hike' })
        .querySelector('.pinned-bar__button--primary'),
    ).toBeNull()
    expect(
      screen.getByText(
        /Walking today as well\? Find and Plan are where they always are\./,
      ),
    ).toBeInTheDocument()
  })

  it('renders no bar outside the shell, where there is nowhere for either door to go', () => {
    render(<Today {...props({ mode: 'day' })} />)

    expect(screen.queryByRole('group', { name: 'Find or plan a hike' })).toBeNull()
  })

  it('opens the finder with the chip’s facet already on, in day mode only', async () => {
    const onFindHike = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <Today {...props({ mode: 'day', suggestedHikes: [walk('A')], onFindHike })} />,
    )

    await user.click(screen.getByRole('button', { name: 'Under 2 hours' }))
    expect(onFindHike).toHaveBeenLastCalledWith({ time: 'under2' })
    await user.click(screen.getByRole('button', { name: 'Easy only' }))
    expect(onFindHike).toHaveBeenLastCalledWith({ difficulty: ['easy'] })

    rerender(
      <Today {...props({ mode: 'long', suggestedHikes: [walk('A')], onFindHike })} />,
    )
    expect(screen.queryByRole('group', { name: 'Have less time?' })).toBeNull()
  })
})
