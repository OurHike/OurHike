import { describe, it, expect } from 'vitest'
import 'fake-indexeddb/auto'
import { set } from 'idb-keyval'
import { conditionsCacheKey } from './conditionsCache'
import { SUGGESTED_HIKES_KEY, dataUrl } from './config'
import {
  recallSuggestedHikes,
  validateSuggestedHike,
  validateSuggestedHikes,
} from './suggestedHikesData'

// What a published route must carry to be shown at all, and what degrades to
// its honest absence instead (#1284). The asymmetry is lib/dayHikes.ts's:
// junk costs the record when it is the record - identity, ends, a named
// publisher - and costs only the field otherwise.

const SOUND = {
  id: 'sunrise',
  name: 'Sunrise Mtn loop',
  miles: 6.2,
  climb: { gainFt: 980, lossFt: 980 },
  difficulty: 'moderate',
  author: { kind: 'club', name: 'NY-NJ Trail Conference' },
  transit: {
    line: 'NJT 197',
    toStop: 'Culvers Gap',
    walkMiles: 0.3,
    source: 'NJ Transit',
  },
  photo: {
    url: 'https://example.test/sunrise.jpg',
    credit: 'A. Hiker',
    licence: 'CC BY 4.0',
  },
  segments: [
    [
      { coord: [-74.6, 41.2], poiId: null },
      { coord: [-74.58, 41.2], poiId: null },
    ],
  ],
}

describe('validating one published route', () => {
  it('reads a sound record through unchanged', () => {
    expect(validateSuggestedHike(SOUND)).toEqual(SOUND)
  })

  it('refuses a route with no identity, no name, no ground, or no ends', () => {
    expect(validateSuggestedHike({ ...SOUND, id: '' })).toBeNull()
    expect(validateSuggestedHike({ ...SOUND, name: '  ' })).toBeNull()
    expect(validateSuggestedHike({ ...SOUND, miles: 0 })).toBeNull()
    expect(validateSuggestedHike({ ...SOUND, miles: 'six' })).toBeNull()
    expect(validateSuggestedHike({ ...SOUND, segments: [] })).toBeNull()
    expect(
      validateSuggestedHike({ ...SOUND, segments: [[{ coord: [1, 2] }]] }),
    ).toBeNull()
  })

  it('refuses a route nobody is named as publishing', () => {
    // Naming who wrote it is the premise of showing it at all.
    expect(
      validateSuggestedHike({ ...SOUND, author: { kind: 'club', name: '' } }),
    ).toBeNull()
    expect(
      validateSuggestedHike({ ...SOUND, author: { kind: 'algorithm', name: 'x' } }),
    ).toBeNull()
    expect(validateSuggestedHike({ ...SOUND, author: undefined })).toBeNull()
  })

  it('keeps the three climb states apart, and never invents a zero', () => {
    expect(validateSuggestedHike({ ...SOUND, climb: null })?.climb).toBeNull()
    const { climb: _never, ...unasked } = SOUND
    expect('climb' in (validateSuggestedHike(unasked) ?? {})).toBe(false)
    expect('climb' in (validateSuggestedHike({ ...SOUND, climb: 'steep' }) ?? {})).toBe(
      false,
    )
    expect(
      'climb' in
        (validateSuggestedHike({ ...SOUND, climb: { gainFt: -1, lossFt: 0 } }) ?? {}),
    ).toBe(false)
  })

  it('degrades a rating it cannot read to no rating, never to a computed one', () => {
    expect(
      validateSuggestedHike({ ...SOUND, difficulty: 'brutal' })?.difficulty,
    ).toBeNull()
    expect(
      validateSuggestedHike({ ...SOUND, difficulty: undefined })?.difficulty,
    ).toBeNull()
  })

  it('drops a transit block it cannot print, which reads as nothing published', () => {
    expect(
      validateSuggestedHike({ ...SOUND, transit: { line: '', walkMiles: 0.3 } }),
    ).not.toHaveProperty('transit')
    expect(
      validateSuggestedHike({ ...SOUND, transit: { line: 'NJT 197', walkMiles: 'far' } }),
    ).not.toHaveProperty('transit')
    // A line to the trailhead itself has no stop to name, and that is fine.
    expect(
      validateSuggestedHike({ ...SOUND, transit: { line: 'NJT 197', walkMiles: 0 } })
        ?.transit,
    ).toEqual({ line: 'NJT 197', toStop: '', walkMiles: 0, source: '' })
  })

  it('resolves a published photo key against the bucket, and leaves a URL alone', () => {
    const key = 'photos/' + 'a'.repeat(64) + '.jpg'
    const fromKey = validateSuggestedHike({
      ...SOUND,
      photo: { url: key, credit: 'Photo by Daniel Chazin', licence: 'By permission' },
    })
    expect(fromKey?.photo?.url).toBe(dataUrl(key))
    const fromUrl = validateSuggestedHike({
      ...SOUND,
      photo: { url: 'https://example.test/x.jpg', credit: 'c', licence: 'l' },
    })
    expect(fromUrl?.photo?.url).toBe('https://example.test/x.jpg')
  })

  it('shows no photo that arrives without its credit or licence', () => {
    expect(
      validateSuggestedHike({ ...SOUND, photo: { url: 'https://example.test/x.jpg' } }),
    ).not.toHaveProperty('photo')
  })

  it('rebuilds each end field by field, so no edgeIndex survives a load', () => {
    const smuggled = {
      ...SOUND,
      segments: [
        [
          { coord: [-74.6, 41.2], poiId: null, edgeIndex: 41 },
          { coord: [-74.58, 41.2], poiId: null, edgeIndex: 42 },
        ],
      ],
    }
    const read = validateSuggestedHike(smuggled)
    expect(read?.segments[0][0]).toEqual({ coord: [-74.6, 41.2], poiId: null })
    expect(read?.segments[0][0]).not.toHaveProperty('edgeIndex')
  })
})

