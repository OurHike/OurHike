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
// on 2026-09-30 - against its publisher's live service, or, for the rows and
// spellings added later that day, against what UA ships - and then checked
// GEOGRAPHICALLY against the states the trail runs through. That second step
// rejected 16 names the first step accepted - a New York State Parks line
// called "Long Trail" 200 miles from Vermont, a "PALMETTO" in California, a
// "CUMBERLAND" in Colorado - and the rejections are written down over there
// so nobody re-adds them.
//
// EXACT AFTER FOLDING, NEVER A PREFIX, which is the same refusal
// lib/trails.ts makes and the reason spurs stay ordinary lines: DEC publishes
// "Northville-Placid Trail Spur", USFS publishes "FNST - WESTERN CONNECTOR",
// and neither is the trail. A SECTION IS the trail - "MST - PISGAH RD" is the
// Mountains-to-Sea Trail in the Pisgah Ranger District - but only the section
// spellings somebody reviewed are here. This comment used to call
// "BARTRAM NRT - CHEOAH RD" a road-walk. RD is a ranger district, and that
// spelling has been in the table since 2026-09-30.
//
// THE COST OF BEING WRONG IS NOT SYMMETRIC, so where a name was ambiguous it
// was left out. Bare "COLORADO" is 90 USFS segments in roughly the right part
// of Colorado and might well be the Colorado Trail; it is not here, because a
// badge naming the wrong trail is worse than a trail with no badge.
//
// AND EACH ROW'S OWN TRAIL NAME, not only its published spellings. Since
// #1776 pipeline/export_nearby_trails.py writes a through route's TRAIL name
// on the sketch rather than the spelling - "Benton MacKaye Trail", not
// "BENTON MACKAYE" - and says this table "already" lists it. For 10 of the 22
// rows it did not, among them the Bartram, Benton MacKaye, Pinhoti and
// Superior Hiking trails. MEASURED 2026-09-30 on UA release 2026-09-30-3
// (a632bf73), the first that export built: its sketch names through routes
// "Benton MacKaye Trail", "Maah Daah Hey Trail" and "Pinhoti Trail", and the
// table resolved none of the three, so those lines drew unbadged below z5.
// Every row's name is its own reviewed trail, and the extent gate below still
// applies to it.
const LONG_TRAIL_BY_NAME: Readonly<Record<string, string>> = {
  '7 - finger lakes trail': 'flt',
  appalachian: 'at',
  'appalachian trail': 'at',
  'appalachian trail/long trail': 'at',
  arizona: 'azt',
  'arizona trail': 'azt',
  bartram: 'bartram',
  'bartram nrt - cheoah rd': 'bartram',
  'bartram nrt - nantahala rd': 'bartram',
  'bartram trail': 'bartram',
  'benton mackaye': 'bmt',
  'benton mackaye -cheoah rd': 'bmt',
  'benton mackaye trail': 'bmt',
  'bonneville shoreline trail': 'bst',
  'boss lake/cdnst': 'cdt',
  cdnst: 'cdt',
  'cdnst - colorado': 'cdt',
  'cdnst - cottonwood south': 'cdt',
  'continental divide': 'cdt',
  'continental divide nat scenic': 'cdt',
  'continental divide nation scen': 'cdt',
  'continental divide nst': 'cdt',
  'continental divide trail': 'cdt',
  'finger lakes': 'flt',
  'finger lakes trail': 'flt',
  'finger lakes trail (orange)': 'flt',
  'florida trail': 'fnst',
  'fnst - apalach section': 'fnst',
  'fnst - lake george section': 'fnst',
  'fnst - osceola section': 'fnst',
  'fnst - seminole section': 'fnst',
  'fnst - wakulla section': 'fnst',
  'great western trail': 'gwt',
  'hancock lake/cdnst': 'cdt',
  'hunt lake/cdnst': 'cdt',
  'ice age nst-a': 'iat',
  'ice age nst-b': 'iat',
  'ice age nst-c': 'iat',
  'ice age trail': 'iat',
  'john muir': 'jmt',
  'john muir trail': 'jmt',
  'maah daah hey': 'mdh',
  'maah daah hey trail': 'mdh',
  'monarch crest-cdnst': 'cdt',
  'mountains-to-sea trail': 'mst',
  'mst - appalachian rd': 'mst',
  'mst - grandfather rd': 'mst',
  'mst - nantahala rd': 'mst',
  'mst - pisgah rd': 'mst',
  'north country national 187-188': 'nct',
  'north country national 188-604': 'nct',
  'north country national 202-383': 'nct',
  'north country national 383-187': 'nct',
  'north country national 604-390': 'nct',
  'north country national d-202': 'nct',
  'north country national scenic': 'nct',
  'north country ntl scenic-east': 'nct',
  'north country trail': 'nct',
  'north country trail (hiking)': 'nct',
  'northville-placid trail': 'npt',
  'ouachita nrt': 'ouachita',
  'ouachita trail': 'ouachita',
  'ozark highlands trail': 'oht',
  'pacific crest': 'pct',
  'pacific crest national scenic': 'pct',
  'pacific crest trail': 'pct',
  'pacific crest trail - wif1': 'pct',
  'pacific crest trail - wif2': 'pct',
  'pacific crest trail - wif3': 'pct',
  'pacific crest trail - wif4': 'pct',
  pcnst: 'pct',
  'pct - pacific crest trail': 'pct',
  'pct baden-powell': 'pct',
  'pct dawson saddle': 'pct',
  'pct grassy hollow': 'pct',
  'pct indian cyn to vasquez': 'pct',
  'pct mt gleason': 'pct',
  'pct pacifico mountain': 'pct',
  'pct section 10': 'pct',
  'pct section 11': 'pct',
  'pct section 12': 'pct',
  'pct section 13': 'pct',
  'pct section 14': 'pct',
  'pct section 15': 'pct',
  'pct section 16': 'pct',
  'pct section 17': 'pct',
  'pct section 18': 'pct',
  'pct section 19': 'pct',
  'pct section 2': 'pct',
  'pct section 20': 'pct',
  'pct section 21': 'pct',
  'pct section 22': 'pct',
  'pct section 23': 'pct',
  'pct section 24': 'pct',
  'pct section 25': 'pct',
  'pct section 26': 'pct',
  'pct section 27': 'pct',
  'pct section 28': 'pct',
  'pct section 29': 'pct',
  'pct section 3': 'pct',
  'pct section 30': 'pct',
  'pct section 31': 'pct',
  'pct section 32': 'pct',
  'pct section 33': 'pct',
  'pct section 33a': 'pct',
  'pct section 34': 'pct',
  'pct section 35': 'pct',
  'pct section 36': 'pct',
  'pct section 37': 'pct',
  'pct section 38': 'pct',
  'pct section 4': 'pct',
  'pct section 5': 'pct',
  'pct section 6': 'pct',
  'pct section 7': 'pct',
  'pct section 8': 'pct',
  'pct section 9': 'pct',
  'pct vasquez to sierra hwy': 'pct',
  'pct wright mt to inspiration p': 'pct',
  'pct: cle elum north': 'pct',
  'pct: cle elum south': 'pct',
  'pct: columbia gorge': 'pct',
  'pct: def bend north': 'pct',
  'pct: def bend south': 'pct',
  'pct: def sisters': 'pct',
  'pct: glacier peak wilderness': 'pct',
  'pct: mbs darrington': 'pct',
  'pct: mbs skykomish north': 'pct',
  'pct: mbs skykomish south': 'pct',
  'pct: mbs white river': 'pct',
  'pct: methow valley n. terminus': 'pct',
  'pct: mt hood': 'pct',
  'pct: naches central': 'pct',
  'pct: naches north': 'pct',
  'pct: naches south': 'pct',
  'pct: plumas': 'pct',
  'pct: rrs central': 'pct',
  'pct: rrs south': 'pct',
  'pct: rrs-fw sky lakes n': 'pct',
  'pct: shasta-trinity': 'pct',
  'pct: sonora pass - carson pass': 'pct',
  'pct: sonora pass - dorothy lk': 'pct',
  'pct: stanislaus': 'pct',
  'pct: wenatchee river north': 'pct',
  'pct: wenatchee river south': 'pct',
  pinhoti: 'pinhoti',
  'pinhoti nrt': 'pinhoti',
  'pinhoti trail': 'pinhoti',
  'sheltowee trace': 'sheltowee',
  'superior hiking': 'sht',
  'superior hiking trail': 'sht',
  'tahoe rim trail': 'tahoe-rim',
  'tunnel lake/cdnst': 'cdt',
}

