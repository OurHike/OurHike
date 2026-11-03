import { describe, it, expect, vi, beforeEach } from 'vitest'
import { del, get, getMany, keys, update } from 'idb-keyval'
import {
  addOwnPhoto,
  CARD_PHOTO_EDGE,
  CARD_PHOTO_SLOT_PX,
  chooseOwnPhoto,
  deleteOwnPhoto,
  listAllOwnPhotos,
  listOwnPhotos,
  MIN_HERO_PHOTO_WIDTH,
  ownPhotoUsage,
  photoFrame,
  POI_PHOTOS_PREFIX,
} from './poiPhotos'

// The store behind rung 1 of the precedence ladder. What matters here is the
// ordering contract the card leans on - chosen first, then most recent by
// the same date the card prints - and that deletion cleans up after itself:
// a dangling chosenId or an empty record left in storage would each surface
// as a card quietly showing the wrong photo or a storage line counting
// places with nothing in them.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  update: vi.fn(),
  del: vi.fn(),
  keys: vi.fn(),
}))

const mockedGet = vi.mocked(get)
const mockedUpdate = vi.mocked(update)
const mockedDel = vi.mocked(del)
const mockedKeys = vi.mocked(keys)

/** Backs the mocked idb-keyval with a real in-memory map. The mocked
 *  update() applies its updater synchronously against the stored value,
 *  mirroring the real one's single-transaction semantics. */
function withStore(initial: Record<string, unknown> = {}) {
  const stored = new Map(Object.entries(initial))
  mockedGet.mockImplementation(async (key) => stored.get(key as string))
  // `getMany` follows whatever `get` is doing right now, so #1303's one
  // transaction in lib/trailData.ts reads this file's store like every other
  // read, and a test that re-points `get` need not re-point both.
  vi.mocked(getMany).mockImplementation((keys) =>
    Promise.all(keys.map((key) => vi.mocked(get)(key))),
  )
  mockedUpdate.mockImplementation(async (key, updater) => {
    stored.set(key as string, updater(stored.get(key as string)))
  })
  mockedDel.mockImplementation(async (key) => {
    stored.delete(key as string)
  })
  mockedKeys.mockImplementation(async () => [...stored.keys()])
  return stored
}

