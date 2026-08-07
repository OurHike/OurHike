// What the header is allowed to say about where someone is (#312).
//
// The case that matters most here is the one that used to be invisible: three
// of these states never resolve, and the header told all three of them to keep
// waiting.

import { describe, it, expect } from 'vitest'
import { positionLine, type PositionLineInputs } from './positionLine'
import type { GeolocationState } from './useGeolocation'

const LOCATED: GeolocationState = {
  status: 'located',
  at: { lon: -77, lat: 39 },
  accuracyFeet: 16,
  fixedAt: new Date('2026-08-07T12:00:00Z'),
}

/** A hiker with location on, a fix, and their trail data loaded. */
const WALKING: PositionLineInputs = {
  gps: LOCATED,
  enabled: true,
  mile: 1407.2,
  direction: 'NOBO',
  trailReady: true,
}

describe('positionLine', () => {
  it('reads the mile and the direction once both are known', () => {
    expect(positionLine(WALKING)).toBe('mi 1,407.2 · NOBO')
  })

  it('drops the direction until enough walking has settled it', () => {
    expect(positionLine({ ...WALKING, direction: undefined })).toBe('mi 1,407.2')
  })

  it('keeps the mile one decimal wide so the header cannot twitch', () => {
    // Fixed precision and a thousands separator, carried over from the header
    // unchanged: a number that changes width as someone walks moves every
    // control beside it.
    expect(positionLine({ ...WALKING, mile: 8 })).toBe('mi 8.0 · NOBO')
    expect(positionLine({ ...WALKING, mile: 1043.25 })).toBe('mi 1,043.3 · NOBO')
  })

  it('says location is off rather than pretending to look for it', () => {
    // The state a skipped onboarding step leaves behind, which had no words of
    // its own for the life of the install. It outranks the hook's `idle`,
    // which is what the hook reports when it has not started and says nothing
    // about why.
    expect(positionLine({ ...WALKING, enabled: false, gps: { status: 'idle' } })).toBe(
      'Location is off',
    )
  })

  it('outranks even a stale fix with the switch being off', () => {
    // Turning location off mid-hike leaves the last fix in the hook's state.
    // Reporting the mile from it would be a live-looking claim about a watch
    // that is no longer running.
    expect(positionLine({ ...WALKING, enabled: false })).toBe('Location is off')
  })

  it('names a blocked permission, which no amount of waiting fixes', () => {
    expect(positionLine({ ...WALKING, gps: { status: 'denied' } })).toBe(
      'Location blocked',
    )
  })

  it('names a phone with no geolocation at all', () => {
    expect(positionLine({ ...WALKING, gps: { status: 'unsupported' } })).toBe(
      'No GPS on this phone',
    )
  })

  it('says there is no signal rather than that it is still looking', () => {
    // Not settled - the watch is still running and the next fix flips this
    // back - but "Looking for GPS…" over a lost fix reads as progress, and a
    // hiker deciding whether to walk on for signal deserves the difference.
    expect(positionLine({ ...WALKING, gps: { status: 'unavailable' } })).toBe(
      'No GPS signal',
    )
  })

  it('is still allowed to say it is looking, while it genuinely is', () => {
    expect(positionLine({ ...WALKING, gps: { status: 'locating' } })).toBe(
      'Looking for GPS…',
    )
  })

  it('blames the missing trail data rather than the hiker’s position', () => {
    // The distinction this input exists for. Without the centerline there is
    // no mile to compute, and "Off the trail" to someone standing on it -
    // because their download has not landed - is a confident false statement
    // about the one thing this line answers.
    expect(positionLine({ ...WALKING, trailReady: false, mile: undefined })).toBe(
      'No trail data',
    )
  })

  it('says off the trail when a real fix cannot be placed on it', () => {
    expect(positionLine({ ...WALKING, mile: undefined })).toBe('Off the trail')
  })
})
