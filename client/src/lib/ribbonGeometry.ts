// The elevation ribbon's SVG geometry, as one pure function.
//
// Moved out of chrome/ElevationRibbon.tsx (#1111) so the component can wrap
// the one expensive part of its render - the ~640-point path strings and the
// min/max scan - in a memo, and so a test can watch that memo hold. The shell
// re-renders once per GPS callback while a phone sits still (#1100); the
// ribbon's props now keep their identity when the vertex-snapped mile has not
// moved, and this function not running on those renders is the point of the
// split. That move changed nothing it computed, comments included; #1045
// has since changed it, and the paragraph below is that change.
//
// The geometry itself is fixed by the wireframe (WIREFRAMES.md §1.3): viewBox
// "0 0 100 40" with preserveAspectRatio="none", so the profile stretches to
// whatever width the phone has while the waypoint lanes underneath share the
// same 0-100 percentage space.
//
// ONE SUBPATH PER RUN OF SAMPLES (#1045), split wherever a sample carries
// `partStart`. A day hike built from several stretches (#983) has ground
// between them OurHike will not route - a road walk, most often - and a line
// sloping across it would be a picture of terrain nobody measured. With no
// marker anywhere, which is every ribbon that existed before #1045, this is
// one run and one subpath and the output is byte-for-byte what it always was.

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

  const runs: ElevationSample[][] = []
  for (const sample of samples) {
    if (runs.length === 0 || sample.partStart === true) runs.push([])
    runs[runs.length - 1].push(sample)
  }

  const lineOf = (run: ElevationSample[]) =>
    run
      .map((s, i) => {
        const x = pctAlong(s.mile, startMile, endMile)
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${yFor(s.elevationFt).toFixed(2)}`
      })
      .join(' ')

  const pointsPath = runs.map(lineOf).join(' ')

  // Closing back along the baseline is what makes this a shaded area rather
  // than a bare line. It closes under the LINE's own ends rather than under
  // the ribbon's: with no domain given those are the same two x values, and
  // where a domain leaves the samples short of an edge, shading out to it
  // would fill ground the DEM never covered.
  //
  // Per run, for the same reason the line breaks: shading a single area across
  // a break would fill the gap the break exists to leave empty, which is the
  // one thing the marker is for.
  const areaPath = runs
    .map((run) => {
      const from = pctAlong(run[0].mile, startMile, endMile)
      const to = pctAlong(run[run.length - 1].mile, startMile, endMile)
      return `${lineOf(run)} L${to.toFixed(2)},${VIEW_H} L${from.toFixed(2)},${VIEW_H} Z`
    })
    .join(' ')

  return { minFt, maxFt, pointsPath, areaPath }
}
