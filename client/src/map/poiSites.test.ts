import { describe, it, expect } from 'vitest'
import {
  SITE_MEMBER_TYPES,
  SITE_ROLE_ANCHOR,
  SITE_ROLE_MEMBER,
  composeSites,
  siteDistanceMeters,
  siteMembersKey,
  siteRoster,
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

// The other half of the same fix (#526). One pin means the members have nowhere
// to be read, so the card has to list them - and what it lists them from is this
// roster, which unlike `composeSites` has to keep hold of the points themselves.
describe('siteRoster', () => {
  it('lists every part of the place, the anchor first', () => {
    // Anchor first because the card puts it first: it is the pin that was
    // tapped, and it is the way back once a member has replaced the body.
    const roster = siteRoster([PRIVY, SHELTER, CAMPSITE], SHELTER.id)

    expect(roster.map((part) => part.id)).toEqual([
      'atc_shelter_0421',
      'atc_privy_0421',
      'atc_campsite_0421',
    ])
  })

  it('orders the members the way a pin lists them, not the way they arrived', () => {
    // Same fixed order as the glyph strip, and for a reason the strip's own
    // comment gives: one site should produce one shape. A strip whose chips
    // reshuffled between two renders of the same place would be unlearnable.
    const water = point({
      id: 'opentrail_water_0421',
      type: 'water',
      siteId: 'site_0421',
      siteRole: SITE_ROLE_MEMBER,
    })
    const roster = siteRoster([CAMPSITE, water, PRIVY, SHELTER], SHELTER.id)

    expect(roster.map((part) => part.type)).toEqual([
      'shelter',
      'privy',
      'water',
      'campsite',
    ])
  })

  it('keeps both of two privies at one place, rather than one chip for the pair', () => {
    // Where this parts company with composeSites, which counts members by
    // DISTINCT CATEGORY because a 38px pin only has to answer "is there one".
    // A chip has to LEAD somewhere, so collapsing these would leave one of them
    // exactly as unreachable as it was before this issue - and they are real:
    // features/POI_SITES.md's open question 4 names the "Upper"/"Lower" pair.
    const lower = point({
      id: 'atc_privy_0421_lower',
      type: 'privy',
      siteId: 'site_0421',
      siteRole: SITE_ROLE_MEMBER,
    })
    const roster = siteRoster([SHELTER, lower, PRIVY], SHELTER.id)

    expect(roster.map((part) => part.id)).toEqual([
      'atc_shelter_0421',
      'atc_privy_0421',
      'atc_privy_0421_lower',
    ])
  })

  it('gives a member category this build has never heard of a place in the row', () => {
    // Filtering to the three known member types would be the shorter line and
    // would make a category a later release publishes unreachable from the only
    // card that leads to it, which is the bug this whole issue is about. It
    // sorts last; the neutral pin says it is unfamiliar.
    const bear = point({
      id: 'atc_bearbox_0421',
      type: 'bear_box',
      siteId: 'site_0421',
      siteRole: SITE_ROLE_MEMBER,
    })
    const roster = siteRoster([SHELTER, bear, CAMPSITE], SHELTER.id)

    expect(roster.map((part) => part.type)).toEqual(['shelter', 'campsite', 'bear_box'])
  })

  it('answers the same roster for a member as for its anchor', () => {
    // The site is a fact about the place, not about which of its points was
    // asked - and search opening a privy's card directly is the next issue.
    expect(
      siteRoster([SHELTER, PRIVY, CAMPSITE], PRIVY.id).map((part) => part.id),
    ).toEqual(siteRoster([SHELTER, PRIVY, CAMPSITE], SHELTER.id).map((part) => part.id))
  })

  it('has no site to show when the anchor is not here', () => {
    // composeSites' rule in reverse. It refuses to drop a member whose anchor is
    // absent, so that privy is over there drawing its own pin - and a strip
    // listing it as part of something the map is not drawing would point at
    // nothing.
    expect(siteRoster([PRIVY, CAMPSITE], PRIVY.id)).toEqual([])
  })

  it('has no site to show for a waypoint that is in none', () => {
    // The pre-#523 download, and most POIs even after it: the card must render
    // exactly as it did before sites existed.
    const spring = point({ id: 'opentrail_spring_88', type: 'water' })

    expect(siteRoster([SHELTER, PRIVY, spring], spring.id)).toEqual([])
  })

  it('has no site to show for a role this build cannot read', () => {
    // Same call composeSites makes on an unfamiliar role: the point keeps its own
    // pin, so its card is the plain card. Claiming it as part of a site would
    // put it in a strip that does not contain it.
    const future = point({
      id: 'atc_future_0421',
      type: 'privy',
      siteId: 'site_0421',
      siteRole: 'annex',
    })

    expect(siteRoster([SHELTER, future], future.id)).toEqual([])
  })

  it('has nothing to say about a waypoint it does not hold', () => {
    expect(siteRoster([SHELTER, PRIVY], 'atc_shelter_9999')).toEqual([])
  })
})

describe('siteDistanceMeters', () => {
  it('measures a member’s offset in metres', () => {
    // 0.001 degrees of latitude, which is 111.32 m by the constant the pipeline
    // uses - a hand-checkable case rather than a re-derivation.
    const distance = siteDistanceMeters(
      { lat: 35.7, lon: -83.2 },
      { lat: 35.701, lon: -83.2 },
    )

    expect(distance).toBeCloseTo(111.32, 2)
  })

  it('shrinks a degree of longitude by the latitude it is measured at', () => {
    // The whole reason this is not flat arithmetic on degrees: at 35.7°N a
    // longitude degree is about 81% of a latitude one, and the trail spans 34-46°.
    const east = siteDistanceMeters(
      { lat: 35.7, lon: -83.2 },
      { lat: 35.7, lon: -83.199 },
    )

    expect(east).toBeCloseTo(111.32 * Math.cos((35.7 * Math.PI) / 180), 2)
    expect(east).toBeLessThan(111.32)
  })

  it('agrees with the pipeline gate that admitted the member', () => {
    // The measurement that decided this privy belongs to this shelter is
    // pipeline/lib/spurs.py's distance_m against a 60 m proximity gate, and the
    // furthest real member came in at 143 m. A card that computed the offset a
    // different way would put a different number on it from the one that grouped
    // it. Diagonal, so both terms are exercised at once.
    const distance = siteDistanceMeters(
      { lat: 44.0, lon: -70.0 },
      { lat: 44.0005, lon: -70.0005 },
    )

    const dy = 0.0005 * 111_320
    const dx = 0.0005 * 111_320 * Math.cos((44.00025 * Math.PI) / 180)
    expect(distance).toBeCloseTo(Math.hypot(dx, dy), 6)
  })

  it('is zero for a point against itself', () => {
    expect(siteDistanceMeters(SHELTER, SHELTER)).toBe(0)
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
