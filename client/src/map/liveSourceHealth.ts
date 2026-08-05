// Whether the live sheet's network sources ever actually arrived.
//
// WHY THIS IS NOT THE ONLINE/OFFLINE BRANCH THE PROJECT FORBIDS
//
// features/MAP_OPTIONS.md §1 rules out branching the map on connectivity: the
// live layers are stacked OVER the downloaded archive precisely so that no
// code has to decide between them, and "none of them needs to be detected."
// That rule is about COMPOSITION, and it still holds - nothing observed here
// reaches buildMapStyle, which stays a pure function of the preference, Data
// Saver, and whether a DEM could be built. No source is swapped, no style is
// rebuilt, no request is retried.
//
// What this adds is the other half of the same document: §5 asks for a line of
// chrome that NAMES the state the map is in. lib/useOnline.ts already
// establishes the permitted shape - connectivity drives what the strip SAYS,
// never what the machinery does - and StatusStrip's own header comment claims
// exactly this job: "the strip where the map admits what it doesn't know."
//
// The failure this exists for is specific. A hiker who has downloaded nothing
// is looking at a style whose only guaranteed layer is the paper backdrop, so
// if the vector sheet never loads, the screen is a flat cream rectangle - the
// same rectangle it would show while loading, over ocean, or with the archive
// missing. MapLibre knows the difference and says so, but only to the console:
// vector_tile_source.ts sets `_loaded = true` on a failed TileJSON ("let's
// pretend it's loaded so the source will be ignored") and fires an ErrorEvent.
// Nothing in this app listened, so the map went quiet and blank at once.
//
// ONE GOTCHA WORTH THE COMMENT
//
// util/evented.ts only console.errors an ErrorEvent when NOBODY in the parent
// chain is listening, and ui/map.ts registers no internal error listener. So
// attaching this handler is what SILENCES MapLibre's own logging - which would
// make the app quieter than it was before, in exactly the failure it was added
// to explain. Hence the console.warn below: it is not decoration, it is
// replacing the reporting this listener displaces. Its test asserts it.

import type { Map as MapLibreMap, MapSourceDataEvent } from 'maplibre-gl'
import { OSM_SOURCE_ID } from './liveTopo'
import { DEM_SOURCE_ID } from './terrain'

/**
 * What never arrived, as against what merely has not arrived yet.
 *
 * Both flags mean "this source reported an error AND nothing from it has ever
 * drawn." The second half is what keeps them honest: a source that fails one
 * tile at the edge of the world and serves the rest is working, and saying
 * otherwise over a map the hiker is reading would be its own false statement.
 */
export interface LiveSourceHealth {
  /** The OSM vector sheet - the landcover, water, paths, roads and labels. */
  basemap: boolean
  /** The elevation model behind the hillshade and the generated contours. */
  elevation: boolean
}

export const HEALTHY: LiveSourceHealth = { basemap: false, elevation: false }

/**
 * The sources worth reporting on, and the flag each one answers to.
 *
 * Only the two that reach the network for the BACKGROUND. The trail lines and
 * the POI pins are local, and the downloaded archive has its own error path on
 * the Downloads screen - a second opinion about it here would be a second
 * place to keep right. The contour source is deliberately absent too: it is
 * generated from the DEM in-process, so it fails when and because the DEM
 * does, and reporting both would double-count one outage.
 */
const WATCHED: Record<string, keyof LiveSourceHealth> = {
  [OSM_SOURCE_ID]: 'basemap',
  [DEM_SOURCE_ID]: 'elevation',
}

/** MapLibre merges `sourceId` into events as they bubble up from a source's
 *  TileManager (style.ts's setEventedParent data callback), but the ErrorEvent
 *  type does not declare it - it is added on the way past. */
type SourceScopedError = { error?: unknown; sourceId?: unknown }

/**
 * Reports whether the live background's sources are reaching the hiker.
 *
 * Attached by MapView beside its other best-effort helpers, and reporting
 * through a callback rather than rendering anything: the map view owns the map
 * instance, the chrome owns what the hiker reads, and this is the seam between
 * them.
 *
 * `onChange` fires only when the answer actually changes, so twelve failing
 * DEM tiles are one report rather than twelve renders, and it fires again with
 * everything false when a tile finally lands - which is what walking back into
 * signal looks like from here. The returned detach clears the state the same
 * way, because these flags describe one map and must not outlive it.
 */
export function attachLiveSourceHealth(
  map: MapLibreMap,
  onChange: (health: LiveSourceHealth) => void,
): () => void {
  // Errored-and-never-drew, tracked separately so neither can be inferred from
  // the other. `isSourceLoaded` cannot stand in for `drew`: a vector source
  // that failed its TileJSON reports itself loaded on purpose, so that the
  // style ignores it rather than stalling.
  const errored = new Set<string>()
  const drew = new Set<string>()
  let reported: LiveSourceHealth = HEALTHY

  const report = () => {
    const next: LiveSourceHealth = { ...HEALTHY }
    for (const [sourceId, flag] of Object.entries(WATCHED)) {
      next[flag] = errored.has(sourceId) && !drew.has(sourceId)
    }
    if (next.basemap === reported.basemap && next.elevation === reported.elevation) return
    reported = next
    onChange(next)
  }

  const onError = (event: unknown) => {
    const { error, sourceId } = (event ?? {}) as SourceScopedError
    // Every error, not only the watched ones - see the note at the top of this
    // file. Attaching this listener turned MapLibre's own console reporting
    // off, and losing an error the app does not model would be a worse trade
    // than a duplicate line in the console.
    console.warn('Map source error.', error ?? event)

    if (typeof sourceId !== 'string' || !(sourceId in WATCHED)) return
    errored.add(sourceId)
    report()
  }

  const onSourceData = (event: MapSourceDataEvent) => {
    // `tile` is the arrival proof. A source fires plenty of metadata events
    // that say nothing about whether ink reached the screen, and a 404 on a
    // sparse tileset is swallowed by the source rather than raised, so a tile
    // that is present here really did load.
    if (event.tile === undefined || event.tile === null) return
    if (!(event.sourceId in WATCHED)) return
    if (drew.has(event.sourceId)) return
    drew.add(event.sourceId)
    report()
  }

  map.on('error', onError)
  map.on('sourcedata', onSourceData)

  return () => {
    map.off('error', onError)
    map.off('sourcedata', onSourceData)
    errored.clear()
    drew.clear()
    if (reported.basemap || reported.elevation) {
      reported = HEALTHY
      onChange(HEALTHY)
    }
  }
}
