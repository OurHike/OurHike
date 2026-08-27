import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Today, type TodayProps } from './Today'
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

    await user.click(screen.getByRole('button', { name: 'Choose a download' }))

    expect(onOpenDownloads).toHaveBeenCalled()
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
