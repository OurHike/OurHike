import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { FieldNoteSection, type FieldNoteContext } from './FieldNoteSection'
import type { NoteSummary } from '../lib/fieldNotes'

afterEach(() => {
  cleanup()
})

// The card's conditions section (features/FIELD_NOTES.md, #759). The
// load-bearing behaviours: the tap FILES IMMEDIATELY (one tap, not a form -
// DATA_NUDGES.md's whole design), the day-one wording follows the
// maintainer's #256 decision (water alone says "No recent word"), a failed
// read never wears a staleness claim, and the escalation hands off to the
// real report queue with the place attached.

const NOW = new Date('2026-08-20T12:00:00Z')
const DAY_MS = 24 * 60 * 60 * 1000

function note(overrides: Partial<NoteSummary>): NoteSummary {
  return {
    id: crypto.randomUUID(),
    poi_id: 'osm_water:1',
    lat: 41.2,
    lon: -74.1,
    mile: 1382.4,
    observation: 'dry',
    note: null,
    observed_at: new Date(NOW.getTime() - 3 * DAY_MS).toISOString(),
    reporter_type: 'thru',
    ...overrides,
  }
}

function context(overrides: Partial<FieldNoteContext> = {}): FieldNoteContext {
  return {
    notesFor: () => [],
    reporterType: 'section',
    contributeConditions: false,
    onAddNote: vi.fn(),
    onReportProblem: vi.fn(),
    now: NOW,
    ...overrides,
  }
}

function renderSection(
  ctx: FieldNoteContext,
  poi: Partial<{
    poiId: string
    poiType: string
    lat: number
    lon: number
    mile?: number
  }> = {},
) {
  return render(
    <FieldNoteSection
      poiId={poi.poiId ?? 'osm_water:1'}
      poiType={poi.poiType ?? 'water'}
      lat={poi.lat ?? 41.2}
      lon={poi.lon ?? -74.1}
      {...(poi.mile !== undefined ? { mile: poi.mile } : {})}
      context={ctx}
    />,
  )
}

