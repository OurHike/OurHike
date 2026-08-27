// The elevation ribbon's SVG geometry, as one pure function.
//
// Moved out of chrome/ElevationRibbon.tsx (#1111) so the component can wrap
// the one expensive part of its render - the ~640-point path strings and the
// min/max scan - in a memo, and so a test can watch that memo hold. The shell
// re-renders once per GPS callback while a phone sits still (#1100); the
// ribbon's props now keep their identity when the vertex-snapped mile has not
// moved, and this function not running on those renders is the point of the
// split. What it computes is unchanged, comments included.
//
// The geometry itself is fixed by the wireframe (WIREFRAMES.md §1.3): viewBox
// "0 0 100 40" with preserveAspectRatio="none", so the profile stretches to
// whatever width the phone has while the waypoint lanes underneath share the
// same 0-100 percentage space.

import type { ElevationSample } from '../chrome/ElevationRibbon'

export const VIEW_W = 100
export const VIEW_H = 40

/** Where a mile sits in the ribbon's 0-100 percentage space. */
export function pctAlong(mile: number, startMile: number, endMile: number): number {
  const span = endMile - startMile
  return span === 0 ? 0 : ((mile - startMile) / span) * 100
}

export interface RibbonGeometry {
  minFt: number
  maxFt: number
  /** The profile line, one point per sample. */
  pointsPath: string
  /** The same line closed along the baseline, for the shaded area. */
  areaPath: string
}

export function ribbonGeometry(
  samples: ElevationSample[],
  startMile: number,
  endMile: number,
): RibbonGeometry {
  const elevations = samples.map((s) => s.elevationFt)
  const minFt = Math.min(...elevations)
  const maxFt = Math.max(...elevations)

  // A flat window makes max === min. Dividing by that range would put NaN into
  // the path, which renders as nothing at all - so a flat profile is drawn as
  // a flat line down the middle instead.
  const range = maxFt - minFt
  const yFor = (ft: number) =>
    range === 0 ? VIEW_H / 2 : VIEW_H - ((ft - minFt) / range) * VIEW_H

  const pointsPath = samples
    .map((s, i) => {
      const x = pctAlong(s.mile, startMile, endMile)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${yFor(s.elevationFt).toFixed(2)}`
    })
    .join(' ')

  // Closing back along the baseline is what makes this a shaded area rather
  // than a bare line. It closes under the LINE's own ends rather than under
  // the ribbon's: with no domain given those are the same two x values, and
  // where a domain leaves the samples short of an edge, shading out to it
  // would fill ground the DEM never covered.
  const firstX = samples.length === 0 ? 0 : pctAlong(samples[0].mile, startMile, endMile)
  const lastX =
    samples.length === 0
      ? VIEW_W
      : pctAlong(samples[samples.length - 1].mile, startMile, endMile)
  const areaPath = `${pointsPath} L${lastX.toFixed(2)},${VIEW_H} L${firstX.toFixed(2)},${VIEW_H} Z`

  return { minFt, maxFt, pointsPath, areaPath }
}