describe('the detail block a route carries', () => {
  // THE WIRE IS FLAT AND MEMORY IS NESTED, and the seam between those two
  // shapes had no test at all. `export_suggested_hikes.py` writes `url`,
  // `publishedMiles`, `overview`, `start` and the rest straight onto the
  // hike beside `miles` and `segments`; the validator gathers them into one
  // `detail` block so a screen can ask "is there a detail" once. Nothing
  // pinned that, so a preview fixture that guessed the nested shape produced
  // a detail screen with no publisher's length, no start, no prose and no
  // link back - and the shot was the only thing that noticed.
  const FLAT = {
    url: 'https://example.test/sunrise',
    publishedMiles: 6.8,
    overview: ['A ridge with two views.'],
    description: ['Park at the lot.', 'Follow the blazes.'],
    publication: {
      submittedBy: 'D. Chazin',
      submittedOn: '2016-08-24',
      verifiedOn: null,
    },
    start: { lat: 41.23, lon: -74.61, basis: 'marker' },
    routeType: 'Loop',
    park: 'Stokes State Forest',
    trails: ['Appalachian Trail'],
    hikerNote: 'The turnaround is where their description puts it.',
  }

  it('gathers the exporter’s flat fields into one block', () => {
    const read = validateSuggestedHike({ ...SOUND, ...FLAT })

    expect(read?.detail).toEqual(FLAT)
  })

  it('keeps the publisher’s own length, which is the point of the block', () => {
    // The two figures disagreeing is what the detail screen exists to show.
    // Losing this one silently leaves the screen printing OUR measurement
    // with nobody's name on it.
    const read = validateSuggestedHike({ ...SOUND, publishedMiles: 6.8 })

    expect(read?.detail?.publishedMiles).toBe(6.8)
  })

  it('reads nothing out of a nested `detail`, which is not the wire shape', () => {
    // The exact mistake the fixture made. Asserted rather than left implicit
    // so that anyone who moves the wire format has to move this test too.
    const read = validateSuggestedHike({ ...SOUND, detail: FLAT })

    expect(read?.detail).toBeUndefined()
  })

  it('does not invent a block from a route that carries none', () => {
    expect(validateSuggestedHike(SOUND)?.detail).toBeUndefined()
  })

  it('costs the field and never the route', () => {
    const read = validateSuggestedHike({
      ...SOUND,
      url: '',
      publishedMiles: -2,
      start: { lat: 41.2 },
      park: 'Harriman',
    })

    expect(read).not.toBeNull()
    // Half a coordinate points at the Atlantic; a negative length is not one.
    expect(read?.detail).toEqual({ park: 'Harriman' })
  })
})

describe('validating a published document', () => {
  it('keeps every readable route and drops the rest, once each', () => {
    const hikes = validateSuggestedHikes({
      generated_at: '2026-09-08T12:00:00Z',
      hikes: [SOUND, { ...SOUND, id: 'twin' }, { id: 'junk' }, SOUND],
    })
    expect(hikes.map((hike) => hike.id)).toEqual(['sunrise', 'twin'])
  })

  it('reads anything that is not the document shape as nothing to suggest', () => {
    expect(validateSuggestedHikes(null)).toEqual([])
    expect(validateSuggestedHikes([SOUND])).toEqual([])
    expect(validateSuggestedHikes({ hikes: 'many' })).toEqual([])
  })
})

describe('the kept copy', () => {
  it('comes back validated, through the conditions cache', async () => {
    await set(conditionsCacheKey(SUGGESTED_HIKES_KEY), {
      document: { hikes: [SOUND, { id: 'junk' }] },
      storedAt: '2026-09-08T12:00:00.000Z',
    })
    const kept = await recallSuggestedHikes()
    expect(kept?.map((hike) => hike.id)).toEqual(['sunrise'])
  })
})