describe('FieldNoteSection', () => {
  it('renders nothing at all for a type outside the nudge scope', () => {
    renderSection(context(), { poiType: 'viewpoint' })

    expect(screen.queryByTestId('poi-card-conditions')).toBeNull()
  })

  it('says "No recent word" for never-confirmed water, and "Never confirmed" for a shelter', () => {
    // Maintainer decision 2026-08-20 (#256): water alone carries the
    // day-one invite; everything else unconfirmed stays neutral.
    const { unmount } = renderSection(context(), { poiType: 'water' })
    expect(screen.getByText('No recent word')).toBeTruthy()
    unmount()

    renderSection(context(), { poiType: 'shelter', poiId: 'atc_shelters:9' })
    expect(screen.getByText('Never confirmed')).toBeTruthy()
  })

  it('never wears a staleness claim over a failed read - it says it could not check', () => {
    // Null is "we could not ask", not "no one has said" (#249). Printing
    // "No recent word" about our own silence would be the confident wrong
    // answer this app exists to refuse.
    renderSection(context({ notesFor: () => null }))

    expect(screen.getByText('Recent notes unavailable — no signal.')).toBeTruthy()
    expect(screen.queryByText('No recent word')).toBeNull()
    // The ask stays: writing works everywhere, that is the outbox's point.
    expect(screen.getByTestId('poi-card-observe-dry')).toBeTruthy()
  })

  it('prints the dated sentence and the headline once somebody has said', () => {
    renderSection(context({ notesFor: () => [note({})] }))

    expect(screen.getByText(/^Last confirmed in/)).toBeTruthy()
    expect(screen.getByText('Dry — 3 days ago, thru-hiker')).toBeTruthy()
  })

  it('shows BOTH sides of a live disagreement, labelled, never a winner', () => {
    const saysDry = note({
      observed_at: new Date(NOW.getTime() - 1 * DAY_MS).toISOString(),
    })
    const saysFlowing = note({
      observation: 'flowing',
      reporter_type: 'maintainer',
      observed_at: new Date(NOW.getTime() - 2 * DAY_MS).toISOString(),
    })
    renderSection(context({ notesFor: () => [saysFlowing, saysDry] }))

    expect(screen.getByText('Recent notes disagree:')).toBeTruthy()
    expect(screen.getByText('Dry — yesterday, thru-hiker')).toBeTruthy()
    expect(screen.getByText('Flowing — 2 days ago, maintainer')).toBeTruthy()
  })

  it('files the note on the tap itself - one tap, not a form', () => {
    const onAddNote = vi.fn()
    renderSection(context({ onAddNote }), { mile: 1382.4 })

    fireEvent.click(screen.getByTestId('poi-card-observe-dry'))

    expect(onAddNote).toHaveBeenCalledWith({
      poi_id: 'osm_water:1',
      // The place's own coordinates - the card path never waits on GPS.
      lat: 41.2,
      lon: -74.1,
      mile: 1382.4,
      observation: 'dry',
      reporter_type: 'section',
    })
    expect(screen.getByText(/^Noted: dry\./)).toBeTruthy()
  })

  it('signs with the floor when the hiker has not said who they are', () => {
    const onAddNote = vi.fn()
    renderSection(context({ onAddNote, reporterType: null }))

    fireEvent.click(screen.getByTestId('poi-card-observe-flowing'))

    expect(onAddNote.mock.calls[0][0].reporter_type).toBe('day')
  })

  it('shows the longer version only to a hiker who opted in, and sends the words with the tap', () => {
    const onAddNote = vi.fn()
    const { unmount } = renderSection(context({ onAddNote, contributeConditions: true }))

    fireEvent.change(screen.getByTestId('poi-card-note-input'), {
      target: { value: 'Piped source 0.4 mi north still good.' },
    })
    fireEvent.click(screen.getByTestId('poi-card-observe-trickling'))

    expect(onAddNote.mock.calls[0][0].note).toBe('Piped source 0.4 mi north still good.')
    unmount()

    // Passive stays one-tap: no text field at all (DATA_NUDGES.md - the
    // longer version is what opting in consents to).
    renderSection(context())
    expect(screen.queryByTestId('poi-card-note-input')).toBeNull()
  })

  it('offers the report hand-off after a problem-shaped answer, with the place attached', () => {
    const onReportProblem = vi.fn()
    renderSection(context({ onReportProblem }), { mile: 1382.4 })

    fireEvent.click(screen.getByTestId('poi-card-observe-dry'))
    fireEvent.click(screen.getByTestId('poi-card-escalate'))

    // "dry" opens the PICKER (undefined type): no report type is "a dry
    // spring", and pre-picking a wrong one would file a flooding report
    // about the absence of water (lib/fieldNotes.ts).
    expect(onReportProblem).toHaveBeenCalledWith(
      { poiId: 'osm_water:1', lat: 41.2, lon: -74.1, mile: 1382.4 },
      undefined,
    )
  })

  it('routes a damaged shelter straight to the shelter_repair form', () => {
    const onReportProblem = vi.fn()
    renderSection(context({ onReportProblem }), {
      poiType: 'shelter',
      poiId: 'atc_shelters:9',
    })

    fireEvent.click(screen.getByTestId('poi-card-observe-damaged'))
    fireEvent.click(screen.getByTestId('poi-card-escalate'))

    expect(onReportProblem.mock.calls[0][1]).toBe('shelter_repair')
  })

  it('offers no escalation after an answer that is not a problem', () => {
    renderSection(context())

    fireEvent.click(screen.getByTestId('poi-card-observe-flowing'))

    expect(screen.queryByTestId('poi-card-escalate')).toBeNull()
  })

  it('carries the place on the standing "report a problem here" entry too', () => {
    // FIELD_NOTES.md step 1: the poi_id plumbing ran end to end with nothing
    // populating it - this is the affordance that does.
    const onReportProblem = vi.fn()
    renderSection(context({ onReportProblem }))

    fireEvent.click(screen.getByTestId('poi-card-report-here'))

    expect(onReportProblem).toHaveBeenCalledWith({
      poiId: 'osm_water:1',
      lat: 41.2,
      lon: -74.1,
    })
  })

  it('never renders a count of anything', () => {
    // The anti-gamification rule, stated four docs over: no contribution
    // counts, no "N hikers passed". Dates and words only.
    const many = Array.from({ length: 5 }, (_, index) =>
      note({
        id: `note-${index}`,
        observed_at: new Date(NOW.getTime() - index * DAY_MS).toISOString(),
      }),
    )
    const { container } = renderSection(context({ notesFor: () => many }))

    expect(container.textContent).not.toMatch(/\d+ (notes|hikers|people|confirmations)/)
  })
})
