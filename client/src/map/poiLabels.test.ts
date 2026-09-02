// Tests for map/poiLabels.ts - waypoint names on the builder's map (#1194).
//
// The rules worth pinning, all of them about a name claiming more than it
// should:
//
//   NEVER "Unnamed". lib/trailData.ts fills a missing name with that literal
//   string, so without a filter every anonymous spring in the park would
//   print the word at 13px - worse than silence, in the way a fabricated
//   figure is.
//
//   OFF BY DEFAULT. This is the builder's layer; #1135 decided what the
//   opening map draws without it, and turning it on everywhere is a design
//   question rather than a side effect.
//
//   A CHOSEN STOP OUTRANKS EVERY UNCHOSEN WAYPOINT. The handoff's rule is
//   that "a stop the user chose always keeps its name", and a name that
//   vanishes when the map gets busy is not a kept one.

import { describe, expect, it } from 'vitest'

import {
  buildPoiLabelLayer,
  LABELLED_POI_TYPES,
  poiLabelFilter,
  poiLabelMinZoom,
  poiLabelSortKey,
  POI_LABEL_LAYER_ID,
} from './poiLabels'
import { LABEL_TIER, TIER_MIN_ZOOM } from './labelLadder'
import { POI_NAME_PROPERTY } from './poiLayers'

/** The built layer's filter. `LayerSpecification` is a union and its
 *  background arm has no `filter`, so the narrowing happens once here. */
function filterOf(chosenStopIds: readonly string[]): unknown {
  return (buildPoiLabelLayer(chosenStopIds) as { filter?: unknown }).filter
}

/** The layout of the built layer, as a plain bag. */
function layout(): Record<string, unknown> {
  const built = buildPoiLabelLayer()
  return (built as { layout: Record<string, unknown> }).layout
}

describe('the layer', () => {
  it('draws the name property and nothing else', () => {
    expect(layout()['text-field']).toEqual(['get', POI_NAME_PROPERTY])
  })

  it('uses the one bundled fontstack', () => {
    // map/liveTopo.ts ships exactly one under public/glyphs/. Any other stack
    // 404s and MapLibre draws no text at all - silently, which is how the
    // builder's own tap numbers were blank until #1194 found them.
    expect(layout()['text-font']).toEqual(['Noto Sans Regular'])
  })

  it('is off until the builder asks for it', () => {
    expect(layout().visibility).toBe('none')
  })

  it('leaves the declutter at the spec default, which is the whole ladder', () => {
    // An `text-allow-overlap: true` added later for one screenshot would
    // silently undo every priority decision in map/labelLadder.ts.
    expect(layout()['text-allow-overlap']).toBeUndefined()
  })

  it('sits beside a pin rather than on it', () => {
    // A pin is 30-38px and centred on the waypoint, so an anchored label
    // would land on its own glyph.
    expect(layout()['text-variable-anchor']).toBeDefined()
    expect(layout()['text-radial-offset']).toBeGreaterThan(0)
  })

  it('keeps its id stable, because the shell switches it by name', () => {
    expect(buildPoiLabelLayer().id).toBe(POI_LABEL_LAYER_ID)
  })
})

describe('which names are drawn', () => {
  it('refuses an empty name and the literal "Unnamed"', () => {
    const filter = JSON.stringify(poiLabelFilter([]))

    expect(filter).toContain('Unnamed')
    expect(poiLabelFilter([])[0]).toBe('all')
  })

  it('names the classes worth naming and no others', () => {
    // Privies, crossings and resupply points keep their pins and stay
    // anonymous - this layer answers "where do I start" and "which shelter is
    // that", and a privy label at every shelter is the clutter complaint #2
    // was about.
    expect(LABELLED_POI_TYPES).toContain('parking')
    expect(LABELLED_POI_TYPES).toContain('shelter')
    expect(LABELLED_POI_TYPES).toContain('campsite')
    expect(LABELLED_POI_TYPES).not.toContain('privy')
    expect(LABELLED_POI_TYPES).not.toContain('crossing')
    expect(LABELLED_POI_TYPES).not.toContain('resupply')
  })

  it('drops a class the hiker switched off', () => {
    const shown = poiLabelFilter(['shelter'])[1] as unknown[]

    expect(JSON.stringify(shown)).not.toContain('shelter')
    expect(JSON.stringify(shown)).toContain('campsite')
  })
})

