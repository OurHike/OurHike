import { describe, it, expect } from 'vitest'
import {
  SITE_MEMBER_TYPES,
  SITE_ROLE_ANCHOR,
  SITE_ROLE_MEMBER,
  composeSites,
  siteMembersKey,
  type SitePoint,
} from './poiSites'

// One pin per site (#524). What is asserted here is which points survive into
// the source and what the surviving pin says, because that is the whole of the
// fix: 3% of privies place at z14 while they compete for a box, and 91% of
// shelters do, so a privy that rides a shelter pin is a privy a hiker can see.

function point(overrides: Partial<SitePoint> & { id: string; type: string }): SitePoint {
  return {
    lat: 35.7,
    lon: -83.2,
    confidence: 'high',
    ...overrides,
  }
}

const SHELTER = point({
  id: 'atc_shelter_0421',
  type: 'shelter',
  siteId: 'site_0421',
  siteRole: SITE_ROLE_ANCHOR,
})
const PRIVY = point({
  id: 'atc_privy_0421',
  type: 'privy',
  siteId: 'site_0421',
  siteRole: SITE_ROLE_MEMBER,
})
const CAMPSITE = point({
  id: 'atc_campsite_0421',
  type: 'campsite',
  siteId: 'site_0421',
  siteRole: SITE_ROLE_MEMBER,
})

describe('composeSites', () => {
  it('draws one pin for a site, at the anchor', () => {
    const { drawn } = composeSites([SHELTER, PRIVY, CAMPSITE])

    expect(drawn.map((p) => p.id)).toEqual(['atc_shelter_0421'])
  })

  it('says what the anchor is carrying', () => {
    const { membersFor } = composeSites([SHELTER, PRIVY, CAMPSITE])

    expect(membersFor.get('atc_shelter_0421')).toEqual(['privy', 'campsite'])
  })

  it('lists members in a fixed order whatever order they arrive in', () => {
    // One site must produce one icon id, or the matrix in poiIcons.ts needs an
    // arm per permutation and a re-ordered artifact silently asks for an image
    // that was never registered.
    const forwards = composeSites([SHELTER, PRIVY, CAMPSITE]).membersFor.get(SHELTER.id)
    const backwards = composeSites([CAMPSITE, PRIVY, SHELTER]).membersFor.get(SHELTER.id)

    expect(forwards).toEqual(backwards)
  })

  it('counts distinct categories rather than members', () => {
    // Four campsites at one shelter say "campsite", not "campsite ×4". The
    // question at a shelter is whether there is one.
    const site = composeSites([
      SHELTER,
      point({
        id: 'c1',
        type: 'campsite',
        siteId: 'site_0421',
        siteRole: SITE_ROLE_MEMBER,
      }),
      point({
        id: 'c2',
        type: 'campsite',
        siteId: 'site_0421',
        siteRole: SITE_ROLE_MEMBER,
      }),
      point({
        id: 'c3',
        type: 'campsite',
        siteId: 'site_0421',
        siteRole: SITE_ROLE_MEMBER,
      }),
    ])

    expect(site.membersFor.get(SHELTER.id)).toEqual(['campsite'])
  })

  it('leaves a POI in no site exactly as it was', () => {
    // A phone that downloaded before #523 has no site fields on anything, and
    // must draw the map it drew before rather than an empty one.
    const loose = point({ id: 'water_1188', type: 'water' })

    const { drawn, membersFor } = composeSites([loose])

    expect(drawn).toEqual([loose])
    expect(membersFor.size).toBe(0)
  })

  it('keeps a member drawing its own pin when the anchor is not here', () => {
    // THE CASE THAT MUST NOT SILENTLY LOSE A PIN. Dropping a member on the
    // strength of its `site_id` alone means anything that removes the anchor -
    // a partial download, a grouping naming a POI this build never received -
    // removes the privy with it, leaving the hiker neither pin.
    const { drawn, membersFor } = composeSites([PRIVY])

    expect(drawn.map((p) => p.id)).toEqual(['atc_privy_0421'])
    expect(membersFor.size).toBe(0)
  })

  it('draws a plain pin for an anchor whose members are all absent', () => {
    const { drawn, membersFor } = composeSites([SHELTER])

    expect(drawn.map((p) => p.id)).toEqual([SHELTER.id])
    expect(membersFor.has(SHELTER.id)).toBe(false)
  })

  it('keeps two sites apart', () => {
    const otherShelter = point({
      id: 'shelter_b',
      type: 'shelter',
      siteId: 'site_b',
      siteRole: SITE_ROLE_ANCHOR,
    })
    const otherWater = point({
      id: 'water_b',
      type: 'water',
      siteId: 'site_b',
      siteRole: SITE_ROLE_MEMBER,
    })

    const { drawn, membersFor } = composeSites([SHELTER, PRIVY, otherShelter, otherWater])

    expect(drawn.map((p) => p.id).sort()).toEqual(['atc_shelter_0421', 'shelter_b'])
    expect(membersFor.get(SHELTER.id)).toEqual(['privy'])
    expect(membersFor.get('shelter_b')).toEqual(['water'])
  })

  it('ignores a site role it does not recognise', () => {
    // A later release could add one. An unknown role must draw its own pin
    // rather than vanish - the same "undefined is not a claim" rule the
    // confidence field follows.
    const odd = point({
      id: 'odd',
      type: 'privy',
      siteId: 'site_0421',
      siteRole: 'satellite',
    })

    expect(composeSites([SHELTER, odd]).drawn.map((p) => p.id)).toContain('odd')
  })

  it('ignores a role with no site id behind it', () => {
    const broken = point({ id: 'broken', type: 'privy', siteRole: SITE_ROLE_MEMBER })

    expect(composeSites([SHELTER, broken]).drawn.map((p) => p.id)).toContain('broken')
  })

  it('never lists a category that cannot be a member', () => {
    // The pipeline's MEMBER_TYPES are privy, campsite and water. A viewpoint
    // marked as a member is a data fault, and inventing a fourth glyph slot for
    // it would ask the style for an image that was never built.
    const viewpoint = point({
      id: 'v1',
      type: 'viewpoint',
      siteId: 'site_0421',
      siteRole: SITE_ROLE_MEMBER,
    })

    const { membersFor } = composeSites([SHELTER, PRIVY, viewpoint])

    expect(membersFor.get(SHELTER.id)).toEqual(['privy'])
  })
})

