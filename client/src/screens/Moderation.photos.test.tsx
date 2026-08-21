import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
  within,
} from '@testing-library/react'
import { Moderation } from './Moderation'
import * as api from '../lib/api'

// The photo half of the queue (#579), built to the maintainer-adopted queue
// mockup. The properties under test: a photo is judged by LOOKING (the row
// leads with the photograph); a held photo says nothing is published while
// it waits; the pinned-three collision renders beside the button that hit
// it, spelled out, rather than as a screen-level failure; and only pins are
// pre-moderated - the section says so in words.

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
    // #877's two queues. Mocked here as well because the screen loads all
    // four resources on mount - and an unmocked one would leave this file
    // asserting against a screen in a failure state it never meant to test.
    fetchNoteQueue: vi.fn(),
    hideFieldNote: vi.fn(),
    unhideFieldNote: vi.fn(),
    fetchHoursQueue: vi.fn(),
    confirmVolunteerHours: vi.fn(),
    disputeVolunteerHours: vi.fn(),
  }
})

const mocked = vi.mocked(api)

function aPhoto(over: Partial<api.PoiPhotoQueueEntry> = {}): api.PoiPhotoQueueEntry {
  return {
    id: 'photo-1',
    poi_id: 'atc_shelters:abc',
    url: 'https://photos.example/signed/photo-1',
    taken_month: '2026-06',
    attribution: 'Sawyer',
    license: 'CC BY-SA 4.0',
    pinned: false,
    shared_at: new Date().toISOString(),
    flagged: null,
    held: false,
    reported_reason: null,
    ...over,
  }
}

async function shown(photos: api.PoiPhotoQueueEntry[]) {
  mocked.fetchModerationQueue.mockResolvedValue({ reports: [], closures: [] })
  mocked.fetchPhotoQueue.mockResolvedValue(photos)
  render(<Moderation onClose={vi.fn()} />)
  await screen.findByRole('heading', { name: /photos offered as a pin/i })
  await waitFor(() => expect(screen.queryByText(/reading the photos/i)).toBeNull())
}

beforeEach(() => {
  vi.clearAllMocks()
  // #877's queues load on the same mount; empty so this file keeps
  // asserting about photos only.
  mocked.fetchNoteQueue.mockResolvedValue([])
  mocked.fetchHoursQueue.mockResolvedValue([])
  mocked.pinPhoto.mockResolvedValue(aPhoto({ pinned: true }))
  mocked.unpinPhoto.mockResolvedValue(aPhoto())
  mocked.reviewPhoto.mockResolvedValue(aPhoto())
  mocked.dismissPhoto.mockResolvedValue(aPhoto())
})

afterEach(() => {
  cleanup()
})

describe('the photo queue section', () => {
  it('leads each row with the photograph, and states the masked credit', async () => {
    await shown([
      aPhoto(),
      aPhoto({ id: 'photo-2', attribution: null, taken_month: '2026-05' }),
    ])

    const images = screen.getAllByRole('presentation')
    expect(images).toHaveLength(2)
    expect(images[0]).toHaveAttribute('src', 'https://photos.example/signed/photo-1')
    expect(screen.getByText(/by Sawyer/)).toBeInTheDocument()
    expect(
      screen.getByText(/name withheld by the photographer’s request/),
    ).toBeInTheDocument()
  })

  it('says what only-pins-pre-moderated means, in words', async () => {
    await shown([])

    expect(
      screen.getByText(/a queue nobody can clear protects nobody/i),
    ).toBeInTheDocument()
    // And the standing gap it does not cover, said rather than implied.
    expect(screen.getByText(/no person in the loop at all/i)).toBeInTheDocument()
  })

  it('a held photo says the check decided nothing and nothing is published', async () => {
    await shown([aPhoto({ flagged: 'nudity', held: true })])

    expect(screen.getByText(/it did not decide anything/i)).toBeInTheDocument()
    expect(
      screen.getByText(/nothing is published while it waits here/i),
    ).toBeInTheDocument()
  })

  it('acts on a row and re-reads the queue', async () => {
    await shown([aPhoto()])

    fireEvent.click(screen.getByRole('button', { name: /pin it/i }))

    await waitFor(() => expect(mocked.pinPhoto).toHaveBeenCalledWith('photo-1'))
    expect(mocked.fetchPhotoQueue).toHaveBeenCalledTimes(2)
  })

  it('renders the pinned-three collision beside the row, spelled out', async () => {
    mocked.pinPhoto.mockRejectedValue(
      new api.ApiError(409, 'refused', {
        detail:
          'This place already has 3 pins. Unpin one first, or leave this in the rolling twelve.',
      }),
    )
    await shown([aPhoto()])

    fireEvent.click(screen.getByRole('button', { name: /pin it/i }))

    const collision = await screen.findByRole('alert')
    expect(collision).toHaveTextContent(/already has 3 pins/i)
    expect(collision).toHaveTextContent(/pinning this one takes another down/i)
    // The screen did not fall over: the row and its actions are still there.
    expect(screen.getByRole('button', { name: /refuse it/i })).toBeInTheDocument()
  })

  it('refusing calls the takedown', async () => {
    await shown([aPhoto()])

    fireEvent.click(screen.getByRole('button', { name: /refuse it/i }))

    await waitFor(() => expect(mocked.dismissPhoto).toHaveBeenCalledWith('photo-1'))
  })

  it('a photo queue that could not be read says so beside a queue that loaded', async () => {
    mocked.fetchModerationQueue.mockResolvedValue({ reports: [], closures: [] })
    mocked.fetchPhotoQueue.mockRejectedValue(new Error('no signal'))
    render(<Moderation onClose={vi.fn()} />)

    const section = (
      await screen.findByRole('heading', { name: /photos offered as a pin/i })
    ).closest('section')!
    expect(
      await within(section).findByText(/no answer, not an empty one/i),
    ).toBeInTheDocument()
    // The rest of the queue still reads normally.
    expect(screen.getByRole('heading', { name: /trail conditions/i })).toBeInTheDocument()
  })
})
