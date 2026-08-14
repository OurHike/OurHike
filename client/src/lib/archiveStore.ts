// Where a downloaded archive's bytes actually live in IndexedDB.
//
// One home for the record layout, so that "what is on this phone under this
// package key" has a single answer rather than one per reader. It is separate
// from archiveDownload.ts because the readers are not the writer: the map
// modules resolve tiles out of these records on every camera move and have no
// business importing the download engine (and pmtilesSource.ts cannot, without
// a cycle - archiveDownload.ts imports CORRIDOR_ARCHIVE_KEY from it).
//
// ARCHIVES ARE STORED AS APPEND-ONLY SEGMENTS, AND COMPLETION IS A MARKER
// (#553).
//
// The archive used to be one record, written in a single `set()` after the last
// byte arrived. That made a transfer all-or-nothing: nothing was on disk while
// it ran, so an app the OS killed at 90% lost the whole download and the next
// launch started from zero. On Android a backgrounded tab holding a gigabyte is
// a prime candidate for the low-memory killer, and a killed tab throws no
// error, so none of the error paths that persist a partial ever ran.
//
// So the bytes are written as they arrive, as numbered segment records, and
// each byte is written exactly once:
//
//   <key>:g<generation>:<n>   the bytes, in order, append-only
//   <key>:complete            { generation, segments, totalBytes }
//   <key>                     a LEGACY whole-archive Blob
//
// **Completion is the `:complete` marker and nothing else.** Copying the
// finished segments into one record would need room for the archive and its
// segments at once - reintroducing #544's quota failure at exactly the size it
// hurts, 1.18 GB - and would write every byte a second time. The segments a
// transfer accumulated ARE the archive the moment the marker names them.
//
// Re-writing the whole accumulated Blob on every checkpoint is the other
// approach, and it does not survive measurement (#553): quadratic in bytes
// written, 3,287 ms against 692 ms for 400 MB in 32 MB steps, and ~21 GB of
// writes to get 1.18 GB onto phone flash. Append-only lands `usage` at 1x.
//
// WHY GENERATIONS, AND WHY THERE ARE ONLY EVER TWO
//
// A download under a key that already holds an archive must not damage it:
// "someone with a good map on their phone who taps download and loses signal
// should still have their good map" (archiveDownload.ts), and switching detail
// level re-downloads under the same key by design (lib/packages.ts). With
// segments at fixed names, the new transfer's segment 0 would overwrite the
// working archive's segment 0 - destroying the map before a single new byte was
// verified, and doing it at the moment the hiker asked for an upgrade.
//
// So an in-flight transfer writes into the generation the completed archive is
// NOT in, and completion swings the marker and frees the old one. Two is
// enough, and being a fixed set rather than a counter is what makes the delete
// path exhaustive: there is no generation to forget.
//
// This costs peak room - both copies exist between the last byte and the marker
// - which is real and is already accounted for. `usage` holds the old archive
// throughout, so `estimateAvailableBytes()` has already excluded it, and
// archiveDownload.ts's `shortfall` asks only for the bytes not yet on disk.
//
// THE LEGACY WHOLE-ARCHIVE RECORD KEEPS RESOLVING.
//
// `lib/packages.ts` deliberately kept `ourhike:corridor-archive` so an archive
// already sitting in a tester's IndexedDB "stays readable after this change,
// rather than silently re-downloading". That promise applies to this change
// too, so a Blob found under the bare package key is served as the archive it
// is. A finished download replaces it - see `markComplete`.

import { get, set, del } from 'idb-keyval'

/** The only two generations there are - see the header. Fixed rather than
 *  counted, so `deleteArchiveRecords` can sweep all of them by construction. */
export const GENERATIONS = [0, 1] as const

/** One numbered run of bytes. Suffixed under the package key like every other
 *  download record (archiveDownload.ts), so one key still names everything a
 *  package owns and `deleteArchive` needs no registry to find it. */
export const segmentKeyFor = (packageKey: string, generation: number, index: number) =>
  `${packageKey}:g${generation}:${index}`

/** Says which generation's segments form a whole, verified archive. */
export const completeKeyFor = (packageKey: string) => `${packageKey}:complete`

/**
 * What `:complete` holds.
 *
 * `totalBytes` is carried so that "how big is the map on this phone" costs one
 * record read instead of reassembling the archive - the Downloads screen asks
 * that on every mount, for every package.
 */
export interface ArchiveComplete {
  generation: number
  segments: number
  totalBytes: number
  /**
   * How many segments the generation this marker REPLACED held, so a later
   * delete can sweep that generation to a known floor even after a torn free
   * left a gap at its front (#648). The knowledge has to live here: the free
   * runs right after this marker overwrites the only other record of that
   * count, so a crash mid-free takes the count with it unless the new marker
   * carries it. Absent on markers written before this field existed - readers
   * treat that as 0 and lean on the delete sweep's gap tolerance instead.
   */
  priorSegments?: number
}

