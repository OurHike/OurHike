import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Today, type LongHikeToday, type TodayProps } from './Today'
import { preloadScreens } from './deferred'

// The on-trail conditions rows mount a deferred section (screens/deferred.ts's
// FieldNoteSection), loaded here once so it renders synchronously, the way
// the App harness loads every deferred screen before a test.
beforeAll(() => preloadScreens())
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

  it('prints nothing where the mile would be, when there is no mile', () => {
    // The no-mile sentences are the map plate's. Here they read as filler
    // between the date and the greeting (the maintainer, 2026-09-10, from
    // the frame), so the header is the date and the greeting and nothing
    // else - the status row still says No GPS fix when that is the fault.
    render(<Today {...props({ position: 'Location is off', hasGpsFix: false })} />)

    expect(screen.queryByText('Location is off')).toBeNull()
    expect(screen.getByText('No GPS fix')).toBeInTheDocument()
    expect(screen.getByText(/^Good morning\./)).toBeInTheDocument()
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
  it('lists what is ahead in walking order, as waypoint rows with the miles first', () => {
    render(<Today {...props()} />)

    expect(screen.getByText('AHEAD')).toBeInTheDocument()
    const names = [...document.querySelectorAll('.poi-row__title')].map(
      (name) => name.textContent,
    )
    expect(names).toEqual(['Sartain Spring', 'Bailey Gap Shelter'])
    // Through lib/units.ts (rule R6), never a hand-formatted figure.
    expect(screen.getByText(/^1\.4 mi · /)).toBeInTheDocument()
    expect(screen.getByText(/^8\.4 mi · /)).toBeInTheDocument()
  })

  it('prints the same rows in kilometres when the hiker asked for them', () => {
    render(<Today {...props({ units: 'metric' })} />)

    expect(screen.getByText(/^2\.3 km · /)).toBeInTheDocument()
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

  it('renders honestly with no position at all - no journal, and no sentence about one', () => {
    render(<Today {...props({ currentMile: undefined, position: 'No GPS signal' })} />)

    // The head says what to do next; a line under it saying the journal
    // would fill in from a position nobody has was filler (2026-09-10).
    expect(screen.queryByText(/nothing here claims to know where you are/i)).toBeNull()
    expect(screen.queryByText(/nothing of the journal/i)).toBeNull()
  })

  it('says so when located on a stretch with nothing of the journal’s kinds', () => {
    render(<Today {...props({ currentMile: 100, pois: [] })} />)
    expect(screen.getByText(/nothing of the journal’s kinds/i)).toBeInTheDocument()
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
  it('renders in the two modes that keep it - the deal the tab removal was made on, less one', () => {
    // The deal (#1054) was every mode. The day-hike home gave its card up on
    // the maintainer's read of the frame (2026-09-10): one more section at
    // the foot of a page about today's walk, with More's volunteer row still
    // the day hiker's door. The other two modes hold the deal as it was.
    for (const mode of ['long', 'volunteer'] as const) {
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

  it('keeps the crew card and its two doors off the day-hike home', () => {
    // The maintainer's read of the day-hike frame (2026-09-10): the card and
    // the pair under it were two more sections to get mixed up in, on a page
    // about today's walk. A day hiker reports from the map's press plate or
    // from More; the other two modes keep both, and the outbox line stays
    // everywhere because what is waiting to send is true whatever the day is
    // for.
    const { rerender } = render(
      <Today {...props({ mode: 'day', queuedReportCount: 2 })} />,
    )

    expect(screen.queryByRole('button', { name: 'Report a problem' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Say thanks' })).toBeNull()
    expect(screen.queryByText('The trail crew')).toBeNull()
    expect(screen.getByTestId('today-outbox')).toHaveTextContent('2 waiting to send')

    rerender(<Today {...props({ mode: 'long', queuedReportCount: 2 })} />)
    expect(screen.getByRole('button', { name: 'Report a problem' })).toBeInTheDocument()
    expect(screen.getByText('The trail crew')).toBeInTheDocument()
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
    expect(line).toHaveTextContent('1 waiting to send')
    fireEvent.click(line)
    expect(onOpenVolunteer).toHaveBeenCalled()
  })

  it('pluralises, and says nothing at all when the outbox is empty', () => {
    // No "0 notes waiting to send". An empty outbox is not news, and a line
    // that reports it is a scoreboard for a number that should be zero -
    // which is the anti-gamification rule DATA_NUDGES.md states four times.
    const { rerender } = render(<Today {...props({ queuedReportCount: 2 })} />)
    expect(screen.getByTestId('today-outbox')).toHaveTextContent('2 waiting to send')

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
      expect(screen.getByRole('button', { name: 'All 5 ›' })).toBeInTheDocument()
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
    // The door to the rest sits on the shelf's own label (frame 2a's
    // "All 34 ›"); the pinned bar is the screen's one "Find a hike".
    const all = screen.getByRole('button', { name: 'All 5 ›' })
    expect(screen.queryByRole('button', { name: /find a hike/i })).toBeNull()
    await user.click(all)
    expect(onFindHike).toHaveBeenCalled()
  })

  it('offers no "All" door when the shelf already holds every published route', () => {
    render(
      <Today
        {...props({ suggestedHikes: SUGGESTED.slice(0, 3), onFindHike: vi.fn() })}
      />,
    )
    expect(screen.queryByRole('button', { name: /^All \d+ ›$/ })).toBeNull()
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

  it('prints no provenance note under the row - each card names its publisher', () => {
    render(<Today {...props({ suggestedHikes: SUGGESTED, onFindHike: vi.fn() })} />)

    expect(
      screen.queryByText('Routes from community contributions. Check before traveling.'),
    ).toBeNull()
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

  const walkOn = (
    date: string | null,
    climb?: { gainFt: number; lossFt: number } | null,
  ) =>
    ({
      id: `walk-${date ?? 'undated'}`,
      name: 'Reeves Meadow → Tuxedo',
      date,
      figures: { miles: 6.4, legs: [], ...(climb === undefined ? {} : { climb }) },
      looped: false,
      recorded: 'planned',
      segments: [],
    }) as unknown as TodayProps['dayHikes'][number]

  it('a day hike dated today is the loaded state: its card leads, with the card’s own figures', () => {
    const onOpenDayHike = vi.fn()
    const onWalkDayHike = vi.fn()
    render(
      <Today
        {...props({
          mode: 'day',
          dayHikes: [walkOn('2026-08-26', { gainFt: 780, lossFt: 640 })],
          onOpenDayHike,
          onWalkDayHike,
        })}
      />,
    )

    expect(screen.queryByText('Nothing planned today')).toBeNull()
    const card = screen.getByRole('region', { name: 'Today’s walk' })
    expect(card).toHaveTextContent('Today · day hike')
    expect(card).toHaveTextContent('Reeves Meadow → Tuxedo')
    // Distance, climb both ways, then the time at the standard pace - the
    // card's own line (screens/DayHikeCard.tsx), figure for figure.
    expect(card).toHaveTextContent(
      /6\.4 mi · \+780 ft \/ −640 ft · ≈\d+ ?h ?\d* ?m? walking/,
    )
    // Not also a row in the list below.
    expect(screen.queryByText('Your day hikes')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Open the walk' }))
    expect(onOpenDayHike).toHaveBeenCalledWith('walk-2026-08-26')
    fireEvent.click(screen.getByRole('button', { name: 'Walk this' }))
    expect(onWalkDayHike).toHaveBeenCalledWith('walk-2026-08-26')
  })

  it('prints no time for a walk with no measured climb, and says so', () => {
    render(<Today {...props({ mode: 'day', dayHikes: [walkOn('2026-08-26', null)] })} />)

    const card = screen.getByRole('region', { name: 'Today’s walk' })
    expect(card).toHaveTextContent('6.4 mi · no climb measured, so no time')
    expect(card).not.toHaveTextContent(/walking/)
  })

  it('a planned walk dated another day is not today’s: the setup head stays, and the walk is listed', () => {
    render(<Today {...props({ mode: 'day', dayHikes: [walkOn('2026-08-29')] })} />)

    expect(screen.getByText('Nothing planned today')).toBeInTheDocument()
    expect(screen.getByText('Your day hikes')).toBeInTheDocument()
    expect(screen.getByText('6.4 mi')).toBeInTheDocument()
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

  /** The same walk with a climb somebody measured, which is what makes it
   *  priceable and therefore what makes a time chip honest. */
  const pricedWalk = (name: string) => ({
    ...walk(name),
    climb: { gainFt: 900, lossFt: 900 },
  })

  it('opens the finder with the chip’s facet already on, in day mode only', async () => {
    const onFindHike = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <Today
        {...props({ mode: 'day', suggestedHikes: [pricedWalk('A')], onFindHike })}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Under 2 hours' }))
    expect(onFindHike).toHaveBeenLastCalledWith({ time: 'under2' })
    await user.click(screen.getByRole('button', { name: 'Easy only' }))
    expect(onFindHike).toHaveBeenLastCalledWith({ difficulty: ['easy'] })

    rerender(
      <Today
        {...props({ mode: 'long', suggestedHikes: [pricedWalk('A')], onFindHike })}
      />,
    )
    expect(screen.queryByRole('group', { name: 'Have less time?' })).toBeNull()
  })

  it('withholds a time chip when no published route can be priced, and keeps the difficulty one', () => {
    // THE DEAD CONTROL THIS CLOSES. lib/suggestedHikes.ts makes the rule for
    // the whole feature - a facet no route on the phone can answer is not
    // offered - and `availableFacets` is "the one place that is decided".
    // screens/FindHike.tsx asked it; this shelf rendered its two time chips
    // unconditionally, so on a release where nothing carries a measured climb
    // (which is every release so far - checked 2026-09-11 against 2026-09-10,
    // where none of the nine published routes has one) "Under 2 hours" opened
    // the finder on "0 hikes" for every hiker who tapped it.
    const onFindHike = vi.fn()
    render(<Today {...props({ mode: 'day', suggestedHikes: [walk('A')], onFindHike })} />)

    expect(screen.queryByRole('button', { name: 'Under 2 hours' })).toBeNull()
    expect(screen.queryByRole('button', { name: '2 \u2013 4 hours' })).toBeNull()
    // And the one chip that still has something behind it stays, because
    // withholding the row wholesale would be the opposite mistake.
    expect(screen.getByRole('button', { name: 'Easy only' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Have less time?' })).toBeInTheDocument()
  })

  it('drops the whole row when neither a time nor a difficulty chip can be honest', () => {
    const onFindHike = vi.fn()
    const { climb: _climb, difficulty: _difficulty, ...unrated } = pricedWalk('A')
    render(
      <Today
        {...props({
          mode: 'day',
          suggestedHikes: [{ ...unrated, difficulty: null }],
          onFindHike,
        })}
      />,
    )

    expect(screen.queryByRole('group', { name: 'Have less time?' })).toBeNull()
    expect(screen.queryByText('Have less time?')).toBeNull()
  })
})

// --- On-trail conditions (#1373, frames 2c and 2d) ---------------------------

describe('On-trail conditions for the hiker’s own stops (#1373, F2)', () => {
  const noteContext = () => ({
    notesFor: () => null,
    reporterType: null,
    contributeConditions: false,
    disputeFor: () => null,
    onAddNote: vi.fn(),
    onReportProblem: vi.fn(),
    onSayThanks: vi.fn(),
    now: MORNING,
  })
  const stopFacts = (poiId: string) =>
    poiId === 's1'
      ? { type: 'shelter', lat: 39.3, lon: -77.1, mile: 720.8, unverified: false }
      : null
  const walk = () =>
    ({
      id: 'walk-today',
      name: 'Reeves Meadow → Tuxedo',
      date: '2026-08-26',
      figures: { miles: 6.4, legs: [] },
      stops: [
        { poiId: 's1', type: 'shelter', name: 'Bailey Gap Shelter' },
        { poiId: 'gone', type: 'campsite', name: 'A retired campsite' },
      ],
      looped: false,
      recorded: 'planned',
      segments: [],
    }) as unknown as TodayProps['dayHikes'][number]

  it('asks the card’s own one-tap question for each of today’s stops, and files the tap through the same context', async () => {
    const context = noteContext()
    const user = userEvent.setup()
    render(
      <Today
        {...props({ mode: 'day', dayHikes: [walk()], noteContext: context, stopFacts })}
      />,
    )

    expect(screen.getByText('On-trail conditions')).toBeInTheDocument()
    expect(screen.getByText('your stops today')).toBeInTheDocument()
    const rows = document.querySelectorAll('.today__condition')
    // The retired campsite draws nothing rather than a row with nothing to tap.
    expect(rows).toHaveLength(1)
    expect(rows[0]).toHaveTextContent('Bailey Gap Shelter')
    expect(rows[0]).toHaveTextContent('your stop · mi 720.8')

    // The peek's own controls (chrome/FieldNoteSection.tsx): the good end
    // of the shelter scale, filed as the card would file it.
    await user.click(screen.getByTestId('poi-card-observe-fine'))
    expect(context.onAddNote).toHaveBeenCalledWith(
      expect.objectContaining({ poi_id: 's1', observation: 'fine' }),
      undefined,
    )
  })

  it('on a long hike, asks about the last nights’ sites in the frame’s own order', () => {
    render(
      <Today
        {...props({
          mode: 'long',
          longHike: {
            name: 'Springer → Katahdin',
            figures: '214 mi walked · 1,983 mi to go',
            dayNumber: 14,
            awayLine: null,
            resume: null,
            day: null,
            nights: [
              { label: 'Tonight', poiId: 's1', name: 'Bailey Gap Shelter', mile: 720.8 },
              {
                label: 'Last night',
                poiId: 'gone',
                name: 'Somewhere retired',
                mile: 700,
              },
            ],
          } as unknown as LongHikeToday,
          noteContext: noteContext(),
          stopFacts,
        })}
      />,
    )

    expect(screen.getByText('last 2 days')).toBeInTheDocument()
    expect(screen.getByText('Tonight · mi 720.8')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-observe-fine')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-observe-problem')).toBeInTheDocument()
  })

  it('renders no section without the context to file through', () => {
    render(<Today {...props({ mode: 'day', dayHikes: [walk()], stopFacts })} />)

    expect(screen.queryByText('On-trail conditions')).toBeNull()
  })
})

describe('a walk left open (#1373, frame 6d)', () => {
  const OPEN = {
    hike: {
      id: 'walk-1',
      name: 'Pine Meadow out and back',
      date: null,
      segments: [],
      figures: { miles: 6.4, legs: [] },
      looped: false,
      recorded: 'planned' as const,
      note: '',
    },
    day: '2026-08-25',
  }

  it('asks the morning after, with both answers and no default', async () => {
    const user = userEvent.setup()
    const onFinishOpenWalk = vi.fn()
    const onDropOpenWalk = vi.fn()
    render(
      <Today
        {...props({ mode: 'day', openWalk: OPEN, onFinishOpenWalk, onDropOpenWalk })}
      />,
    )

    const card = screen.getByRole('region', { name: 'A walk is still open' })
    // MORNING is 2026-08-26: the day before is yesterday, and the title says so.
    expect(card).toHaveTextContent('Yesterday’s walk is still open')
    expect(card).toHaveTextContent('Pine Meadow out and back · 6.4 mi')
    expect(card).toHaveTextContent(/nothing changes on its own/)

    await user.click(within(card).getByRole('button', { name: 'Finished it' }))
    expect(onFinishOpenWalk).toHaveBeenCalledWith('walk-1', '2026-08-25')
    await user.click(within(card).getByRole('button', { name: 'Not this time' }))
    expect(onDropOpenWalk).toHaveBeenCalledOnce()
  })

  it('says which day when it was longer ago, and asks nothing with nothing open', () => {
    render(
      <Today
        {...props({
          mode: 'day',
          openWalk: { ...OPEN, day: '2026-08-20' },
          onFinishOpenWalk: vi.fn(),
          onDropOpenWalk: vi.fn(),
        })}
      />,
    )
    expect(
      screen.getByRole('region', { name: 'A walk is still open' }),
    ).toHaveTextContent('A walk is still open')
    expect(screen.queryByText('Yesterday’s walk is still open')).toBeNull()

    cleanup()
    render(<Today {...props({ mode: 'day' })} />)
    expect(screen.queryByRole('region', { name: 'A walk is still open' })).toBeNull()
  })
})
