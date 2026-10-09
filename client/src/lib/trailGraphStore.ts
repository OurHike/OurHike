// Keeping the junction graph on the phone (#1050), one cell at a time since
// #1257 stage 3.
//
// THE GAP THIS CLOSES, IN ONE SENTENCE: a hiker who downloaded the corridor at
// home, drove to Harriman and opened the app at the trailhead with no signal
// got a day-hike builder that refused every tap - because `lib/useTrailData.ts`
// fetched the graph over the network on every launch and nothing wrote it
// anywhere.
//
// The service worker could not help: it precaches the bundle, the glyphs and
// the UI fonts, and these are runtime JSON fetches from a different origin.
//
// WHAT IS STORED SINCE #1257: THE CELLS A PHONE LOADED, EACH HALF ITS OWN
// RECORD. The graph is published in 1° cells (pipeline/cut_trail_graph.py,
// lib/config.ts's TRAIL_GRAPH_CELLS_KEY) and lib/trailGraphData.ts loads only
// the cells under the hike, the fix, the camera and the taps - so what a phone
// keeps is exactly those, four halves each (graph, geometry, elevation,
// profile), under `graphCellStoreKey`. A cell that was loaded once with signal
// routes at the trailhead without it, which is the whole-graph store's promise
// kept at the cell's grain. The four whole-file records earlier releases
// wrote are deleted at launch (`forgetWholeGraph`): the 78,595,556-byte graph
// of 2026-09-07 was verified, stored, and a frozen first page waiting for the
// next launch to parse it, and nothing reads it any more.
//
// ALL FOUR HALVES, WHICH IS THE MAINTAINER'S DECISION OF 2026-08-27 AND NOT
// THE OBVIOUS ONE.
//
// The issue proposed storing `trail_graph.json` alone as the cheap option -
// "the first is the minimum, the third is nearly free, the second is the real
// weight". That was true when it was written and stopped being true the same
// week. #1093 removed the chord fallback from snapping, so `nearestPointOnGraph`
// now skips every edge with no vertices and `canSnapToGraph` is false for the
// routing half alone. A phone holding graph-without-geometry therefore opens a
// builder that refuses EVERY tap with "OurHike hasn't got this area's trail
// lines yet" - a sentence lib/dayHikeDraft.ts already documents as false when
// the geometry is never coming. The minimum set that works offline is graph
// plus geometry.
//
// WHAT IS STORED, AND WHY THE HASH TRAVELS WITH THE BYTES
//
// `{bytes, hash, version, fetchedAt}` per record, verified on write.
//
// A PHONE OFFLINE CANNOT REACH `latest.json`, so it cannot re-derive what the
// bytes it holds SHOULD hash to. It has to trust a hash recorded at write
// time - which is safe, because nothing is ever written that did not match the
// manifest at the moment it was fetched. This is `lib/nearbyTrailData.ts`'s
// shape, copied deliberately: that module already stores an artifact against
// its published hash and its read-through is the one this follows.
//
// It is NOT `lib/conditionsCache.ts`'s shape, which #1050's own comment names
// as the template. That module stores `{document, storedAt}` - no bytes, no
// hash, no version - and its `MAX_CACHED_BYTES = 2 * 1024 * 1024` would
// silently delete a 7.5 MB graph on every write.
//
// WHY THE MANIFEST VERSION IS RECORDED, AND WHAT READS IT NOW (#1828)
//
// `lib/dayHikes.ts` refuses to persist a `GraphPoint.edgeIndex` because
// `build_trail_graph.py` renumbers edges between publishes - and since the
// cells, because the merged graph's positions depend on which cells landed in
// which order. A cached cell inherits that hazard, one level down: each cell
// names its nodes and edges by their number in the WHOLE graph it was cut
// from (`node_ids`, `edge_ids`), and lib/trailGraphData.ts joins two cells by
// those numbers. Node 4,102 of one release can be a different junction from
// node 4,102 of the next, so a cell stored from one release and a cell
// fetched from the next must never be joined.
//
// The version was recorded and nothing read it until #1828 - "a phone merges
// trail-graph cells from two releases by node number, and a new release
// renumbers them". It is read now: lib/trailGraphData.ts hands a stored cell
// back only when it is a copy of the release the graph is being built from -
// its version, or a later release that published the same bytes
// (`alsoPublishedIn`) - and {@link newestStoredGraphVersion} below is how a
// phone with no signal picks that release - the maintainer's choice by poll
// on 2026-10-08, refuse mixed releases rather than join cells by coordinates
// or clear the store.
//
// Still not acted on: a card saying its cached figures were computed
// against a different release. That is a change to what a screen SAYS, which
// wants its own before-and-after.
//
// THE OLDER COPY KEPT BESIDE A REFRESHED CELL HALF (#1837 - after a data
// release changes one piece of a saved hike, the phone strands the rest of
// the hike offline until every piece is refreshed)
//
// One record per cell half used to be all a phone held, so a fetch from a
// release that changed a cell wrote over the copy the hike's other cells
// could still be built with. A hike stored whole from release 9, whose east
// cell alone was refetched from release 10 at home, then held no release
// with both cells, and at the trailhead it routed on one of them. The
// maintainer chose by poll on 2026-10-09: keep the older copy until every
// piece of the hike is refreshed, and build offline from the newest release
// that holds every piece. This module keeps the older copy and drops it.
//
// KEPT: {@link writeStoredGraph} keeps the copy it replaces, under
// {@link olderCopyKey}, when that copy is another release's bytes and some
// stored cell's current routing half is still a copy of that release - a
// cell a graph of that release could be built with.
//
// DROPPED: every write then forgets each older copy that no stored cell's
// current routing half is a copy of the release of any more. That is "until
// every piece is refreshed" without the store knowing which cells make up a
// hike - it has no such notion, and this adds none. It errs both ways:
//   - a copy can outlive the hike that needed it, because one release-9 cell
//     of any other hike keeps every release-9 copy until it is refreshed too;
//   - a copy can go while a hike could still use it, when the hike's cells
//     were refreshed under two different later releases, one cell under
//     each. No cell is current at the release they last shared, and the
//     store builds as it did before #1837, from the newest stored.
//
// ONE OLDER COPY PER HALF, AT MOST. A cell refreshed under two later releases
// keeps one of its two earlier copies: the one a stored routing half is still
// current at, the newer if both are - the same newest-first preference the
// offline choice makes. A hike whose other cells are still current at the
// one given up loses this cell. That takes two data releases with this cell
// refreshed in each and those cells in neither, and each further copy kept
// would cost up to one more multiple of the graph bytes the phone holds.
//
// WHAT IT COSTS, AND THE ROOM CHECK. A half held twice costs one more copy of
// that half. Older copies are what the room check gives up first: a write
// with no room forgets every older copy before it declines, and keeps none on
// that write, so an older copy never costs a current copy its place.
// features/HIKE_PLANNING.md's "One release per graph" has the measured sizes
// and the worst case.

