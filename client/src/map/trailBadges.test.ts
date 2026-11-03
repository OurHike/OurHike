import { describe, it, expect } from 'vitest'
import { createExpression, latest } from '@maplibre/maplibre-gl-style-spec'
import { MockMap } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import {
  attachTrailBadgeImages,
  registryNameForSource,
  BADGE_FIT_PROPERTY,
  BADGE_MARK_PROPERTY,
  BADGE_NAME_PROPERTY,
  BADGE_SOURCES,
  buildTrailBadgeLayer,
  buildBadgePlate,
  markFitBox,
  TRAIL_BADGE_LAYER_ID,
  TRAIL_BADGE_MARK_SIZE,
  TRAIL_BADGE_PLATE_BORDER,
  TRAIL_BADGE_PLATE_DAY,
  TRAIL_BADGE_PLATE_HEIGHT,
  TRAIL_BADGE_PLATE_NIGHT,
  TRAIL_BADGE_TEXT_FIT_PADDING,
  trailIdForSource,
  trailMarkImageId,
} from './trailBadges'
import { POI_PIN_MIN_ZOOM } from './poiLayers'
import { PRIMARY_TRAIL_SOURCES } from './style'
import { THROUGH_ROUTE_SOURCES } from './trailLabels'
import { parseHex, POI_PIN_PIXEL_RATIO, type PoiIconImage } from './poiIcons'
import { TRAILS } from '../lib/trails'

// The through-route badge (#1283): who earns one, and what the two images
// behind it are made of. The images are checked pixel by pixel the way
// atcNoticeMark.test.ts checks the burst, because "renders something" would
// pass over a chip whose blaze bar had vanished into its ground.

function pixel(
  image: PoiIconImage,
  x: number,
  y: number,
): [number, number, number, number] {
  const at = (y * image.width + x) * 4
  return [image.data[at], image.data[at + 1], image.data[at + 2], image.data[at + 3]]
}

function rgb(hex: string): [number, number, number] {
  return [...parseHex(hex)] as [number, number, number]
}

describe('the layer', () => {
  it('is allowed to overlap, because the placer already kept it clear (the review of #1374)', () => {
    const layout = buildTrailBadgeLayer({ theme: 'light' }).layout as Record<
      string,
      unknown
    >
    expect(layout['icon-allow-overlap']).toBe(true)
    expect(layout['text-allow-overlap']).toBe(true)
    // Still claiming its box, so what is placed after it yields to it.
    expect(layout['icon-ignore-placement']).toBeUndefined()
    expect(layout['text-ignore-placement']).toBeUndefined()
  })
})

