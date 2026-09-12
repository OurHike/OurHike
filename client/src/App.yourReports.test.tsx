// "Your reports" and "Your photos and notes" through the shell (#1373,
// frame 9d and D5): the outbox's waiting rows, the sent ledger joined to the
// live list by id, and the own-work list's door to a place that has left the
// map.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { keys } from 'idb-keyval'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness } from './test/appHarness'
import { OUTBOX_KEY } from './lib/outbox'
import { SENT_REPORTS_KEY } from './lib/sentReports'
import { POI_PHOTOS_PREFIX } from './lib/poiPhotos'
import { RETIRED_POI_STORE_KEY } from './lib/trailData'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
  keys: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => 'a-real-token'),
  sendOutboxItem: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchReports: vi.fn(async () => [
    {
      id: 'sent-1',
      type: 'flooding',
      reporter_type: 'thru',
      status: 'verified',
      severity: 'normal',
      lat: null,
      lon: null,
      mile: 1347.2,
      poi_id: null,
      note: null,
      timestamp: '2026-09-04T09:00:00.000Z',
    },
  ]),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  fetchDisputes: vi.fn(async () => []),
  fetchMyProfile: vi.fn(async () => ({ id: 'p-1', role: 'hiker', display_name: null })),
  fetchMyVolunteerHours: vi.fn(async () => []),
}))

const app = appHarness()
const store = app.store

/** A report waiting in the outbox, held so the mount flush leaves it be. */
const WAITING = {
  id: 'w1',
  authoredAt: '2026-09-09T08:00:00.000Z',
  payload: { type: 'trash', reporter_type: 'day', mile: 1347.2 },
  holdUntil: '2999-01-01T00:00:00.000Z',
}

beforeEach(() => {
  app.onboard()
  app.putTrailData()
  // The harness fakes get/set/update/del; the own-photo list walks the keys.
  vi.mocked(keys).mockImplementation(async () => [...store.keys()])
})

async function openMore(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)
  await user.click(await screen.findByRole('tab', { name: 'More' }))
}

describe('Your reports', () => {
  it('lists what waits and what went, with the live word beside a sent row', async () => {
    store.set(OUTBOX_KEY, [WAITING])
    store.set(SENT_REPORTS_KEY, [
      {
        id: 'sent-1',
        type: 'flooding',
        poiId: null,
        mile: 1347.2,
        authoredAt: '2026-09-04T08:00:00.000Z',
        sentAt: '2026-09-04T09:00:00.000Z',
      },
      {
        id: 'sent-2',
        type: 'blowdown',
        poiId: null,
        mile: null,
        authoredAt: '2026-08-01T08:00:00.000Z',
        sentAt: '2026-08-01T09:00:00.000Z',
      },
    ])
    const user = userEvent.setup()
    await openMore(user)
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
    expect(await screen.findByText('2 sent from this phone.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Your reports' }))

    const waiting = await screen.findByRole('region', { name: 'Waiting to send' })
    expect(within(waiting).getByText('Trash at mi 1,347.2')).toBeInTheDocument()

    const sent = screen.getByRole('region', { name: 'Sent from this phone' })
    // Joined by id to the live list: 'verified' reads as the reporter's
    // word, and a row the list does not hold carries no word at all.
    expect(await within(sent).findByText(/Confirmed/)).toBeInTheDocument()
    expect(within(sent).getByText(/does not hold them/)).toBeInTheDocument()
    expect(sent.textContent).not.toMatch(/verified|rejected/i)
  })
})

describe('Your photos and notes', () => {
  it('lists an own photo of a place that has left the map, and opens its card', async () => {
    // The tombstone the download carries for a retired place (#831), and a
    // photo of it on this phone - the encounter-only card the review found.
    store.set(RETIRED_POI_STORE_KEY, {
      'gone-1': {
        id: 'gone-1',
        poiType: 'water',
        source: 'opentrail_at',
        retired: '2025-09-01',
        lon: -74.8123,
        lat: 41.2087,
        name: 'Brink Road spring',
      },
    })
    store.set(`${POI_PHOTOS_PREFIX}gone-1`, {
      photos: [
        {
          id: 'ph-1',
          blob: new Blob([new Uint8Array(4)], { type: 'image/jpeg' }),
          taken: '2025-08-30',
          added: '2025-08-30',
          source: 'camera',
        },
      ],
    })
    const user = userEvent.setup()
    await openMore(user)
    await user.click(await screen.findByRole('button', { name: /^You/ }))
    await user.click(screen.getByRole('button', { name: 'Your photos and notes' }))

    const row = await screen.findByRole('button', { name: /Brink Road spring/ })
    expect(row).toHaveTextContent('a place no longer on the map')

    await user.click(row)
    // The removed-place card, on the map, with the photo's place named.
    expect(await screen.findByText(/This place is no longer in/)).toBeInTheDocument()
  })
})
