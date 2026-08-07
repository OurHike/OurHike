// Whether the background's sources ever actually arrived.
//
// NAMED "LIVE" FOR THE TWO IT STARTED WITH, AND NO LONGER ONLY ABOUT THEM
//
// This watched the two network sources and deliberately not the downloaded
// archive, on the reasoning that "the downloaded archive has its own error
// path on the Downloads screen - a second opinion about it here would be a
// second place to keep right." That was wrong in one specific way, and #314
// is the shape of it: the Downloads screen reports a download that FAILED,
// and says nothing whatever about one that finished and cannot be read. A
// truncated or corrupt archive is a blob under the key, so every indicator
// stays green - `downloaded` on the card, `archiveDownloaded` in the shell -
// while the raster source fails every tile it asks for and the hiker looks
// at blank paper. Nothing anywhere said so.
//
// The archive source is therefore watched here too, and the honesty rule
// below is what makes that safe rather than noisy. See lib/backgroundHealth.ts
// for the other half: `archive` reports that the SOURCE never drew, which is
// the ordinary state on a phone that has downloaded nothing - only a phone
// that HAS a download and still sees this has something wrong with it.
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
import { TOPO_SOURCE_ID } from './style'

/**
 * What never arrived, as against what merely has not arrived yet.
 *
 * Both flags mean "this source reported an error AND nothing from it has ever
 * drawn." The second half is what keeps them honest: a source that fails one
 * tile at the edge of the world and serves the rest is working, and saying
 * otherwise over a map the hiker is reading would be its own false statement.
 */
export interface LiveSourceHealth {
  /** The OSM vector sheet - the landcover, water, paths, roads and labels.
   *  Its tiles come from the downloaded hiking sheet first and the network
   *  where the package does not answer (map/basemap.ts), so this one flag
   *  covers both halves of that fallthrough - which is right, because what a
   *  hiker sees is one sheet either way. */
  basemap: boolean
  /** The elevation model behind the hillshade and the generated contours. */
  elevation: boolean
  /**
   * The downloaded raster archive - the USGS sheet the offline background is
   * drawn from.
   *
   * True on any phone with no archive downloaded, and that is not a defect:
   * map/style.ts declares this source under BOTH backgrounds (the live sheet
   * stacks OVER it), so with nothing under the key every tile request fails
   * exactly as it should. The flag says "this source drew nothing", never
   * "your download is broken" - only a caller that knows an archive IS on the
   * phone can say the second thing, and lib/backgroundHealth.ts is the one
   * that does.
   */
  archive: boolean
}

export const HEALTHY: LiveSourceHealth = {
  basemap: false,
  elevation: false,
  archive: false,
}

/** Every flag, for callers that fold over them rather than naming each. */
export const SOURCE_FLAGS = Object.keys(HEALTHY) as (keyof LiveSourceHealth)[]

/**
 * One map's answer about its background sources.
 *
 * TWO FACTS, NOT ONE, AND #352 IS WHY
 *
 * `unreachable` alone cannot be remembered past the map that observed it, and
 * the shell has to remember it: the downloads window opens from the More tab,
 * where the map screen is not rendered at all (#334). The trouble is that a
 * map which never fails never reports - `report()` only fires on a CHANGE, and
 * a healthy map computes the same all-false answer it started with. So a
 * remembered failure was never contradicted by a later, perfectly healthy map,
 * and one transient error marked a good archive damaged for the rest of the
 * session, with the strip and the Downloads card both saying so.
 *
 * `drew` is the missing half: not "nothing has failed" but "this source has
 * actually put ink on the screen". It is a positive fact, so it can clear a
 * remembered negative one, and a shell that folds the two together
 * (lib/backgroundHealth.ts's `rememberNotDrawing`) needs no separate clearing
 * mechanism to keep in step - which is what the first attempt got wrong in
 * three different places at once.
 */