describe('who earns a badge', () => {
  it('is exactly the through-route tier the style keys width and sort order off', () => {
    // Restated rather than imported to avoid the import cycle; only safe
    // while the three lists cannot drift.
    expect(BADGE_SOURCES).toEqual(PRIMARY_TRAIL_SOURCES)
    expect(BADGE_SOURCES).toEqual(THROUGH_ROUTE_SOURCES)
  })

  it('keys the A.T. mark off `source`, because nothing publishes a trail_id yet', () => {
    expect(trailMarkImageId('centerline')).toBe(`trail-mark-${TRAILS.AT.id}`)
    expect(trailMarkImageId('oprhp_trails')).toBeNull()
    expect(trailMarkImageId(null)).toBeNull()
  })

  it('wears the Long Path’s own mark since #1307', () => {
    expect(trailMarkImageId('nynjtc_long_path')).toBe(`trail-mark-${TRAILS.LP.id}`)
  })

  it('lets the A.T.’s badge be taken, and not the Long Path’s yet', () => {
    // A mark is a claim about which trail a line IS; taking one is a claim
    // about mileage, elevation and position this build can only back for
    // the A.T. (lib/hikes.ts's trailHasMileAxis, #1317). Wearing a mark and
    // not being takeable is the Long Path's honest state today, not a bug -
    // see TAKEABLE_SOURCES's own header.
    expect(trailIdForSource('centerline')).toBe(TRAILS.AT.id)
    expect(trailIdForSource('nynjtc_long_path')).toBeNull()
    expect(trailIdForSource('oprhp_trails')).toBeNull()
    expect(trailIdForSource(null)).toBeNull()
  })

  it('names no image at all for a source whose steward has granted no mark', () => {
    // The rule this replaced a blaze chip to keep: sources.json's `org_marks`
    // says an ungranted slot renders empty, "never a placeholder mark, never
    // an initial, never a generated shape". Every source but the two the
    // registry knows answers null here, and the layer draws the plate and the
    // name with nothing in front of them.
    expect(trailMarkImageId('centerline')).toBe('trail-mark-AT')
    expect(trailMarkImageId('nynjtc_long_path')).toBe('trail-mark-LP')
    for (const source of [
      'oprhp_trails',
      'side_trails',
      'nynjtc_trails',
      'unknown_source',
    ]) {
      expect(trailMarkImageId(source)).toBeNull()
    }
    expect(trailMarkImageId(null)).toBeNull()
  })

  it('sets the name on a full badge and only the mark on a mark-only one', () => {
    // The layer's text is a `case` on the feature's fit: the mark alone
    // where trailsInView found room for nothing wider.
    const layout = buildTrailBadgeLayer({ theme: 'light' }).layout as Record<
      string,
      unknown
    >
    const text = layout['text-field'] as unknown[]
    expect(text[0]).toBe('case')
    expect(text[1]).toEqual(['==', ['get', BADGE_FIT_PROPERTY], 'mark'])
    const markOnly = JSON.stringify(text[2])
    const full = JSON.stringify(text[3])
    expect(markOnly).toContain('-bare')
    expect(markOnly).not.toContain('"name"')
    expect(full).toContain('["get","name"]')
    expect(full).not.toContain('-bare')
  })
})

describe('the badge with no mark', () => {
  /** What MapLibre's own parser makes of the layer's `text-field` for one
   *  badge feature. Evaluated rather than string-matched, because the claim
   *  being made is about what RENDERS, and the shape of the expression is
   *  only evidence for that if MapLibre agrees. `availableImages` is what the
   *  style has loaded - `attachTrailBadgeImages` registers the marks, so a
   *  registered mark is available and anything else is not. */
  function sections(
    properties: Record<string, string>,
    availableImages: readonly string[],
  ): { text: string; image: string | null }[] {
    const layout = buildTrailBadgeLayer({ theme: 'light' }).layout as Record<
      string,
      unknown
    >
    const compiled = createExpression(
      layout['text-field'] as never,
      latest.layout_symbol['text-field'] as never,
    )
    if (compiled.result === 'error') {
      throw new Error('text-field on the badge layer is not a valid expression')
    }
    const formatted = compiled.value.evaluate(
      { zoom: POI_PIN_MIN_ZOOM - 1 } as never,
      { properties } as never,
      {} as never,
      undefined as never,
      availableImages as never,
    ) as { sections: { text: string; image: { name: string } | null }[] }
    return formatted.sections.map((section) => ({
      text: section.text,
      image: section.image === null ? null : section.image.name,
    }))
  }

  it('renders the name with no image section at all, rather than a stand-in', () => {
    // THE EMPTY SLOT, measured through MapLibre 6.7.0's own expression
    // parser rather than asserted. `badgeFeatures` writes `''` into the mark
    // property for a source with no registry mark, and `['image', '']` is
    // `ResolvedImage.fromString('')`, which returns null for a falsy name
    // (maplibre-gl-shared-dev.mjs:7725). A section with a null image is laid
    // out by `TaggedString.fromFeature` as a TEXT section (:23287), so it
    // contributes no glyph and no warning - the `addImageSection` path that
    // would `warnOnce` about an empty image is never reached.
    expect(sections({ fit: 'full', mark: '', name: 'Long Path' }, [])).toEqual([
      { text: '', image: null },
      { text: 'Long Path', image: null },
    ])
  })

  it('still resolves the mark for a trail that has one, in the same expression', () => {
    // The other half: one expression serves both, so the markless case is not
    // a separate branch that could rot while this one keeps passing.
    const mark = trailMarkImageId('centerline')
    expect(mark).not.toBeNull()
    expect(
      sections({ fit: 'full', mark: mark as string, name: 'Appalachian Trail' }, [
        mark as string,
      ]),
    ).toEqual([
      { text: '', image: mark },
      { text: 'Appalachian Trail', image: null },
    ])
  })

  it('names no blaze chip anywhere in the field', () => {
    // Before 2026-09-29 this was a `coalesce` onto a blaze-chip id, and the
    // chip drew for every trail in the country bar two. The evaluation above
    // would pass with a `coalesce` still present and a chip id that happened
    // to be unavailable, so this guards the expression itself.
    const layout = buildTrailBadgeLayer({ theme: 'light' }).layout as Record<
      string,
      unknown
    >
    const field = JSON.stringify(layout['text-field'])
    expect(field).not.toContain('coalesce')
    expect(field).not.toContain('chip')
    expect(field).toContain(BADGE_MARK_PROPERTY)
    expect(field).toContain(BADGE_NAME_PROPERTY)
  })
})

