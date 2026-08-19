import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act, waitFor } from '@testing-library/react'
import { get, update, del, keys } from 'idb-keyval'
import { PoiCard, type PoiDetail } from './PoiCard'
import { addOwnPhoto, POI_PHOTOS_PREFIX } from '../lib/poiPhotos'
import { preparePhoto, PhotoUnusable } from '../lib/reportPhoto'
import { exifCaptureDate } from '../lib/exifDate'

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

const mockedGet = vi.mocked(get)
const mockedUpdate = vi.mocked(update)
const mockedDel = vi.mocked(del)
const mockedKeys = vi.mocked(keys)
const mockedPrepare = vi.mocked(preparePhoto)
const mockedExifDate = vi.mocked(exifCaptureDate)

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
  mockedPrepare.mockResolvedValue(PREPARED)
  mockedExifDate.mockResolvedValue('2026-06-18')
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
