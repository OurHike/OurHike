// The hiking sheet's download levels (#276) - downloadDetail.ts's sibling,
// for the other sheet.
//
// The USGS raster's levels are whole alternative archives. The hiking sheet's
// switch its BASEMAP cut - z12 Light, z13 Standard, the full z14 Fine - and,
// since #1088, its DEM as well: the terrain corridor narrows with depth
// (pipeline/export_dem.py's CORRIDOR_TAPER_MILES), and Light is a harder taper
// rather than a shallower pyramid. Both artifacts are therefore per-level,
// which is why this table names an artifact of each kind per level rather than
// a whole-sheet anything; the sheet's total is composed where sheets are
// composed (lib/packages.ts).
//
// THIS TABLE CARRIES NO SIZES, AND THAT IS THE POINT (#1167).
//
// It used to carry each artifact's exact published bytes. Since #505 those
// were only a FALLBACK - lib/usePublishedSizes.ts reads what publish.py
// measured on upload out of `latest.json`, and packageSizeBytes prefers it -
// so the constants rendered in one place only: before the manifest lands.
// First run, on a slow connection, which is exactly when somebody is deciding
// whether they have room.
//
// They were the wrong shape for that job. A byte-exact literal is precise
// enough to look authoritative and it rots in silence, and this one had
// already rotted three times by the time it was removed:
//
//   - Standard's basemap read 182,286,799, "copied from an older build log",
//     against a bucket holding 182,774,166;
//   - Fine's read 532,459,439 against 533,455,195;
//   - and on 2026-08-28, measured against both manifests, all three basemap
//     cuts were 10.0% / 12.5% / 34.7% away from UA, which carries #1118's
//     layer-stripped rebuild that production has not taken.
//
// The first two understated, which is the direction downloadDetail.ts names as
// the one that strands a hiker who freed exactly enough.
//
// #1144 pointed verify_release.py check 18 at these artifacts, which turned a
// silent lie into a red gate. Better, and still the wrong trade: it made
// promoting the basemap and hand-editing three constants ONE indivisible
// change, so a hand copy was now gating the release. Removing the copy removes
// the gate and the trap together.
//
// WHAT A HIKER SEES WITH NO MANIFEST YET is a level they can still choose,
// with its size withheld rather than guessed (screens/DetailPicker.tsx says
// "Unknown offline"). An honest unknown outranks a confident answer -
// FEATURES.md's rule, and a stale figure a hiker frees exactly enough room for
// is the confidently wrong one.
//
// WHAT IS DELIBERATELY STILL HERE is `published`, which is not a size: it is
// the gate that keeps a level whose artifacts are not in the bucket off the
// screen at all. See below.
//
// Standard is recommended for the same reason it is the preference default
// (userPreferences.ts): it is the level that fits the storage envelope, and z14
// is individual-building detail MapLibre renders acceptably by overzooming z13.
//
// A LEVEL WHOSE ARTIFACT IS NOT IN THE BUCKET CARRIES `published: false` AND A
// NULL SIZE, and that is this file's version of packages.ts's `source: null`
// rule. The comment there records what it is defending against - "the app was
// offering a Light tier that did not exist" - and calls the failure by its
// right name: a 404 on a mountain. A level can be catalogued here, typed, and
// referenced by the picker long before `publish.py` has actually put its bytes
// behind a key; what it may not do is become choosable. `published` is the one
// gate, and it flips only when a maintainer has run the build and measured the
// object in the bucket.
//
// ALL THREE LEVELS ARE PUBLISHED TODAY, so the gate removes nothing - which is
// the state it is easiest to let rot in. It stays because the next level added
// here will be catalogued before it is built, exactly as Light was between
// #1088 and #1107, and because the same table is what a hiker weighs against
// their remaining storage.

import type { HikingDetailLevel } from './userPreferences'