describe('the plate', () => {
  it('is a 9-slice pill: rounded caps around one stretchable column, with a border outside its content', () => {
    const { image, options } = buildBadgePlate(TRAIL_BADGE_PLATE_DAY)
    const ratio = POI_PIN_PIXEL_RATIO
    const radius = TRAIL_BADGE_PLATE_HEIGHT / 2

    expect(image.height).toBe(TRAIL_BADGE_PLATE_HEIGHT * ratio)
    expect(image.width).toBe((radius * 2 + 1) * ratio)
    expect(options.pixelRatio).toBe(ratio)
    expect(options.stretchX).toEqual([[radius * ratio, (radius + 1) * ratio]])
    expect(options.content).toEqual([
      TRAIL_BADGE_PLATE_BORDER * ratio,
      TRAIL_BADGE_PLATE_BORDER * ratio,
      (radius * 2 + 1 - TRAIL_BADGE_PLATE_BORDER) * ratio,
      (TRAIL_BADGE_PLATE_HEIGHT - TRAIL_BADGE_PLATE_BORDER) * ratio,
    ])
  })

  it('fills with the sheet’s paper at 95% and edges it in the border token', () => {
    for (const face of [TRAIL_BADGE_PLATE_DAY, TRAIL_BADGE_PLATE_NIGHT]) {
      const { image } = buildBadgePlate(face)
      const middle = pixel(
        image,
        Math.floor(image.width / 2),
        Math.floor(image.height / 2),
      )
      expect(middle.slice(0, 3)).toEqual(rgb(face.fill))
      expect(middle[3]).toBe(Math.round(0.95 * 255))
      // The outermost row of the straight edge: border ink, opaque.
      const edge = pixel(image, Math.floor(image.width / 2), 0)
      expect(edge.slice(0, 3)).toEqual(rgb(face.border))
      // Corners are outside the pill.
      expect(pixel(image, 0, 0)[3]).toBe(0)
    }
  })

  it('pads the text so the plate is the mark plus four px of paper each way', () => {
    const [top, right, bottom, left] = TRAIL_BADGE_TEXT_FIT_PADDING
    expect(top + bottom + TRAIL_BADGE_PLATE_BORDER * 2 + TRAIL_BADGE_MARK_SIZE).toBe(
      TRAIL_BADGE_PLATE_HEIGHT,
    )
    expect(left + TRAIL_BADGE_PLATE_BORDER).toBe(4)
    expect(right + TRAIL_BADGE_PLATE_BORDER).toBe(10)
  })
})

