// Connects the Downloads screen's buttons to the real archive downloads.
//
// Kept as a hook rather than folded into the screen so the screen stays a
// pure render of the status it is handed - which is what let its own tests
// cover every state (not-downloaded / downloading / failed / downloaded)
// without a network anywhere near them.
//
// Resume is the reason this holds AbortControllers and reads persisted
// progress on mount: a download interrupted by the app being closed is
// resumable on the next launch, not just within one session.
//
// PLURAL, since #192. The offline map program (#184) puts several archives
// on the same phone - raster sheet, vector basemap, DEM - and each has its
// own independent lifecycle. They are held in ONE hook rather than one hook
// per package because the shell needs a package's state whether or not the
// Downloads window is open (App.tsx reads the corridor package's to decide
// whether an offline background can be honoured at all), and because the
// per-package bookkeeping below - one in-flight attempt, one abort, delete
// waiting on the writer - is the part that was subtle enough to be worth
// having exactly one copy of. useArchiveDownload() is the single-package
// view of the same machinery.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { get } from 'idb-keyval'
import {
  ArchiveHashMismatchError,
  deleteArchive,
  downloadArchive,
  readDownloadProgress,
  type CheckProgress,
  type DownloadProgress,
} from './archiveDownload'
import {
  completedMarker,
  readPersistence,
  requestPersistence,
  type PersistenceState,
} from './storageHealth'
import type { DownloadStatus } from '../screens/DownloadCard'

/** The status when the blob is gone: evicted if a completed archive was ever
 *  recorded here, plainly not-downloaded otherwise. The one distinction #190
 *  exists for - "your map is gone and here is why" against "no map". */
function absentStatus(packageKey: string): DownloadStatus {
  const completed = completedMarker(packageKey)
  return completed === null
    ? { state: 'not-downloaded' }
    : { state: 'evicted', completedAt: completed }
}

const NOT_DOWNLOADED: DownloadStatus = { state: 'not-downloaded' }

/** One package to hold state for: its store key, and where its bytes come
 *  from right now (the corridor sheet's URL follows the detail level, so
 *  this is not a constant). */
export interface ArchiveDownloadRequest {
  packageKey: string
  url: string
  /** What `latest.json` calls this artifact, so the download can be held to
   *  its published hash (lib/packages.ts, `packageArtifactKey`). */
  artifactKey: string
}

