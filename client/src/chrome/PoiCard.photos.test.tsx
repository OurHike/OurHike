import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act, waitFor } from '@testing-library/react'
import { get, update, del, keys } from 'idb-keyval'
import { PoiCard, type PoiDetail } from './PoiCard'
import { addOwnPhoto, POI_PHOTOS_PREFIX } from '../lib/poiPhotos'
import { preparePhoto, PhotoUnusable } from '../lib/reportPhoto'
import { exifCaptureDate } from '../lib/exifDate'
import { fetchPoiPhotos } from '../lib/api'
import { clearCommunityPhotoCache } from '../lib/useCommunityPhotos'
import { loadPreferences } from '../lib/preferences'
import { OUTBOX_KEY, type OutboxItem } from '../lib/outbox'

// The hiker's own photo on the waypoint card: capture with a keep-or-discard
// review (#571), several per place with a sticky choice (#575), the honest
// strip about which copy is which (#573), and the one render rule worth a
// test that fails loudly (#578): rung 1 always wins, and nothing - not a
// fresher photo, not a better-credited one - displaces it.
//
// The pixel machinery is doubled: reportPhoto.test.ts owns proving the
// re-encode, and exifDate.test.ts owns the EXIF walk. What this file proves
// is the FLOW - that discard means nothing was written, that the capture
// date travels from the original to the stored record, that the choice
// sticks in storage rather than in component state.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  update: vi.fn(),
  del: vi.fn(),
  keys: vi.fn(),
}))

vi.mock('../lib/reportPhoto', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/reportPhoto')>()),
  preparePhoto: vi.fn(),
}))

vi.mock('../lib/exifDate', () => ({ exifCaptureDate: vi.fn() }))

// The community rung's fetch (#578). Mocked at the api seam rather than at
// the hook, so the hook's cache and silent-failure behaviour stay under test.
vi.mock('../lib/api', () => ({ fetchPoiPhotos: vi.fn() }))

// The share and report paths (#577/#579) queue through the real outbox into
// the same mocked idb-keyval store, so "what was queued" is asserted against
// storage; only the flush trigger and the sheet's preferences read are
// doubled.
vi.mock('../lib/outboxSync', () => ({ syncOutbox: vi.fn() }))
vi.mock('../lib/preferences', () => ({ loadPreferences: vi.fn() }))

const mockedGet = vi.mocked(get)
const mockedUpdate = vi.mocked(update)
const mockedDel = vi.mocked(del)
const mockedKeys = vi.mocked(keys)
const mockedPrepare = vi.mocked(preparePhoto)
const mockedExifDate = vi.mocked(exifCaptureDate)
const mockedFetchPoiPhotos = vi.mocked(fetchPoiPhotos)
const mockedLoadPreferences = vi.mocked(loadPreferences)

/** In-memory IndexedDB, with update() applied synchronously against the
 *  stored value - the real one's single-transaction semantics. */
function withStore() {
  const stored = new Map<string, unknown>()
  mockedGet.mockImplementation(async (key) => stored.get(key as string))
  mockedUpdate.mockImplementation(async (key, updater) => {
    stored.set(key as string, updater(stored.get(key as string)))
  })
  mockedDel.mockImplementation(async (key) => {
    stored.delete(key as string)
  })
  mockedKeys.mockImplementation(async () => [...stored.keys()])
  return stored
}

const SHELTER: PoiDetail = {
  id: 'atc_shelters:abc',
  name: 'Chairback Gap Lean-to',
  type: 'shelter',
  lat: 45.4732,
  lon: -69.1183,
  confidence: 'high',
}

const PREPARED = new Blob([new Uint8Array(38 * 1024)], { type: 'image/jpeg' })

/** Render and flush the own-photos load, so no state lands after a test
 *  has moved on. */
async function renderCard(poi: PoiDetail = SHELTER) {
  const view = render(<PoiCard poi={poi} map={null} onClose={vi.fn()} />)
  await act(async () => {})
  return view
}

function pickFile(testId: string, name = 'trail.jpg') {
  const file = new File([new Uint8Array(1024)], name, { type: 'image/jpeg' })
  fireEvent.change(screen.getByTestId(testId), { target: { files: [file] } })
  return file
}