describe('attachTrailBadgeImages', () => {
  it('registers the two plates and no blaze image once the layer is in the style, never twice', () => {
    const map = new MockMap({
      style: { layers: [{ id: TRAIL_BADGE_LAYER_ID }], sources: {} },
    })

    attachTrailBadgeImages(map as unknown as MapLibreMap)

    expect(map.hasImage(TRAIL_BADGE_PLATE_DAY.id)).toBe(true)
    expect(map.hasImage(TRAIL_BADGE_PLATE_NIGHT.id)).toBe(true)
    // NO BLAZE IMAGES AT ALL since 2026-09-29. This loop used to assert one
    // chip per palette member plus a bare twin for each; the mark slot is
    // empty now where a steward has granted nothing, so there is nothing
    // keyed off a blaze for this function to add.
    expect([...map.images.keys()].filter((id) => String(id).includes('blaze'))).toEqual(
      [],
    )
    const plate = map.imageOptions.get(TRAIL_BADGE_PLATE_DAY.id) as { stretchX: unknown }
    expect(plate.stretchX).toBeDefined()

    const before = map.images.size
    attachTrailBadgeImages(map as unknown as MapLibreMap)
    expect(map.images.size).toBe(before)
  })

  it('waits for the layer, and registers nothing after detaching', () => {
    const map = new MockMap({})
    const detach = attachTrailBadgeImages(map as unknown as MapLibreMap)
    expect(map.images.size).toBe(0)

    detach()
    map.layerIds = [TRAIL_BADGE_LAYER_ID]
    map.emit('styledata')
    expect(map.images.size).toBe(0)
  })
})

describe('registryNameForSource', () => {
  // The fallback the published sketch below the seam needs: 38 features
  // carrying source, blaze and status and no name at all (read live
  // 2026-09-11), because the publish that would refresh it is held back with
  // the network file it sketches.
  it('names a source the badge already marks', () => {
    expect(registryNameForSource('nynjtc_long_path')).toBe('Long Path')
    expect(registryNameForSource('centerline')).toBe('Appalachian Trail')
  })

  it('names nothing else - a park feed stays unnamed, which is what keeps it off the list', () => {
    expect(registryNameForSource('oprhp_trails')).toBeNull()
    expect(registryNameForSource('dec_hiking_trails')).toBeNull()
    expect(registryNameForSource('')).toBeNull()
    expect(registryNameForSource(null)).toBeNull()
    expect(registryNameForSource(undefined)).toBeNull()
  })

  it('answers for exactly the sources that carry a mark, so the two cannot drift', () => {
    // A source gains a name the moment it gains a mark, and never before:
    // both read BADGE_MARK_BY_SOURCE, which is the file's one answer to
    // "which registry trail is this line".
    for (const source of BADGE_SOURCES) {
      expect(trailMarkImageId(source)).not.toBeNull()
      expect(registryNameForSource(source)).not.toBeNull()
    }
  })

  it('stands down at the waypoint seam, so a pill never competes with a pin', () => {
    // The maintainer, 2026-09-14: "when a user zooms in close enough to see a
    // POI, the trail pills (AT & LP) should hide." The ceiling is the seam
    // constant itself and not a literal, so the two cannot drift apart and
    // leave pills on a map that has just filled with pins.
    const layer = buildTrailBadgeLayer({ theme: 'light' })

    expect(layer.maxzoom).toBe(POI_PIN_MIN_ZOOM)
    // maplibre reads `maxzoom` as exclusive: the badge is gone on the FIRST
    // frame a waypoint can draw, rather than sharing that frame with it.
    expect(layer.maxzoom).not.toBeGreaterThan(POI_PIN_MIN_ZOOM)
    // And it still has no floor of its own - the line layers' floors are the
    // badge's (the review of #1374), which this must not quietly reintroduce.
    expect(layer.minzoom).toBeUndefined()
  })
})

