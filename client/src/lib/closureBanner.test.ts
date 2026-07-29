import { describe, it, expect } from 'vitest'
import { closureBanner, closureReasonLabel } from './closureBanner'

// WIREFRAMES.md §7's header banner: "Trail closed 1.4 mi ahead · Storm damage
// · mi 1,408.6 – 1,411.0".
//
// "Ahead" depends on which way you are walking, which is the part that is
// easy to get wrong. A NOBO hiker at mile 1,407 has a closure at 1,408.6
// ahead of them; a SOBO hiker at the same spot has already walked through it.
// Telling a southbounder about a closure behind them is noise, and worse,
// silently omitting the one actually in front of them is a real failure.

const CLOSURE = {
  id: 'c1',
  reason_type: 'storm_damage' as const,
  note: null,
  status: 'closed' as const,
  start_mile_marker: 1408.6,
  end_mile_marker: 1411.0,
}

describe('closureBanner', () => {
  it('warns a northbound hiker about a closure up-trail', () => {
    expect(closureBanner(CLOSURE, 1407.2, 'NOBO')).toBe(
      'Trail closed 1.4 mi ahead · Storm damage · mi 1,408.6 – 1,411.0',
    )
  })

  it('says nothing to a northbound hiker who has already passed it', () => {
    expect(closureBanner(CLOSURE, 1412.0, 'NOBO')).toBeNull()
  })

  it('warns a southbound hiker about a closure down-trail', () => {
    // Walking south from 1,412, the closure's far end (1,411.0) comes first.
    expect(closureBanner(CLOSURE, 1412.0, 'SOBO')).toBe(
      'Trail closed 1.0 mi ahead · Storm damage · mi 1,408.6 – 1,411.0',
    )
  })

  it('says nothing to a southbound hiker who has already passed it', () => {
    expect(closureBanner(CLOSURE, 1407.2, 'SOBO')).toBeNull()
  })

  it('warns while standing inside the closure, whichever way they face', () => {
    // 0.0 mi ahead is still very much worth saying.
    expect(closureBanner(CLOSURE, 1409.5, 'NOBO')).toContain('Trail closed')
    expect(closureBanner(CLOSURE, 1409.5, 'SOBO')).toContain('Trail closed')
  })

  it('reports the whole mile range, not just the near edge', () => {
    expect(closureBanner(CLOSURE, 1407.2, 'NOBO')).toContain('1,408.6 – 1,411.0')
  })

  it('says nothing about a closure that is open again', () => {
    const reopened = { ...CLOSURE, status: 'open' as const }

    expect(closureBanner(reopened, 1407.2, 'NOBO')).toBeNull()
  })

  it('still warns when a reroute exists - a reroute is not an all-clear', () => {
    const reroute = { ...CLOSURE, status: 'reroute_available' as const }

    expect(closureBanner(reroute, 1407.2, 'NOBO')).toContain('Trail closed')
  })
})

describe('closureReasonLabel', () => {
  it.each([
    ['storm_damage', 'Storm damage'],
    ['flooding', 'Flooding'],
    ['maintenance', 'Maintenance'],
    ['relocation', 'Trail relocation'],
  ] as const)('says %s in plain language', (reason, label) => {
    expect(closureReasonLabel(reason)).toBe(label)
  })

  it('falls back to plain "Closed" rather than printing a raw enum value', () => {
    expect(closureReasonLabel('other')).toBe('Closed')
  })
})
