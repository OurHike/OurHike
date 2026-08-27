// Whole-corridor download detail levels. See WIREFRAMES.md's Known
// Deviations #1: the wireframe's per-section download list is superseded by
// ROADMAP.md Phase 2's decision - one package for the whole corridor, with
// this Light/Standard/Fine choice as the *only* download's detail, not a
// per-section override.
//
// SIZES ARE MEASURED FROM THE BUCKET, NOT FROM A BUILD LOG (#505).
//
// They used to be copied from pipeline/README.md's table, which records what a
// particular run produced. That is a different fact from what is currently
// SERVED, and the two had drifted apart: the advertised Standard tier was
// 300.3 MB while the published archive was 315.1 MB - 14.8 MB larger, in the
// direction that strands somebody who freed up exactly enough space.
//
// This number's only job is to let a hiker at a trailhead decide whether they
// have room, so it tracks the object they will actually download.
//
// SINCE #505 THESE ARE THE FALLBACK, NOT THE FIGURE. lib/usePublishedSizes.ts
// reads what publish.py measured on upload out of `latest.json`, and
// packageSizeBytes prefers it wherever the manifest carries one. What is left
// here is the answer for a phone that has not been able to ask - first run
// before the manifest lands, a build with no bucket, an unreachable one - and
// that is a real state rather than a degenerate one, so these stay measured
// and stay maintained.
//
// `verify_release.py` check 18 still fails a release where any tier drifts more
// than 2% from what is advertised here, and it is worth more rather than less
// now: it is the only thing that notices when the fallback rots, and the
// fallback is what a hiker on a slow connection actually reads.

export type DetailLevel = 'light' | 'standard' | 'fine'

export interface DownloadDetail {
  level: DetailLevel
  zoom: 11 | 12 | 13
  sizeBytes: number
  recommended: boolean
}

export const DOWNLOAD_DETAIL_LEVELS: DownloadDetail[] = [
  // Measured against the published bucket on 2026-08-09, rounded to the
  // hundred-kilobyte the display never shows past.
  { level: 'light', zoom: 11, sizeBytes: 65_000_000, recommended: false },
  { level: 'standard', zoom: 12, sizeBytes: 315_100_000, recommended: true },
  { level: 'fine', zoom: 13, sizeBytes: 1_184_700_000, recommended: false },
]

export function getDownloadDetail(level: DetailLevel): DownloadDetail {
  const found = DOWNLOAD_DETAIL_LEVELS.find((d) => d.level === level)
  if (!found) throw new Error(`Unknown download detail level: ${level}`)
  return found
}

/** The reverse lookup, for reading the choice back out of
 *  UserPreferences.max_background_zoom - which is where it is stored, since
 *  the zoom ceiling IS what the choice means. */
export function detailLevelForZoom(zoom: number): DetailLevel {
  const found = DOWNLOAD_DETAIL_LEVELS.find((d) => d.zoom === zoom)
  if (!found) throw new Error(`No download detail level for zoom ${zoom}`)
  return found.level
}