beforeEach(() => {
  withStore()
  clearCommunityPhotoCache()
  mockedPrepare.mockResolvedValue(PREPARED)
  mockedExifDate.mockResolvedValue('2026-06-18')
  mockedFetchPoiPhotos.mockResolvedValue([])
  mockedLoadPreferences.mockResolvedValue({
    trail_name: 'Sawyer',
    anonymity_window_days: 0,
  } as Awaited<ReturnType<typeof loadPreferences>>)
  // jsdom implements neither; the card only ever hands these URLs to <img>
  // and <a>, so strings are all a test needs. Assigned onto the real URL
  // rather than replacing the global, which would take the constructor
  // with it.
  let minted = 0
  URL.createObjectURL = vi.fn(() => `blob:mock-${(minted += 1)}`)
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  cleanup()
  // @ts-expect-error jsdom never had them; put it back the way it was
  delete URL.createObjectURL
  // @ts-expect-error same
  delete URL.revokeObjectURL
  vi.clearAllMocks()
})

describe('the waiting affordance (#571)', () => {
  it('offers camera and library, and nothing else asks', async () => {
    await renderCard()

    expect(screen.getByTestId('poi-card-take-photo')).toHaveTextContent('Take a photo')
    expect(screen.getByTestId('poi-card-add-photo')).toHaveTextContent(
      'Add from your photos',
    )
    // No review, no note, no prompt: the affordance waits.
    expect(screen.queryByTestId('poi-card-review-photo')).not.toBeInTheDocument()
  })
})

