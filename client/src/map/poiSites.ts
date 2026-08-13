// One pin per SITE rather than one per POI (#524, features/POI_SITES.md).
//
// THE PROBLEM IS NOT OVERLAP, IT IS DELETION. map/poiLayers.ts sets
// `icon-allow-overlap: false` deliberately, so MapLibre draws no two colliding
// pins - it drops whichever loses POI_PRIORITY. Privies lose to shelters and sit
// a median 42 m from theirs, so simulating placement over the whole corridor puts
// the share of privies drawn ANYWHERE on the trail at 3% at zoom 14, and
// `BASEMAP_MAX_ZOOM` is 14, so that is the zoom an offline hiker lives at. The
// privy layer, added at real download cost in #510, effectively does not exist.
// A hiker sees a clean map and concludes there is no privy.
//
// That is not a bug in POI_PRIORITY. It is the right answer to the wrong
// question: where two pins describe PARTS OF THE SAME PLACE, "which one
// survives" has no acceptable answer. So the members stop competing. They are
// removed from the source, and the anchor's pin says what is there.
//
// The measured effect, from #523's grouping over the live corridor: 284 of 316
// privies and 144 of 232 campsites stop asking for a box, and start riding a pin
// that places at 91% at z14.
//
// WHAT THIS DELIBERATELY IS NOT:
//
//  - Not a change to `icon-allow-overlap`. Letting pins overlap is the symptom
//    the original complaint started from. Sites remove the colliding pins; the
//    collision engine keeps doing its job on what is left, and two shelters
//    400 m apart still collide at z12, correctly.
//  - Not a clustering layer. A crowded ridge of viewpoints is still the
//    collision engine's problem, and #531's is the zoom tiering.
//  - Not spiderfying. Fanning members out on leader lines draws every member at
//    a position it is not at. This app refuses to draw a stale GPS fix like a
//    live one; drawing a privy 80 px from where it is, is the same refusal.

import type { MapPoint } from '../lib/legendContents'

/** What `site_role` says on a published feature - pipeline/lib/poi_sites.py. */
export const SITE_ROLE_ANCHOR = 'anchor'
export const SITE_ROLE_MEMBER = 'member'

/**
 * The feature property naming what a site pin carries.
 *
 * A property rather than a separate layer, for the reason POI_ID_PROPERTY is one:
 * the style has to reach it from a `match` expression, and MapLibre gives an
 * expression the properties of the feature it is placing and nothing else.
 */
export const SITE_MEMBERS_PROPERTY = 'site_members'

/**
 * The categories that can ride an anchor's pin, in the order a pin lists them.
 *
 * The same three `MEMBER_TYPES` the pipeline groups on, and the order is fixed
 * here rather than taken from the data so that one site always produces one icon
 * id. Sorted by what a hiker asks first at a shelter: features/POI_SITES.md's own
 * framing is "is there a privy, and is there water", and a campsite is the one of
 * the three you can see for yourself once you are standing there.
 */
export const SITE_MEMBER_TYPES = ['privy', 'water', 'campsite'] as const

/**
 * The categories that can ANCHOR a site - pipeline/lib/poi_sites.py's
 * ANCHOR_TYPES.
 *
 * Only these get site pin variants built, because only these can ever carry a
 * footer strip. A viewpoint given the full member matrix would be fourteen
 * images the style can never ask for.
 */
export const SITE_ANCHOR_TYPES = ['shelter', 'campsite'] as const

/**
 * A map point that may belong to a site.
 *
 * All three fields optional, and for the reason `StoredPoi.source` is: a phone
 * that downloaded before #523 published them has POIs without any, and undefined
 * means "this copy predates the grouping" rather than "this POI is not in a
 * site". Both come out as a plain pin, which is exactly what that phone drew
 * before, so an old download degrades to the old behaviour instead of to a blank
 * map.
 */
export interface SitePoint extends MapPoint {
  siteId?: string
  siteRole?: string
}

export interface SiteComposition {
  /** The points that get a pin of their own: every anchor, and everything that
   *  is not in a site at all. */
  drawn: readonly SitePoint[]
  /** Per anchor id, the distinct member categories riding its pin, in
   *  `SITE_MEMBER_TYPES` order. Absent for a point that carries nothing. */
  membersFor: ReadonlyMap<string, readonly string[]>
}

/**
 * Which points draw a pin, and what each site pin has to say.
 *
 * A MEMBER WHOSE ANCHOR IS NOT HERE KEEPS ITS OWN PIN. That is the case worth
 * spelling out: dropping a member on the strength of its `site_id` alone would
 * mean that anything removing the anchor from this list - a future filter, a
 * partial download, a grouping written against a POI this build never received -
 * silently removes the privy too. The hiker would be left with neither pin and no
 * way to discover either. So the drop is conditional on the pin that replaces it
 * actually being drawn.
 *
 * Members are counted by DISTINCT CATEGORY, not by count. A site with four
 * campsites says "campsite", not "campsite ×4": the question at a shelter is
 * whether there is one, and a number answers a question nobody asked - the same
 * reasoning features/POI_SITES.md gives for rejecting a bare `+N` bubble.
 */