/**
 * A backstop on segment probing, not a limit on archive size.
 *
 * Segments are written contiguously from 0, so probing stops at the first gap.
 * This only bounds the damage if a store answers for every index - at 32 MiB a
 * segment, 4,096 of them is 128 GB, which is two orders of magnitude past the
 * largest archive the pipeline publishes (1.18 GB, 36 segments) and far past
 * what any phone will hold.
 *
 * Kept small deliberately. A generous bound is not free: it is the number of
 * reads a corrupt or stubbed store can extract from one lookup.
 */
const MAX_SEGMENTS = 4_096

/**
 * The segment records of one generation, in order, up to the first gap.
 *
 * Contiguous probing rather than an enumeration of the store: `keys()` would
 * answer this in one call, but the unit suite mocks idb-keyval as `{ get, set,
 * del }` in eleven files, and a fourth import would be undefined in all of
 * them. The write order makes probing exact anyway - a gap can only mean the
 * end.
 *
 * `atLeast` keeps going past a gap up to a count that is known from a marker or
 * a source record. Note what that does NOT claim: a torn WRITE cannot leave a
 * gap at all - writes are awaited in order from 0, so a killed transfer leaves
 * a contiguous prefix. The tear that makes gaps is a killed DELETE, which
 * removes ascending from 0 and so leaves a gap at the FRONT (#648); reads
 * correctly treat that generation as empty, and the delete paths carry their
 * own gap tolerance so they cannot be fooled the same way.
 */
async function segmentBlobs(
  packageKey: string,
  generation: number,
  atLeast = 0,
): Promise<(Blob | undefined)[]> {
  const found: (Blob | undefined)[] = []
  for (let index = 0; index < MAX_SEGMENTS; index += 1) {
    const stored = (await get(segmentKeyFor(packageKey, generation, index))) as
      Blob | undefined
    if (stored === undefined && index >= atLeast) break
    found.push(stored)
  }
  return found
}

/**
 * One generation's bytes as a single Blob, or undefined where it holds none.
 *
 * `new Blob(parts)` references its parts rather than copying them, so
 * assembling a 1.18 GB archive out of 36 segment records allocates nothing of
 * consequence and the readers keep slicing byte ranges the way they always
 * have.
 *
 * Stops at the first gap, which is what makes this safe to call on a transfer
 * that is still running: it returns the contiguous prefix that is really on
 * disk.
 */
export async function readSegments(
  packageKey: string,
  generation: number,
): Promise<Blob | undefined> {
  return (await readSegmentRun(packageKey, generation)).blob
}

/** One generation's bytes together with how many records they came in - what a
 *  resume needs, since the count of held segments is the index the next one
 *  goes to. One probe rather than two. */
export interface SegmentRun {
  blob: Blob | undefined
  count: number
}

export async function readSegmentRun(
  packageKey: string,
  generation: number,
): Promise<SegmentRun> {
  const parts = await segmentBlobs(packageKey, generation)
  const present = parts.filter((part): part is Blob => part !== undefined)
  return {
    blob: present.length === 0 ? undefined : new Blob(present),
    count: parts.length,
  }
}

/**
 * The completion marker, or null where no transfer under this key has ever
 * finished.
 *
 * The shape is CHECKED rather than asserted, because everything downstream
 * indexes records by what it says: a record with no numeric generation would
 * send `readSegments` looking for `<key>:gundefined:0` and probing to
 * MAX_SEGMENTS. Anything that is not a marker this module wrote is not a marker.
 */
export async function readComplete(packageKey: string): Promise<ArchiveComplete | null> {
  const stored = await get(completeKeyFor(packageKey))
  if (stored === null || typeof stored !== 'object') return null
  const { generation, segments, totalBytes, priorSegments } =
    stored as Partial<ArchiveComplete>
  if (
    typeof generation !== 'number' ||
    typeof segments !== 'number' ||
    typeof totalBytes !== 'number'
  )
    return null
  // Optional rather than required: markers written before this field existed
  // are still markers, and the delete sweep's gap tolerance covers what they
  // cannot say (#648).
  return typeof priorSegments === 'number'
    ? { generation, segments, totalBytes, priorSegments }
    : { generation, segments, totalBytes }
}

/**
 * The whole archive on this phone under `packageKey`, or undefined where there
 * is not one.
 *
 * The one accessor every reader goes through, which is what let the segment
 * layout land without touching the tile paths: `map/pmtilesSource.ts` slices
 * what this returns exactly as it sliced the single record before.
 *
 * A finished download wins over a legacy whole-archive record, because that is
 * the direction time runs - `markComplete` removes the legacy record, and a
 * marker beside one that survived a crash still describes the newer bytes.
 */
export async function readArchive(packageKey: string): Promise<Blob | undefined> {
  const complete = await readComplete(packageKey)
  if (complete !== null) return await readSegments(packageKey, complete.generation)
  const legacy = (await get(packageKey)) as Blob | undefined
  return legacy instanceof Blob ? legacy : undefined
}

