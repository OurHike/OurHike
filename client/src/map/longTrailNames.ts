// Which published line name is which long trail (#1543).
//
// WHAT IT FIXES. map/trailsInView.ts decided a badge off the SOURCE -
// `BADGE_SOURCES`, two entries - so ATC's centerline and NYNJTC's Long Path
// feed were the only trails on the map that could wear one. Everything else
// drew as an anonymous line, including Sheltowee Trace, Ozark Highlands,
// Bartram, Pinhoti, Ouachita, Maah Daah Hey and the Tahoe Rim, all of which
// this app already downloads. A trail is not a feed, and this table is what
// lets the badge key off the trail.
//
// GENERATED FROM pipeline/reference/trail_name_aliases.json, which is the
// reviewed half and carries the evidence: every spelling here was measured
// against its publisher's live service on 2026-09-30 and then checked
// GEOGRAPHICALLY against the states the trail runs through. That second step
// rejected 16 names the first step accepted - a New York State Parks line
// called "Long Trail" 200 miles from Vermont, a "PALMETTO" in California, a
// "CUMBERLAND" in Colorado - and the rejections are written down over there
// so nobody re-adds them.
//
// EXACT AFTER FOLDING, NEVER A PREFIX, which is the same refusal
// lib/trails.ts makes and the reason spurs stay ordinary lines: DEC publishes
// "Northville-Placid Trail Spur", USFS publishes "BARTRAM NRT - CHEOAH RD",
// and neither is the trail.
//
// THE COST OF BEING WRONG IS NOT SYMMETRIC, so where a name was ambiguous it
// was left out. Bare "COLORADO" is 90 USFS segments in roughly the right part
// of Colorado and might well be the Colorado Trail; it is not here, because a
// badge naming the wrong trail is worse than a trail with no badge.
const LONG_TRAIL_BY_NAME: Readonly<Record<string, string>> = {
  '7 - finger lakes trail': 'flt',
  appalachian: 'at',
  'appalachian trail': 'at',
  arizona: 'azt',
  'arizona trail': 'azt',
  bartram: 'bartram',
  'benton mackaye': 'bmt',
  'bonneville shoreline trail': 'bst',
  'continental divide': 'cdt',
  'continental divide nat scenic': 'cdt',
  'continental divide nation scen': 'cdt',
  'continental divide nst': 'cdt',
  'continental divide trail': 'cdt',
  'dublin trail monadnock sunapee grnwy': 'msg',
  'finger lakes': 'flt',
  'finger lakes trail': 'flt',
  'finger lakes trail (orange)': 'flt',
  'great western trail': 'gwt',
  'john muir': 'jmt',
  'maah daah hey': 'mdh',
  'north country national scenic': 'nct',
  'north country trail': 'nct',
  'north country trail (hiking)': 'nct',
  'northville-placid trail': 'npt',
  'ouachita nrt': 'ouachita',
  'ozark highlands trail': 'oht',
  'pacific crest': 'pct',
  'pacific crest national scenic': 'pct',
  'pacific crest trail': 'pct',
  pinhoti: 'pinhoti',
  'pinhoti nrt': 'pinhoti',
  'sheltowee trace': 'sheltowee',
  'superior hiking': 'sht',
  'tahoe rim trail': 'tahoe-rim',
}

/** The long trail a published line name is, or null. Folded and trimmed. */
export function longTrailForName(name: string): string | null {
  return LONG_TRAIL_BY_NAME[name.trim().toLowerCase()] ?? null
}

/** How many spellings the table holds, so a dropped row goes red in a test
 *  rather than as a trail quietly losing its badge. */
export const LONG_TRAIL_NAME_COUNT = Object.keys(LONG_TRAIL_BY_NAME).length

/**
 * The badged trails a steward marker actually exists for.
 *
 * WHY THIS IS NOT DERIVED FROM THE TABLE ABOVE. Earning a badge and having a
 * marker are different facts: 7 of the 20 trails this badges publish no
 * per-trail symbol anybody could find - Pinhoti's steward domain serves
 * spam, PCTA states written permission is required, and the rest publish a
 * club wordmark or nothing. Those wear the plate and their name.
 *
 * WHAT GOES WRONG WITHOUT IT, which is why the list is here rather than
 * assumed: map/trailBadges.ts minted `trail-mark-steward-<slug>` for any
 * badged trail, so a badge for the Great Western Trail asked the sprite for
 * an image nothing registers. The empty slot still rendered - an unavailable
 * image is dropped - but the FEATURE said it had a mark, so the placer was
 * free to fall back to the bare-mark form, whose whole content is that
 * missing image. A badge that draws nothing at all, only when the map is
 * crowded. Caught by trailsInView.test.ts rather than on a phone.
 */
const SLUGS_WITH_A_STEWARD_MARKER: ReadonlySet<string> = new Set([
  'azt',
  'bartram',
  'bmt',
  'cdt',
  'flt',
  'mdh',
  'nct',
  'npt',
  'oht',
  'ouachita',
  'sheltowee',
  'sht',
  'tahoe-rim',
])

/** Whether a long trail has a steward marker to draw. */
export function longTrailHasMarker(slug: string): boolean {
  return SLUGS_WITH_A_STEWARD_MARKER.has(slug)
}