export function composeSites(points: readonly SitePoint[]): SiteComposition {
  const anchors = new Set<string>()
  for (const point of points) {
    if (point.siteRole === SITE_ROLE_ANCHOR && point.siteId !== undefined) {
      anchors.add(point.siteId)
    }
  }

  const members = new Map<string, Set<string>>()
  const drawn: SitePoint[] = []

  for (const point of points) {
    const ridesAnchor =
      point.siteRole === SITE_ROLE_MEMBER &&
      point.siteId !== undefined &&
      anchors.has(point.siteId)

    if (!ridesAnchor) {
      drawn.push(point)
      continue
    }

    const carried = members.get(point.siteId!) ?? new Set<string>()
    carried.add(point.type)
    members.set(point.siteId!, carried)
  }

  // Keyed by ANCHOR ID rather than site id, because that is what the feature
  // collection has to hand when it writes the property - one lookup at build
  // time instead of a second index from site id back to anchor.
  const membersFor = new Map<string, readonly string[]>()
  for (const point of drawn) {
    if (point.siteRole !== SITE_ROLE_ANCHOR || point.siteId === undefined) continue
    const carried = members.get(point.siteId)
    if (carried === undefined || carried.size === 0) continue
    membersFor.set(
      point.id,
      SITE_MEMBER_TYPES.filter((type) => carried.has(type)),
    )
  }

  return { drawn, membersFor }
}

/**
 * Every POI at one site, the anchor first, for the card that has to lead to
 * them (#526).
 *
 * A SIBLING OF `composeSites` RATHER THAN A SECOND READING OF IT. That function
 * answers what a PIN says and deliberately throws away everything a card needs:
 * its members are distinct category strings keyed by anchor id, so a site with
 * two privies collapses to one entry and neither privy has an id left to open.
 * Correct for a 38 px pin, fatal for a strip that has to lead somewhere - the
 * "Backpacker Campsite Upper Privy" / "...Lower Privy" pair in
 * features/POI_SITES.md's open question 4 is two real points at one place, and
 * both must be reachable. So this keys on POI id and returns the points
 * themselves.
 *
 * Generic over the point type, which is what lets the shell pass its stored
 * POIs - names, photos, descriptions and all - and get them back without an
 * adapter type in between, while this file still knows nothing about
 * lib/trailData.ts.
 *
 * IT MIRRORS `composeSites`' RULE, IN REVERSE. There is no site here unless the
 * anchor is: a member whose anchor is missing from `points` - a partial
 * download, a future filter - is drawing its own pin, so listing it as part of
 * something the map is not drawing would be a strip hanging off nothing. Same
 * for a role this build does not recognise: the point keeps its own pin over
 * there, so its card is the plain card, not a site's.
 */
export function siteRoster<T extends SitePoint>(
  points: readonly T[],
  poiId: string,
): readonly T[] {
  const found = points.find((point) => point.id === poiId)
  if (found === undefined || found.siteId === undefined) return []
  if (found.siteRole !== SITE_ROLE_ANCHOR && found.siteRole !== SITE_ROLE_MEMBER)
    return []

  const siteId = found.siteId
  const anchor = points.find(
    (point) => point.siteId === siteId && point.siteRole === SITE_ROLE_ANCHOR,
  )
  if (anchor === undefined) return []

  const members = points.filter(
    (point) => point.siteId === siteId && point.siteRole === SITE_ROLE_MEMBER,
  )
  members.sort(
    (a, b) => memberRank(a.type) - memberRank(b.type) || compareIds(a.id, b.id),
  )

  return [anchor, ...members]
}

/**
 * Where a member type sorts in the strip - `SITE_MEMBER_TYPES` order, and
 * anything else after it rather than dropped.
 *
 * Filtering to the known three would be the shorter line and would make a
 * member type a later release publishes unreachable from its own site's card,
 * which is the exact bug #526 exists to fix. An unfamiliar category sorts last
 * and still gets a chip; the neutral diamond pin MapIcon draws for it says it
 * is something this build has not heard of.
 */
function memberRank(type: string): number {
  const at = (SITE_MEMBER_TYPES as readonly string[]).indexOf(type)
  return at === -1 ? SITE_MEMBER_TYPES.length : at
}

/** A stable tiebreak inside one category, so two privies at one campsite come
 *  out in the same order on every render. By id and not by name because a
 *  `SitePoint` carries no name - this file's whole input is geometry and site
 *  keys - and an unstable strip is worse than an arbitrary one. */
function compareIds(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0
}

/** Metres per degree of latitude, and of longitude at the equator -
 *  pipeline/lib/spurs.py's `METERS_PER_DEGREE`. */
const METERS_PER_DEGREE = 111_320

/**
 * How far apart two points at one site are, in metres.
 *
 * Equirectangular, not haversine, and copied from the pipeline's `distance_m`
 * (pipeline/lib/spurs.py) on purpose: THAT is the measurement that decided this
 * member belongs to this site - a 60 m proximity gate and a 150 m name gate,
 * with the furthest real member at 143 m. A second formula here would put a
 * different number on the card from the one that admitted the point, which is
 * the drift map/MapIcon.ts's header calls the one failure a symbol cannot
 * survive, in arithmetic. Its own docstring gives the accuracy: under a
 * kilometre the flat approximation is good to well under 1%, and `cos()` at the
 * midpoint latitude is what keeps a longitude degree honest across the trail's
 * 34-46 degree span.
 */
export function siteDistanceMeters(
  from: { lat: number; lon: number },
  to: { lat: number; lon: number },
): number {
  const meanLat = (((from.lat + to.lat) / 2) * Math.PI) / 180
  const dy = (to.lat - from.lat) * METERS_PER_DEGREE
  const dx = (to.lon - from.lon) * METERS_PER_DEGREE * Math.cos(meanLat)
  return Math.hypot(dx, dy)
}

/**
 * The member list as one property value, for the style to `match` on.
 *
 * A sorted, joined string rather than an array because a MapLibre `match`
 * expression compares scalars, and the icon matrix is keyed on exactly this -
 * see map/poiIcons.ts. Empty string for a pin carrying nothing, so the property
 * is always present and the expression needs no `coalesce`.
 */
export function siteMembersKey(members: readonly string[] | undefined): string {
  return members === undefined ? '' : members.join('+')
}