import { del, delMany, get, getMany, keys, set, setMany, update } from 'idb-keyval'

import { oversized, warnOversized } from './artifactBudget'
import type { TrailGraphCellHalf } from './config'

/** One artifact's stored copy. */
export interface StoredGraphArtifact {
  bytes: Blob
  /** The sha256 the manifest named when these bytes were fetched. */
  hash: string
  /** The release version the manifest carried then, or null when it named
   *  none. See the header for what this is for and what it is not. */
  version: string | null
  /**
   * Every later release whose manifest named this record's `hash` for its
   * key - the same bytes, so this copy is that release's copy too (#1828
   * review). Empty for a record no later manifest has vouched for, and for
   * every record written before this field existed.
   *
   * WHY A LIST BESIDE `version`, NOT A NEW `version`. A release that leaves
   * a cell byte-identical leaves it in both releases. Measured 2026-10-09
   * against UA's manifests (data.ourhike.org/environments/ua): releases
   * 2026-10-03, 2026-10-03-2 and 2026-10-08 carry three different
   * `version`s and publish all 779 routing halves and all 779 geometry
   * halves byte-identical, and the elevation and profile halves, which
   * 2026-10-03 did not publish, are byte-identical across the other two.
   * Rewriting `version` to the later release took the copy out of the
   * earlier one, so a hike whose other cells were stored under the earlier
   * release was refused offline - measured in
   * lib/trailGraphReleases.realIdb.test.ts. Kept as a list, the copy joins
   * a graph of either release.
   *
   * {@link newestStoredGraphVersion} still reads `version` alone. A later
   * release recorded here does not make the copy newer.
   */
  alsoPublishedIn: Array<string | null>
  /** Epoch ms. Read by {@link newestStoredGraphVersion}, which is the one
   *  decision made on it: which stored release a phone with no signal builds
   *  its graph from. */
  fetchedAt: number
}

