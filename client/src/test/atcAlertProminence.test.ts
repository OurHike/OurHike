import { describe, it, expect } from 'vitest'
import {
  ATC_NOTICE_CASING_WIDTH,
  ATC_NOTICE_FILL_RADIUS,
  ATC_UPDATE_CASING_LAYER_ID,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
  ATC_UPDATE_POINT_LAYER_ID,
  ATC_UPDATE_POINT_ZOOM_STOPS,
} from '../lib/atcUpdateStyle'
import {
  POI_ICON_SIZE_EXPRESSION,
  POI_LAYER_ID,
  POI_PIN_MIN_ZOOM,
} from '../map/poiLayers'
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

  it('keeps that clearance at every zoom a waypoint pin is drawn at', () => {
    // Both ramp, so "wider than a pin" is a claim about a range rather than a
    // number, and the dot must not be the smaller mark at some middle zoom
    // nobody screenshotted.
    //
    // ASSERTED AS THE PROPERTY, NOT AS A SHARED STOP LIST. It used to compare
    // the two `interpolate` tables for equality, which held only because the
    // dot's middle stop had been chosen as `POI_MIN_ZOOM`/0.6 to match. #597
    // moved the pins' lower anchor to POI_PIN_MIN_ZOOM = 12 and the dot's
    // stayed at 9 - correctly, because lib/atcUpdateStyle.ts sizes this dot
    // against THE GROUND IT IS DRAWN ON rather than against pins, and it has no
    // minzoom precisely so a hiker planning a week can still see it. Shrinking
    // ATC's notices at planning zooms to keep two tables identical would have
    // been the tail wagging the dog.
    //
    // So this now measures what the section is actually about, and holds
    // whichever constant moves next.
    const scaleAt = (
      stops: ReadonlyArray<readonly [number, number]>,
      zoom: number,
    ): number => {
      const clamped = Math.min(Math.max(zoom, stops[0][0]), stops[stops.length - 1][0])
      for (let at = 0; at < stops.length - 1; at += 1) {
        const [lowZoom, lowScale] = stops[at]
        const [highZoom, highScale] = stops[at + 1]
        if (clamped <= highZoom) {
          const span = highZoom - lowZoom
          const along = span === 0 ? 0 : (clamped - lowZoom) / span
          return lowScale + along * (highScale - lowScale)
        }
      }
      return stops[stops.length - 1][1]
    }

    const pinStops: Array<[number, number]> = []
    for (let at = 3; at < POI_ICON_SIZE_EXPRESSION.length; at += 2) {
      pinStops.push([
        POI_ICON_SIZE_EXPRESSION[at] as number,
        POI_ICON_SIZE_EXPRESSION[at + 1] as number,
      ])
    }

    // Every zoom where both are drawn - the pin layer's minzoom upward. 22 is
    // MapLibre's own maximum.
    for (let zoom = POI_PIN_MIN_ZOOM; zoom <= 22; zoom += 0.5) {
      const dot =
        ATC_UPDATE_POINT_DRAWN_WIDTH * scaleAt(ATC_UPDATE_POINT_ZOOM_STOPS, zoom)
      const pin = POI_PIN_SIZE * scaleAt(pinStops, zoom)
      expect(dot, `ATC dot must outsize a waypoint pin at z${zoom}`).toBeGreaterThan(pin)
    }
  })

  it('does NOT outgrow the serious-warning pin as a disc', () => {
    // 44px, and poiIcons.ts calls it "the biggest thing on the map". The first
    // pass took the dot past it at `--space-12`; the second still tied it once
    // the casing was counted. It now stops short with the casing included,
    // which is the only spelling of this that means anything.
    expect(ATC_UPDATE_POINT_DRAWN_WIDTH).toBeLessThan(WARNING_PIN.sizePx)
  })

  it('reaches its full width with its own casing inside it', () => {
    // The derivation, held so the two cannot drift apart: the red plus the
    // hairline round it is the drawn width above. It used to read the other way
    // - MapLibre puts `circle-stroke-width` OUTSIDE the radius, so a dot
    // declared at 40 covered 44 and tied the warning pin it was meant to stay
    // under. The burst is rasterised rather than stroked, so the edge is inside
    // the number by construction; this holds that it stayed that way.
    expect(ATC_NOTICE_FILL_RADIUS + ATC_NOTICE_CASING_WIDTH).toBe(
      ATC_UPDATE_POINT_DRAWN_WIDTH / 2,
    )
  })

  it('no longer buys any of that with a glow', () => {
    // WHAT #1071 GAVE UP, asserted rather than left as an absence in a diff.
    // The glow reached past every pin on the map and was the one form in which
    // this notice could be the widest mark without hiding anything. It is gone,
    // because a 54px wash of red behind an open burst is the solid disc back
    // again - so every claim this file makes about prominence now rests on
    // size, draw order and shape alone.
    //
    // @unvalidated Nobody has watched a hiker find one of these on a phone in
    // sun. lib/atcUpdateStyle.ts carries the trade in full and what would
    // settle it; if the answer comes back wrong, the glow returns on a zoom
    // ramp rather than at one strength.
    for (const sheet of SHEETS) {
      expect(drawOrder(sheet).some((id) => id.includes('halo'))).toBe(false)
    }
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
      expect(drawOrder(sheet).slice(-3)).toEqual([
        ATC_UPDATE_CASING_LAYER_ID,
        ATC_UPDATE_LAYER_ID,
        ATC_UPDATE_POINT_LAYER_ID,
      ])
    }
  })
})
