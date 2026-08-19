import { describe, it, expect, vi, beforeEach } from 'vitest'
import { del, get, keys, update } from 'idb-keyval'
import {
  addOwnPhoto,
  chooseOwnPhoto,
  deleteOwnPhoto,
  listOwnPhotos,
  ownPhotoUsage,
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