export interface SourceReport {
  /** Errored and never drew - see LiveSourceHealth. */
  unreachable: LiveSourceHealth
  /** Has drawn at least once, for THIS map. Never inferred from the absence
   *  of an error: a source that has not been asked for a tile yet has neither
   *  failed nor drawn, and the difference is the whole of #352. */
  drew: LiveSourceHealth
  /**
   * True on precisely one report: the one the detach sends.
   *
   * The flags are all false either way, and they mean opposite things - "the
   * sources recovered" against "there is no longer a map here to make a claim
   * about". A caller drawing only this map's chrome can ignore it; one that
   * remembers a failure past this map cannot.
   */
  withdrawn: boolean
}

/**
 * The sources worth reporting on, and the flag each one answers to.
 *
 * The three that draw the BACKGROUND. The trail lines and the POI pins are
 * local and drawn from data the app already holds, so a failure there is a
 * different report on a different screen. The contour source is deliberately
 * absent too: it is generated from the DEM in-process, so it fails when and
 * because the DEM does, and reporting both would double-count one outage.
 */
const WATCHED: Record<string, keyof LiveSourceHealth> = {
  [OSM_SOURCE_ID]: 'basemap',
  [DEM_SOURCE_ID]: 'elevation',
  [TOPO_SOURCE_ID]: 'archive',
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
 * DEM tiles are one report rather than twelve renders, and it fires again when
 * a tile finally lands - which is what walking back into signal looks like
 * from here. The returned detach withdraws what it claimed, because these
 * flags describe one map and must not outlive it.
 *
 * WHAT "CHANGES" MEANS, AFTER #352
 *
 * A change in EITHER fact, not only in `unreachable`. That distinction is the
 * whole bug: while only failures were reported, a map that drew everything
 * perfectly computed the same all-false answer it started with and therefore
 * never reported at all - so a shell remembering an earlier failure was never
 * told the sheet was fine now, and went on calling a good archive damaged for
 * the rest of the session. The first tile that draws is a change worth
 * sending, and it is the only thing that can honestly retract a failure
 * observed by some earlier map.
 */
export function attachLiveSourceHealth(
  map: MapLibreMap,
  onChange: (report: SourceReport) => void,
): () => void {
  // Errored-and-never-drew, tracked separately so neither can be inferred from
  // the other. `isSourceLoaded` cannot stand in for `drew`: a vector source
  // that failed its TileJSON reports itself loaded on purpose, so that the
  // style ignores it rather than stalling.
  const errored = new Set<string>()
  const drew = new Set<string>()
  let reported: SourceReport = { unreachable: HEALTHY, drew: HEALTHY, withdrawn: false }

  const currently = (): { unreachable: LiveSourceHealth; drew: LiveSourceHealth } => {
    const unreachable: LiveSourceHealth = { ...HEALTHY }
    const hasDrawn: LiveSourceHealth = { ...HEALTHY }
    for (const [sourceId, flag] of Object.entries(WATCHED)) {
      hasDrawn[flag] = drew.has(sourceId)
      unreachable[flag] = errored.has(sourceId) && !drew.has(sourceId)
    }
    return { unreachable, drew: hasDrawn }
  }

  const report = () => {
    const next = currently()
    // Compared over the flags themselves rather than field by field: a fourth
    // source added to WATCHED with nothing added here would report once and
    // then go quiet, which is the failure this whole module exists to prevent
    // wearing the shape of a missed line.
    const unchanged = SOURCE_FLAGS.every(
      (flag) =>
        next.unreachable[flag] === reported.unreachable[flag] &&
        next.drew[flag] === reported.drew[flag],
    )
    if (unchanged) return
    reported = { ...next, withdrawn: false }
    onChange(reported)
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
    // Only a claim of unreachability is worth withdrawing. `drew` is a fact
    // about a map that no longer exists and nothing downstream keeps it, so a
    // map that merely drew fine leaves without saying anything - which is what
    // keeps "detach after a quiet session" silent.
    if (SOURCE_FLAGS.some((flag) => reported.unreachable[flag])) {
      reported = { unreachable: HEALTHY, drew: HEALTHY, withdrawn: true }
      onChange(reported)
    }
  }
}