function jpeg(bytes: number): Blob {
  return new Blob([new Uint8Array(bytes)], { type: 'image/jpeg' })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('addOwnPhoto and listOwnPhotos', () => {
  it('stores a photo and lists it back', async () => {
    withStore()
    const added = await addOwnPhoto('poi-1', {
      blob: jpeg(10),
      taken: '2026-06-18',
      source: 'library',
    })

    const listed = await listOwnPhotos('poi-1')
    expect(listed).toHaveLength(1)
    expect(listed[0].id).toBe(added.id)
    expect(listed[0].taken).toBe('2026-06-18')
    expect(listed[0].source).toBe('library')
    // The added date is stamped by the store, "YYYY-MM-DD".
    expect(listed[0].added).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('orders most recent first, dating by capture where present else added', async () => {
    withStore()
    await addOwnPhoto('poi-1', { blob: jpeg(1), taken: '2024-05-01', source: 'camera' })
    await addOwnPhoto('poi-1', { blob: jpeg(2), taken: '2026-05-01', source: 'camera' })
    // No capture date: dated by today's added date, which sorts newest.
    await addOwnPhoto('poi-1', { blob: jpeg(3), taken: null, source: 'library' })

    const listed = await listOwnPhotos('poi-1')
    expect(listed.map((photo) => photo.blob.size)).toEqual([3, 2, 1])
  })

  it('returns an empty list for a place with no photos', async () => {
    withStore()
    await expect(listOwnPhotos('poi-none')).resolves.toEqual([])
  })
})

describe('chooseOwnPhoto', () => {
  it('puts the chosen photo first, and the choice sticks over recency', async () => {
    withStore()
    const older = await addOwnPhoto('poi-1', {
      blob: jpeg(1),
      taken: '2020-01-01',
      source: 'camera',
    })
    await addOwnPhoto('poi-1', { blob: jpeg(2), taken: '2026-01-01', source: 'camera' })

    await chooseOwnPhoto('poi-1', older.id)
    const listed = await listOwnPhotos('poi-1')
    expect(listed[0].id).toBe(older.id)
  })

  it('ignores a choice naming a photo that does not exist', async () => {
    withStore()
    await addOwnPhoto('poi-1', { blob: jpeg(1), taken: '2026-01-01', source: 'camera' })
    await chooseOwnPhoto('poi-1', 'no-such-id')
    const listed = await listOwnPhotos('poi-1')
    expect(listed).toHaveLength(1)
  })
})

describe('deleteOwnPhoto', () => {
  it('removes one photo and keeps the rest', async () => {
    withStore()
    const first = await addOwnPhoto('poi-1', {
      blob: jpeg(1),
      taken: '2026-01-01',
      source: 'camera',
    })
    const second = await addOwnPhoto('poi-1', {
      blob: jpeg(2),
      taken: '2025-01-01',
      source: 'camera',
    })

    await deleteOwnPhoto('poi-1', first.id)
    const listed = await listOwnPhotos('poi-1')
    expect(listed.map((photo) => photo.id)).toEqual([second.id])
  })

  it('clears the choice when the chosen photo is deleted', async () => {
    withStore()
    const chosen = await addOwnPhoto('poi-1', {
      blob: jpeg(1),
      taken: '2020-01-01',
      source: 'camera',
    })
    const newest = await addOwnPhoto('poi-1', {
      blob: jpeg(2),
      taken: '2026-01-01',
      source: 'camera',
    })
    const middle = await addOwnPhoto('poi-1', {
      blob: jpeg(3),
      taken: '2023-01-01',
      source: 'camera',
    })
    await chooseOwnPhoto('poi-1', chosen.id)

    await deleteOwnPhoto('poi-1', chosen.id)
    // Back to recency order, no dangling id.
    const listed = await listOwnPhotos('poi-1')
    expect(listed.map((photo) => photo.id)).toEqual([newest.id, middle.id])
  })

  it('removes the key outright when the last photo goes', async () => {
    const stored = withStore()
    const only = await addOwnPhoto('poi-1', {
      blob: jpeg(1),
      taken: null,
      source: 'library',
    })
    await deleteOwnPhoto('poi-1', only.id)
    expect(stored.has(`${POI_PHOTOS_PREFIX}poi-1`)).toBe(false)
  })
})

describe('listAllOwnPhotos (#1373, D5)', () => {
  it('lists every own photo with its place, newest first, holding no bytes', async () => {
    withStore({ 'ourhike:outbox': [{ note: 'not a photo' }] })
    await addOwnPhoto('poi-1', { blob: jpeg(100), taken: '2026-09-01', source: 'camera' })
    await addOwnPhoto('poi-2', { blob: jpeg(7), taken: '2026-09-04', source: 'library' })
    await addOwnPhoto('poi-1', { blob: jpeg(50), taken: null, source: 'camera' })

    const all = await listAllOwnPhotos()
    expect(all.map((photo) => photo.poiId)).toEqual(['poi-1', 'poi-2', 'poi-1'])
    expect(all[1]).toMatchObject({
      poiId: 'poi-2',
      taken: '2026-09-04',
      source: 'library',
    })
    expect(all.every((photo) => !('blob' in photo))).toBe(true)
  })

  it('is empty for a phone with no photos', async () => {
    withStore()
    await expect(listAllOwnPhotos()).resolves.toEqual([])
  })
})

describe('ownPhotoUsage', () => {
  it('sums measured bytes and counts across places, ignoring other keys', async () => {
    withStore({
      'ourhike:outbox': [{ note: 'not a photo' }],
    })
    await addOwnPhoto('poi-1', { blob: jpeg(100), taken: null, source: 'camera' })
    await addOwnPhoto('poi-1', { blob: jpeg(50), taken: null, source: 'library' })
    await addOwnPhoto('poi-2', { blob: jpeg(7), taken: null, source: 'camera' })

    await expect(ownPhotoUsage()).resolves.toEqual({ count: 3, bytes: 157 })
  })

  it('reports zero for a phone with no photos', async () => {
    withStore()
    await expect(ownPhotoUsage()).resolves.toEqual({ count: 0, bytes: 0 })
  })
})

// --- which frame a photograph earns (#1495) -----------------------------------
//
// The decision lives here rather than in PoiCard so it can be checked without
// rendering anything, and so the number it rests on sits beside the slot width
// it is derived from.
describe('photoFrame', () => {
  it('derives the line from the slot rather than picking a round number', () => {
    // 240 is the 264px card less the body's 12px padding either side, and 2 is
    // the density POI_PHOTOS.md sizes every other photo decision against. If
    // either moves, this fails rather than drifting quietly.
    expect(CARD_PHOTO_SLOT_PX).toBe(240)
    expect(MIN_HERO_PHOTO_WIDTH).toBe(480)
  })

  it('sits inside the gap the recorded decision left', () => {
    // The maintainer's decision of 2026-09-15 was "hero at 640 and above,
    // inset below 400" and said nothing about 400-639. The line has to honour
    // both bounds rather than override either.
    expect(photoFrame(640)).toBe('hero')
    expect(photoFrame(399)).toBe('inset')
    expect(MIN_HERO_PHOTO_WIDTH).toBeGreaterThan(400)
    expect(MIN_HERO_PHOTO_WIDTH).toBeLessThan(640)
  })

  it('fills the box at the line and insets one pixel under it', () => {
    expect(photoFrame(MIN_HERO_PHOTO_WIDTH)).toBe('hero')
    expect(photoFrame(MIN_HERO_PHOTO_WIDTH - 1)).toBe('inset')
  })

  it('insets the width the NYNJTC archive corpus actually is', () => {
    // 396 of 403 recovered images are under 640px, measured over the whole
    // corpus 2026-09-15: min 100, median 250, max 4000. The two widths below
    // are the measured minimum and the measured median, so this asserts the
    // real distribution rather than two round numbers near it.
    // This is the case the whole rule exists for, so it is asserted with the
    // real numbers rather than a token small one.
    expect(photoFrame(100)).toBe('inset')
    expect(photoFrame(250)).toBe('inset')
  })

  it('fills the box for every source the card was built for', () => {
    // The hiker's own photos are re-encoded to CARD_PHOTO_EDGE on the device,
    // and the Commons and ATC fetches ask for the same edge. None of them
    // should ever take the new path.
    expect(photoFrame(CARD_PHOTO_EDGE)).toBe('hero')
  })

  it.each([null, undefined, 0, -1])('fills the box when unmeasured: %s', (width) => {
    // Unmeasured is what every first paint is, and 0 is what a broken decode
    // reports. Neither is evidence the photograph is small, and both must
    // render as the card always did rather than flashing small then growing.
    expect(photoFrame(width)).toBe('hero')
  })
})
