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
 * marker are different facts: 6 of the 20 trails this badges publish no
 * per-trail symbol anybody could find - Pinhoti's steward domain serves
 * spam, and the rest publish a club wordmark or nothing. Those wear the plate
 * and their name. The PCT left that group on 2026-09-30: PCTA still requires
 * written permission for its own files, but the Forest Service administers
 * the trail and publishes the emblem itself, so `pct-logo.png` is the federal
 * copy (lib/trails.ts's header has the reasoning, including the insignia
 * question that a public-domain answer does not reach).
 *
 * WHAT GOES WRONG WITHOUT IT, which is why the list is here rather than
 * assumed: map/trailBadges.ts minted `trail-mark-steward-<slug>` for any
 * badged trail, so a badge for the Great Western Trail asked the sprite for
 * an image nothing registers. The empty slot still rendered - an unavailable
 * image is dropped - but the FEATURE said it had a mark, so the placer was
 * free to fall back to the bare-mark form, whose whole content is that
 * missing image. A badge that draws nothing at all, only when the map is
 * crowded. Caught by trailsInView.test.ts rather than on a phone.
 *
 * AND THE SAME THING HAPPENS WHEN THIS LIST IS RIGHT AND THE REGISTRY IS NOT.
 * `cdt` sat here from the day the list was written while
 * lib/stewardMarks.ts's STEWARD_MARKS_BY_SLUG had no `cdt` row, so every
 * badge on the 267 USFS Continental Divide segments asked for an id nothing
 * held - the identical failure, reached from the other side, with
 * cdt-logo.png in the tree the whole time. Fixed 2026-09-30 by registering
 * it; stewardMarks.test.ts now asserts every slug in this set resolves to a
 * file, which is the check neither side had. Containment, not equality -
 * stewardMarks holds 20 markers this set has no entry for, because the line
 * sheet reaches those by name.
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
  'pct',
  'sheltowee',
  'sht',
  'tahoe-rim',
])

/** Whether a long trail has a steward marker to draw. */
export function longTrailHasMarker(slug: string): boolean {
  return SLUGS_WITH_A_STEWARD_MARKER.has(slug)
}

/** Every slug this file CLAIMS a marker for. Exported for the one check that
 *  catches the cdt defect above: lib/stewardMarks.test.ts asserts each of
 *  these resolves to a file, which is the half neither module could see on
 *  its own. Not the reverse - stewardMarks holds 20 more markers that only
 *  chrome/LineSheet.tsx reaches, by name. */
export function longTrailMarkerSlugs(): readonly string[] {
  return [...SLUGS_WITH_A_STEWARD_MARKER]
}

/**
 * What the badge PRINTS for a long trail, which is not what the publisher
 * spells it.
 *
 * WHY. The Forest Service publishes in capitals and by designation:
 * `SHELTOWEE TRACE`, `BENTON MACKAYE`, `PINHOTI NRT`, `NORTH COUNTRY
 * NATIONAL SCENIC`. Printed raw those shout across the map and name the
 * trail the way a GIS table does rather than the way its steward and a
 * hiker do. This is the same decision lib/trails.ts already took for the
 * A.T. - "the maintainer asked on 2026-09-16 for the app to say
 * 'Appalachian Trail' wherever a hiker reads it" - applied to the other
 * nineteen.
 *
 * The names come from trail_emblems.json through trail_name_aliases.json, so
 * they are the steward's own spelling rather than a case transform of the
 * publisher's: `PINHOTI NRT` becomes "Pinhoti Trail", not "Pinhoti Nrt".
 */
const LONG_TRAIL_DISPLAY_NAME: Readonly<Record<string, string>> = {
  at: 'Appalachian Trail',
  azt: 'Arizona Trail',
  bartram: 'Bartram Trail',
  bmt: 'Benton MacKaye Trail',
  bst: 'Bonneville Shoreline Trail',
  cdt: 'Continental Divide Trail',
  flt: 'Finger Lakes Trail',
  gwt: 'Great Western Trail',
  jmt: 'John Muir Trail',
  mdh: 'Maah Daah Hey Trail',
  nct: 'North Country Trail',
  npt: 'Northville-Placid Trail',
  oht: 'Ozark Highlands Trail',
  ouachita: 'Ouachita Trail',
  pct: 'Pacific Crest Trail',
  pinhoti: 'Pinhoti Trail',
  sheltowee: 'Sheltowee Trace',
  sht: 'Superior Hiking Trail',
  'tahoe-rim': 'Tahoe Rim Trail',
}

/** The name a badge prints for a long trail, or null if it is not one. */
export function longTrailDisplayName(slug: string): string | null {
  return LONG_TRAIL_DISPLAY_NAME[slug] ?? null
}

/**
 * A last resort so a badge NEVER shouts, on the maintainer's instruction of
 * 2026-09-30: "Always proper case, not alll caps".
 *
 * WHAT IT IS FOR, AND WHY IT IS THE WORSE ANSWER. Every trail this badges
 * today has a curated name in LONG_TRAIL_DISPLAY_NAME above, and that is the
 * one to use: it comes from the steward, so `PINHOTI NRT` reads "Pinhoti
 * Trail" and `BENTON MACKAYE` keeps its capital K. Mechanical title case
 * cannot do either - it would give "Pinhoti Nrt" and "Benton Mackaye". This
 * only catches a name that reaches a badge with no curated spelling at all,
 * which happens if BADGE_SOURCES grows before its trail is added to
 * trail_name_aliases.json.
 *
 * LEFT ALONE UNLESS IT IS ACTUALLY SHOUTING. A name with any lower-case in
 * it is somebody's considered spelling and is not touched - "Long Path",
 * "Northville-Placid Trail", and anything with an internal capital.
 */
export function neverShout(name: string): string {
  if (/[a-z]/.test(name)) return name
  return name.replace(/[A-Za-z]+/g, (word) => word[0] + word.slice(1).toLowerCase())
}
