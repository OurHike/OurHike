import { describe, it, expect } from 'vitest'
import {
  ESTIMATE_MARK,
  MEASURED_WATER_SOURCES,
  estimateMark,
  formatWaterDistance,
  waterDistanceIsEstimate,
} from './waterProvenance'

// Where a stated water distance came from, and the one mark this app puts in
// front of an estimate (#1728). The maintainer chose the tilde by poll,
// 2026-09-30; what these pin is which provenances earn it and which do not.

describe('a stated water distance and where ATC got it', () => {
  it('reads OSA_Field_Estimate as an estimate and the three measured provenances as not one', () => {
    expect(waterDistanceIsEstimate('OSA_Field_Estimate')).toBe(true)
    expect(estimateMark('OSA_Field_Estimate')).toBe(ESTIMATE_MARK)
    for (const source of MEASURED_WATER_SOURCES) {
      expect(waterDistanceIsEstimate(source)).toBe(false)
      expect(estimateMark(source)).toBe('')
    }
    expect([...MEASURED_WATER_SOURCES].sort()).toEqual([
      'FarOut',
      'NHDP_HR_Pond',
      'NHDP_HR_Stream',
    ])
  })

  it('reads a provenance this build does not know as an estimate, and no provenance as nothing', () => {
    // The cautious direction runs one way. A value the pipeline learned to
    // publish before this set did reads as an estimate, because a tilde on
    // a measurement costs less than a bare figure on an estimate; an ABSENT
    // provenance - a download from before the column - gets no mark, because
    // marking every row would call the 263 measured ones estimates too.
    expect(waterDistanceIsEstimate('Something_ATC_Adds_Later')).toBe(true)
    expect(waterDistanceIsEstimate(undefined)).toBe(false)
    expect(estimateMark(undefined)).toBe('')
  })

  it('puts the mark in front of the figure in either unit, floored like every stated distance', () => {
    expect(formatWaterDistance(250, 'OSA_Field_Estimate', 'imperial')).toBe('~250 ft')
    expect(formatWaterDistance(250, 'OSA_Field_Estimate', 'metric')).toBe('~76 m')
    expect(formatWaterDistance(339, 'NHDP_HR_Stream', 'imperial')).toBe('339 ft')
    expect(formatWaterDistance(120, undefined, 'imperial')).toBe('120 ft')
    // lib/units.ts's MIN_STATED_FEET: a published zero prints as the metre it
    // rounds up to, never as "walk zero feet", in both voices.
    expect(formatWaterDistance(0, 'OSA_Field_Estimate', 'imperial')).toBe('~3 ft')
    expect(formatWaterDistance(0, 'FarOut', 'metric')).toBe('1 m')
  })
})
