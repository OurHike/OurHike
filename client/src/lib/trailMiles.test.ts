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
    ['another format', JSON.stringify({ format: 2, trails_sha256: HASH, miles: {} })],
    ['no hash', JSON.stringify({ format: 1, miles: {} })],
    ['no miles', JSON.stringify({ format: 1, trails_sha256: HASH })],
  ])('is null for %s', (_, text) => {
    expect(parseTrailMiles(text)).toBeNull()
  })
})