/** Whether a stored copy is a copy of the release whose manifest `version`
 *  is given: the release it was stored under, or one that has published the
 *  same bytes since. */
export function isCopyOf(stored: StoredGraphArtifact, version: string | null): boolean {
  return stored.version === version || stored.alsoPublishedIn.includes(version)
}

/** Every graph cell record starts with this, so the whole family can be
 *  found, summed and cleared by prefix. */
export const GRAPH_CELL_STORE_PREFIX = 'ourhike:trail-graph-cell:'

/** Where one half of one cell lives. The half before the name, so a
 *  family's halves sort together when a screen lists the store. */
export function graphCellStoreKey(name: string, half: TrailGraphCellHalf): string {
  return `${GRAPH_CELL_STORE_PREFIX}${half}:${name}`
}

/** What every older copy's key ends with - see {@link olderCopyKey}. */
const OLDER_COPY_SUFFIX = ':older'

/**
 * Where the older copy of the record under `storeKey` lives (#1837): the
 * copy a refetch from another release replaced, kept while a stored cell can
 * still be built with it (the header says when). Beside the current copy's
 * key and inside {@link GRAPH_CELL_STORE_PREFIX}, so {@link storedGraphBytes}
 * counts it for the Downloads window and {@link clearStoredGraph} forgets it.
 */
export function olderCopyKey(storeKey: string): string {
  return `${storeKey}${OLDER_COPY_SUFFIX}`
}

function isOlderCopyKey(storeKey: string): boolean {
  return storeKey.endsWith(OLDER_COPY_SUFFIX)
}

/** Whether `storeKey` holds a cell's current routing half - the records
 *  whose releases decide which older copies are still kept. */
function isCurrentRoutingKey(storeKey: string): boolean {
  return storeKey.startsWith(graphCellStoreKey('', 'graph')) && !isOlderCopyKey(storeKey)
}

/**
 * The four whole-file records releases before #1257 stage 3 wrote, kept as
 * names only so {@link forgetWholeGraph} can delete what they left. Nothing
 * writes them and nothing reads them; a phone that fetched 2026-09-07's
 * 78.6 MB graph before the budget existed is still holding it, plus 224 MB
 * of geometry, and IndexedDB gives nothing back unasked.
 */
export const LEGACY_GRAPH_STORE_KEYS = [
  'ourhike:trail-graph',
  'ourhike:trail-graph-geometry',
  'ourhike:trail-graph-elevation',
  'ourhike:trail-graph-profile',
] as const

/**
 * How much room to leave free after writing.
 *
 * NOTHING IN THIS CODEBASE CHECKED ROOM BEFORE STORING A VECTOR ARTIFACT, and
 * the graph would have been the largest one yet. `archiveDownload.ts` refuses a
 * download that would not fit; `nearbyTrailData.ts` writes 7.3 MB behind a bare
 * try/catch and lets the browser decide. A quota error is caught either way -
 * the session keeps working on the bytes in hand - so this is not about
 * correctness. It is about not evicting a hiker's downloaded MAP to make room
 * for a routing graph, which a browser under pressure will do without asking.
 *
 * @unvalidated - 50 MB was roughly twice what the four whole artifacts decoded
 * to in August; a cell's four halves are far smaller (Harriman's graph half is
 * 1.8 MB), so a phone that cannot spare this is a phone with nothing to
 * spare. Nobody has measured what a real phone's headroom looks like after a
 * 314 MB archive, which is what would settle it.
 */
export const GRAPH_STORE_HEADROOM_BYTES = 50 * 1024 * 1024

/**
 * A record as this module reads it back, or null when it is not one.
 *
 * Shape-checked because this store is written by every past version of this
 * module there will ever be. A record that is not a blob and a hash is
 * treated as absent, and the next verified fetch rewrites it.
 */
function asStoredCopy(record: unknown): StoredGraphArtifact | null {
  const candidate = record as Partial<StoredGraphArtifact> | null | undefined
  if (!(candidate?.bytes instanceof Blob) || typeof candidate.hash !== 'string') {
    return null
  }
  return {
    bytes: candidate.bytes,
    hash: candidate.hash,
    version: typeof candidate.version === 'string' ? candidate.version : null,
    alsoPublishedIn: Array.isArray(candidate.alsoPublishedIn)
      ? candidate.alsoPublishedIn.filter(
          (version: unknown): version is string | null =>
            version === null || typeof version === 'string',
        )
      : [],
    fetchedAt: typeof candidate.fetchedAt === 'number' ? candidate.fetchedAt : 0,
  }
}

