// Connects Downloads.tsx's buttons to the real archive download.
//
// Kept as a hook rather than folded into the screen so the screen stays a
// pure render of the status it is handed - which is what let its own tests
// cover every state (not-downloaded / downloading / failed / downloaded)
// without a network anywhere near them.
//
// Resume is the reason this holds an AbortController and reads persisted
// progress on mount: a download interrupted by the app being closed is
// resumable on the next launch, not just within one session.

import { useCallback, useEffect, useRef, useState } from 'react'
import { get } from 'idb-keyval'
import {
  deleteArchive,
  downloadArchive,
  readDownloadProgress,
  type DownloadProgress,
} from './archiveDownload'
import {
  completedMarker,
  readPersistence,
  requestPersistence,
  type PersistenceState,
} from './storageHealth'
import type { DownloadStatus } from '../screens/Downloads'

/** The status when the blob is gone: evicted if a completed archive was ever
 *  recorded here, plainly not-downloaded otherwise. The one distinction #190
 *  exists for - "your map is gone and here is why" against "no map". */
function absentStatus(packageKey: string): DownloadStatus {
  const completed = completedMarker(packageKey)
  return completed === null
    ? { state: 'not-downloaded' }
    : { state: 'evicted', completedAt: completed }
}

export function useArchiveDownload(packageKey: string, archiveUrl: string) {
  const [status, setStatus] = useState<DownloadStatus>({ state: 'not-downloaded' })
  const [error, setError] = useState<string | null>(null)
  /** What asking the browser for durable storage came to - null until the
   *  first answer arrives. Read on mount, re-asked at download time. */
  const [persistence, setPersistence] = useState<PersistenceState | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  /** The attempt currently in flight, so a delete can wait for it to stop
   *  writing before it starts deleting - see `remove`. */
  const runningRef = useRef<Promise<void> | null>(null)

  // On mount, reflect what is already on the phone: a finished archive, an
  // interrupted one worth resuming, an archive that was here and is gone, or
  // nothing at all.
  useEffect(() => {
    let cancelled = false

    void (async () => {
      try {
        const finished = (await get(packageKey)) as Blob | undefined
        if (cancelled) return
        if (finished !== undefined) {
          setStatus({
            state: 'downloaded',
            totalBytes: finished.size,
            completedAt: new Date(),
          })
          return
        }

        const partial = await readDownloadProgress(packageKey)
        if (cancelled) return
        if (partial !== null) {
          setStatus({ state: 'failed', ...partial })
          return
        }

        // No blob, no partial - but if the completion marker says an archive
        // finished here, this is an eviction, and saying "not downloaded"
        // would be the FarOut failure: a map that silently vanished offered
        // back as if it had never existed (#190).
        setStatus(absentStatus(packageKey))
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
        if (!cancelled) setStatus(absentStatus(packageKey))
      }
    })()

    return () => {
      cancelled = true
    }
  }, [packageKey])

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

  const run = useCallback(async () => {
    setError(null)
    const controller = new AbortController()
    abortRef.current = controller

    // Ask for durable storage at the moment it means something - the hiker
    // just chose to store hundreds of megabytes, which is the context a
    // Firefox-style permission prompt is answerable in. Not awaited: the
    // download must not sit behind a prompt, and a denial changes what the
    // screen says about durability, never whether the bytes arrive.
    void requestPersistence().then(setPersistence)

    const onProgress = (progress: DownloadProgress) =>
      setStatus({ state: 'downloading', ...progress })

    try {
      await downloadArchive(packageKey, archiveUrl, {
        onProgress,
        signal: controller.signal,
      })
      const finished = (await get(packageKey)) as Blob | undefined
      setStatus({
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

      // Whatever arrived is already persisted by downloadArchive, so the
      // resumable state is still what the screen shows. But the reason is kept
      // and surfaced too - this catch used to swallow it entirely, and when the
      // archive 404'd the screen simply returned to "Download the map" with no
      // explanation at all. "Nothing happened" is the one answer that leaves
      // someone with no idea whether to retry, wait, or check their signal.
      setError(thrown instanceof Error ? thrown.message : 'The map download failed.')
      const partial = await readDownloadProgress(packageKey)
      // absentStatus rather than a bare not-downloaded: a download that
      // failed before its first byte, on a phone whose previous archive was
      // evicted, should keep saying so.
      setStatus(
        partial === null ? absentStatus(packageKey) : { state: 'failed', ...partial },
      )
    }
  }, [packageKey, archiveUrl])

  /** Wraps `run` so the in-flight attempt is always knowable. */
  const start = useCallback(() => {
    // One attempt at a time. There is an async gap between the tap and
    // `status` becoming 'downloading' (two IndexedDB reads), during which
    // the screen still offers the button - and a second run() would
    // overwrite abortRef and runningRef, so remove() would abort only the
    // newest attempt while the orphan kept streaming and persisted its
    // partial AFTER the delete: the "delete doesn't free the space" race
    // these refs exist to prevent, reintroduced one tap deeper.
    if (runningRef.current) return runningRef.current

    const attempt = run()
    runningRef.current = attempt
    const clear = () => {
      if (runningRef.current === attempt) runningRef.current = null
    }
    attempt.then(clear, clear)
    return attempt
  }, [run])

  const remove = useCallback(async () => {
    setError(null)
    abortRef.current?.abort()

    // Aborting does not stop the attempt immediately, and what it does on the
    // way out is SAVE: downloadArchive keeps whatever arrived so it can be
    // resumed, which is right when the app is closing and wrong when the
    // hiker has just asked for the space back. Deleting first raced those
    // writes and lost - the partial bytes came back, the screen went to
    // "failed" rather than "not downloaded", and several hundred megabytes
    // stayed on a phone that had been told they were gone.
    await runningRef.current?.catch(() => undefined)
    runningRef.current = null

    await deleteArchive(packageKey)
    setStatus({ state: 'not-downloaded' })
  }, [packageKey])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { status, error, persistence, start, resume: start, remove }
}
