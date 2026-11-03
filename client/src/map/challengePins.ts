// Which challenge places to pin, and how (#1780 — Let a club publish a
// challenge — places on its own trails that hikers opt into and tag at camp —
// starting with the ATC's A.T. Summer Bucket List; features/CHALLENGES.md,
// frame 1).
//
// The pure half of the challenge layer: the hiker's joined challenges and
// record in, GeoJSON points out. Its own module rather than a function in
// map/challengeLayers.ts because that file is imported by map/style.ts, and
// style.ts by every map this app builds (the viewer page included); this one
// reads lib/challenges.ts, whose kept copy rides IndexedDB, and nothing that
// only builds a style needs that in its graph.

import {
  isPlaceItem,
  isSealed,
  type Challenge,
  type ChallengeItem,
} from '../lib/challenges'
import {
  isItemDone,
  tagsFor,
  type ChallengeState,
  type ChallengeTag,
} from '../lib/challengeProgress'
import {
  CHALLENGE_TAGGED_PROPERTY,
  type ChallengePinFeatureCollection,
  type ChallengePinProperties,
} from './challengePinData'

/**
 * Whether the hiker has tagged THIS place for THIS item.
 *
 * Per place, not per item, for a `places_all` item: Virginia's Triple Crown
 * is done only when all three peaks are, but a hiker who tagged McAfee Knob
 * on Monday has tagged McAfee Knob, and a pin left hollow until Wednesday's
 * Tinker Cliffs would be the map disagreeing with the hiker about a place
 * they stood on. For a `place` item it is the item - an item naming two
 * places is "either of these", and once it is done, neither is still owed.
 */
function placeTagged(
  item: ChallengeItem,
  challengeId: string,
  poi: string,
  tags: readonly ChallengeTag[],
): boolean {
  if (item.match.kind === 'places_all') {
    return tags.some(
      (tag) =>
        tag.challengeId === challengeId && tag.itemId === item.id && tag.poi === poi,
    )
  }
  return isItemDone(item, challengeId, tags)
}

/**
 * The pins for the challenges a hiker joined: one point per published POI
 * that any place-kind item of any of them names.
 *
 * WHAT IS LEFT OUT, each for a reason:
 *  - challenges not in `joined`, so leaving one takes its pins off the map
 *    at once (lib/challengeProgress.ts's `leave` promises exactly that);
 *  - items that are not places (`isPlaceItem`): "any shelter", a height, a
 *    section walked and a workday have no one point to draw;
 *  - sealed mystery items (`isSealed`): a pin at a place is the answer to
 *    the mystery, so it waits for the reveal date like the title does.
 *
 * WHAT IS KEPT: a place marked `offTrail` - a town, a visitor centre. It can
 * only be tagged by hand, but it is a real place a hiker can walk into.
 *
 * ONE PIN PER POI, FILLED ONLY WHEN EVERY ITEM THERE IS DONE. The ATC's draft
 * names three POIs in two items each: McAfee Knob (its own item and the
 * Triple Crown), the Pine Grove Furnace point (the museum and the ice cream)
 * and the Harpers Ferry community point (the visitor centre and the
 * psychological halfway). Filled
 * because ANY of them was tagged would put a finished-looking mark on a place
 * where the hiker still has something to do, and the map is the one surface
 * where they would not see the rest; hollow until all are done keeps the
 * mark meaning "nothing left here". It is the more conservative reading of a
 * mark that can only say one thing, and the card lists every item at the
 * place with its own state. The same across two challenges: a place is one
 * place on the map whichever club listed it.
 *
 * `today` is the hiker's local YYYY-MM-DD (lib/passedToday.ts's localDay),
 * the clock a mystery's reveal date is read on.
 */
export function challengePinFeatures(
  joined: readonly Challenge[],
  state: ChallengeState,
  today: string,
): ChallengePinFeatureCollection {
  const byPoi = new Map<
    string,
    { coordinates: [number, number]; properties: ChallengePinProperties }
  >()
  for (const challenge of joined) {
    const tags = tagsFor(state, challenge.id)
    for (const item of challenge.items) {
      if (!isPlaceItem(item) || isSealed(item, today)) continue
      for (const place of item.match.places) {
        const tagged = placeTagged(item, challenge.id, place.poi, tags)
        const existing = byPoi.get(place.poi)
        if (existing === undefined) {
          byPoi.set(place.poi, {
            coordinates: [place.lon, place.lat],
            properties: {
              poi: place.poi,
              name: place.name,
              poi_type: place.poiType,
              [CHALLENGE_TAGGED_PROPERTY]: tagged,
              challengeId: challenge.id,
              itemId: item.id,
            },
          })
        } else if (!tagged) {
          existing.properties[CHALLENGE_TAGGED_PROPERTY] = false
        }
      }
    }
  }
  return {
    type: 'FeatureCollection',
    features: [...byPoi.values()].map(({ coordinates, properties }) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates },
      properties,
    })),
  }
}
