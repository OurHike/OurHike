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
  const abortRef = useRef<AbortController | null>(null)

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
    } catch {
      // Whatever arrived is already persisted by downloadArchive; surface the
      // resumable state rather than an error the hiker can do nothing with.
      const partial = await readDownloadProgress()
      setStatus(
        partial === null ? { state: 'not-downloaded' } : { state: 'failed', ...partial },
      )
    }
  }, [archiveUrl])

  const remove = useCallback(async () => {
    abortRef.current?.abort()
    await deleteArchive()
    setStatus({ state: 'not-downloaded' })
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { status, start: run, resume: run, remove }
}
