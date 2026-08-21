import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Moderation } from './Moderation'
import * as api from '../lib/api'

// The two queues #877 gave a screen: flagged field notes, and hours waiting
// on a club's word. Both had backends and API clients and no surface at all,
// which made FIELD_NOTES.md §5's whole moderation model reachable only by
// curl.
//
// Four properties carry this file, and each is a way the screen could be
// wrong while still rendering something plausible:
//
//  1. **A queue that could not be read is not an empty queue**, section by
//     section. This screen now loads four resources; one refusal must not
//     draw the other three as "nothing waiting", and must not draw itself
//     that way either.
//  2. **The archive of removals is listed, under the work.** §5's promise is
//     that a flagged note is hidden and never deleted so a wrong removal is
//     recoverable - which is only true if a moderator can find it and put it
//     back.
//  3. **A date filed as a date does not move.** `worked_on` has no time in
//     it, and rendering it through a `Date` puts a volunteer's Thursday on
//     Wednesday for every club west of Greenwich.
//  4. **Nothing here totals anybody's hours.** VOLUNTEERING.md §5's rules
//     bind wherever hours render, and a per-person total in a queue is a
//     comparison between rows waiting to happen.

vi.mock('../lib/api', () => {
  class ApiError extends Error {
    readonly status: number
    readonly detail: unknown
    constructor(status: number, message: string, detail?: unknown) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.detail = detail
    }
  }
  return {
    ApiError,
    fetchModerationQueue: vi.fn(),
    fetchReportPhotoLink: vi.fn(),
    verifyReport: vi.fn(),
    dismissReport: vi.fn(),
    verifyClosure: vi.fn(),
    dismissClosure: vi.fn(),
    fetchPhotoQueue: vi.fn(),
    pinPhoto: vi.fn(),
    unpinPhoto: vi.fn(),
    reviewPhoto: vi.fn(),
    dismissPhoto: vi.fn(),
    fetchNoteQueue: vi.fn(),
    hideFieldNote: vi.fn(),
    unhideFieldNote: vi.fn(),
    fetchHoursQueue: vi.fn(),
    confirmVolunteerHours: vi.fn(),
    disputeVolunteerHours: vi.fn(),
  }
})

const mocked = vi.mocked(api)

type NoteOverrides = Partial<Omit<api.NoteQueueEntry, 'note'>> & {
  note?: Partial<api.NoteQueueEntry['note']>
}

function aNote({ note, ...rest }: NoteOverrides = {}): api.NoteQueueEntry {
  return {
    note: {
      id: 'note-1',
      poi_id: 'atc_shelters:abc',
      lat: null,
      lon: null,
      mile: null,
      observation: 'dry',
      note: 'Spring was dry at noon.',
      observed_at: new Date().toISOString(),
      reporter_type: 'thru',
      reporter_id: 'account-7',
      ...note,
    },
    flag_count: 1,
    reasons: [],
    hidden: false,
    ...rest,
  }
}

function anHour(
  over: Partial<api.VolunteerHoursQueueEntry> = {},
): api.VolunteerHoursQueueEntry {
  return {
    id: 'hours-1',
    user_id: 'account-9',
    club_id: 'nynjtc',
    worked_on: '2026-08-20',
    hours: 3.5,
    work_project_id: null,
    activity: 'maintenance',
    note: 'Cut two blowdowns above the col.',
    mile: null,
    lat: null,
    lon: null,
    state: 'claimed',
    confirmed_at: null,
    recorded_at: new Date().toISOString(),
    ...over,
  }
}

/** Renders with both new queues served, and waits for the screen to have
 *  settled - on something observable, never on a timer. */
async function shown(
  notes: api.NoteQueueEntry[],
  hours: api.VolunteerHoursQueueEntry[] = [],
) {
  mocked.fetchNoteQueue.mockResolvedValue(notes)
  mocked.fetchHoursQueue.mockResolvedValue(hours)
  render(<Moderation onClose={vi.fn()} />)
  await screen.findByRole('heading', { name: /hours waiting on a club/i })
  await waitFor(() => {
    expect(screen.queryByText(/reading the notes/i)).toBeNull()
    expect(screen.queryByText(/reading the hours/i)).toBeNull()
  })
}

