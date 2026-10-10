import { describe, expect, it } from 'vitest'
import { parseTrailMiles } from './trailMiles'

const HASH = 'a'.repeat(64)

describe('parseTrailMiles', () => {
  it('reads one list of miles per centerline feature', () => {
    const parsed = parseTrailMiles(
      JSON.stringify({
        format: 1,
        trails_sha256: HASH,
        miles: { 'centerline:chain:0': [0, 0.5, 1.2], 'centerline:chain:1': [1.2, 1.9] },
      }),
    )

    expect(parsed?.trailsSha256).toBe(HASH)
    expect(parsed?.byId.get('centerline:chain:0')).toEqual([0, 0.5, 1.2])
    expect(parsed?.byId.get('centerline:chain:1')).toEqual([1.2, 1.9])
  })

  it('skips a MultiLineString entry rather than flattening it', () => {
    // The index reads LineStrings only, and a flattened list would line up
    // with no feature's coordinates.
    const parsed = parseTrailMiles(
      JSON.stringify({
        format: 1,
        trails_sha256: HASH,
        miles: {
          multi: [
            [0, 1],
            [2, 3],
          ],
          flat: [4, 5],
        },
      }),
    )

    expect(parsed?.byId.has('multi')).toBe(false)
    expect(parsed?.byId.get('flat')).toEqual([4, 5])
  })

  it('skips a list with anything but numbers in it', () => {
    const parsed = parseTrailMiles(
      JSON.stringify({
        format: 1,
        trails_sha256: HASH,
        miles: { bad: [0, 'x'], good: [1] },
      }),
    )

    expect(parsed?.byId.has('bad')).toBe(false)
    expect(parsed?.byId.get('good')).toEqual([1])
  })

  it.each([
    ['not JSON', '{'],
    ['a list', '[]'],
    [
      'a format this build does not know',
      JSON.stringify({ format: 3, trails_sha256: HASH, miles: {} }),
    ],
    [
      'format 2 carrying v1 miles',
      JSON.stringify({ format: 2, trails_sha256: HASH, miles: {} }),
    ],
    ['no hash', JSON.stringify({ format: 1, miles: {} })],
    ['no miles', JSON.stringify({ format: 1, trails_sha256: HASH })],
  ])('is null for %s', (_, text) => {
    expect(parseTrailMiles(text)).toBeNull()
  })
})

// v2/trail_miles.json (decision 44, stage 6 of #1793): each chain's miles as
// whole thousandths, delta-coded. A mile is a safety field, so a chain has to
// read exactly v1's numbers, not numbers close to them.
describe('parseTrailMiles on a v2 file', () => {
  const V1 = JSON.stringify({
    format: 1,
    trails_sha256: HASH,
    miles: {
      'centerline:chain:0': [2197.973, 2197.989, 2197.987],
      'centerline:chain:1': [0.5],
    },
  })
  const V2 = JSON.stringify({
    format: 2,
    trails_sha256: HASH,
    milli_mile_deltas: {
      'centerline:chain:0': [2197973, 16, -2],
      'centerline:chain:1': [500],
    },
  })

  it('parseTrailMiles reads v2 milli_mile_deltas to exactly the miles v1 carries, a backward step kept', () => {
    expect(parseTrailMiles(V2)).toEqual(parseTrailMiles(V1))
    expect(parseTrailMiles(V2)?.byId.get('centerline:chain:0')).toEqual([
      2197.973, 2197.989, 2197.987,
    ])
  })

  it('parseTrailMiles skips a v2 chain whose steps are not whole numbers, keeping the others', () => {
    const parsed = parseTrailMiles(
      JSON.stringify({
        format: 2,
        trails_sha256: HASH,
        milli_mile_deltas: { bad: [0, 0.5], good: [1000] },
      }),
    )

    expect(parsed?.byId.has('bad')).toBe(false)
    expect(parsed?.byId.get('good')).toEqual([1])
  })
})