/** A stored copy under `storeKey`, or null when there is none this module
 *  trusts. */
export async function readStoredGraph(
  storeKey: string,
): Promise<StoredGraphArtifact | null> {
  try {
    const stored = asStoredCopy(await get(storeKey))
    if (stored !== null) {
      // Weighed on the way out (#1254): a launch before the budget existed
      // stored whatever it had verified, and on 2026-09-07 that was a
      // 78,595,556-byte graph whose parse is the frozen first page the
      // budget exists to prevent. lib/nearbyTrailData.ts makes the same call
      // for the same reason. Forgotten rather than kept: a copy nothing will
      // parse is storage taken from the map, and the next fetch that fits
      // rewrites it.
      if (oversized(stored.bytes.size)) {
        warnOversized(storeKey, stored.bytes.size, 'store')
        await forgetStoredGraph(storeKey)
        return null
      }
      return stored
    }
  } catch {
    // An unreadable store is the no-store case. The fetch path still answers.
  }
  return null
}

/**
 * Keep a verified copy under `storeKey`, or decline quietly.
 *
 * NEVER THROWS, and never costs the session the bytes in hand: a full store,
 * a refusing one, or one with no room to spare all end with the caller holding
 * exactly what it fetched. Storing is an improvement on the next launch, not a
 * condition of this one.
 *
 * KEEPS THE COPY IT REPLACES under {@link olderCopyKey} while a stored cell
 * can still be built with it, and then forgets every older copy no stored
 * cell can be built with any more (#1837; the header says why, and why one
 * older copy per half). With no room for the new copy, every older copy is
 * forgotten first, and none is kept on this write.
 */
export async function writeStoredGraph(
  storeKey: string,
  record: Omit<StoredGraphArtifact, 'fetchedAt' | 'alsoPublishedIn'> & {
    fetchedAt?: number
  },
): Promise<boolean> {
  // No `alsoPublishedIn`: a copy just fetched has been published in no
  // later release yet, and readStoredGraph reads the missing list as empty.
  const next = {
    bytes: record.bytes,
    hash: record.hash,
    version: record.version,
    fetchedAt: record.fetchedAt ?? Date.now(),
  } satisfies Omit<StoredGraphArtifact, 'alsoPublishedIn'>
  try {
    if (!(await hasRoomFor(record.bytes.size))) {
      // OLDER COPIES GO BEFORE ANYTHING CURRENT (#1837). An older copy serves
      // only a hike whose other cells were not refreshed; a current copy is
      // the one every graph built with signal uses. So a write with no room
      // forgets every older copy and asks again, keeps none on this write,
      // and declines - as it always has - only when that still leaves too
      // little room.
      await forgetOlderCopies()
      if (!(await hasRoomFor(record.bytes.size))) return false
      await set(storeKey, next)
      return true
    }
    const replaced = await readStoredGraph(storeKey)
    if (replaced !== null && (await keptAsOlderCopy(replaced, storeKey, next))) {
      // One transaction, so neither record is ever written without the other.
      await setMany([
        [olderCopyKey(storeKey), replaced],
        [storeKey, next],
      ])
    } else {
      await set(storeKey, next)
    }
  } catch {
    return false
  }
  await forgetOlderCopiesNoCellNeeds()
  return true
}

/** The two fields that say which releases a stored copy belongs to. */
type Releases = Pick<StoredGraphArtifact, 'version' | 'alsoPublishedIn'>

/** Every release a stored copy is a copy of. */
function releasesOf(copy: Releases): Array<string | null> {
  return [copy.version, ...copy.alsoPublishedIn]
}

/**
 * Every release that some stored cell's current routing half is a copy of -
 * the releases whose older copies this store keeps (#1837). Read with `next`
 * in place of the record under its `storeKey`, for a write about to put it
 * there.
 */
async function currentReleases(
  storeKeys: readonly string[],
  next?: { storeKey: string; copy: Releases },
): Promise<Set<string | null>> {
  const routingKeys = storeKeys.filter(
    (storeKey) => isCurrentRoutingKey(storeKey) && storeKey !== next?.storeKey,
  )
  const copies: Array<Releases | null> =
    routingKeys.length === 0
      ? []
      : (await getMany(routingKeys)).map((record) => asStoredCopy(record))
  if (next !== undefined && isCurrentRoutingKey(next.storeKey)) copies.push(next.copy)
  const current = new Set<string | null>()
  for (const copy of copies) {
    if (copy !== null) for (const version of releasesOf(copy)) current.add(version)
  }
  return current
}

