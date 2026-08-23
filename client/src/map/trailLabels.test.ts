import { describe, it, expect } from 'vitest'
import {
  buildTrailLabelLayer,
  CHOSEN_LABEL_SORT_KEY,
  NEARBY_LABEL_SORT_KEY,
  TRAIL_LABEL_LAYER_ID,
  TRAIL_LABEL_SORT_KEY_EXPRESSION,
} from './trailLabels'
import { nearbyTrailOpacityExpression, CHOSEN_SYSTEM_SOURCES } from './nearbyTrails'
import {
  BLAZE_LAYER_ID,
  PRIMARY_TRAIL_SORT_KEY,
  SIDE_TRAIL_SORT_KEY,
  TRAILS_SOURCE_ID,
  buildMapStyle,
} from './style'
import { POI_LAYER_ID, POI_PIN_MIN_ZOOM } from './poiLayers'
import { WARNING_LAYER_ID } from './warningLayers'

const STYLE_OPTIONS = {
  topoArchiveUrl: 'pmtiles://archive.pmtiles',
  trailsUrl: 'blob:trails',
  background: 'usgs_topo_offline' as const,
}

const LABEL = buildTrailLabelLayer(
  TRAILS_SOURCE_ID,
  '#14130f',
  '#ffffff',
  POI_PIN_MIN_ZOOM,
)

function layerIds() {
  return buildMapStyle(STYLE_OPTIONS).layers.map((l) => l.id)
}

function layout(layer: { layout?: unknown }): Record<string, unknown> {
  return layer.layout as Record<string, unknown>
}

/** One built layer's paint, or a failure naming the layer - so a rename reads
 *  as "no layer" rather than as an undefined paint property. */
function paintOf(layerId: string): Record<string, unknown> {
  const found = buildMapStyle(STYLE_OPTIONS).layers.find((l) => l.id === layerId)
  if (found === undefined) throw new Error(`no layer "${layerId}" in the style`)
  return found.paint as Record<string, unknown>
}

describe('the trail-name label layer', () => {
  it('names a trail from the property the tap handler already reads', () => {
    // `name` is what map/lineTaps.ts pulls off a tapped feature for the sheet.
    // One property, so a trail the sheet can name is a trail the map can label.
    expect(layout(LABEL)['text-field']).toEqual(['get', 'name'])
  })

  it('draws the name along its line, not floating beside a point', () => {
    expect(layout(LABEL)['symbol-placement']).toBe('line')
  })

  it('omits an unnamed trail rather than labelling it "Unnamed"', () => {
    // The restraint lib/lineDetail.ts applies to a spur with no resolved
    // destination. A label this map invented is a fact about somebody else's
    // data that nobody stands behind.
    const filter = (LABEL as { filter?: unknown }).filter as unknown[]
    expect(filter[0]).toBe('!=')
    expect(filter[1]).toEqual(['to-string', ['get', 'name']])
    expect(filter[2]).toBe('')
  })

  it('lets a name that will not fit be dropped, rather than placing it off its trail', () => {
    // MapLibre's own behaviour for `symbol-placement: line`, kept by NOT
    // setting text-allow-overlap. A name printed where its trail is not is the
    // false statement at a junction this layer exists to prevent.
    expect(layout(LABEL)['text-allow-overlap']).toBeUndefined()
    expect(layout(LABEL)['text-ignore-placement']).toBeUndefined()
  })
})

describe('labels dim with their lines', () => {
  it('takes the line’s own opacity expression, not a copy of the rule', () => {
    // features/NEARBY_TRAILS.md §1, and the half #783 could not build. One
    // expression shared with the blaze layer is what stops a label drifting
    // away from the line it names — a full-strength name on a ghosted line
    // points at the wrong thing.
    const paint = LABEL.paint as Record<string, unknown>
    expect(paint['text-opacity']).toEqual(nearbyTrailOpacityExpression())
  })

  it('is the same expression the blaze layer paints with, in the built style', () => {
    expect(paintOf(TRAIL_LABEL_LAYER_ID)['text-opacity']).toEqual(
      paintOf(BLAZE_LAYER_ID)['line-opacity'],
    )
  })
})

