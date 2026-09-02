import { describe, it, expect } from 'vitest'
import {
  CAMERA_ZOOM_TILE_OFFSET,
  archiveCoversZoom,
  coverageAt,
  openingZoomFloor,
} from './archiveCoverage'

// #216: the pipeline exported the corridor from z6, the app opened at ~z4, and
// nothing compared the two - so a complete 314 MB download rendered as blank
// paper on every launch. These are the rules that stop the client ever
// asserting coverage it has not established.

const Z6 = { minZoom: 6, maxZoom: 12 }
const Z0 = { minZoom: 0, maxZoom: 12 }

describe('archiveCoversZoom', () => {
  it('says no below the archive floor, which is where the paper shows through', () => {
    expect(archiveCoversZoom(Z6, 3.9)).toBe(false)
    expect(archiveCoversZoom(Z6, 4.99)).toBe(false)
  })

  it('says yes from one camera zoom under the floor, where @2x tiles begin', () => {
    // The tileSize: 256 declaration (map/style.ts, #191) has MapLibre
    // request tiles one level deeper than the camera, so a z6-floored
    // archive first draws at camera z5 - the header speaks tile zooms,
    // the camera does not.
    expect(archiveCoversZoom(Z6, 5)).toBe(true)
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
  it('lifts an opening view that fell under the archive up to its camera floor', () => {
    // One under the header floor - the shallowest camera zoom that really
    // has tiles behind it under the @2x declaration.
    expect(openingZoomFloor(Z6, 3.9)).toBe(6 - CAMERA_ZOOM_TILE_OFFSET)
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

describe('coverageAt', () => {
  // The horizontal edge (#557): the same rules as the zoom floor above,
  // applied to ground. A held cell in Georgia and the whole-sheet archive's
  // declared rectangle are both footprints; what matters is what the answer
  // may claim and when.
  const GEORGIA = { west: -85, south: 34, east: -84, north: 35 }
  const CORRIDOR = { west: -84.4, south: 34.1, east: -68.9, north: 45.9 }

  it('says covered inside a held cell', () => {
    expect(coverageAt([GEORGIA], -84.5, 34.5)).toBe('covered')
  })

  it('says outside past every footprint held', () => {
    expect(coverageAt([GEORGIA], -77.1, 39.3)).toBe('outside')
  })

  it('says covered inside any one of several', () => {
    expect(coverageAt([GEORGIA, CORRIDOR], -77.1, 39.3)).toBe('covered')
  })

  it('says unknown before anything has been read, never outside', () => {
    // Not-looked-yet rendered as your-download-does-not-reach-here is the
    // conflation #216 was made of, and here it would send a hiker to town
    // for a download they have.
    expect(coverageAt(null, -84.5, 34.5)).toBe('unknown')
  })

  it('says unknown on a phone holding nothing - there is no edge to be outside of', () => {
    // That phone's flags already exist (lib/backgroundHealth.ts), and a
    // second one saying "outside" would describe an edge nobody crossed.
    expect(coverageAt([], -84.5, 34.5)).toBe('unknown')
  })

  it('gives a point on the eastern edge to the ground beyond it', () => {
    // Half-open, the way the cells themselves are: a point on a seam is in
    // exactly one cell, and this footprint is not it.
    expect(coverageAt([GEORGIA], -84, 34.5)).toBe('outside')
    expect(coverageAt([GEORGIA], -85, 34.5)).toBe('covered')
  })
})
