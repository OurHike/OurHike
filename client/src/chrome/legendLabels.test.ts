import { describe, it, expect } from 'vitest'
import { typeLabel } from './legendLabels'
import { POI_TYPES } from '../lib/config'

// One place that turns a pipeline `type` string into words a hiker reads -
// shared by the legend and the search results so the same thing is never
// called two different names on two screens.

describe('typeLabel', () => {
  it('gives every published POI type a human label', () => {
    for (const type of POI_TYPES) {
      expect(typeLabel(type)).not.toBe(type)
    }
  })

  it('labels the two map-only types the legend also has to name', () => {
    expect(typeLabel('closure')).toBe('Closure')
    expect(typeLabel('serious-warning')).toBe('Serious warning')
  })

  it('shows an unknown type as itself rather than as nothing', () => {
    // The pipeline can publish a type this build predates. Showing the raw
    // string is honest and still findable; showing a blank row, or "undefined",
    // hides a real thing that is on the trail.
    expect(typeLabel('yurt')).toBe('yurt')
  })
})
