// Tests for planDisplay.ts (#756).

import { describe, expect, it } from 'vitest'

import {
  dayDateLabel,
  dayRowHeight,
  MIN_ROW_PX,
  ROW_CHROME_PX,
  ROW_PX_PER_WALKING_HOUR,
  stopLabel,
} from './planDisplay'

describe('stopLabel', () => {
  it('prefers the place’s name', () => {
    expect(stopLabel({ mile: 470.8, name: 'Damascus' })).toBe('Damascus')
  })

  it('falls back to the mile marker, grouped and never converted', () => {
    // A mile MARKER is a shared reference, not a distance - positionLine.ts
    // and units.ts both hold this line, and this label joins them.
    expect(stopLabel({ mile: 1407.2 })).toBe('mi 1,407.2')
    expect(stopLabel({ mile: 5, name: '' })).toBe('mi 5.0')
  })
})

describe('dayDateLabel', () => {
  it('reads the date in UTC, so it cannot shift with the phone', () => {
    expect(dayDateLabel('2026-05-12')).toBe('TUE 12')
    expect(dayDateLabel('2026-05-14')).toBe('THU 14')
  })
})

describe('dayRowHeight', () => {
  it('scales with walking hours - the timeline’s one physical encoding', () => {
    const seven = dayRowHeight(7 * 60)
    const eight = dayRowHeight(8 * 60)
    expect(eight - seven).toBe(ROW_PX_PER_WALKING_HOUR)
    expect(seven).toBe(7 * ROW_PX_PER_WALKING_HOUR + ROW_CHROME_PX)
  })

  it('never drops below the touch-target floor', () => {
    expect(dayRowHeight(0)).toBe(MIN_ROW_PX)
    expect(dayRowHeight(30)).toBe(MIN_ROW_PX)
  })
})
