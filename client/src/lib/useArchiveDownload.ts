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
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'
import type { DownloadStatus } from '../screens/Downloads'

export function useArchiveDownload(archiveUrl: string) {
  const [status, setStatus] = useState<DownloadStatus>({ state: 'not-downloaded' })
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  /** The attempt currently in flight, so a delete can wait for it to stop
   *  writing before it starts deleting - see `remove`. */
  const runningRef = useRef<Promise<void> | null>(null)

  // On mount, reflect what is already on the phone: a finished archive, an
  // interrupted one worth resuming, or neither.
  useEffect(() => {
    let cancelled = false

    void (async () => {
      const finished = (await get(CORRIDOR_ARCHIVE_KEY)) as Blob | undefined
      if (cancelled) return
      if (finished !== undefined) {
        setStatus({
          state: 'downloaded',
          totalBytes: finished.size,
          completedAt: new Date(),
        })
        return
      }

      const partial = await readDownloadProgress()
      if (cancelled || partial === null) return
      setStatus({ state: 'failed', ...partial })
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const run = useCallback(async () => {
    setError(null)
    const controller = new AbortController()
    abortRef.current = controller

    const onProgress = (progress: DownloadProgress) =>
      setStatus({ state: 'downloading', ...progress })

    try {
      await downloadArchive(archiveUrl, { onProgress, signal: controller.signal })
      const finished = (await get(CORRIDOR_ARCHIVE_KEY)) as Blob | undefined
      setStatus({
        state: 'downloaded',
        totalBytes: finished?.size ?? 0,
        completedAt: new Date(),
      })
    } catch (thrown) {
      // Whatever arrived is already persisted by downloadArchive, so the
      // resumable state is still what the screen shows. But the reason is kept
      // and surfaced too - this catch used to swallow it entirely, and when the
      // archive 404'd the screen simply returned to "Download the map" with no
      // explanation at all. "Nothing happened" is the one answer that leaves
      // someone with no idea whether to retry, wait, or check their signal.
      setError(thrown instanceof Error ? thrown.message : 'The map download failed.')
      const partial = await readDownloadProgress()
      setStatus(
        partial === null ? { state: 'not-downloaded' } : { state: 'failed', ...partial },
      )
    }
  }, [archiveUrl])

  /** Wraps `run` so the in-flight attempt is always knowable. */
  const start = useCallback(() => {
    const attempt = run()
    runningRef.current = attempt
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

    await deleteArchive()
    setStatus({ state: 'not-downloaded' })
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { status, error, start, resume: start, remove }
}
