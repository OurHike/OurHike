import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import {
  deleteArchiveRecords,
  deleteGeneration,
  markComplete,
  readArchive,
  readArchiveSize,
  readComplete,
  readSegmentRun,
  readSegments,
  segmentKeyFor,
  writeSegment,
} from './archiveStore'

// The record layout an archive is stored in (#553). What the download engine
// writes and what the map reads, with nothing in between - archiveDownload.ts's
// own suite covers the transfer; this covers the shape it leaves behind.
//
// Two properties carry the weight here, and both are about not destroying a map
// somebody is navigating by:
//
//   - a finished archive is its SEGMENTS plus a marker, never a second copy, so
//     completion needs no room at all; and
//   - an in-flight transfer writes into the generation the finished archive is
//     NOT in, so a re-download cannot overwrite the map it is replacing.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

const KEY = 'ourhike:corridor-archive'

function withStore(initial: Record<string, unknown> = {}) {
  const store: Record<string, unknown> = { ...initial }
  vi.mocked(get).mockImplementation(async (key) => store[key as string])
  vi.mocked(set).mockImplementation(async (key, value) => {
    store[key as string] = value
  })
  vi.mocked(del).mockImplementation(async (key) => {
    delete store[key as string]
  })
  return store
}

/** Segment records for one generation, in order. */
function segments(generation: number, ...parts: string[]): Record<string, unknown> {
  return Object.fromEntries(
    parts.map((text, index) => [segmentKeyFor(KEY, generation, index), new Blob([text])]),
  )
}

