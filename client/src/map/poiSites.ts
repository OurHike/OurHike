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
// AND THE FOLD IS CONDITIONAL ON THAT PIN BEING DRAWN (#607). "The anchor's pin
// says what is there" holds only while there IS an anchor's pin: the legend's
// filter works one layer on, so hiding shelters used to take the privies riding
// them off the map as well - filtering to privies drew 32 of the 316. So a site
// whose anchor is filtered out falls back to its highest-priority drawn member,
// and goes dark only when every part of it is hidden. See `SiteVisibility`.
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
import { poiPriorityRank } from './poiPriority'

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
  /** The points that get a pin of their own: each site's carrier, and
   *  everything that is not in a site at all. */
  drawn: readonly SitePoint[]
  /** Per carrier id, the distinct member categories riding its pin, in
   *  `SITE_MEMBER_TYPES` order. Absent for a point that carries nothing. */
  membersFor: ReadonlyMap<string, readonly string[]>
}

/**
 * What the map is currently drawing, in the same two terms poiLayers.ts's
 * `poiFilter` is built from (#607).
 *
 * The composition has to know this. It removes a member from the source on the
 * strength of the anchor's pin replacing it, and the layer filter can take that
 * pin off the map afterwards - at which point the member is gone from both, and
 * the hiker who filtered the legend to privies is looking at a map with no
 * privies on it. Both fields optional and defaulting to "everything is drawn",
 * so a caller that has no filter to apply asks for the composition it always
 * got.
 */
export interface SiteVisibility {
  /** The legend's hidden categories - poiLayers.ts's `poiFilter`, first clause.
   *  Already filtered through `NEVER_HIDEABLE` by lib/waypointVisibility.ts,
   *  which stays the one guard on the safety layers rather than being copied
   *  here. */
  hiddenTypes?: ReadonlySet<string>
  /** The legend's "Verified?" toggle - `poiFilter`'s second clause. The same
   *  hole opens through it: an unverified anchor is taken off the map and its
   *  verified privy goes with it. */
  verifiedOnly?: boolean
}

/** Whether the layer filter would draw this point, had it a pin of its own.
 *
 *  Not exported: it answers `poiFilter`'s question, and poiLayers.ts already
 *  owns that question in the form MapLibre needs. A second exported way to ask
 *  it is a second thing that can drift from the expression actually applied. */
function isPointDrawn(point: SitePoint, visibility: SiteVisibility = {}): boolean {
  if (visibility.hiddenTypes?.has(point.type) === true) return false
  if (visibility.verifiedOnly === true && point.confidence !== 'high') return false
  return true
}

/**
 * Which point of a site carries its one pin.
 *
 * The anchor, whenever the anchor is drawn - that is the ordinary case and the
 * whole of #524. Otherwise the highest-priority DRAWN member, by the same
 * POI_PRIORITY that decides collisions, because "which of these does a hiker
 * most need" is the same question here as it is there: a promoted water source
 * outranks a promoted campsite outranks a promoted privy.
 *
 * NOT every drawn member getting its own pin back. Hide shelters with campsites
 * and privies both shown and that hands the collision engine a campsite and a
 * privy 40 m apart - the campsite wins POI_PRIORITY and the privy disappears,
 * which is the deletion this whole model exists to stop. One pin per site
 * survives; only WHICH point carries it changes.
 *
 * Falls back to the anchor when nothing in the site is drawn at all. The style
 * drops it either way, so this is not a visible choice - it is the invariant
 * that one site contributes exactly one feature, kept rather than special-cased.
 */