describe('markFitBox', () => {
  it('leaves a square mark filling the whole slot', () => {
    expect(markFitBox(144, 144, 18)).toEqual({ x: 0, y: 0, width: 18, height: 18 })
  })

  it('letterboxes the widest mark the sweep found rather than squashing it', () => {
    // The Foothills Trail's, 185x120, the widest departure from square among
    // the 35 marks in pipeline/reference/trail_marks.json. A filling draw
    // stretched those 120 px of height to all 18, 54% in one axis.
    const box = markFitBox(185, 120, 18)
    expect(box.width).toBe(18)
    expect(box.height).toBeCloseTo(18 * (120 / 185), 6)
    expect(box.y).toBeCloseTo((18 - box.height) / 2, 6)
    expect(box.x).toBe(0)
  })

  it('letterboxes a 4.4:1 image, an extreme no collected mark reaches', () => {
    // SYNTHETIC, and said so: 4.4:1 is not in the manifest. An earlier version
    // of this test called 440x100 "CDTC's, the widest of the 35" - CDTC's mark
    // is 192x192, and 4.40:1 was left over from a superseded sweep round that
    // collected wordmark banners. The case is worth keeping as an extreme; the
    // claim that it was measured was not.
    const box = markFitBox(440, 100, 18)
    expect(box.width).toBe(18)
    expect(box.height).toBeCloseTo(18 * (100 / 440), 6)
    expect(box.y).toBeCloseTo((18 - box.height) / 2, 6)
    expect(box.x).toBe(0)
  })

  it('pillarboxes a mark taller than it is wide', () => {
    // Buckeye's 136x150 is the real tallest; 100x400 is the synthetic extreme.
    for (const [w, h] of [
      [136, 150],
      [100, 400],
    ] as const) {
      const box = markFitBox(w, h, 18)
      expect(box.height).toBe(18)
      expect(box.width).toBeCloseTo(18 * (w / h), 6)
      expect(box.x).toBeCloseTo((18 - box.width) / 2, 6)
    }
  })

  it('keeps the mark inside the slot at every aspect ratio the sweep found', () => {
    // Every non-square pair in pipeline/reference/trail_marks.json, widest
    // first, plus the square case. RE-MEASURED FROM THE BYTES on 2026-09-30
    // when the marks were fetched into the tree: 20 of the 35 are exactly 1:1
    // and these 15 are the rest. Five moved against the first recording -
    // four in absolute size only (the SVGs record viewBox units; Wix served
    // a different rendition of Standing Stone's) and Mason-Dixon in aspect,
    // 512x512 recorded against 300x288 actual.
    for (const [w, h] of [
      [185, 120], // Foothills Trail, 1.54:1 - the widest
      [322.738, 210.842], // Long Trail, 1.531:1 (an SVG, so viewBox units)
      [191, 150], // Northville-Placid
      [266, 209], // Finger Lakes
      [97, 90], // Grand Enchantment
      [300, 288], // Mason-Dixon
      [150, 144], // Mogollon Rim
      [372, 356], // New England
      [178, 171], // Loyalsock
      [153, 150], // Lone Star
      [142, 140], // Ice Age
      [114, 115], // Condor
      [150, 151], // Long Path
      [47, 50], // Cohos
      [121.25, 134.03], // Buckeye, the tallest (an SVG)
      [144, 144], // and the square case
    ] as const) {
      const box = markFitBox(w, h, 18)
      expect(box.width).toBeLessThanOrEqual(18 + 1e-9)
      expect(box.height).toBeLessThanOrEqual(18 + 1e-9)
      expect(box.x).toBeGreaterThanOrEqual(-1e-9)
      expect(box.y).toBeGreaterThanOrEqual(-1e-9)
      // Proportions survive, which is the whole point of the change.
      expect(box.width / box.height).toBeCloseTo(w / h, 6)
    }
  })

  it('falls back to the full slot for an image with no intrinsic size', () => {
    // An SVG with no width/height attributes decodes to 0x0 in some browsers;
    // a mark drawn at 0x0 would be an invisible badge rather than a wrong one.
    expect(markFitBox(0, 0, 18)).toEqual({ x: 0, y: 0, width: 18, height: 18 })
  })
})
