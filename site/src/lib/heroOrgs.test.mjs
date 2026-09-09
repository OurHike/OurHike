import { describe, expect, it } from 'vitest'
import { ORGS, allSlides, orgCountLine } from './heroOrgs.mjs'

describe('the real roster', () => {
  it('names the count line after however many organizations are registered', () => {
    expect(orgCountLine(ORGS)).toBe(
      `${ORGS.length} organizations sharing all their trails and paths`
    )
  })

  it('puts every organization’s lines into the rotation', () => {
    const slides = allSlides(ORGS)
    for (const org of ORGS) {
      for (const line of org.lines) {
        expect(slides).toContain(line)
      }
    }
  })

  it('has no line repeated across organizations', () => {
    const lines = ORGS.flatMap((org) => org.lines)
    expect(new Set(lines).size).toBe(lines.length)
  })

  it('gives every organization a real lat/lon and at least one line', () => {
    for (const org of ORGS) {
      expect(org.lines.length).toBeGreaterThan(0)
      expect(Number.isFinite(org.lat)).toBe(true)
      expect(Number.isFinite(org.lon)).toBe(true)
    }
  })
})

describe('adding a new organization later', () => {
  // The regression this guards against: #1059 was exactly this bug - the
  // count line and several credits strings were hand-typed numbers/names
  // that stayed frozen at "one organization" while the roster grew to five.
  // This constructs a sixth, synthetic organization to prove the rotation
  // actually grows with the roster rather than needing to be told to.
  const sixthOrg = {
    lines: ['A sixth line for a sixth organization.', 'And its second line.'],
    lat: 0,
    lon: 0,
  }
  const grown = [...ORGS, sixthOrg]

  it('bumps the count line to match', () => {
    expect(orgCountLine(grown)).toBe(orgCountLine(ORGS).replace(/^\d+/, String(grown.length)))
  })

  it('adds exactly the new lines to the rotation, without dropping any old ones', () => {
    const after = allSlides(grown)

    // The count line itself is meant to change (5 orgs -> 6) - that's the
    // previous test's job. What this one checks is that growing the roster
    // is purely additive to every ORGANIZATION's own lines.
    const oldOrgLines = ORGS.flatMap((org) => org.lines)
    expect(after.length).toBe(1 + oldOrgLines.length + sixthOrg.lines.length)
    for (const line of oldOrgLines) {
      expect(after).toContain(line)
    }
    for (const line of sixthOrg.lines) {
      expect(after).toContain(line)
    }
  })
})
