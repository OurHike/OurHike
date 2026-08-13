import { describe, it, expect } from 'vitest'
import {
  ATC_UPDATE_CASING_LAYER_ID,
  ATC_UPDATE_CASING_WIDTH,
  ATC_UPDATE_HALO_LAYER_ID,
  ATC_UPDATE_HALO_RADIUS,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_POINT_DIAMETER,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
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

describe('the ATC’s point notice sits just above every pin on the map', () => {
  // MEASURED AS INK AGAINST INK, which is the comparison that went wrong
  // twice. MapLibre draws `circle-stroke-width` OUTSIDE `circle-radius`, so
  // the constant handed to the spec is 4px narrower than what a hiker sees; a
  // pin's own 38px is its whole circle, disc and edge and halo together
  // (`pinGeometry`). Comparing the spec value to the pin's drawn size made the
  // dot a size larger than every assertion here claimed - which is exactly how
  // a version that had already been cut once still read too big.
  it('is wider than a waypoint pin, drawn edge to drawn edge', () => {
    // 38px. The dot was 10px, so a closed shelter reported by the organisation
    // that maintains it was a quarter of the width of OurHike's own pin for
    // the same shelter.
    expect(ATC_UPDATE_POINT_DRAWN_WIDTH).toBeGreaterThan(POI_PIN_SIZE)
  })

  it('clears it by as little as the scale allows, and no more', () => {
    // The size is a threshold, not a ranking. Being drawn over everything
    // (map/style.ts) is what stops a notice being hidden; the pixels only have
    // to make an eye land here rather than on the pin beside it. Two passes
    // spent more than that and both looked wrong on a phone.
    expect(ATC_UPDATE_POINT_DRAWN_WIDTH - POI_PIN_SIZE).toBeLessThanOrEqual(4)
  })

  it('does NOT outgrow the serious-warning pin as a disc', () => {
    // 44px, and poiIcons.ts calls it "the biggest thing on the map". The first
    // pass took the dot past it at `--space-12`; the second still tied it once
    // the casing was counted. It now stops short with the casing included,
    // which is the only spelling of this that means anything.
    expect(ATC_UPDATE_POINT_DRAWN_WIDTH).toBeLessThan(WARNING_PIN.sizePx)
  })

  it('declares a radius that leaves room for its own casing', () => {
    // The derivation, held so the two cannot drift apart: what MapLibre is
    // told, plus the stroke it puts outside that, is the width above.
    expect(ATC_UPDATE_POINT_DIAMETER + ATC_UPDATE_CASING_WIDTH * 2).toBe(
      ATC_UPDATE_POINT_DRAWN_WIDTH,
    )
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
    expect(ATC_UPDATE_HALO_RADIUS).toBeLessThan(ATC_UPDATE_POINT_DRAWN_WIDTH)
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
