// Putting the elevation chart's focus on the map: the hovered mile as a dot,
// the selected stretch as a band (#135).
//
// Same division of labour as routeLayers.ts: lib/chartProfile.ts is
// arithmetic, lib/trailPosition.ts turns miles into coordinates, and this is
// the module that knows about MapLibre. The band is drawn from `trailSlice`
// output, so it follows the centerline's real geometry - the same reason the
// route builder gives.
//
// UNLIKE the other overlay modules, this one adds its own source and layers
// at runtime instead of being baked into the style build (map/style.ts).
// Deliberate, for two reasons that agree: the chart exists only above the
// 900px breakpoint, so baking its layers into every phone's style would
// spend style-build surface on something a phone never draws; and hover
// focus is ephemeral view state, not map content - when the style is
// swapped (background change, theme change) there is nothing worth
// preserving across the swap. The cost is re-adding after each style swap,
// which the styledata listener below pays; whenStyleReady cannot, because
// it waits for a source the build put there and this source is ours to put.

import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'

export const CHART_FOCUS_SOURCE_ID = 'chart-focus'
export const CHART_FOCUS_BAND_LAYER_ID = 'chart-focus-band'
export const CHART_FOCUS_LINE_LAYER_ID = 'chart-focus-line'
export const CHART_FOCUS_POINT_LAYER_ID = 'chart-focus-point'

// Fixed inks, both themes, like the closure bands and the route: an overlay
// that carries one identity keeps it everywhere. Blaze orange is the chart's
// own selection wash (chrome: --accent-blaze-orange), so the band on the
// ground and the band on the profile read as the same statement; the paper
// ring keeps the dot visible on the dark styles.
const FOCUS_INK = '#c1611a'
const FOCUS_RING = '#fffdf7'

/** One or more centerline runs, straight from trailSlice. */
export type StretchRuns = Array<Array<[number, number]>>

export interface ChartFocusHandle {
  /** The hovered mile's coordinate, or null to clear the dot. */
  setPoint(at: [number, number] | null): void
  /** The selected stretch's centerline runs, or null to clear the band. */
  setStretch(runs: StretchRuns | null): void
  /** Removes the layers, the source and the listener. Safe to call twice. */
  detach(): void
}

interface FocusState {
  point: [number, number] | null
  stretch: StretchRuns | null
}

function featureCollection(state: FocusState): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = []
  if (state.stretch !== null && state.stretch.length > 0) {
    features.push({
      type: 'Feature',
      geometry: { type: 'MultiLineString', coordinates: state.stretch },
      properties: {},
    })
  }
  if (state.point !== null) {
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: state.point },
      properties: {},
    })
  }
  return { type: 'FeatureCollection', features }
}

/**
 * Attaches the focus source and layers to a live map and returns a handle
 * whose setters write through immediately. Everything is guarded the way
 * whenStyleReady guards its one write: a failure warns and costs the
 * overlay, never the map.
 */
export function attachChartFocus(map: MapLibreMap): ChartFocusHandle {
  const state: FocusState = { point: null, stretch: null }
  let detached = false

  const ensure = () => {
    if (detached) return
    try {
      if (map.getSource(CHART_FOCUS_SOURCE_ID) === undefined) {
        map.addSource(CHART_FOCUS_SOURCE_ID, {
          type: 'geojson',
          data: featureCollection(state) as never,
        })
        // The wide translucent band and the solid core, the same two-pass
        // reading the chart's own selection rect + edges give.
        map.addLayer({
          id: CHART_FOCUS_BAND_LAYER_ID,
          type: 'line',
          source: CHART_FOCUS_SOURCE_ID,
          filter: ['==', ['geometry-type'], 'LineString'],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': FOCUS_INK, 'line-width': 10, 'line-opacity': 0.28 },
        })
        map.addLayer({
          id: CHART_FOCUS_LINE_LAYER_ID,
          type: 'line',
          source: CHART_FOCUS_SOURCE_ID,
          filter: ['==', ['geometry-type'], 'LineString'],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': FOCUS_INK, 'line-width': 2.5, 'line-opacity': 0.9 },
        })
        map.addLayer({
          id: CHART_FOCUS_POINT_LAYER_ID,
          type: 'circle',
          source: CHART_FOCUS_SOURCE_ID,
          filter: ['==', ['geometry-type'], 'Point'],
          paint: {
            'circle-radius': 5,
            'circle-color': FOCUS_INK,
            'circle-stroke-color': FOCUS_RING,
            'circle-stroke-width': 2,
          },
        })
        return
      }

      const source = map.getSource<GeoJSONSource>(CHART_FOCUS_SOURCE_ID)
      if (source !== undefined && typeof source.setData === 'function') {
        source.setData(featureCollection(state) as never)
      }
    } catch {
      // The style is mid-parse or mid-swap; the next styledata retries. Not
      // warned per-attempt - styledata fires often and this is the normal
      // path during a style swap, not a defect.
    }
  }

  // styledata keeps firing (see map/styleReady.ts for why `load` cannot be
  // trusted for this), so it covers both the initial attach racing the
  // style parse and every later setStyle swap dropping the runtime source.
  const onStyleData = () => ensure()
  map.on('styledata', onStyleData)
  ensure()

  return {
    setPoint(at) {
      state.point = at
      ensure()
    },
    setStretch(runs) {
      state.stretch = runs
      ensure()
    },
    detach() {
      if (detached) return
      detached = true
      map.off('styledata', onStyleData)
      try {
        for (const id of [
          CHART_FOCUS_POINT_LAYER_ID,
          CHART_FOCUS_LINE_LAYER_ID,
          CHART_FOCUS_BAND_LAYER_ID,
        ]) {
          if (map.getLayer(id) !== undefined) map.removeLayer(id)
        }
        if (map.getSource(CHART_FOCUS_SOURCE_ID) !== undefined) {
          map.removeSource(CHART_FOCUS_SOURCE_ID)
        }
      } catch {
        // A map already tearing itself down has nothing left to clean.
      }
    },
  }
}