/**
 * Whether the copy `next` replaces under `storeKey` is kept as its older copy
 * (#1837): other bytes, from another release, which some stored cell's
 * current routing half will still be a copy of once `next` is written. Bytes
 * replaced under the release they were stored as are not kept - two copies
 * claiming one release (two releases that named no version read as one) would
 * leave nothing to choose between them.
 */
async function keptAsOlderCopy(
  replaced: StoredGraphArtifact,
  storeKey: string,
  next: Omit<StoredGraphArtifact, 'alsoPublishedIn'>,
): Promise<boolean> {
  if (replaced.hash === next.hash || isCopyOf(replaced, next.version)) return false
  const current = await currentReleases(await graphCellStoreKeys(), {
    storeKey,
    copy: { version: next.version, alsoPublishedIn: [] },
  })
  return releasesOf(replaced).some((version) => current.has(version))
}

/**
 * Forget every older copy whose release no stored cell's current routing half
 * is a copy of any more (#1837) - the maintainer's "until every piece of the
 * hike is refreshed", read without knowing which cells make up a hike (the
 * header says what that keeps too long and what it drops too soon).
 *
 * Run after every write, of any half: a write is what takes a cell off a
 * release, and writes are fire-and-forget and can overlap, so the call after
 * the last of them is the one that sees them all. Never throws: a copy left
 * behind is forgotten by the next write, or by the room check.
 */
async function forgetOlderCopiesNoCellNeeds(): Promise<void> {
  try {
    const storeKeys = await graphCellStoreKeys()
    const olderKeys = storeKeys.filter(isOlderCopyKey)
    if (olderKeys.length === 0) return
    const current = await currentReleases(storeKeys)
    const olderCopies = await getMany(olderKeys)
    const unneeded = olderKeys.filter((_storeKey, at) => {
      const copy = asStoredCopy(olderCopies[at])
      return copy === null || !releasesOf(copy).some((version) => current.has(version))
    })
    if (unneeded.length > 0) await delMany(unneeded)
  } catch {
    // See above.
  }
}

/** Forget every older copy, which is what the room check gives up first.
 *  Never throws, like the rest of this module's writes. */
async function forgetOlderCopies(): Promise<void> {
  try {
    const olderKeys = (await graphCellStoreKeys()).filter(isOlderCopyKey)
    if (olderKeys.length > 0) await delMany(olderKeys)
  } catch {
    // The room check asks again either way.
  }
}

/**
 * Record that the manifest of release `version` names `hash` for the record
 * under `storeKey` (#1828 review) - which makes the stored copy that
 * release's copy too, without a byte moved. See `alsoPublishedIn` for why
 * this adds to a list rather than rewriting `version`.
 *
 * A no-op unless the record's hash is `hash` and it is not already a copy of
 * `version`. The read and the write are one IndexedDB transaction, and the
 * hash is checked again inside it, so a different copy written in between is
 * never given a release its bytes were not published in.
 *
 * NEVER THROWS, like {@link writeStoredGraph}: a refusing store leaves the
 * copy a copy of the releases it already named, which is today's answer.
 */
export async function recordAlsoPublishedIn(
  storeKey: string,
  hash: string,
  version: string | null,
): Promise<void> {
  try {
    const stored = await readStoredGraph(storeKey)
    if (stored === null || stored.hash !== hash || isCopyOf(stored, version)) return
    await update(storeKey, (current: unknown) => {
      const record = current as Partial<StoredGraphArtifact> | undefined
      if (record?.hash !== hash) return current
      const already = Array.isArray(record.alsoPublishedIn) ? record.alsoPublishedIn : []
      if (record.version === version || already.includes(version)) return current
      return { ...record, alsoPublishedIn: [...already, version] }
    })
  } catch {
    // See above: the copy stays what it was.
  }
}

/**
 * Whether the phone can spare the bytes plus the headroom above.
 *
 * True when the browser will not say, which is the right way for this to fail:
 * `navigator.storage.estimate` is absent on some engines and inaccurate on
 * others, and refusing to store on a phone that never answers would make the
 * offline builder a feature only some browsers get. The write itself is still
 * guarded - a quota error is caught above.
 */
