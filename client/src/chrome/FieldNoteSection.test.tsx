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
    // No dispute by default (#876), so every case written before disputes
    // existed reads exactly as it did.
    disputeFor: () => null,
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
    /** `confidence: low` upstream - changes only the dispute wording (#876). */
    unverified: boolean
    /** Which of the card's two heights (#941). Defaults to the opened card,
     *  which is what every test written before the peek existed asserts. */
    variant: 'peek' | 'open'
  }> = {},
) {
  return render(
    <FieldNoteSection
      poiId={poi.poiId ?? 'osm_water:1'}
      poiType={poi.poiType ?? 'water'}
      unverified={poi.unverified ?? false}
      lat={poi.lat ?? 41.2}
      lon={poi.lon ?? -74.1}
      {...(poi.mile !== undefined ? { mile: poi.mile } : {})}
      {...(poi.variant !== undefined ? { variant: poi.variant } : {})}
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

    // The second argument is the photo, `undefined` when nobody attached one
    // (#879) - asserted explicitly rather than left to a loose matcher, so a
    // note that silently started carrying bytes would fail here.
    expect(onAddNote).toHaveBeenCalledWith(
      {
        poi_id: 'osm_water:1',
        // The place's own coordinates - the card path never waits on GPS.
        lat: 41.2,
        lon: -74.1,
        mile: 1382.4,
        observation: 'dry',
        reporter_type: 'section',
      },
      undefined,
    )
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

// --- The photo the opt-in promises (#879) ---------------------------------
//
// Maintainer decision, 2026-08-21: publish-now, screened on device. What
// these cases hold is the part that could go wrong quietly - the tap must
// not start waiting on a model, the screen's verdict must ride WITH the
// note, and a screen that fails must be indistinguishable from a clean one.

describe('a note’s photo', () => {
  it('is offered only inside the opt-in, where the longer form lives', () => {
    renderSection(context({ contributeConditions: false }))
    expect(screen.queryByTestId('poi-card-note-photo')).toBeNull()

    cleanup()
    renderSection(context({ contributeConditions: true }))
    expect(screen.getByTestId('poi-card-note-photo')).toBeTruthy()
  })

  it('says who sees it, before anybody attaches one', () => {
    renderSection(context({ contributeConditions: true }))

    // A note's photo publishes with its note. Somebody attaching a picture
    // to a dry spring should know it is going to the next hiker rather than
    // into a queue.
    expect(screen.getByText(/the next hiker sees it with your note/i)).toBeTruthy()
  })

  it('files the note without a photo when nobody attached one', () => {
    const onAddNote = vi.fn()
    renderSection(context({ onAddNote, contributeConditions: true }))

    fireEvent.click(screen.getByTestId('poi-card-observe-dry'))

    expect(onAddNote.mock.calls[0][1]).toBeUndefined()
    expect(onAddNote.mock.calls[0][0].photo_flagged).toBeUndefined()
  })

  it('acknowledges the tap before the screen has run', () => {
    const onAddNote = vi.fn()
    renderSection(context({ onAddNote, contributeConditions: true }))

    fireEvent.click(screen.getByTestId('poi-card-observe-dry'))

    // Synchronously, with no await: the one-tap answer is the contribution
    // DATA_NUDGES.md designed, and putting a model load in front of it would
    // spend the one interaction that has to be free.
    expect(screen.getByText(/^Noted: dry\./)).toBeTruthy()
  })

  it('renders a photo that came back with somebody else’s note', () => {
    renderSection(
      context({
        notesFor: () => [
          note({ note: 'Ford is passable', photo_url: 'https://x/y.jpg' }),
        ],
      }),
    )

    const image = screen.getByRole('img')
    expect(image.getAttribute('src')).toBe('https://x/y.jpg')
    // Named rather than empty: the photo IS part of the claim the note
    // makes, so a hiker on a screen reader is told it is there.
    expect(image.getAttribute('alt')).toMatch(/photo with a note/i)
  })

  it('draws nothing, and says nothing, when a note has no photo url', () => {
    renderSection(context({ notesFor: () => [note({ photo_url: null })] }))

    // Absent covers "no photo", "still uploading", "held on a flag" and "no
    // photo storage on this server" all at once, and the card must not
    // distinguish them: "a photo is waiting on a moderator" tells a stranger
    // something only the author and that moderator have any use for.
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByText(/waiting|held|moderator/i)).toBeNull()
  })

  it('reads a note baked before photos existed', () => {
    // `photo_url` is optional as well as nullable: conditions/notes.json
    // written before this shipped omits the key entirely.
    const { photo_url: _omitted, ...older } = note({ note: 'Spring is fine' })
    renderSection(context({ notesFor: () => [older as NoteSummary] }))

    expect(screen.getByText(/Spring is fine/)).toBeTruthy()
    expect(screen.queryByRole('img')).toBeNull()
  })
})

// --- Disputes on the card (#876, FIELD_NOTES.md §4) -----------------------
//
// WIREFRAMES.md §11's rule: the visual channel never carries the meaning
// alone. A dashed pin says something is unusual about a place; only these
// sentences say which of two very different things it is.

describe('a place the field says is not there', () => {
  const disputed = {
    poi_id: 'osm_water:1',
    accounts: 2,
    latest_at: new Date(NOW.getTime() - 4 * DAY_MS).toISOString(),
    maintainer_said: false,
  }

  it('says it in words, in the doc’s own sentence', () => {
    renderSection(context({ disputeFor: () => disputed }))

    expect(screen.getByTestId('poi-card-disputed').textContent).toBe(
      '2 hikers reported this missing, most recently 4 days ago.',
    )
  })

  it('says the existence claim before the freshness one', () => {
    renderSection(context({ disputeFor: () => disputed }))

    // "When did somebody last say this was fine" is a question about a place
    // that exists. Reading them the other way round tells a hiker how fresh
    // the news is about something that may not be there.
    const card = screen.getByTestId('poi-card-conditions')
    const order = Array.from(card.querySelectorAll('p')).map((p) => p.className)
    expect(order.indexOf('poi-card__disputed')).toBeLessThan(
      order.indexOf('poi-card__last-confirmed'),
    )
  })

  it('hedges when upstream never confirmed the place either', () => {
    renderSection(context({ disputeFor: () => disputed }), { unverified: true })

    expect(screen.getByTestId('poi-card-disputed').textContent).toMatch(
      /never confirmed to exist/,
    )
  })

  it('says nothing at all about a place nobody disputes', () => {
    renderSection(context({ disputeFor: () => null }))

    expect(screen.queryByTestId('poi-card-disputed')).toBeNull()
  })

  it('offers "Not here" as an answer, on every type it asks about', () => {
    // The button this feature was waiting for: the picker withheld
    // `not_found` until something could render, corroborate and decay it.
    renderSection(context())
    expect(screen.getByTestId('poi-card-observe-not_found')).toBeTruthy()

    cleanup()
    renderSection(context(), { poiType: 'shelter' })
    expect(screen.getByTestId('poi-card-observe-not_found')).toBeTruthy()
  })

  it('offers it on an unverified place too, and lets the card do the hedging', () => {
    // §4's carried-over open question. A hiker standing where a
    // low-confidence spring should be cannot tell "upstream never verified
    // this" from "it is gone", and asking them to is asking them to know our
    // data's provenance.
    renderSection(context(), { unverified: true })

    expect(screen.getByTestId('poi-card-observe-not_found')).toBeTruthy()
  })

  it('files it as an ordinary note, not a second flow', () => {
    const onAddNote = vi.fn()
    renderSection(context({ onAddNote }))

    fireEvent.click(screen.getByTestId('poi-card-observe-not_found'))

    // "A dispute is an observation value, not a second model" - no second
    // form, no second flow, nothing extra to moderate.
    expect(onAddNote.mock.calls[0][0].observation).toBe('not_found')
  })
})

// The peek (#941): the height a tapped pin opens at, before anybody asks for
// the record. What is asserted here is what it CARRIES - one condition line
// and the answer a hiker standing at a dry spring wants to give - and, just
// as load-bearing, what it declines to carry.
describe('FieldNoteSection, the list of notes', () => {
  it('says when each note was made and who made it', () => {
    // #941: the list carried the tag and the quote alone, which asks a hiker
    // to weigh "Dry" without saying whether it was said this morning or in
    // June, or by a maintainer or by somebody walking past. Both facts are on
    // every note the wire and the bake carry.
    renderSection(
      context({
        notesFor: () => [
          note({
            observation: 'dry',
            note: 'Nothing here in the heat.',
            reporter_type: 'maintainer',
            observed_at: new Date(NOW.getTime() - 6 * DAY_MS).toISOString(),
          }),
        ],
      }),
    )

    expect(screen.getByText('6 days ago · maintainer')).toBeInTheDocument()
    expect(screen.getByText('“Nothing here in the heat.”')).toBeInTheDocument()
  })

  it('dates a note through the same arithmetic the roll-up above it uses', () => {
    // One note, so the headline and the list are describing the same
    // observation - and a card that said "yesterday" in one and "2 days ago"
    // in the other about one note is the quiet contradiction #4 is about.
    renderSection(
      context({
        notesFor: () => [
          note({
            observation: 'flowing',
            reporter_type: 'thru',
            observed_at: new Date(NOW.getTime() - DAY_MS).toISOString(),
          }),
        ],
      }),
    )

    expect(screen.getByText('Flowing — yesterday, thru-hiker')).toBeInTheDocument()
    expect(screen.getByText('yesterday · thru-hiker')).toBeInTheDocument()
  })
})

describe('FieldNoteSection, peeking', () => {
  it('carries the two ends of the scale, and files from either of them', () => {
    // Flowing and Dry for water, which is the pair the design pass drew.
    const onAddNote = vi.fn()
    renderSection(context({ onAddNote }), { variant: 'peek' })

    expect(screen.getByTestId('poi-card-observe-flowing')).toBeTruthy()
    expect(screen.getByTestId('poi-card-observe-dry')).toBeTruthy()

    fireEvent.click(screen.getByTestId('poi-card-observe-dry'))

    // The same tap, not a lighter version of it: DATA_NUDGES.md's one-tap
    // contribution is the whole reason the peek carries buttons at all, and a
    // peek that only opened the card would have spent its two lines on
    // nothing.
    expect(onAddNote.mock.calls[0][0].observation).toBe('dry')
  })

  it('withholds the middle answers and the dispute, rather than crowding them in', () => {
    // Not a filter - every one of these is one tap away in the opened card.
    // `not_found` in particular: a dispute filed by a mis-hit on a crowded
    // peek is the claim #876 built corroboration to keep out.
    renderSection(context(), { variant: 'peek' })

    expect(screen.queryByTestId('poi-card-observe-trickling')).toBeNull()
    expect(screen.queryByTestId('poi-card-observe-not_found')).toBeNull()
  })

  it('asks its question in words, not only to a screen reader', () => {
    renderSection(context(), { variant: 'peek' })

    // Visible, and the group's accessible name at the same time - one
    // question, said once.
    expect(screen.getByText('How is it right now?')).toBeInTheDocument()
    expect(
      screen.getByRole('group', { name: 'How is it right now?' }),
    ).toBeInTheDocument()
  })

  it('prints the newest dated observation as its one line', () => {
    renderSection(
      context({
        notesFor: () => [
          note({
            observation: 'flowing',
            reporter_type: 'maintainer',
            observed_at: new Date(NOW.getTime() - 2 * DAY_MS).toISOString(),
          }),
        ],
      }),
      { variant: 'peek' },
    )

    expect(screen.getByTestId('poi-card-peek-line')).toHaveTextContent(
      'Flowing — 2 days ago, maintainer',
    )
  })

  it('says two people disagree rather than picking the newer one', () => {
    // FIELD_NOTES.md §3, at the height with room for one line. Printing the
    // newer note and dropping the other is the one thing this line must not
    // do: for a spring that is the difference between carrying water and not.
    renderSection(
      context({
        notesFor: () => [
          note({ observation: 'flowing', observed_at: NOW.toISOString() }),
          note({
            observation: 'dry',
            observed_at: new Date(NOW.getTime() - DAY_MS).toISOString(),
          }),
        ],
      }),
      { variant: 'peek' },
    )

    expect(screen.getByTestId('poi-card-peek-line')).toHaveTextContent(
      'Recent notes disagree',
    )
    expect(screen.getByTestId('poi-card-peek-line')).not.toHaveTextContent('Flowing —')
  })

  it('falls back to the freshness sentence where nobody has said anything', () => {
    // The maintainer's day-one wording for water (#256), unchanged by the
    // height it is printed at.
    renderSection(context({ notesFor: () => [] }), { variant: 'peek' })

    expect(screen.getByTestId('poi-card-peek-line')).toHaveTextContent('No recent word')
  })

  it('leaves the history, the composer and the report entry to the opened card', () => {
    renderSection(
      context({
        contributeConditions: true,
        notesFor: () => [note({ observation: 'dry', note: 'Nothing here in the heat.' })],
      }),
      { variant: 'peek' },
    )

    expect(screen.queryByText(/Nothing here in the heat/)).toBeNull()
    expect(screen.queryByTestId('poi-card-note-input')).toBeNull()
    expect(screen.queryByTestId('poi-card-report-here')).toBeNull()
  })

  it('acknowledges the tap and offers the escalation, exactly as the opened card does', () => {
    // The half of the interaction that must NOT be traded away for room: a
    // hiker who taps Dry on the peek has filed a problem-shaped note, and
    // FIELD_NOTES.md §5's hand-off is what turns it into a report.
    const onReportProblem = vi.fn()
    renderSection(context({ onReportProblem }), { variant: 'peek' })

    fireEvent.click(screen.getByTestId('poi-card-observe-dry'))

    expect(screen.getByRole('status')).toHaveTextContent('Noted: dry')
    fireEvent.click(screen.getByTestId('poi-card-escalate'))
    expect(onReportProblem).toHaveBeenCalledWith(
      expect.objectContaining({ poiId: 'osm_water:1' }),
      undefined,
    )
  })

  it('says nothing at all about a type the app does not ask about', () => {
    // A viewpoint has no condition to be stale about, at either height.
    const { container } = renderSection(context(), {
      poiType: 'viewpoint',
      variant: 'peek',
    })

    expect(container).toBeEmptyDOMElement()
  })
})
