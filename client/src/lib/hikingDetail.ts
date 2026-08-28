// The hiking sheet's download levels (#276) - downloadDetail.ts's sibling,
// for the other sheet.
//
// The USGS raster's levels are whole alternative archives. The hiking sheet's
// switch its BASEMAP cut - z12 Light, z13 Standard, the full z14 Fine - and,
// since #1088, its DEM as well: the terrain corridor narrows with depth
// (pipeline/export_dem.py's CORRIDOR_TAPER_MILES), and Light is a harder taper
// rather than a shallower pyramid. Both artifacts are therefore per-level,
// which is why this table carries an artifact and a size for each rather than a
// whole-sheet total; the sheet's total is composed where sheets are composed
// (lib/packages.ts).
//
// Sizes are the published artifacts' exact bytes, per the same honesty bar as
// everything in packages.ts - and since #505 they are the FALLBACK rather than
// the figure: lib/usePublishedSizes.ts reads what publish.py measured on upload
// out of `latest.json`, and packageSizeBytes prefers that wherever the manifest
// carries one. These remain because a phone that has not been able to ask still
// has to print something, and they must stay accurate for exactly that reader.
//
// As of 2026-08-27 UA's latest.json carries `transfer_bytes` for all five of
// these keys: both DEMs and all three basemap cuts have now been republished
// since #505 taught publish.py to measure on upload, so a phone that can reach
// the manifest reads the bucket's own figures and never these. publish.py's
// merge lets an entry published earlier "survive without one rather than
// gaining a guess", which is why a newly-added key's size appears the first
// time its workflow publishes and not before - with no client edit either way.
//
// That does NOT make these constants decorative. They are what a phone shows
// before latest.json lands, and first run on a slow connection is exactly when
// somebody is deciding whether they have room, so they are kept exact and
// refreshed in the same change as any republish that moves them.
//
// EVERY FIGURE BELOW IS PRODUCTION'S, AND UA HAS ALREADY MOVED PAST THREE OF
// THEM. Measured 2026-08-28 against both manifests, which is the first thing
// #1144's new coverage of this table asked and the reason it was worth adding:
//
//                                    production        UA     drift
//   at_basemap_package_z12.pmtiles   75,451,755   67,921,100   -10.0%
//   at_basemap_package_z13.pmtiles  182,774,166  159,913,857   -12.5%
//   at_basemap_package.pmtiles      533,926,586  348,761,067   -34.7%
//   dem_light.pmtiles               182,205,873  182,205,873     same
//   dem.pmtiles                     275,601,483  275,601,483     same
//
// UA's three basemap cuts are #1118's layer-stripped rebuild ("Stop downloading
// what nothing draws"); production has not taken it yet. So these constants are
// correct for the bucket a shipped build reads and WRONG for UA by up to
// 34.7% - overstating, which is the safe direction (a hiker is told to free
// more room than the download needs), and still wrong.
//
// WHAT THAT MEANS FOR THE NEXT RELEASE, stated here rather than left to be
// rediscovered when the gate goes red: promoting the basemap family to
// production and updating these three constants are ONE change, not two. Land
// them apart and check 18 fails the release - which is now the point of it.
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
  /** That artifact's exact published size, or null while it is unpublished. */
  basemapSizeBytes: number | null
  /** The flat R2 key of this level's DEM, same mapping. Leveled since #1088. */
  demArtifact: string
  /** That artifact's exact published size, or null while it is unpublished. */
  demSizeBytes: number | null
  recommended: boolean
  /** Whether both of this level's artifacts are actually in the bucket. See
   *  the header - this is the gate that keeps an unbuilt level off the screen. */
  published: boolean
}

export const HIKING_DETAIL_LEVELS: HikingDetail[] = [
  {
    // OFFERED SINCE 2026-08-27, and both figures are the bucket's own rather
    // than projections. `dem_light.pmtiles` is 182,205,873 bytes, published to
    // UA by build-dem.yml run 33067212006 at the 20/6/3 taper (#1088);
    // `at_basemap_package_z12.pmtiles` is 75_451_755 bytes, published by
    // build-basemap.yml run 33069162537 (#1107). Both read back out of UA's
    // latest.json, not out of a build log.
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
    basemapSizeBytes: 75_451_755,
    demArtifact: 'dem_light.pmtiles',
    demSizeBytes: 182_205_873,
    recommended: false,
    published: true,
  },
  {
    // THE TAPERED DEM, measured in the bucket rather than projected: 275,601,483
    // bytes, published 2026-08-27 by build-dem.yml run 33065561782 at the
    // shipped 30/15/6 schedule (#1088). It replaces the untapered 607,265,661,
    // and the two had to move together.
    //
    // That last sentence used to credit verify_release.py check 18 with
    // enforcing it - "fails a release where an advertised size drifts more than
    // 2% from the bucket, and 607 against 276 is not close". FALSE WHEN
    // WRITTEN: check 18 read only downloadDetail.ts's withdrawn raster tiers,
    // so nothing mechanical held THIS table to the bucket at all. #1144 pointed
    // checks 2 and 18 at these five artifacts, which is what makes the sentence
    // true now.
    //
    // The basemap figure is production's measured 182,774,166, replacing a
    // 182,286,799 copied from an older build log. Nothing rebuilt the basemap
    // then; the constant was simply out, in the direction downloadDetail.ts
    // warns about - understating, so a hiker who freed exactly enough is
    // stranded.
    level: 'standard',
    artifact: 'at_basemap_package_z13.pmtiles',
    basemapSizeBytes: 182_774_166,
    demArtifact: 'dem.pmtiles',
    demSizeBytes: 275_601_483,
    recommended: true,
    published: true,
  },
  {
    // Same measured DEM; the basemap is UA's z14 cut at 533,455,195 against a
    // constant of 532,459,439 - 995,756 bytes out, same direction.
    level: 'fine',
    artifact: 'at_basemap_package.pmtiles',
    basemapSizeBytes: 533_926_586,
    demArtifact: 'dem.pmtiles',
    demSizeBytes: 275_601_483,
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