export function useArchiveDownloads(requests: readonly ArchiveDownloadRequest[]) {
  const [statuses, setStatuses] = useState<Record<string, DownloadStatus>>({})
  const [errors, setErrors] = useState<Record<string, string | null>>({})
  /** What asking the browser for durable storage came to - null until the
   *  first answer arrives. Read on mount, re-asked at download time. One
   *  answer for the whole origin, not per package: it is the origin's
   *  storage the browser is deciding about. */
  const [persistence, setPersistence] = useState<PersistenceState | null>(null)

  const abortControllers = useRef(new Map<string, AbortController>())
  /** The attempt currently in flight per package, so a delete can wait for
   *  it to stop writing before it starts deleting - see `remove`. */
  const running = useRef(new Map<string, Promise<void>>())

  // Read during callbacks rather than closed over, so `start` does not have
  // to be rebuilt every time a URL changes - and so a tap always fetches the
  // detail level that is selected NOW, not the one selected when the
  // callback was made.
  const requestsRef = useRef(requests)
  requestsRef.current = requests

  // Effects key off the package set, never off the URLs: changing the detail
  // level re-points where the corridor sheet is fetched from, and must not
  // re-read (or reset) what is already on the phone.
  //
  // The set is identified by a joined string rather than by the array, which
  // callers rebuild on every render. Depending on the array itself would put
  // this hook in a loop - the effect sets state, the render that follows
  // builds a new array, the effect runs again - and the loop's body is
  // IndexedDB reads. Keys are IndexedDB key names (`ourhike:...`) carrying no
  // newline, so the join round-trips exactly.
  const keySignature = requests.map((request) => request.packageKey).join('\n')
  const packageKeys = useMemo(
    () => (keySignature === '' ? [] : keySignature.split('\n')),
    [keySignature],
  )

  const setStatus = useCallback((packageKey: string, status: DownloadStatus) => {
    setStatuses((previous) => ({ ...previous, [packageKey]: status }))
  }, [])

  const setError = useCallback((packageKey: string, error: string | null) => {
    setErrors((previous) => ({ ...previous, [packageKey]: error }))
  }, [])

  // On mount, reflect what is already on the phone for every package: a
  // finished archive, an interrupted one worth resuming, an archive that was
  // here and is gone, or nothing at all.
  useEffect(() => {
    let cancelled = false

    for (const packageKey of packageKeys) {
      void (async () => {
        try {
          const finished = (await get(packageKey)) as Blob | undefined
          if (cancelled) return
          if (finished !== undefined) {
            setStatus(packageKey, {
              state: 'downloaded',
              totalBytes: finished.size,
              completedAt: new Date(),
            })
            return
          }

          const partial = await readDownloadProgress(packageKey)
          if (cancelled) return
          if (partial !== null) {
            setStatus(packageKey, { state: 'failed', ...partial })
            return
          }

          // No blob, no partial - but if the completion marker says an
          // archive finished here, this is an eviction, and saying "not
          // downloaded" would be the FarOut failure: a map that silently
          // vanished offered back as if it had never existed (#190).
          setStatus(packageKey, absentStatus(packageKey))
        } catch {
          // The reads above are IndexedDB, which can fail outright - storage
          // evicted under pressure, a corrupt database, private browsing.
          // Unhandled that was an unhandled rejection on app start; handled,
          // the marker still gets its say: an unreadable database on a phone
          // that completed a download is closer to "your map is gone" than to
          // "no map downloaded", and the marker lives in localStorage, which
          // is still readable in exactly the incidents this guards against.
          //
          // Deliberately not surfaced as an error: this runs before the hiker
          // has asked for anything. A failure they DID ask for still reports
          // itself - see the catch in `run`.
          if (!cancelled) setStatus(packageKey, absentStatus(packageKey))
        }
      })()
    }

    return () => {
      cancelled = true
    }
  }, [packageKeys, setStatus])

  // The standing durability answer, without prompting anyone: persisted()
  // reports what the browser already decided, so the Downloads screen can be
  // honest about best-effort storage before the first download ever starts.
  useEffect(() => {
    let cancelled = false
    void readPersistence().then((state) => {
      if (!cancelled) setPersistence(state)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const run = useCallback(
    async (packageKey: string) => {
      const request = requestsRef.current.find(
        (candidate) => candidate.packageKey === packageKey,
      )
      if (request === undefined) return

      setError(packageKey, null)
      const controller = new AbortController()
      abortControllers.current.set(packageKey, controller)

      // Ask for durable storage at the moment it means something - the hiker
      // just chose to store hundreds of megabytes, which is the context a
      // Firefox-style permission prompt is answerable in. Not awaited: the
      // download must not sit behind a prompt, and a denial changes what the
      // screen says about durability, never whether the bytes arrive.
      void requestPersistence().then(setPersistence)

      const onProgress = (progress: DownloadProgress) =>
        setStatus(packageKey, { state: 'downloading', ...progress })

      // Bytes already here, being read back to catch their hash up. Its own
      // state because on a phone it takes seconds and looks exactly like a
      // stalled transfer - and the two ask for opposite responses from
      // someone standing in a dead spot.
      const onChecking = (progress: CheckProgress) =>
        setStatus(packageKey, { state: 'checking', ...progress })

      try {
        await downloadArchive(packageKey, request.url, {
          artifactKey: request.artifactKey,
          onProgress,
          onChecking,
          signal: controller.signal,
        })
        const finished = (await get(packageKey)) as Blob | undefined
        setStatus(packageKey, {
          state: 'downloaded',
          totalBytes: finished?.size ?? 0,
          completedAt: new Date(),
        })
      } catch (thrown) {
        // An abort is this hook's own doing - remove() asking for the space
        // back, or the screen unmounting - not news for the hiker. Surfacing
        // it here raced remove(): its setError(null) ran first, then this
        // catch fired during its await and put a "download failed" alert on
        // top of a delete that succeeded.
        if (controller.signal.aborted) return

        // A refused archive is its own state, not an error string (#238):
        // downloadArchive discarded everything before throwing, so there is
        // no partial to resume and the generic failed/absent path below
        // would say either "Resume" over bytes that no longer exist or
        // nothing at all. Keyed off the type here because this catch is the
        // last place the type still exists. The status is session-only on
        // purpose - nothing about a mismatch is persisted, so a reload
        // falls back to absentStatus, which is then also true.
        if (thrown instanceof ArchiveHashMismatchError) {
          setStatus(packageKey, { state: 'hash-mismatch' })
          return
        }

        // Whatever arrived is already persisted by downloadArchive, so the
        // resumable state is still what the screen shows. But the reason is
        // kept and surfaced too - this catch used to swallow it entirely, and
        // when the archive 404'd the screen simply returned to "Download the
        // map" with no explanation at all. "Nothing happened" is the one
        // answer that leaves someone with no idea whether to retry, wait, or
        // check their signal.
        setError(
          packageKey,
          thrown instanceof Error ? thrown.message : 'The map download failed.',
        )
        const partial = await readDownloadProgress(packageKey)
        // absentStatus rather than a bare not-downloaded: a download that
        // failed before its first byte, on a phone whose previous archive was
        // evicted, should keep saying so.
        setStatus(
          packageKey,
          partial === null ? absentStatus(packageKey) : { state: 'failed', ...partial },
        )
      }
    },
    [setError, setStatus],
  )

  /** Wraps `run` so the in-flight attempt is always knowable, per package. */
  const start = useCallback(
    (packageKey: string) => {
      // One attempt at a time PER PACKAGE. There is an async gap between the
      // tap and `status` becoming 'downloading' (two IndexedDB reads), during
      // which the screen still offers the button - and a second run() would
      // overwrite this package's controller and in-flight promise, so
      // remove() would abort only the newest attempt while the orphan kept
      // streaming and persisted its partial AFTER the delete: the "delete
      // doesn't free the space" race these maps exist to prevent,
      // reintroduced one tap deeper.
      //
      // Different packages deliberately do NOT exclude each other. They write
      // to different keys, and a hiker who taps the trail's whole manifest is
      // asking for all of it.
      const inFlight = running.current.get(packageKey)
      if (inFlight !== undefined) return inFlight

      const attempt = run(packageKey)
      running.current.set(packageKey, attempt)
      const clear = () => {
        if (running.current.get(packageKey) === attempt)
          running.current.delete(packageKey)
      }
      attempt.then(clear, clear)
      return attempt
    },
    [run],
  )

  /** One tap, every package: the trail manifest's whole set at once (#192).
   *  Already-finished packages are skipped rather than re-fetched. */
  const startAll = useCallback(
    async (keys: readonly string[]) => {
      await Promise.all(keys.map((packageKey) => start(packageKey)))
    },
    [start],
  )

  const remove = useCallback(
    async (packageKey: string) => {
      setError(packageKey, null)
      abortControllers.current.get(packageKey)?.abort()

      // Aborting does not stop the attempt immediately, and what it does on
      // the way out is SAVE: downloadArchive keeps whatever arrived so it can
      // be resumed, which is right when the app is closing and wrong when the
      // hiker has just asked for the space back. Deleting first raced those
      // writes and lost - the partial bytes came back, the screen went to
      // "failed" rather than "not downloaded", and several hundred megabytes
      // stayed on a phone that had been told they were gone.
      await running.current.get(packageKey)?.catch(() => undefined)
      running.current.delete(packageKey)

      await deleteArchive(packageKey)
      setStatus(packageKey, { state: 'not-downloaded' })
    },
    [setError, setStatus],
  )

  useEffect(() => {
    const controllers = abortControllers.current
    return () => {
      for (const controller of controllers.values()) controller.abort()
    }
  }, [])

  const statusFor = useCallback(
    (packageKey: string): DownloadStatus => statuses[packageKey] ?? NOT_DOWNLOADED,
    [statuses],
  )

  /**
   * Whether `statusFor` is answering from the phone yet, rather than from its
   * own default.
   *
   * The distinction the fallback above cannot make: a package nobody has read
   * yet and a package that was read and is not here both come back
   * `not-downloaded`, and a caller deciding something on that answer decides
   * it twice - once wrongly, then again a tick later when the read lands.
   * That was a whole extra map build on every launch: the shell asks this
   * hook whether an offline background can be honoured, got "no" before the
   * first IndexedDB read had returned, drew the live sheet, and rebuilt the
   * map around the archive the moment the truth arrived.
   *
   * Derived rather than held as its own flag, so it cannot drift: it is
   * exactly "every package in the set has a status", which also answers
   * correctly if the set ever changes underneath. An empty set is read - there
   * was nothing to ask.
   */
  const statusesKnown = packageKeys.every(
    (packageKey) => statuses[packageKey] !== undefined,
  )

  const errorFor = useCallback(
    (packageKey: string): string | null => errors[packageKey] ?? null,
    [errors],
  )

  return {
    statusFor,
    errorFor,
    statusesKnown,
    persistence,
    start,
    startAll,
    resume: start,
    remove,
  }
}

/**
 * The single-package view of the store, for callers that hold exactly one -
 * the shell's corridor-background wiring, and every test written against it.
 * Identical semantics to the plural hook; the package key is simply bound.
 */
export function useArchiveDownload(
  packageKey: string,
  archiveUrl: string,
  artifactKey: string,
) {
  const requests = useMemo(
    () => [{ packageKey, url: archiveUrl, artifactKey }],
    [packageKey, archiveUrl, artifactKey],
  )
  const {
    statusFor,
    errorFor,
    statusesKnown,
    persistence,
    start: startPackage,
    remove: removePackage,
  } = useArchiveDownloads(requests)

  const start = useCallback(() => startPackage(packageKey), [startPackage, packageKey])
  const remove = useCallback(() => removePackage(packageKey), [removePackage, packageKey])

  return {
    status: statusFor(packageKey),
    error: errorFor(packageKey),
    /** Whether `status` is the phone's answer yet - see `statusesKnown`. */
    statusKnown: statusesKnown,
    persistence,
    start,
    resume: start,
    remove,
  }
}
