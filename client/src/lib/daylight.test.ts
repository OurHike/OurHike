import { describe, expect, it } from 'vitest'
import { isDaylight } from './daylight'

// Sunrise and sunset as `astral` 3.2 (an independent implementation of NOAA's
// solar calculator) gave them on 2026-09-30, in UTC, for four trail points on
// four dates spanning both solstices and an equinox.
const ASTRAL: [string, number, number, string, string][] = [
  [
    'Lakes of the Clouds Hut',
    44.2587,
    -71.319,
    '2026-09-30T10:42:10Z',
    '2026-09-30T22:27:30Z',
  ],
  [
    'Springer Mountain',
    34.6272,
    -84.1936,
    '2026-06-21T10:24:30Z',
    '2026-06-22T00:52:34Z',
  ],
  ['Harts Pass, WA', 48.721, -120.668, '2026-12-21T15:53:14Z', '2026-12-22T00:08:06Z'],
  ['Katahdin', 45.9044, -68.9213, '2026-03-20T10:38:52Z', '2026-03-20T22:48:04Z'],
]

const MINUTE = 60_000

describe('isDaylight', () => {
  it.each(ASTRAL)(
    'agrees with astral about sunrise and sunset at %s, to within a minute',
    (_, lat, lon, sunrise, sunset) => {
      const rise = Date.parse(sunrise)
      const set = Date.parse(sunset)
      expect(isDaylight(lat, lon, new Date(rise - MINUTE))).toBe(false)
      expect(isDaylight(lat, lon, new Date(rise + MINUTE))).toBe(true)
      expect(isDaylight(lat, lon, new Date(set - MINUTE))).toBe(true)
      expect(isDaylight(lat, lon, new Date(set + MINUTE))).toBe(false)
    },
  )
})