/** The long trail a published line name is, or null. Folded and trimmed.
 *  Name only: the badge asks longTrailForLine below, which also checks
 *  where the line is. */
export function longTrailForName(name: string): string | null {
  return LONG_TRAIL_BY_NAME[name.trim().toLowerCase()] ?? null
}

/**
 * The box, [west, south, east, north] in degrees, that a line must lie in to
 * wear each trail's badge (#1781).
 *
 * WHY A NAME IS NOT ENOUGH. The Forest Service publishes "BARTRAM" for the
 * Georgia-North Carolina Bartram Trail and for Tuskegee National Forest's own
 * Bartram trail in Alabama, and until 2026-09-30 the Alabama lines wore the
 * first one's badge and its steward's marker. Same spelling, different trail;
 * only where the line is can tell them apart.
 *
 * GENERATED FROM each row's `extent` in trail_name_aliases.json, whose
 * `_extent` says how the boxes were measured: the accepted features in UA and
 * production, padded by 0.25 degrees (@unvalidated there). A box is drawn
 * round what was reviewed rather than round the whole trail, so a segment
 * published later outside it goes unbadged until the box is widened - a
 * missing badge, never a wrong one.
 */
const LONG_TRAIL_EXTENT: Readonly<
  Record<string, readonly [number, number, number, number]>
