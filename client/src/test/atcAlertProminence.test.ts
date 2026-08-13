import { describe, it, expect } from 'vitest'
import {
  ATC_UPDATE_CASING_LAYER_ID,
  ATC_UPDATE_HALO_LAYER_ID,
  ATC_UPDATE_HALO_RADIUS,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_POINT_DIAMETER,
  ATC_UPDATE_POINT_LAYER_ID,
} from '../lib/atcUpdateStyle'
import { POI_LAYER_ID } from '../map/poiLayers'
import { POI_PIN_SIZE } from '../map/poiIcons'
import { WARNING_LAYER_ID } from '../map/warningLayers'
import { WARNING_PIN } from '../lib/seriousWarnings'
import { buildMapStyle } from '../map/style'

// The ATC's dot against everything else drawn on the same canvas.
//
// This file exists because neither half of the comparison could be made where
// either side lives. lib/atcUpdateStyle.ts knows the dot's size and nothing
// about a waypoint pin; map/poiIcons.ts knows the pin's and nothing about the
// dot; map/style.ts stacks the layers and knows the size of none of them. So
// the property that actually matters - THE ATC'S NOTICE IS THE LOUDEST AND
// TOP-MOST MARK ON THIS MAP - was, until this file, asserted nowhere, which is
// how it came to be false in both directions at once: a 10px dot underneath a
// 38px pin.
//
// Both halves are held here, against the real constants rather than against
// numbers copied out of them, so that shrinking the dot or reordering the
// layers fails a test instead of quietly restoring the bug.

/** Layer ids in draw order - later means on top.
 *
 *  Both sheets, because the live one splices seventeen more layers into the
 *  same array and "last of all" has to survive that. `every` rather than a
 *  loop so a failure names which sheet broke. */
const SHEETS = ['usgs_topo_offline', 'hiking_topo_live'] as const

function drawOrder(background: (typeof SHEETS)[number]): string[] {
  return buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
    background,
  }).layers.map((layer) => layer.id)
}

function isAboveOnEverySheet(top: string, bottom: string): boolean {
  return SHEETS.every((sheet) => {
    const ids = drawOrder(sheet)
    return ids.indexOf(bottom) !== -1 && ids.indexOf(top) > ids.indexOf(bottom)
  })
}

describe('the ATC’s point notice outsizes every pin on the map', () => {
  it('is larger than a waypoint pin', () => {
    // 38px, `--space-9`. The dot was 10px, so a closed shelter reported by the
    // organisation that maintains it was a quarter of the width of OurHike's
    // own pin for the same shelter.
    expect(ATC_UPDATE_POINT_DIAMETER).toBeGreaterThan(POI_PIN_SIZE)
  })

  it('does NOT outgrow the serious-warning pin as a disc', () => {
    // 44px, and poiIcons.ts calls it "the biggest thing on the map". A first
    // pass took the dot past it at `--space-12` and the result read as a wound
    // rather than a notice, so the disc now stops short - the dot only has to
    // out-read the pins it sits among, and being drawn over all of them is
    // what does the rest.
    expect(ATC_UPDATE_POINT_DIAMETER).toBeLessThan(WARNING_PIN.sizePx)
  })

  it('carries a glow that reaches past every one of them', () => {
    // Size alone is what a hiker sees once they are already looking at that
    // part of the screen. The glow is for the rest of the time - and it is
    // where the ATC notice does end up the widest mark on the map, in the one
    // form that cannot hide anything: an edgeless gradient fading to zero.
    expect(ATC_UPDATE_HALO_RADIUS * 2).toBeGreaterThan(WARNING_PIN.sizePx)
    expect(ATC_UPDATE_HALO_RADIUS * 2).toBeGreaterThan(POI_PIN_SIZE)
  })

  it('keeps the glow tighter than the dot is wide, so it reads as a rim', () => {
    // The other half of the first pass being too big: at scale 2 the glow was
    // a 96px circle of red per notice, most of a phone's width for one mile
    // marker. The dot says where; the glow only says look.
    expect(ATC_UPDATE_HALO_RADIUS).toBeLessThan(ATC_UPDATE_POINT_DIAMETER)
  })
})

describe('and nothing on the map is drawn over it', () => {
  it('sits above the waypoint pins', () => {
    expect(isAboveOnEverySheet(ATC_UPDATE_POINT_LAYER_ID, POI_LAYER_ID)).toBe(true)
    expect(isAboveOnEverySheet(ATC_UPDATE_LAYER_ID, POI_LAYER_ID)).toBe(true)
  })

  it('sits above the serious-warning pins', () => {
    expect(isAboveOnEverySheet(ATC_UPDATE_POINT_LAYER_ID, WARNING_LAYER_ID)).toBe(true)
  })

  it('is the last thing either sheet draws, so this cannot be got round', () => {
    // Named layers can be added one at a time and each addition argued for
    // separately; "the ATC group is last" is the property that survives that.
    // Asserted on the live sheet too, which splices seventeen OSM layers into
    // the same array - a new one appended rather than inserted would cover
    // exactly the mark this whole file is about.
    for (const sheet of SHEETS) {
      expect(drawOrder(sheet).slice(-4)).toEqual([
        ATC_UPDATE_HALO_LAYER_ID,
        ATC_UPDATE_CASING_LAYER_ID,
        ATC_UPDATE_LAYER_ID,
        ATC_UPDATE_POINT_LAYER_ID,
      ])
    }
  })
})