describe('the review step (#571)', () => {
  it('shows the prepared rendering with keep and discard, having written nothing', async () => {
    const stored = withStore()
    await renderCard()

    pickFile('poi-card-library-input')

    const preview = await screen.findByTestId('poi-card-review-photo')
    expect(preview).toHaveAttribute('src', expect.stringMatching(/^blob:mock-/))
    expect(screen.getByTestId('poi-card-keep')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-discard')).toBeInTheDocument()
    // The size and date are said before the keep, and the store is untouched.
    expect(screen.getByText(/Keep stores this 38 KB copy/)).toBeInTheDocument()
    expect(screen.getByText(/dated Jun 2026/)).toBeInTheDocument()
    expect(stored.size).toBe(0)
  })

  it('discard writes nothing - not written-then-deleted, nothing', async () => {
    const stored = withStore()
    await renderCard()

    pickFile('poi-card-library-input')
    fireEvent.click(await screen.findByTestId('poi-card-discard'))
    await act(async () => {})

    expect(screen.queryByTestId('poi-card-review-photo')).not.toBeInTheDocument()
    expect(stored.size).toBe(0)
    expect(mockedUpdate).not.toHaveBeenCalled()
  })

  it('keep stores the rendering with the capture date read off the original', async () => {
    const stored = withStore()
    await renderCard()

    const original = pickFile('poi-card-library-input')
    fireEvent.click(await screen.findByTestId('poi-card-keep'))

    // The card now shows the hiker's own photo, dated by capture month.
    await screen.findByText('Your photo · Jun 2026')
    // The EXIF walk saw the ORIGINAL file - the re-encode output has no date.
    expect(mockedExifDate).toHaveBeenCalledWith(original)
    const record = stored.get(`${POI_PHOTOS_PREFIX}${SHELTER.id}`) as {
      photos: { blob: Blob; taken: string | null; source: string }[]
    }
    expect(record.photos).toHaveLength(1)
    expect(record.photos[0].blob).toBe(PREPARED)
    expect(record.photos[0].taken).toBe('2026-06-18')
    expect(record.photos[0].source).toBe('library')
  })

  it('says why a photo could not be prepared, and stores nothing', async () => {
    const stored = withStore()
    mockedPrepare.mockRejectedValue(
      new PhotoUnusable('That file could not be read as a photo. Try taking another.'),
    )
    await renderCard()

    pickFile('poi-card-library-input')

    expect(
      await screen.findByText(
        'That file could not be read as a photo. Try taking another.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByTestId('poi-card-review-photo')).not.toBeInTheDocument()
    expect(stored.size).toBe(0)
  })

  it('says so when storage refuses, rather than pretending the keep worked', async () => {
    withStore()
    mockedUpdate.mockRejectedValue(new Error('quota'))
    await renderCard()

    pickFile('poi-card-library-input')
    fireEvent.click(await screen.findByTestId('poi-card-keep'))

    expect(
      await screen.findByText(
        'This phone could not store the photo, so nothing was kept.',
      ),
    ).toBeInTheDocument()
    // The review stays up - the hiker can still act on the photo in hand.
    expect(screen.getByTestId('poi-card-review-photo')).toBeInTheDocument()
  })

  it('drops an unkept review when the card moves to another waypoint', async () => {
    const stored = withStore()
    const view = await renderCard()

    pickFile('poi-card-library-input')
    await screen.findByTestId('poi-card-review-photo')

    view.rerender(
      <PoiCard
        poi={{ ...SHELTER, id: 'atc_shelters:other', name: 'Another Lean-to' }}
        map={null}
        onClose={vi.fn()}
      />,
    )
    await act(async () => {})

    expect(screen.queryByTestId('poi-card-review-photo')).not.toBeInTheDocument()
    expect(stored.size).toBe(0)
  })
})

describe('rung 1 always wins (#578)', () => {
  it('renders the hiker’s own photo ahead of everything the artifacts carry', async () => {
    withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2021-03-05',
      source: 'library',
    })

    // A pipeline photo that is fresher, better credited, and first in the
    // artifact's own gallery - and still loses.
    await renderCard({
      ...SHELTER,
      photoUrl: 'https://photos.example/commons.jpg',
      photoAuthor: 'A. Photographer',
      photoLicense: 'CC BY-SA 4.0',
      photoTaken: '2026-07-01',
    })

    expect(await screen.findByText('Your photo · Mar 2021')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute(
      'src',
      expect.stringMatching(/^blob:mock-/),
    )
    // The artifact photo is still there, one step down the ladder.
    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 2')
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    expect(
      screen.getByText('Photo: A. Photographer · CC BY-SA 4.0 · Jul 2026'),
    ).toBeInTheDocument()
  })
})

describe('several per place, and the choice sticks (#575)', () => {
  it('orders most recent first and lets the hiker put another on the card', async () => {
    const stored = withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2020-01-10',
      source: 'library',
    })
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-02-20',
      source: 'library',
    })
    await renderCard()

    // Most recent first by default.
    expect(await screen.findByText('Your photo · Feb 2026')).toBeInTheDocument()

    // Step to the older one; it is not the card photo, so the offer shows.
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    expect(screen.getByText('Your photo · Jan 2020')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('poi-card-choose'))

    // Both facts at once - the chosen photo, at the front - because either
    // alone was true at some earlier moment: Jan 2020 was on screen before
    // the click, and "1 of 2" is what an index reset alone shows.
    await waitFor(() => {
      expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 2')
      expect(screen.getByText('Your photo · Jan 2020')).toBeInTheDocument()
    })
    // And the choice is in storage, not in component state, so it sticks
    // past this card. Waited for: the write follows the repaint.
    await waitFor(() => {
      const record = stored.get(`${POI_PHOTOS_PREFIX}${SHELTER.id}`) as {
        photos: { id: string; taken: string | null }[]
        chosenId?: string
      }
      const older = record.photos.find((photo) => photo.taken === '2020-01-10')
      expect(record.chosenId).toBe(older?.id)
    })
  })

  it('the chosen photo offers no choose button - it is already the card', async () => {
    withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-02-20',
      source: 'library',
    })
    await renderCard()

    await screen.findByText('Your photo · Feb 2026')
    expect(screen.queryByTestId('poi-card-choose')).not.toBeInTheDocument()
  })

  it('remove takes a second tap, then falls back down the ladder', async () => {
    const stored = withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-02-20',
      source: 'library',
    })
    await renderCard()
    await screen.findByText('Your photo · Feb 2026')

    const remove = screen.getByTestId('poi-card-remove')
    fireEvent.click(remove)
    // One tap arms; nothing is deleted yet.
    expect(remove).toHaveTextContent('Tap again to remove')
    expect(stored.size).toBe(1)

    fireEvent.click(remove)
    await act(async () => {})

    // Gone from storage entirely, and the card shows what it showed before
    // the feature existed: the placeholder.
    expect(stored.size).toBe(0)
    expect(screen.getByTestId('poi-card-placeholder')).toBeInTheDocument()
  })
})