async function hasRoomFor(bytes: number): Promise<boolean> {
  try {
    const estimate = await navigator.storage?.estimate?.()
    if (estimate === undefined) return true
    const { quota, usage } = estimate
    if (typeof quota !== 'number' || typeof usage !== 'number') return true
    return quota - usage >= bytes + GRAPH_STORE_HEADROOM_BYTES
  } catch {
    return true
  }
}

/** Forget one stored record. Never throws: a key that will not delete is
 *  the no-store case, and the caller has already decided not to read it. */
export async function forgetStoredGraph(storeKey: string): Promise<void> {
  try {
    await del(storeKey)
  } catch {
    // See above.
  }
}

/** Every graph cell record on this phone, by store key. Absent stores and
 *  unreadable ones answer as empty - the list says "nothing here", which is
 *  also what the router can route from. */
async function graphCellStoreKeys(): Promise<string[]> {
  try {
    return (await keys())
      .filter((key): key is string => typeof key === 'string')
      .filter((key) => key.startsWith(GRAPH_CELL_STORE_PREFIX))
  } catch {
    return []
  }
}

/**
 * The manifest version of the newest routing half this phone holds for any of
 * `names`, or null when it holds none of them (#1828).
 *
 * WHAT "NEWEST" MEANS HERE, because the version cannot say it. A version is
 * `str(uuid.uuid4())` (pipeline/publish.py), so two of them cannot be put in
 * order. `fetchedAt` can: of two copies, the one written later came from the
 * release this phone fetched more recently, and a build only ever fetches the
 * release it pins (lib/dataRelease.ts's DATA_RELEASE), so that is the newer
 * build's release. Reasoned from the code, not measured on a phone. A phone
 * clock set backwards between two fetches would order them wrongly, and
 * nothing here can see that.
 *
 * AMONG THE CELLS ASKED FOR, NOT THE WHOLE STORE. A phone that stored a
 * stretch's cells before an update and then fetched one cell at home after it
 * holds two releases, and the stretch's cells still agree with each other.
 * Read across the whole store, the home cell would make every stretch cell
 * unusable at the trailhead - the failure #1050 fixed ("a day hike cannot be
 * built or followed offline"), brought back by one cell the hiker is not
 * using. Read across the cells a graph is being built from, a newer release
 * wins exactly where two releases would otherwise meet.
 *
 * ROUTING HALVES ONLY. The other three halves line up with a routing half and
 * are held to its release by lib/trailGraphData.ts, so they say nothing about
 * which release a graph should be built from.
 *
 * Wrapped in an object so that "nothing held" (null) and "held from a manifest
 * that named no version" (`{ version: null }`) stay two answers.
 */
export async function newestStoredGraphVersion(
  names: readonly string[],
): Promise<{ version: string | null } | null> {
  let newest: StoredGraphArtifact | null = null
  for (const name of new Set(names)) {
    const stored = await readStoredGraph(graphCellStoreKey(name, 'graph'))
    // Strictly later, so a tie keeps the first name asked about and the
    // answer depends on nothing but what is stored and what was asked.
    if (stored !== null && (newest === null || stored.fetchedAt > newest.fetchedAt)) {
      newest = stored
    }
  }
  return newest === null ? null : { version: newest.version }
}

/**
 * Delete the whole-file records earlier releases stored (#1257 stage 3). Called
 * once per launch by lib/useTrailGraph.ts; deleting nothing is free, and the
 * store carries no version to check first.
 */
export async function forgetWholeGraph(): Promise<void> {
  for (const storeKey of LEGACY_GRAPH_STORE_KEYS) {
    await forgetStoredGraph(storeKey)
  }
}

/** Forget every stored record, cells and legacy alike - what "remove the
 *  trail data" has to reach. */
export async function clearStoredGraph(): Promise<void> {
  for (const storeKey of [...LEGACY_GRAPH_STORE_KEYS, ...(await graphCellStoreKeys())]) {
    try {
      await del(storeKey)
    } catch {
      // One key that will not delete must not stop the others.
    }
  }
}

/** The bytes each stored cell half holds, by store key, for the Downloads
 *  window's row. Absent records are absent from the result rather than zero:
 *  nothing stored is not the same claim as an empty file. */
export async function storedGraphBytes(): Promise<Record<string, number>> {
  const sizes: Record<string, number> = {}
  for (const storeKey of await graphCellStoreKeys()) {
    const stored = await readStoredGraph(storeKey)
    if (stored !== null) sizes[storeKey] = stored.bytes.size
  }
  return sizes
}