function complete(
  generation: number,
  segmentCount: number,
  totalBytes: number,
): Record<string, unknown> {
  return { [`${KEY}:complete`]: { generation, segments: segmentCount, totalBytes } }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('readArchive', () => {
  it('assembles the segments the marker names, in order', async () => {
    withStore({ ...segments(0, 'one ', 'two ', 'three'), ...complete(0, 3, 14) })

    expect(await (await readArchive(KEY))?.text()).toBe('one two three')
  })

  it('is undefined while a transfer is still unfinished', async () => {
    // Segments on disk with no marker are a download in progress. Serving them
    // would hand the map a truncated PMTiles archive, which opens fine and then
    // returns nothing for tiles past the cut.
    withStore(segments(0, 'half a map'))

    expect(await readArchive(KEY)).toBeUndefined()
  })

  it('is undefined when the phone holds nothing at all', async () => {
    withStore()

    expect(await readArchive(KEY)).toBeUndefined()
  })

  it('serves a whole-archive record written by the pre-segment build', async () => {
    // lib/packages.ts kept this key so an archive already in a tester's
    // IndexedDB "stays readable after this change, rather than silently
    // re-downloading". That promise outlived the layout it was written about.
    const legacy = new Blob(['a map from the old build'])
    withStore({ [KEY]: legacy })

    expect(await readArchive(KEY)).toBe(legacy)
  })

  it('prefers the marker to a legacy record that outlived a crash', async () => {
    // markComplete removes the legacy record after writing the marker. A phone
    // holding both was interrupted in between, and the segments are the newer
    // bytes.
    withStore({
      [KEY]: new Blob(['the older map']),
      ...segments(1, 'the newer map'),
      ...complete(1, 1, 13),
    })

    expect(await (await readArchive(KEY))?.text()).toBe('the newer map')
  })

  it('ignores a non-Blob under the package key', async () => {
    withStore({ [KEY]: 'not a map' })

    expect(await readArchive(KEY)).toBeUndefined()
  })
})

describe('readArchiveSize', () => {
  it('answers from the marker rather than reassembling the archive', async () => {
    // The Downloads screen asks this for every package on every mount. At 36
    // segments for the Fine tier, reassembling would be 36 record reads to
    // learn a number the marker already holds.
    withStore({ ...segments(0, 'one ', 'two '), ...complete(0, 2, 8) })
    vi.mocked(get).mockClear()

    expect(await readArchiveSize(KEY)).toBe(8)
    expect(vi.mocked(get)).toHaveBeenCalledTimes(1)
  })

  it('measures a legacy whole-archive record', async () => {
    withStore({ [KEY]: new Blob(['12345']) })

    expect(await readArchiveSize(KEY)).toBe(5)
  })

  it('is null where there is no archive', async () => {
    withStore(segments(0, 'unfinished'))

    expect(await readArchiveSize(KEY)).toBeNull()
  })
})

describe('readSegmentRun', () => {
  it('reports the bytes and how many records they came in', async () => {
    withStore(segments(0, 'aa', 'bb', 'cc'))

    const run = await readSegmentRun(KEY, 0)

    expect(await run.blob?.text()).toBe('aabbcc')
    expect(run.count).toBe(3)
  })

  it('stops at the first gap, so a running transfer reads back its real prefix', async () => {
    // Segments are written contiguously, so a gap can only mean the end. Reading
    // past one would assemble bytes that are not adjacent in the archive.
    withStore({
      ...segments(0, 'aa', 'bb'),
      [segmentKeyFor(KEY, 0, 3)]: new Blob(['dd']),
    })

    const run = await readSegmentRun(KEY, 0)

    expect(await run.blob?.text()).toBe('aabb')
    expect(run.count).toBe(2)
  })

  it('reads each generation separately', async () => {
    withStore({ ...segments(0, 'old'), ...segments(1, 'new') })

    expect(await (await readSegments(KEY, 0))?.text()).toBe('old')
    expect(await (await readSegments(KEY, 1))?.text()).toBe('new')
  })

  it('is empty where the generation holds nothing', async () => {
    withStore(segments(0, 'only in generation zero'))

    expect((await readSegmentRun(KEY, 1)).blob).toBeUndefined()
  })
})

describe('markComplete', () => {
  it('makes the segments the archive without copying them', async () => {
    // The whole point: completion costs one small record. Copying the finished
    // segments into a single archive record would need room for the archive AND
    // its segments at once - #544's quota failure at 1.18 GB, the size where it
    // hurts most - and would write every byte a second time.
    const store = withStore(segments(0, 'one ', 'two '))

    await markComplete(KEY, { generation: 0, segments: 2, totalBytes: 8 })

    expect(await (await readArchive(KEY))?.text()).toBe('one two ')
    const blobBytes = Object.values(store).reduce<number>(
      (total, value) => total + (value instanceof Blob ? value.size : 0),
      0,
    )
    expect(blobBytes).toBe(8)
  })

  it('frees the generation it replaced', async () => {
    const store = withStore({
      ...segments(0, 'the old map'),
      ...segments(1, 'the new map'),
    })

    await markComplete(KEY, { generation: 1, segments: 1, totalBytes: 11 })

    expect(store[segmentKeyFor(KEY, 0, 0)]).toBeUndefined()
    expect(await (await readArchive(KEY))?.text()).toBe('the new map')
  })

  it('frees the legacy whole-archive record it replaced', async () => {
    // Left standing it would waste up to 1.18 GB for good, since nothing would
    // ever read it again.
    const store = withStore({
      [KEY]: new Blob(['a map from the old build']),
      ...segments(0, 'a map from this one'),
    })

    await markComplete(KEY, { generation: 0, segments: 1, totalBytes: 19 })

    expect(store[KEY]).toBeUndefined()
  })

  it('writes the marker before freeing anything', async () => {
    // Order is the correctness argument. Freeing first opens a window where the
    // phone holds neither archive; this way a crash in between leaves the older
    // one intact and the newer bytes as the unfinished transfer they are.
    withStore({ ...segments(0, 'the old map'), ...segments(1, 'the new map') })
    const order: string[] = []
    vi.mocked(set).mockImplementation(async (key) => {
      order.push(`set ${String(key)}`)
    })
    vi.mocked(del).mockImplementation(async (key) => {
      order.push(`del ${String(key)}`)
    })

    await markComplete(KEY, { generation: 1, segments: 1, totalBytes: 11 })

    expect(order[0]).toBe(`set ${KEY}:complete`)
  })
})

describe('deleteArchiveRecords', () => {
  it('takes both generations, the marker and the legacy record', async () => {
    const store = withStore({
      [KEY]: new Blob(['legacy']),
      ...segments(0, 'aa', 'bb'),
      ...segments(1, 'cc'),
      ...complete(0, 2, 4),
    })

    await deleteArchiveRecords(KEY)

    expect(store).toEqual({})
  })

  it('deletes through a gap up to a claimed count', async () => {
    // A segment write can fail on quota while earlier ones stand, so a gap is
    // reachable. Probing alone stops there and would leave the rest on a phone
    // whose owner is deleting a 1.18 GB map precisely to free the space (#554).
    const store = withStore({
      ...segments(0, 'aa'),
      [segmentKeyFor(KEY, 0, 2)]: new Blob(['cc']),
      [segmentKeyFor(KEY, 0, 3)]: new Blob(['dd']),
    })

    await deleteArchiveRecords(KEY, 4)

    expect(store).toEqual({})
  })

  it('leaves another package alone', async () => {
    const other = 'ourhike:dem'
    const store = withStore({
      ...segments(0, 'corridor'),
      [segmentKeyFor(other, 0, 0)]: new Blob(['dem']),
      [`${other}:complete`]: { generation: 0, segments: 1, totalBytes: 3 },
    })

    await deleteArchiveRecords(KEY)

    expect(store[segmentKeyFor(other, 0, 0)]).toBeInstanceOf(Blob)
    expect(await readComplete(other)).toEqual({
      generation: 0,
      segments: 1,
      totalBytes: 3,
    })
  })
})

describe('deleteGeneration', () => {
  it('takes one generation and leaves the other', async () => {
    const store = withStore({ ...segments(0, 'keep'), ...segments(1, 'drop') })

    await deleteGeneration(KEY, 1)

    expect(store[segmentKeyFor(KEY, 0, 0)]).toBeInstanceOf(Blob)
    expect(store[segmentKeyFor(KEY, 1, 0)]).toBeUndefined()
  })
})

describe('writeSegment', () => {
  it('appends under the generation and index it is given', async () => {
    const store = withStore()

    await writeSegment(KEY, 1, 4, new Blob(['bytes']))

    expect(store[segmentKeyFor(KEY, 1, 4)]).toBeInstanceOf(Blob)
    expect(segmentKeyFor(KEY, 1, 4)).toBe('ourhike:corridor-archive:g1:4')
  })
})