/** The section a heading belongs to, awaited - the screen draws only its
 *  title until the reports queue resolves, so a synchronous lookup would
 *  race the first render rather than the thing under test. */
async function section(name: RegExp): Promise<HTMLElement> {
  const heading = await screen.findByRole('heading', { name })
  return heading.closest('section') as HTMLElement
}

beforeEach(() => {
  vi.clearAllMocks()
  mocked.fetchModerationQueue.mockResolvedValue({ reports: [], closures: [] })
  mocked.fetchPhotoQueue.mockResolvedValue([])
  mocked.fetchNoteQueue.mockResolvedValue([])
  mocked.fetchHoursQueue.mockResolvedValue([])
  mocked.hideFieldNote.mockResolvedValue(aNote({ hidden: true }))
  mocked.unhideFieldNote.mockResolvedValue(aNote())
  mocked.confirmVolunteerHours.mockResolvedValue(anHour({ state: 'confirmed' }))
  mocked.disputeVolunteerHours.mockResolvedValue(anHour({ state: 'disputed' }))
})

afterEach(() => {
  cleanup()
})

describe('the flagged-notes section', () => {
  it('shows what was said, how many said it, and who wrote the note', async () => {
    await shown([
      aNote({
        flag_count: 3,
        reasons: ['This spring is fine, I filled up an hour ago', 'wrong place'],
      }),
    ])

    const notes = await section(/field notes people flagged/i)
    expect(within(notes).getByText(/spring was dry at noon/i)).toBeTruthy()
    expect(within(notes).getByText(/3 people flagged this/i)).toBeTruthy()
    expect(within(notes).getByText(/i filled up an hour ago/i)).toBeTruthy()
    // The one place in this app an account id is printed: a pattern of
    // abuse is a pattern across one account's notes, never inside one.
    expect(within(notes).getByText(/account-7/)).toBeTruthy()
  })

  it('hides a note, then re-reads rather than patching the row in place', async () => {
    await shown([aNote()])

    await userEvent.click(screen.getByRole('button', { name: /hide it/i }))

    await waitFor(() => expect(mocked.hideFieldNote).toHaveBeenCalledWith('note-1'))
    // Twice: the mount, and the re-read. A second moderator working the same
    // queue is the ordinary case for a club.
    await waitFor(() => expect(mocked.fetchNoteQueue).toHaveBeenCalledTimes(2))
  })

  it('lists removals under their own heading, so a wrong one can be put back', async () => {
    await shown([
      aNote({ note: { id: 'note-visible' }, flag_count: 2 }),
      aNote({ note: { id: 'note-gone' }, hidden: true }),
    ])

    const notes = await section(/field notes people flagged/i)
    expect(
      within(notes).getByRole('heading', { name: /already taken down/i }),
    ).toBeTruthy()
    expect(within(notes).getByText(/no hiker sees this/i)).toBeTruthy()

    await userEvent.click(within(notes).getByRole('button', { name: /put it back/i }))
    await waitFor(() => expect(mocked.unhideFieldNote).toHaveBeenCalledWith('note-gone'))
  })

  it('keeps the server order inside each half rather than re-sorting', async () => {
    await shown([
      aNote({ note: { id: 'note-most' }, flag_count: 5 }),
      aNote({ note: { id: 'note-fewer' }, flag_count: 1 }),
      aNote({ note: { id: 'note-hidden' }, hidden: true }),
    ])

    const rows = within(await section(/field notes people flagged/i)).getAllByRole(
      'listitem',
    )
    // Visible work first, most corroborated first within it, the archive
    // last - exactly as `GET /moderation/field-notes` sorted it. The reasons
    // list would also be listitems, so these rows carry none.
    expect(rows).toHaveLength(3)
    expect(rows[0].textContent).toMatch(/5 people flagged this/)
    expect(rows[1].textContent).toMatch(/1 person flagged this/)
    expect(rows[2].textContent).toMatch(/no hiker sees this/i)
  })

  it('says the notes queue is unread rather than empty, and only for itself', async () => {
    mocked.fetchNoteQueue.mockRejectedValue(new Error('offline'))
    mocked.fetchHoursQueue.mockResolvedValue([anHour()])
    render(<Moderation onClose={vi.fn()} />)

    const notes = await section(/field notes people flagged/i)
    await within(notes).findByText(/could not be read/i)
    expect(within(notes).queryByText(/nothing waiting/i)).toBeNull()

    // The hours half loaded, and says so - one refusal is not four.
    const hours = await section(/hours waiting on a club/i)
    await waitFor(() =>
      expect(within(hours).queryByText(/could not be read/i)).toBeNull(),
    )
    expect(within(hours).getByText(/blowdowns above the col/i)).toBeTruthy()
  })
})