describe('which copy is which (#573)', () => {
  it('a library pick says the library has the original', async () => {
    withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-02-20',
      source: 'library',
    })
    await renderCard()

    expect(
      await screen.findByText(
        'A copy sized for this card — your library has the original.',
      ),
    ).toBeInTheDocument()
  })

  it('a camera capture says the small copy may be the only one', async () => {
    withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-02-20',
      source: 'camera',
    })
    await renderCard()

    expect(
      await screen.findByText(
        'Taken in OurHike. Unless you saved the original, this small copy is the only one.',
      ),
    ).toBeInTheDocument()
  })

  it('offers the original for saving while a camera capture is in hand', async () => {
    withStore()
    await renderCard()

    pickFile('poi-card-camera-input', 'ridge.jpg')

    const save = await screen.findByTestId('poi-card-save-original')
    expect(save).toHaveAttribute('download', 'ridge.jpg')
    expect(save).toHaveAttribute('href', expect.stringMatching(/^blob:mock-/))
  })

  it('offers no save for a library pick - its original is already home', async () => {
    withStore()
    await renderCard()

    pickFile('poi-card-library-input')

    await screen.findByTestId('poi-card-review-photo')
    expect(screen.queryByTestId('poi-card-save-original')).not.toBeInTheDocument()
  })
})

describe('the share sheet and its verbs (#577)', () => {
  const outbox = (stored: Map<string, unknown>) =>
    (stored.get(OUTBOX_KEY) as OutboxItem[] | undefined) ?? []

  it('says the terms, then queues the share and shows the cooling-off truth', async () => {
    const stored = withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-06-18',
      source: 'library',
    })
    await renderCard()
    await screen.findByText('Your photo · Jun 2026')

    fireEvent.click(screen.getByTestId('poi-card-share'))

    // The sheet's load-bearing sentences, verbatim from the adopted mockup.
    expect(await screen.findByText('Two different promises')).toBeInTheDocument()
    expect(screen.getByText(/OurHike never had it/)).toBeInTheDocument()
    expect(screen.getByText(/The licence cannot be taken back/)).toBeInTheDocument()
    // Nothing queued while the sheet is open - the share is the tap below.
    expect(outbox(stored)).toHaveLength(0)

    fireEvent.click(screen.getByTestId('share-sheet-share'))

    await screen.findByTestId('poi-card-share-state')
    const queued = outbox(stored)
    expect(queued).toHaveLength(1)
    expect(queued[0].action).toEqual({
      kind: 'poi_photo_share',
      poiId: SHELTER.id,
      // The claim is coarsened to the month BEFORE it is queued - the
      // sheet's "the picture and the month" made true in storage.
      taken: '2026-06-01',
      flagged: null,
    })
    expect(queued[0].photo).toBe(PREPARED)
    // And the strip stops offering Share and starts telling the truth.
    expect(screen.getByTestId('poi-card-share-state')).toHaveTextContent(
      /goes live in about 2h/,
    )
    expect(screen.getByTestId('poi-card-unshare')).toHaveTextContent('Take it back')
  })

  it('take it back queues the withdrawal and returns the photo to private', async () => {
    const stored = withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-06-18',
      source: 'library',
    })
    await renderCard()
    await screen.findByText('Your photo · Jun 2026')
    fireEvent.click(screen.getByTestId('poi-card-share'))
    fireEvent.click(await screen.findByTestId('share-sheet-share'))
    await screen.findByTestId('poi-card-unshare')

    fireEvent.click(screen.getByTestId('poi-card-unshare'))

    await screen.findByTestId('poi-card-share')
    const queued = outbox(stored)
    expect(queued).toHaveLength(2)
    expect(queued[1].action).toEqual({
      kind: 'poi_photo_withdraw',
      poiId: SHELTER.id,
    })
    expect(
      screen.getByText(/Nobody ever had it, so nothing was released/),
    ).toBeInTheDocument()
  })

  it('with no trail name the sheet refuses with the reason, not a stuck outbox item', async () => {
    const stored = withStore()
    mockedLoadPreferences.mockResolvedValue({
      trail_name: null,
      anonymity_window_days: 0,
    } as Awaited<ReturnType<typeof loadPreferences>>)
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-06-18',
      source: 'library',
    })
    await renderCard()
    await screen.findByText('Your photo · Jun 2026')

    fireEvent.click(screen.getByTestId('poi-card-share'))

    expect(await screen.findByTestId('share-sheet-no-name')).toHaveTextContent(
      /needs a trail name/,
    )
    expect(screen.queryByTestId('share-sheet-share')).not.toBeInTheDocument()
    expect(outbox(stored)).toHaveLength(0)
  })

  it('the anonymity window is said to the sharer in days, when one is set', async () => {
    withStore()
    mockedLoadPreferences.mockResolvedValue({
      trail_name: 'Sawyer',
      anonymity_window_days: 12,
    } as Awaited<ReturnType<typeof loadPreferences>>)
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-06-18',
      source: 'library',
    })
    await renderCard()
    await screen.findByText('Your photo · Jun 2026')

    fireEvent.click(screen.getByTestId('poi-card-share'))

    expect(
      await screen.findByText(/For 12 more days even Sawyer is withheld/),
    ).toBeInTheDocument()
  })
})