> = {
  at: [-84.45, 34.37, -72.04, 43.98],
  azt: [-112.44, 32.92, -110.87, 37.16],
  bartram: [-83.94, 34.61, -82.91, 35.58],
  bmt: [-84.78, 34.37, -83.54, 35.71],
  bst: [-112.2, 39.97, -111.35, 41.59],
  cdt: [-114.19, 32.14, -105.88, 47.49],
  flt: [-79.15, 41.74, -75.05, 42.99],
  fnst: [-85.27, 28.72, -81.28, 30.6],
  gwt: [-112.56, 34.76, -111.09, 38.48],
  iat: [-91.2, 44.78, -90.03, 45.59],
  jmt: [-119.43, 37.38, -118.83, 37.98],
  mdh: [-103.93, 46.34, -103.02, 47.84],
  mst: [-83.29, 35.05, -81.52, 36.34],
  nct: [-97.72, 41.19, -78.59, 47.39],
  npt: [-74.88, 42.95, -73.76, 44.52],
  oht: [-94.28, 35.41, -92.65, 36.15],
  ouachita: [-95.21, 34.4, -92.5, 35.13],
  pct: [-123.51, 33.29, -116.31, 49.26],
  pinhoti: [-86.34, 32.94, -84.27, 35.15],
  sheltowee: [-84.99, 36.35, -83.11, 38.65],
  sht: [-91.23, 47.29, -89.65, 48.18],
  'tahoe-rim': [-120.49, 38.47, -119.63, 39.58],
}

/**
 * The long trail a published line is, checked by name AND by where it is:
 * null unless the name resolves and `at` - any vertex of the line - lies
 * inside that trail's box. A tile-clipped piece's vertices all lie on the
 * line, so any one of them answers for the piece.
 */
export function longTrailForLine(
  name: string,
  at: readonly [number, number] | undefined,
): string | null {
  const slug = longTrailForName(name)
  if (slug === null || at === undefined) return null
  const box = LONG_TRAIL_EXTENT[slug]
  if (box === undefined) return null
  const [lon, lat] = at
  const [west, south, east, north] = box
  return lon >= west && lon <= east && lat >= south && lat <= north ? slug : null
}

/** How many spellings the table holds, so a dropped row goes red in a test
 *  rather than as a trail quietly losing its badge. */
export const LONG_TRAIL_NAME_COUNT = Object.keys(LONG_TRAIL_BY_NAME).length

/**
 * The badged trails a steward marker actually exists for.
 *
 * WHY THIS IS NOT DERIVED FROM THE TABLE ABOVE. Earning a badge and having a
 * marker are different facts: 5 of the 22 trails this badges have no
 * per-trail symbol in the tree - `bst`, `gwt`, `jmt` and `pinhoti`, whose
 * steward domain serves spam, and `mst`, which has no trail_marks row.
 * Recounted 2026-09-30 when the Florida, Ice Age and Mountains-to-Sea rows
 * were added; before that it said "4 of the 19", and earlier "6 of the 20"
 * after the `msg` slug was dropped and the PCT and the A.T. gained marks,
 * and none of those three changes had updated it. Those wear the plate
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
  'at',
  'azt',
  'bartram',
  'bmt',
  'cdt',
  'flt',
  'fnst',
  'iat',
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
 * twenty-one of the twenty-two slugs this table produces.
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
  fnst: 'Florida Trail',
  gwt: 'Great Western Trail',
  iat: 'Ice Age Trail',
  jmt: 'John Muir Trail',
  mdh: 'Maah Daah Hey Trail',
  mst: 'Mountains-to-Sea Trail',
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
  if (/\p{Ll}/u.test(name)) return name
  // WORD BOUNDARIES ARE LETTERS, NOT [A-Za-z], and both halves of that matter.
  // The first version was `/[A-Za-z]+/g`, which broke a word at the apostrophe
  // and skipped accented capitals, so it mangled rather than fixed:
  //   "DEVIL'S PATH"   -> "Devil'S Path"
  //   "CANON DEL AGUA" with a tilde -> "CaNOn Del Agua"
  // Both are reachable - trailsInView.ts runs EVERY named line through this,
  // not only badged ones, and the Forest Service's Southwestern Region
  // publishes plenty of both. features/NEARBY_TRAILS.md §6 forbids rewording a
  // steward's value, and mangling it is worse than leaving it shouting.
  // `\p{L}` with the `u` flag takes the accented letters; the trailing
  // `(?:'\p{L}+)?` keeps a possessive inside the word it belongs to.
  return name.replace(
    /\p{L}+(?:'\p{L}+)?/gu,
    (word) => word[0] + word.slice(1).toLowerCase(),
  )
}