describe('the sort key, which runs the opposite way from the lines’', () => {
  // The trap this module was written around. `line-sort-key` HIGHER draws
  // later and therefore on top; `symbol-sort-key` LOWER is placed first and
  // therefore WINS. Copying the line expression would have given the chosen
  // trail's label the worst claim on space at a crowded junction — the one
  // place the feature exists to help.

  it('gives the chosen trail the LOWER key, so its label is placed first', () => {
    expect(CHOSEN_LABEL_SORT_KEY).toBeLessThan(NEARBY_LABEL_SORT_KEY)
  })

  it('is inverted relative to the line sort key, and that is the point', () => {
    // Asserted as a relationship rather than as two numbers: if somebody
    // "fixes" the labels to match the lines, this fails and says why.
    const linesFavourHigher = PRIMARY_TRAIL_SORT_KEY > SIDE_TRAIL_SORT_KEY
    const labelsFavourLower = CHOSEN_LABEL_SORT_KEY < NEARBY_LABEL_SORT_KEY

    expect(linesFavourHigher).toBe(true)
    expect(labelsFavourLower).toBe(true)
  })

  it('resolves the chosen system to the winning key and everything else to the loser', () => {
    const [op, condition, whenChosen, whenNearby] = TRAIL_LABEL_SORT_KEY_EXPRESSION
    expect(op).toBe('case')

    const members = ((condition as unknown[])[2] as ['literal', string[]])[1]
    expect(members).toEqual([...CHOSEN_SYSTEM_SOURCES])
    expect(whenChosen).toBe(CHOSEN_LABEL_SORT_KEY)
    expect(whenNearby).toBe(NEARBY_LABEL_SORT_KEY)
  })
})

describe('where it sits in the stack', () => {
  it('is placed before every pin, so a trail name can never suppress a waypoint', () => {
    // The safety rule, and the one an earlier draft of this layer broke.
    // Placement runs TOP-DOWN — liveTopo.test.ts's pins-last case establishes
    // that from MapLibre's own PauseablePlacement, which starts at
    // `order.length - 1` and decrements — so a LATER symbol layer wins. A
    // trail name is the lowest-priority symbol on this map, so it must come
    // first and lose.
    const ids = layerIds()

    expect(ids.indexOf(TRAIL_LABEL_LAYER_ID)).toBeGreaterThan(-1)
    expect(ids.indexOf(TRAIL_LABEL_LAYER_ID)).toBeLessThan(ids.indexOf(POI_LAYER_ID))
    expect(ids.indexOf(TRAIL_LABEL_LAYER_ID)).toBeLessThan(ids.indexOf(WARNING_LAYER_ID))
  })

  it('draws over the line it names', () => {
    const ids = layerIds()
    expect(ids.indexOf(BLAZE_LAYER_ID)).toBeLessThan(ids.indexOf(TRAIL_LABEL_LAYER_ID))
  })

  it('ships on the offline sheet, not only the live one', () => {
    // The trails draw on both, so their names do too — and it is why the
    // offline style had to start declaring a glyph endpoint.
    expect(layerIds()).toContain(TRAIL_LABEL_LAYER_ID)
    expect(buildMapStyle(STYLE_OPTIONS).glyphs).toBeDefined()
  })

  it('stays off the map at the zoom where the subject is the park, not the trails', () => {
    // features/NEARBY_TRAILS.md §8: "at z7 Harriman is one green shape". Tied
    // to the pins' own threshold so the two cannot drift.
    const label = buildMapStyle(STYLE_OPTIONS).layers.find(
      (l) => l.id === TRAIL_LABEL_LAYER_ID,
    )
    expect((label as { minzoom?: number }).minzoom).toBe(POI_PIN_MIN_ZOOM)
  })
})