/**
 * How big the stored archive is, or null where there is not one.
 *
 * Separate from `readArchive` because the Downloads screen asks only this, for
 * every package, on every mount - and the marker already knows, so it costs one
 * record read instead of reassembling every segment.
 */
export async function readArchiveSize(packageKey: string): Promise<number | null> {
  const complete = await readComplete(packageKey)
  if (complete !== null) return complete.totalBytes
  const legacy = (await get(packageKey)) as Blob | undefined
  return legacy instanceof Blob ? legacy.size : null
}

/** Appends one segment. Callers write them in order from 0 within a generation
 *  and never rewrite one, which is the property every reader here depends on. */
export async function writeSegment(
  packageKey: string,
  generation: number,
  index: number,
  blob: Blob,
): Promise<void> {
  await set(segmentKeyFor(packageKey, generation, index), blob)
}

/**
 * Turns one generation's segments into the archive under this key, and frees
 * whatever it replaced.
 *
 * Order is the whole correctness argument. The marker is written FIRST, so the
 * instant anything is freed the newer archive is already the one `readArchive`
 * serves; a crash before it leaves the old archive intact and the new bytes as
 * an unfinished transfer, which is exactly what they are. Freeing first would
 * open a window where the phone holds neither.
 */
export async function markComplete(
  packageKey: string,
  complete: ArchiveComplete,
): Promise<void> {
  // Read BEFORE the overwrite on the next line destroys it: the old marker is
  // the only record of how many segments the outgoing generation holds, and
  // the free below is exactly the kind of many-transaction loop an OS kill
  // interrupts. Carried in the new marker so the count survives the crash and
  // a later delete can still sweep to it (#648).
  const replaced = await readComplete(packageKey)
  const priorSegments = Math.max(replaced?.segments ?? 0, replaced?.priorSegments ?? 0)
  await set(completeKeyFor(packageKey), { ...complete, priorSegments })
  for (const generation of GENERATIONS) {
    if (generation !== complete.generation)
      await deleteGeneration(packageKey, generation, priorSegments)
  }
  // The bytes this replaces. Left standing it would waste up to 1.18 GB of a
  // hiker's phone for good, since `readArchive` now serves the segments and
  // nothing would ever read it again.
  await del(packageKey)
}

/**
 * How far past `atLeast` a delete keeps probing through absences before
 * concluding a generation is spent.
 *
 * A killed delete leaves a gap at the FRONT of a generation (it removes
 * ascending from 0), and a marker from before `priorSegments` existed - or a
 * marker the tear itself outlived - names no floor that reaches past it. So
 * the delete paths do not trust a gap the way the read paths may: they keep
 * probing until this many consecutive indexes answer nothing. At 32 MiB a
 * segment, 64 covers a 2 GiB front gap - past every archive the pipeline
 * publishes - for 64 extra reads on the ordinary gapless path, which is the
 * cost of never again leaving 800 MB stranded on a phone whose owner deleted
 * the map to free the space (#648).
 */
const DELETE_GAP_RUN = 64

/** Reclaims one generation's segments. `atLeast` is a count claimed by a marker
 *  or a source record; past it, absences are tolerated up to DELETE_GAP_RUN in
 *  a row rather than read as the end, because on a delete a gap may be a torn
 *  earlier delete rather than the truth (#648). */
export async function deleteGeneration(
  packageKey: string,
  generation: number,
  atLeast = 0,
): Promise<void> {
  let absentRun = 0
  for (let index = 0; index < MAX_SEGMENTS; index += 1) {
    const key = segmentKeyFor(packageKey, generation, index)
    const stored = await get(key)
    if (stored === undefined) {
      if (index >= atLeast) {
        absentRun += 1
        if (absentRun >= DELETE_GAP_RUN) break
      }
      continue
    }
    absentRun = 0
    await del(key)
  }
}

/**
 * Reclaims every byte stored under this key: both generations, the marker, and
 * any legacy whole-archive record.
 *
 * Someone deleting a 1.18 GB map to free room must not be left holding most of
 * it (#554), so this sweeps generations it has no record of rather than trusting
 * the marker to name the only one present - and it asks the marker itself for
 * the deepest floor it knows (its own count, and the replaced generation's via
 * `priorSegments`), so the caller's floor is a contribution rather than the
 * whole answer (#648).
 */
export async function deleteArchiveRecords(
  packageKey: string,
  atLeast = 0,
): Promise<void> {
  const marker = await readComplete(packageKey)
  const floor = Math.max(atLeast, marker?.segments ?? 0, marker?.priorSegments ?? 0)
  for (const generation of GENERATIONS) {
    await deleteGeneration(packageKey, generation, floor)
  }
  await del(completeKeyFor(packageKey))
  await del(packageKey)
}
