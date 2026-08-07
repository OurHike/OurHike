// The states a blank map can be in, and which of them the app is allowed to
// explain (#314).
//
// Every case here is written from the phone outwards - what is downloaded,
// what drew - because that is the pair the shell can actually observe. The
// screen a hiker is looking at is the same in all of them: paper.

import { describe, it, expect } from 'vitest'
import {
  backgroundProblem,
  forgetSheet,
  sheetNotDrawing,
  type BackgroundHealthInputs,
} from './backgroundHealth'
import { HEALTHY, type LiveSourceHealth } from '../map/liveSourceHealth'
import { HIKING_SHEET, USGS_SHEET } from './packages'

/** A phone with signal, nothing downloaded, and a map that is drawing. */
const WELL: BackgroundHealthInputs = {
  sources: HEALTHY,
  online: true,
  rasterArchiveDownloaded: false,
  hikingSheetDownloaded: false,
}

function failing(...flags: (keyof LiveSourceHealth)[]): LiveSourceHealth {
  return flags.reduce((health, flag) => ({ ...health, [flag]: true }), HEALTHY)
}

describe('backgroundProblem', () => {
  it('says nothing about a map that is drawing', () => {
    expect(backgroundProblem(WELL)).toBeNull()
  })

  it('is silent about the archive source on a phone with no archive', () => {
    // The case that makes this module necessary rather than a rename of the
    // source flag. map/style.ts declares the raster source under BOTH
    // backgrounds, so on a phone that has downloaded nothing it fails every
    // request it makes - correctly, and constantly. Reporting that as a
    // problem would put a permanent warning on the ordinary first run.
    expect(backgroundProblem({ ...WELL, sources: failing('archive') })).toBeNull()
  })

  it('reports a raster archive that is on the phone and drew nothing', () => {
    // #314's first path: the blob is present, so `downloaded` is true
    // everywhere the app asks - and the archive is truncated, or corrupt, or
    // half evicted, so every tile read against it fails.
    expect(
      backgroundProblem({
        ...WELL,
        sources: failing('archive'),
        rasterArchiveDownloaded: true,
      }),
    ).toBe('download-not-drawing')
  })

  it('reports a hiking sheet that is on the phone and drew nothing', () => {
    // The same failure one package over. `basemap` covers the package and the
    // network fallthrough behind it (map/basemap.ts), so this flag with the
    // package present means neither answered.
    expect(
      backgroundProblem({
        ...WELL,
        sources: failing('basemap'),
        hikingSheetDownloaded: true,
      }),
    ).toBe('download-not-drawing')
  })

  it('blames the download rather than the signal, even offline', () => {
    // Ordering that matters on the ground: a phone holding a download that
    // will not draw is not suffering from being offline, and saying so would
    // send someone walking for signal they do not need.
    expect(
      backgroundProblem({
        ...WELL,
        online: false,
        sources: failing('basemap', 'archive'),
        rasterArchiveDownloaded: true,
      }),
    ).toBe('download-not-drawing')
  })

  it('still says the live sheet never loaded, which "Offline" cannot say', () => {
    expect(backgroundProblem({ ...WELL, sources: failing('basemap') })).toBe(
      'live-unreachable',
    )
  })

  it('says the live sheet is missing even while the archive draws underneath', () => {
    // Carried over unchanged from the flag this replaced. The hiker has a map,
    // but it is not the one they chose, and this line is the only thing that
    // explains why the sheet looks different today.
    expect(
      backgroundProblem({
        ...WELL,
        sources: failing('basemap'),
        rasterArchiveDownloaded: true,
      }),
    ).toBe('live-unreachable')
  })

  it('names the missing download when offline with nothing to draw', () => {
    // #314's second path, and the one that was silent by design: the strip
    // suppressed its background flag whenever the phone was offline, on the
    // reasoning that "Offline" accounted for the paper. It does not account
    // for a hiking sheet deleted an hour ago.
    expect(
      backgroundProblem({ ...WELL, online: false, sources: failing('basemap') }),
    ).toBe('nothing-to-draw')
  })

  it('stays quiet offline when the archive is drawing under the live sheet', () => {
    // Stacking working exactly as features/MAP_OPTIONS.md §1 designed it: the
    // live layers draw nothing, the download shows through, and there is no
    // problem to report.
    expect(
      backgroundProblem({
        ...WELL,
        online: false,
        sources: failing('basemap'),
        rasterArchiveDownloaded: true,
      }),
    ).toBeNull()
  })

  it('never reports a DEM outage as a background problem', () => {
    // terrain.ts promises a failed elevation model costs relief and contours
    // on a sheet that still draws. A flag for it would spend a hiker's
    // attention on something they cannot act on and do not need.
    expect(backgroundProblem({ ...WELL, sources: failing('elevation') })).toBeNull()
    expect(
      backgroundProblem({ ...WELL, online: false, sources: failing('elevation') }),
    ).toBeNull()
  })
})

describe('sheetNotDrawing', () => {
  // The Downloads card's half of the same question (#334). What makes this a
  // separate function rather than a second read of `backgroundProblem` is
  // which claim it is contradicting: the card's own "this finished".

  it('says a downloaded sheet whose source drew nothing is not drawing', () => {
    expect(sheetNotDrawing(failing('archive'), USGS_SHEET, true)).toBe(true)
    expect(sheetNotDrawing(failing('basemap'), HIKING_SHEET, true)).toBe(true)
  })

  it('stays silent when the card is not claiming the download finished', () => {
    // The whole point of the notice is to contradict a green card. With no
    // card saying so - nothing downloaded, a partial, an eviction - there is
    // nothing to contradict, and the archive source failing with no archive
    // is the ordinary state.
    expect(sheetNotDrawing(failing('archive'), USGS_SHEET, false)).toBe(false)
    expect(sheetNotDrawing(failing('basemap'), HIKING_SHEET, false)).toBe(false)
  })

  it('never blames one sheet for the other one’s source', () => {
    expect(sheetNotDrawing(failing('archive'), HIKING_SHEET, true)).toBe(false)
    expect(sheetNotDrawing(failing('basemap'), USGS_SHEET, true)).toBe(false)
  })

  it('does not let a failed DEM condemn the sheet it belongs to', () => {
    // The hiking sheet is the basemap AND the DEM, and only one of them is
    // the map. A hillshade that never arrived costs relief on a sheet that
    // still draws - telling someone to re-download 300 MB for that would be
    // the strip's DEM rule broken on a different screen.
    expect(sheetNotDrawing(failing('elevation'), HIKING_SHEET, true)).toBe(false)
  })

  it('is silent about a healthy download', () => {
    expect(sheetNotDrawing(HEALTHY, USGS_SHEET, true)).toBe(false)
  })
})

describe('forgetSheet', () => {
  it('clears the sheet being fetched again and leaves its neighbour alone', () => {
    // A remembered failure describes bytes that are about to be replaced.
    // Carried into the fresh copy it would tell a hiker their new download is
    // broken too - and clearing everything would lose a real failure on the
    // sheet nobody touched.
    const both = failing('archive', 'basemap')

    expect(forgetSheet(both, USGS_SHEET)).toEqual({
      basemap: true,
      elevation: false,
      archive: false,
    })
    expect(forgetSheet(both, HIKING_SHEET)).toEqual({
      basemap: false,
      elevation: false,
      archive: true,
    })
  })

  it('leaves the flags it does not speak for untouched', () => {
    expect(forgetSheet(failing('elevation'), HIKING_SHEET).elevation).toBe(true)
  })
})
