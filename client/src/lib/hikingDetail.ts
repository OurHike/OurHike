// The hiking sheet's download levels (#276) - downloadDetail.ts's sibling,
// for the other sheet.
//
// The USGS raster's levels are whole alternative archives. The hiking sheet's
// switch its BASEMAP cut - the z13 Standard package or the full z14 Fine one -
// and, since #1088, its DEM as well: the terrain corridor narrows with depth
// (pipeline/export_dem.py's CORRIDOR_TAPER_MILES), and a Light level is a
// harder taper rather than a shallower pyramid. Both artifacts are therefore
// per-level, which is why this table carries an artifact and a size for each
// rather than a whole-sheet total; the sheet's total is composed where sheets
// are composed (lib/packages.ts).
//
// Sizes are the published artifacts' exact bytes, per the same honesty bar as
// everything in packages.ts - and since #505 they are the FALLBACK rather than
// the figure: lib/usePublishedSizes.ts reads what publish.py measured on upload
// out of `latest.json`, and packageSizeBytes prefers that wherever the manifest
// carries one. These remain because a phone that has not been able to ask still
// has to print something, and they must stay accurate for exactly that reader.
//
// Today the manifest carries no size for any .pmtiles - the six entries were
// published by the build workflows before sizes were measured, and publish.py's
// merge lets such an entry "survive without one rather than gaining a guess" -
// so these numbers are what every hiker currently sees. That changes with no
// client edit the first time build-basemap.yml and build-dem.yml publish again.
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
    // NOT OFFERED YET, and the null DEM size is the honest reason rather than
    // an oversight. `dem_light.pmtiles` is a real artifact name publish.py
    // knows and build-dem.yml can now produce (`variant: light`, #1088), but no
    // build has produced it - checked against UA's manifest 2026-08-27, where
    // it is absent while `dem.pmtiles` is present at its tapered size. So
    // nobody can state its bytes, and a projection is exactly the grade that
    // may not be shown to a hiker deciding whether they have room.
    //
    // BOTH ARTIFACTS ARE LIGHT'S OWN since #1107, and that is the point of the
    // rung. The taper narrowed Standard's TERRAIN and left both levels carrying
    // the same 182.6 MB of vector basemap, so Light came out only ~93 MB below
    // Standard - thin for a choice a hiker has to understand. The z12 cut is
    // the other ~107 MB.
    //
    // Capping the BASEMAP at z12 is safe where capping the DEM there was not,
    // and the asymmetry is measured rather than assumed: MapLibre overzooms
    // z13 vector cleanly (BASEMAP.md), while the same cap on the raster-dem
    // measured worse than a quantize step already rejected
    // (pipeline/LIGHT_DOWNLOAD.md). Geometry and labels survive magnification;
    // a hillshade computed from magnified elevation does not.
    //
    // Flip `published` when both objects are in the bucket and have been
    // weighed, and put their exact bytes here in the same change. Neither
    // exists yet, which is why both sizes are null rather than projected -
    // a size shown before a download is what a hiker weighs against their
    // remaining storage, and a projection may not appear there.
    level: 'light',
    artifact: 'at_basemap_package_z12.pmtiles',
    basemapSizeBytes: null,
    demArtifact: 'dem_light.pmtiles',
    demSizeBytes: null,
    recommended: false,
    published: false,
  },
  {
    // THE TAPERED DEM, measured in the bucket rather than projected: 275,601,483
    // bytes, published to UA 2026-08-27 by build-dem.yml run 33065561782 at the
    // shipped 30/15/6 schedule (#1088). It replaces the untapered 607,265,661,
    // and the two had to move together - verify_release.py check 18 fails a
    // release where an advertised size drifts more than 2% from the bucket, and
    // 607 against 276 is not close.
    //
    // The basemap figure is UA's measured 182,610,914, replacing a 182,286,799
    // copied from an older build log. Nothing rebuilt the basemap; the constant
    // was simply 324,115 bytes out, in the direction downloadDetail.ts warns
    // about - understating, so a hiker who freed exactly enough is stranded.
    level: 'standard',
    artifact: 'at_basemap_package_z13.pmtiles',
    basemapSizeBytes: 182_610_914,
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
    basemapSizeBytes: 533_455_195,
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
