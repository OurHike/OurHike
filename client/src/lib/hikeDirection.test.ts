import { describe, it, expect } from 'vitest'
import { DIRECTION_THRESHOLD_MILES, startTracking, trackDirection } from './hikeDirection'

describe('hike direction', () => {
  it('does not claim a direction before anyone has gone anywhere', () => {
    expect(startTracking(1000).direction).toBeUndefined()
  })

  it('holds its silence while the fix only wanders', () => {
    // GPS under tree cover moves by tens of feet with the phone in a pocket.
    // Reacting to that would flip the header back and forth at a lunch stop.
    let tracker = startTracking(1000)
    for (const mile of [1000.01, 999.99, 1000.02, 999.98]) {
      tracker = trackDirection(tracker, mile)
    }

    expect(tracker.direction).toBeUndefined()
  })

  it('reads increasing miles as northbound once the threshold is passed', () => {
    const tracker = trackDirection(startTracking(1000), 1000 + DIRECTION_THRESHOLD_MILES)

    expect(tracker.direction).toBe('NOBO')
  })

  it('reads decreasing miles as southbound', () => {
    const tracker = trackDirection(startTracking(1000), 1000 - DIRECTION_THRESHOLD_MILES)

    expect(tracker.direction).toBe('SOBO')
  })

  it('follows a turnaround without first undoing the whole walk', () => {
    // The anchor resets each time direction is settled, so someone who walks
    // ten miles north and then turns back reads SOBO after a quarter mile -
    // not after re-walking the ten.
    let tracker = startTracking(1000)
    tracker = trackDirection(tracker, 1010)
    expect(tracker.direction).toBe('NOBO')

    tracker = trackDirection(tracker, 1010 - DIRECTION_THRESHOLD_MILES)
    expect(tracker.direction).toBe('SOBO')
  })

  it('keeps the direction it had while movement stays under the threshold', () => {
    const northbound = trackDirection(startTracking(1000), 1001)
    const stillNorthbound = trackDirection(northbound, 1001.01)

    expect(stillNorthbound.direction).toBe('NOBO')
  })
})