describe('the priority', () => {
  it('puts the way IN on the gateway rung, above the landmarks', () => {
    // The handoff's central claim: how a hiker reaches the trail is what a
    // PLANNING map is for, so a trailhead and a lot outrank a spring.
    // Deliberately the opposite of map/poiPriority.ts, which is right about a
    // hiker already walking.
    const key = JSON.stringify(poiLabelSortKey([]))

    expect(key).toContain(`"trailhead",${LABEL_TIER.gateway}`)
    expect(key).toContain(`"parking",${LABEL_TIER.gateway + 1}`)
    expect(key).toContain(`"shelter",${LABEL_TIER.landmark}`)
    expect(LABEL_TIER.gateway).toBeLessThan(LABEL_TIER.landmark)
  })

  it('breaks the gateway tie toward the trailhead, WITHIN the rung', () => {
    // Both are tier 1 and both must stay tier 1 - map/labelLadder.ts spaces
    // the rungs by tens precisely so a layer can rank inside one without
    // leaving it. A trailhead wins the tie because it is the choice the map
    // is being read to make; a lot is how you get to it.
    //
    // The +1 has to stay under the next rung or the ordering silently becomes
    // a demotion rather than a tiebreak, which is the failure this pins.
    const key = JSON.stringify(poiLabelSortKey([]))

    expect(key.indexOf('"trailhead"')).toBeLessThan(key.indexOf('"parking"'))
    expect(LABEL_TIER.gateway + 1).toBeLessThan(LABEL_TIER.route)
  })

  it('draws a trailhead name in the same zoom band as a lot', () => {
    // A tiebreak inside a rung must not become a different arrival zoom: the
    // handoff's "park" band names both, and one showing up two zooms later
    // than the other would read as the map losing it.
    const zoom = JSON.stringify(poiLabelMinZoom([]))

    expect(zoom).toContain('trailhead')
    expect(zoom).toContain('parking')
  })

  it('lifts a chosen stop to the route rung, above every trail name', () => {
    const key = poiLabelSortKey(['s1'])

    // The `case` arm's consequent - the chosen branch.
    expect(key[2]).toBe(LABEL_TIER.route)
    expect(JSON.stringify(key)).toContain('s1')
    expect(LABEL_TIER.route).toBeLessThan(LABEL_TIER.routeTrail)
  })

  it('shows a chosen stop’s name as soon as any label draws', () => {
    const zoom = poiLabelMinZoom(['s1'])

    expect(zoom[2]).toBe(TIER_MIN_ZOOM.route)
  })

  it('gates the rungs in the FILTER, so a hidden name takes no collision space', () => {
    // The wiring this pins was missing once: `poiLabelMinZoom` was written,
    // exported and tested while the layer ignored it, so every landmark name
    // drew at the parking tier's zoom. A layer has one `minzoom` and the
    // ladder has three rungs, so the gate has to be a filter.
    //
    // And a filter rather than `text-opacity`: a symbol faded to zero still
    // takes part in placement, so it would go on costing a parking label its
    // space at the zoom where parking is the only thing that matters.
    expect(JSON.stringify(filterOf([]))).toContain('"zoom"')
    expect(JSON.stringify(filterOf([]))).toContain(String(TIER_MIN_ZOOM.landmark))
  })

  it('carries the chosen stops into the filter as well as the sort key', () => {
    // Otherwise a stop picked at the park view would rank first among labels
    // that the filter had already taken off the map.
    expect(JSON.stringify(filterOf(['s1']))).toContain('s1')
  })

  it('holds landmark names back to the landmark zoom', () => {
    // So the wide view is the handoff's "park" band - parking, roads and the
    // route - rather than every shelter in Harriman at once.
    const zoom = JSON.stringify(poiLabelMinZoom([]))

    expect(zoom).toContain(String(TIER_MIN_ZOOM.landmark))
    expect(TIER_MIN_ZOOM.gateway).toBeLessThanOrEqual(TIER_MIN_ZOOM.landmark)
  })
})