function siteCarrier(
  anchor: SitePoint,
  members: readonly SitePoint[],
  visibility: SiteVisibility,
): SitePoint {
  if (isPointDrawn(anchor, visibility)) return anchor

  let best: SitePoint | undefined
  for (const member of members) {
    if (!isPointDrawn(member, visibility)) continue
    if (best === undefined) {
      best = member
      continue
    }
    const rank = poiPriorityRank(member.type)
    const bestRank = poiPriorityRank(best.type)
    // Ties broken on id rather than on arrival order, for the reason the member
    // list is sorted rather than taken as it comes: two campsites at one site
    // are equally right to promote, and picking by array order would make the
    // pin depend on the order IndexedDB happened to hand the POIs back.
    if (rank < bestRank || (rank === bestRank && member.id < best.id)) best = member
  }

  return best ?? anchor
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
 * "A future filter" arrived, and it got in under that guard rather than through
 * it (#607). The legend's filter does not remove the anchor from this list - it
 * leaves the anchor here and takes its PIN off the map, one layer further on, so
 * every check above still passed while the replacement pin was not being drawn.
 * Filtering the legend to privies drew 32 of the trail's 316: the 284 that fold
 * into a site were removed here, and the shelters carrying them were removed by
 * `poiFilter`. Hence {@link SiteVisibility} - the fold is now conditional on the
 * replacement being drawn IN FACT rather than in principle, and a site whose
 * anchor is filtered out redraws as its highest-priority drawn member.
 *
 * Members are counted by DISTINCT CATEGORY, not by count. A site with four
 * campsites says "campsite", not "campsite ×4": the question at a shelter is
 * whether there is one, and a number answers a question nobody asked - the same
 * reasoning features/POI_SITES.md gives for rejecting a bare `+N` bubble.
 */
export function composeSites(
  points: readonly SitePoint[],
  visibility: SiteVisibility = {},
): SiteComposition {
  const anchorFor = new Map<string, SitePoint>()
  for (const point of points) {
    if (point.siteRole === SITE_ROLE_ANCHOR && point.siteId !== undefined) {
      anchorFor.set(point.siteId, point)
    }
  }

  const membersOf = new Map<string, SitePoint[]>()
  for (const point of points) {
    if (point.siteRole !== SITE_ROLE_MEMBER || point.siteId === undefined) continue
    if (!anchorFor.has(point.siteId)) continue
    const carried = membersOf.get(point.siteId) ?? []
    carried.push(point)
    membersOf.set(point.siteId, carried)
  }

  const carrierFor = new Map<string, SitePoint>()
  for (const [siteId, anchor] of anchorFor) {
    carrierFor.set(siteId, siteCarrier(anchor, membersOf.get(siteId) ?? [], visibility))
  }

  const drawn: SitePoint[] = []
  for (const point of points) {
    const siteId = point.siteId
    const inSite =
      siteId !== undefined &&
      anchorFor.has(siteId) &&
      (point.siteRole === SITE_ROLE_ANCHOR || point.siteRole === SITE_ROLE_MEMBER)

    // Everything that is not part of a site keeps its own pin, which covers a
    // member whose anchor is not in this list at all and an unrecognised role a
    // later release adds - both drawn rather than dropped, for the reason this
    // function's docstring gives.
    if (!inSite || carrierFor.get(siteId) === point) drawn.push(point)
  }

  // Keyed by CARRIER ID rather than site id, because that is what the feature
  // collection has to hand when it writes the property - one lookup at build
  // time instead of a second index from site id back to the pin.
  const membersFor = new Map<string, readonly string[]>()
  for (const [siteId, carrier] of carrierFor) {
    const carried = new Set<string>()
    for (const member of membersOf.get(siteId) ?? []) {
      if (member === carrier) continue
      // A hidden member is not listed on the strip it rides. The alternative -
      // a shelter pin still wearing a privy glyph on a map where the hiker
      // turned privies off - is the legend and the map disagreeing, which
      // poiLayers.ts's header comment makes a structural property of the
      // one-layer design rather than a nicety.
      if (!isPointDrawn(member, visibility)) continue
      carried.add(member.type)
    }
    if (carried.size === 0) continue
    membersFor.set(
      carrier.id,
      SITE_MEMBER_TYPES.filter((type) => carried.has(type)),
    )
  }

  return { drawn, membersFor }
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