describe('the hours section', () => {
  it('prints the day as it was filed, not as a local midnight', async () => {
    await shown([], [anHour({ worked_on: '2026-08-20' })])

    const hours = await section(/hours waiting on a club/i)
    expect(within(hours).getByText(/worked 2026-08-20/)).toBeTruthy()
    // The failure this guards: `new Date('2026-08-20')` is midnight UTC, so
    // every US club would read the 19th.
    expect(within(hours).queryByText(/2026-08-19/)).toBeNull()
  })

  it('says a claim is somebody’s, and confirms it on the club’s behalf', async () => {
    await shown([], [anHour({ hours: 3.5, activity: 'maintenance' })])

    const hours = await section(/hours waiting on a club/i)
    expect(within(hours).getByText(/3\.5 h · Trail maintenance/)).toBeTruthy()
    expect(within(hours).getByText(/claimed by account-9/)).toBeTruthy()

    await userEvent.click(
      within(hours).getByRole('button', { name: /the club stands behind this/i }),
    )
    await waitFor(() =>
      expect(mocked.confirmVolunteerHours).toHaveBeenCalledWith('hours-1'),
    )
    await waitFor(() => expect(mocked.fetchHoursQueue).toHaveBeenCalledTimes(2))
  })

  it('disputes without pretending the record is gone', async () => {
    await shown([], [anHour()])

    const hours = await section(/hours waiting on a club/i)
    // The section has to say what a dispute does, because the button cannot:
    // the hours already count, and disputing is what takes them out.
    expect(within(hours).getByText(/already count for the volunteer/i)).toBeTruthy()
    expect(within(hours).getByText(/rather than an erasure/i)).toBeTruthy()

    await userEvent.click(within(hours).getByRole('button', { name: /dispute it/i }))
    await waitFor(() =>
      expect(mocked.disputeVolunteerHours).toHaveBeenCalledWith('hours-1'),
    )
  })

  it('totals nobody, across rows or within one', async () => {
    await shown(
      [],
      [
        anHour({ id: 'hours-1', user_id: 'account-9', hours: 3.5 }),
        anHour({ id: 'hours-2', user_id: 'account-9', hours: 2 }),
        anHour({ id: 'hours-3', user_id: 'account-4', hours: 4 }),
      ],
    )

    // Scoped to the rows, not the section: the preamble says what a dispute
    // does to a total, which is the sentence a club admin needs and not a
    // number about anybody.
    const rows = within(await section(/hours waiting on a club/i)).getByRole('list')
    expect(within(rows).getAllByRole('listitem')).toHaveLength(3)
    // 5.5 is account-9's total and 9.5 is the queue's. Neither is a number
    // this screen is allowed to compute - VOLUNTEERING.md §5, which binds
    // wherever hours render and not only on the volunteer's own dashboard.
    expect(within(rows).queryByText(/5\.5/)).toBeNull()
    expect(within(rows).queryByText(/9\.5/)).toBeNull()
    expect(within(rows).queryByText(/total/i)).toBeNull()
  })

  it('says the hours queue is unread rather than empty', async () => {
    mocked.fetchHoursQueue.mockRejectedValue(new Error('offline'))
    render(<Moderation onClose={vi.fn()} />)

    const hours = await section(/hours waiting on a club/i)
    await within(hours).findByText(/could not be read/i)
    expect(within(hours).queryByText(/nothing waiting/i)).toBeNull()
  })
})