describe('reporting a community photo (#579)', () => {
  const COMMUNITY_PHOTO = {
    id: 'p9',
    poi_id: SHELTER.id,
    url: 'https://photos.example/signed/p9',
    taken_month: '2026-05',
    attribution: 'Somebody',
    license: 'CC BY-SA 4.0',
    pinned: false,
  }

  it('offers the three reasons and queues the chosen one', async () => {
    const stored = withStore()
    mockedFetchPoiPhotos.mockResolvedValue([COMMUNITY_PHOTO])
    await renderCard()
    await screen.findByTestId('poi-card-community-strip')

    fireEvent.click(screen.getByTestId('poi-card-report'))
    fireEvent.click(await screen.findByTestId('poi-card-report-person'))

    await screen.findByText(/stays on the card until one of them has looked/)
    const queued = (stored.get(OUTBOX_KEY) as OutboxItem[] | undefined) ?? []
    expect(queued).toHaveLength(1)
    expect(queued[0].action).toEqual({
      kind: 'poi_photo_report',
      poiId: SHELTER.id,
      photoId: 'p9',
      reason: 'person',
    })
  })

  it('offers no report verb on the hiker’s own photo', async () => {
    withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2026-06-18',
      source: 'library',
    })
    await renderCard()
    await screen.findByText('Your photo · Jun 2026')

    expect(screen.queryByTestId('poi-card-report')).not.toBeInTheDocument()
  })
})

describe('the community rung (#578, from #576)', () => {
  const COMMUNITY = {
    id: 'p1',
    poi_id: SHELTER.id,
    url: 'https://photos.example/signed/p1',
    taken_month: '2026-05',
    attribution: 'Sawyer',
    license: 'CC BY-SA 4.0',
    pinned: false,
  }

  it('renders below the hiker’s own photo and above the artifacts’', async () => {
    withStore()
    await addOwnPhoto(SHELTER.id, {
      blob: PREPARED,
      taken: '2021-03-05',
      source: 'library',
    })
    mockedFetchPoiPhotos.mockResolvedValue([COMMUNITY])

    await renderCard({
      ...SHELTER,
      photoUrl: 'https://photos.example/commons.jpg',
      photoAuthor: 'A. Photographer',
      photoLicense: 'CC BY-SA 4.0',
      photoTaken: '2026-07-01',
    })

    // Rung 1 first - the community photo, though fresher, does not displace it.
    expect(await screen.findByText('Your photo · Mar 2021')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 3')

    // Rung 2 next, credited to the trail name.
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    expect(
      await screen.findByText('Photo: Sawyer · CC BY-SA 4.0 · May 2026'),
    ).toBeInTheDocument()

    // The artifact photo one further down.
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    expect(
      screen.getByText('Photo: A. Photographer · CC BY-SA 4.0 · Jul 2026'),
    ).toBeInTheDocument()
  })

  it('a masked credit carries licence and month, never an invented name', async () => {
    withStore()
    mockedFetchPoiPhotos.mockResolvedValue([{ ...COMMUNITY, attribution: null }])

    await renderCard()

    expect(await screen.findByText('Photo: CC BY-SA 4.0 · May 2026')).toBeInTheDocument()
  })

  it('degrades silently when the backend is unreachable', async () => {
    withStore()
    mockedFetchPoiPhotos.mockRejectedValue(new Error('offline'))

    await renderCard()

    // The card as it shipped before the rung existed: placeholder, no error.
    expect(screen.getByTestId('poi-card-placeholder')).toBeInTheDocument()
    expect(screen.queryByTestId('poi-card-photo-count')).not.toBeInTheDocument()
  })
})