export interface HikingDetail {
  level: HikingDetailLevel
  /** The flat R2 key of this level's basemap cut, as latest.json names it -
   *  publish.py's OFFLINE_SHEET_ARCHIVES spelling. */
  artifact: string
  /** The flat R2 key of this level's DEM, same mapping. Leveled since #1088. */
  demArtifact: string
  recommended: boolean
  /** Whether both of this level's artifacts are actually in the bucket. See
   *  the header - this is the gate that keeps an unbuilt level off the screen. */
  published: boolean
}

export const HIKING_DETAIL_LEVELS: HikingDetail[] = [
  {
    // OFFERED SINCE 2026-08-27: `dem_light.pmtiles` at the 20/6/3 taper
    // (#1088, build-dem.yml run 33067212006) and
    // `at_basemap_package_z12.pmtiles` (#1107, build-basemap.yml run
    // 33069162537). What either one weighs is the manifest's to say.
    //
    // BOTH ARTIFACTS ARE LIGHT'S OWN, and that is the point of the rung. The
    // taper only ever narrowed TERRAIN, so Light and Standard were still
    // carrying the same 182.6 MB of vector basemap and Light came out only
    // ~93 MB below Standard - thin for a choice a hiker has to understand.
    // The z12 cut is the other ~107 MB.
    //
    // Capping the BASEMAP at z12 is safe where capping the DEM there was not,
    // and the asymmetry is measured rather than assumed: MapLibre overzooms
    // z13 vector cleanly (BASEMAP.md), while the same cap on the raster-dem
    // measured worse than a quantize step already rejected
    // (pipeline/LIGHT_DOWNLOAD.md). Geometry and labels survive magnification;
    // a hillshade computed from magnified elevation does not.
    //
    // What Light gives up is stated where it is decided, in export_dem.py:
    // terrain runs out 3 miles from the trail, exactly
    // trailPosition.MAX_OFF_TRAIL_MILES. #1107 carries whether 20/6/3 are the
    // right numbers - they are picked, not derived.
    level: 'light',
    artifact: 'at_basemap_package_z12.pmtiles',
    demArtifact: 'dem_light.pmtiles',
    recommended: false,
    published: true,
  },
  {
    // THE TAPERED DEM, shipped at the 30/15/6 schedule (#1088, build-dem.yml
    // run 33065561782). It replaced an untapered build roughly 2.2x its size,
    // which is the change that taught this file how badly a hand-copied figure
    // ages: for a while the table advertised the old one.
    //
    // Standard shares `dem.pmtiles` with Fine. The two levels differ only in
    // their basemap cut, which is why the DEM key repeats below rather than
    // Fine inheriting anything.
    level: 'standard',
    artifact: 'at_basemap_package_z13.pmtiles',
    demArtifact: 'dem.pmtiles',
    recommended: true,
    published: true,
  },
  {
    // The full z14 cut and Standard's DEM. The largest sheet on offer, and the
    // one whose basemap moved furthest when #1118 stripped the layers nothing
    // draws - which is the drift the header records.
    level: 'fine',
    artifact: 'at_basemap_package.pmtiles',
    demArtifact: 'dem.pmtiles',
    recommended: false,
    published: true,
  },
]

export function getHikingDetail(level: HikingDetailLevel): HikingDetail {
  const found = HIKING_DETAIL_LEVELS.find((d) => d.level === level)
  if (!found) throw new Error(`Unknown hiking detail level: ${level}`)
  return found
}

/**
 * The levels a hiker may actually be asked to take - catalogued, and with both
 * artifacts published.
 *
 * The same filter `offeredPackages()` applies to packages, one level up. Every
 * screen that OFFERS a hiking-sheet level reads this; the picker still draws
 * the unoffered rungs greyed, because a missing row cannot say whether this
 * sheet has no Light version or whether the app forgot to ask (WIREFRAMES.md
 * §4).
 */
export function offeredHikingDetails(): HikingDetail[] {
  return HIKING_DETAIL_LEVELS.filter((d) => d.published)
}
