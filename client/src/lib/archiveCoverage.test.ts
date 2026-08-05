import { describe, it, expect } from 'vitest'
import { archiveCoversZoom, openingZoomFloor } from './archiveCoverage'

// #216: the pipeline exported the corridor from z6, the app opened at ~z4, and
// nothing compared the two - so a complete 314 MB download rendered as blank
// paper on every launch. These are the rules that stop the client ever
// asserting coverage it has not established.

const Z6 = { minZoom: 6, maxZoom: 12 }
const Z0 = { minZoom: 0, maxZoom: 12 }

describe('archiveCoversZoom', () => {
  it('says no below the archive floor, which is where the paper shows through', () => {
    expect(archiveCoversZoom(Z6, 3.9)).toBe(false)
    expect(archiveCoversZoom(Z6, 5.99)).toBe(false)
  })

  it('says yes at the floor itself', () => {
    expect(archiveCoversZoom(Z6, 6)).toBe(true)
  })

  it('says yes ABOVE the top tier, because a raster overzooms', () => {
    // Asymmetric on purpose. Past maxZoom MapLibre stretches the top tier -
    // blurry, and still a map. Below minZoom there is no tile at all.
    expect(archiveCoversZoom(Z6, 16)).toBe(true)
  })

  it('says yes when coverage is unknown, rather than inventing an absence', () => {
    // The exact conflation that made #216 hard to see: "we have not looked
    // yet" must never render as "your download does not reach here."
    expect(archiveCoversZoom(null, 0)).toBe(true)
  })

  it('covers everything once the archive starts at z0', () => {
    // What the pipeline now ships. The whole mechanism becomes inert.
    expect(archiveCoversZoom(Z0, 0)).toBe(true)
    expect(archiveCoversZoom(Z0, 3.9)).toBe(true)
  })
})

describe('openingZoomFloor', () => {
  it('lifts an opening view that fell under the archive up to its floor', () => {
    expect(openingZoomFloor(Z6, 3.9)).toBe(6)
  })

  it('leaves a view the archive already reaches alone', () => {
    expect(openingZoomFloor(Z6, 9)).toBeNull()
  })

  it('leaves the camera alone when the archive covers everything', () => {
    // The z0 archives the pipeline builds from now on: nothing to clamp, so
    // the whole-trail opening view survives exactly as designed.
    expect(openingZoomFloor(Z0, 3.9)).toBeNull()
  })

  it('leaves the camera alone when there is nothing to ask', () => {
    expect(openingZoomFloor(null, 3.9)).toBeNull()
  })
})
