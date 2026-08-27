import { describe, it, expect } from 'vitest'
import { waypointDistance } from './waypointDistance'

// #953: the waypoint card's "how far ahead" line. The distance is a
// subtraction; the WORD is the thing that had to be earned, and it is the
// subject of most of what is below. "0.3 mi ahead" said to a southbound hiker
// walking away from a spring is the opposite of the truth, on the one subject
// FEATURES.md's "a confidently wrong prediction is more dangerous than an
// honest unknown" is most obviously about.

describe('waypointDistance', () => {
  describe('which way it is', () => {
    it('is ahead of a northbound hiker when its mile is higher', () => {
      expect(
        waypointDistance({ waypointMile: 1407.5, hikerMile: 1407.2, direction: 'NOBO' }),
      ).toBe('0.3 mi ahead')
    })

    it('is behind a northbound hiker when its mile is lower', () => {
      expect(
        waypointDistance({ waypointMile: 1406.9, hikerMile: 1407.2, direction: 'NOBO' }),
      ).toBe('0.3 mi behind')
    })

    it('reverses both for a southbound hiker', () => {
      // The failure this whole module exists to prevent, asserted as the pair:
      // the same two places, the same two distances, and both words swapped.
      expect(
        waypointDistance({ waypointMile: 1406.9, hikerMile: 1407.2, direction: 'SOBO' }),
      ).toBe('0.3 mi ahead')
      expect(
        waypointDistance({ waypointMile: 1407.5, hikerMile: 1407.2, direction: 'SOBO' }),
      ).toBe('0.3 mi behind')
    })

    it('claims nothing about direction while the tracker has not committed', () => {
      // chrome/NextUpRail.tsx's rule, one surface over: a heading without a
      // settled direction "would be a coin flip printed as a claim". "Away" is
      // still a useful sentence - it is the distance, which is most of what was
      // being asked - and it is true in both directions.
      expect(waypointDistance({ waypointMile: 1407.5, hikerMile: 1407.2 })).toBe(
        '0.3 mi away',
      )
      expect(waypointDistance({ waypointMile: 1406.9, hikerMile: 1407.2 })).toBe(
        '0.3 mi away',
      )
    })
  })

  describe('when it says nothing at all', () => {
    it('says nothing without a fix on the trail', () => {
      // Every state positionLine has its own wording for arrives here as one
      // absence - location off, denied, no signal, still looking, no trail
      // data, a fix that will not place. The header says which; this stays
      // quiet rather than guessing at a seventh phrasing.
      expect(waypointDistance({ waypointMile: 1407.5, direction: 'NOBO' })).toBeNull()
    })

    it('says nothing about a place the centerline index has no mile for', () => {
      expect(waypointDistance({ hikerMile: 1407.2, direction: 'NOBO' })).toBeNull()
    })

    it('says nothing when a mile is not a number', () => {
      expect(waypointDistance({ waypointMile: Number.NaN, hikerMile: 1407.2 })).toBeNull()
      expect(
        waypointDistance({ waypointMile: 1407.2, hikerMile: Number.POSITIVE_INFINITY }),
      ).toBeNull()
    })

    it('says nothing rather than "0.0 mi ahead" at the hiker’s own mile', () => {
      // A directional claim on a number that is not there to support it. The
      // tempting alternative is "Here", and this must not say that: a zero
      // distance ALONG the trail says nothing about how far OFF it the place
      // sits, which is exactly the fact this card does not have (#953 item 4).
      expect(
        waypointDistance({ waypointMile: 1407.2, hikerMile: 1407.2, direction: 'NOBO' }),
      ).toBeNull()
      expect(
        waypointDistance({ waypointMile: 1407.22, hikerMile: 1407.2, direction: 'NOBO' }),
      ).toBeNull()
    })
  })

  describe('units', () => {
    it('reads the distance in the hiker’s own units', () => {
      expect(
        waypointDistance({
          waypointMile: 1407.5,
          hikerMile: 1407.2,
          direction: 'NOBO',
          units: 'metric',
        }),
      ).toBe('480 m ahead')
    })

    it('keeps the line at a distance metric can print and imperial cannot', () => {
      // The zero test asks the FORMATTER rather than a threshold written down
      // here, so it inherits lib/units.ts's asymmetry: metric drops to metres
      // under a kilometre, imperial stays in miles all the way down. Asserted
      // rather than left implicit because it is a real difference in what two
      // hikers see, and lib/units.ts records the imperial half as "a copy
      // change to argue on its own evidence" - not something to smuggle in here.
      const near = {
        waypointMile: 1407.22,
        hikerMile: 1407.2,
        direction: 'NOBO',
      } as const

      expect(waypointDistance({ ...near, units: 'metric' })).toBe('30 m ahead')
      expect(waypointDistance({ ...near, units: 'imperial' })).toBeNull()
    })
  })
})