describe('siteMembersKey', () => {
  it('is empty for a pin carrying nothing, rather than absent', () => {
    // The style reads this property on every pin, so it is always present and
    // the expression needs no `coalesce`.
    expect(siteMembersKey(undefined)).toBe('')
  })

  it('joins the categories in the order they were listed', () => {
    expect(siteMembersKey(['privy', 'water'])).toBe('privy+water')
  })

  it('is stable for one site, which is what the icon matrix is keyed on', () => {
    const { membersFor } = composeSites([SHELTER, CAMPSITE, PRIVY])

    expect(siteMembersKey(membersFor.get(SHELTER.id))).toBe('privy+campsite')
  })
})

describe('SITE_MEMBER_TYPES', () => {
  it('is the pipeline’s three member categories', () => {
    // pipeline/lib/poi_sites.py's MEMBER_TYPES. A fourth here would need a
    // fourth glyph slot and a wider icon matrix; a missing one silently stops
    // being reported on any pin.
    expect([...SITE_MEMBER_TYPES].sort()).toEqual(['campsite', 'privy', 'water'])
  })

  it('bounds the icon matrix at seven member combinations', () => {
    // The argument for the glyph strip that is not about looks: distinct
    // categories are at most three, so the strip needs 2^3 - 1 = 7 variants per
    // anchor and confidence, all pre-registerable. A `+N` badge is unbounded in
    // N - a site with five campsites wants a "+5" image nobody built.
    const combinations = 2 ** SITE_MEMBER_TYPES.length - 1

    expect(combinations).toBe(7)
  })
})
