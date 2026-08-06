// The community safety data behind the map: closures and reports, read from
// the backend (#286) so the closure bands and serious-warning pins (#232)
// have something to render.
//
// Three properties are load-bearing:
//
// **A failed fetch keeps the last copy, and never becomes an empty list.**
// The reads themselves throw on failure (lib/api.ts), and this hook's answer
// to a throw is to keep what it had - an empty list and a failed fetch draw
// the same map and mean opposite things on the ground. The sync ages say how
// old the surviving copy is, which is the honest statement about it.
//
// **Closures and reports fail independently.** One endpoint erroring must
// not blank the other's data: a 500 from /reports on a day the trail is
// closed would otherwise cost the map its closure bands too.
//
// **`fetchedAt` is per-collection**, because ClosureSheet promises "your copy
// of this closure is N days old" about the closure specifically - a fresh
// reports fetch must not make a stale closure copy read as current.
//
// Held in memory only, for now: a hiker who launches offline sees no bands
// until the first successful fetch, the same state every launch was in
// before the read path existed. Persisting a copy in IndexedDB - which the
// sync-age wording is really about - needs the same offline store treatment
// the trail data has, and is called out in the PR rather than half-done here.

import { useEffect, useState } from 'react'
import {
  API_CONFIGURED,
  fetchClosures,
  fetchReports,
  type RemoteClosure,
  type RemoteReport,
} from './api'

interface Copy<T> {
  list: T[]
  at: Date
}

export interface SafetyData {
  closures: RemoteClosure[]
  /** When the closures on screen were fetched; null until a fetch succeeds. */
  closuresSyncedAt: Date | null
  reports: RemoteReport[]
  reportsSyncedAt: Date | null
}

/**
 * Reads closures and reports whenever there is a connection to read over.
 *
 * `accountKey` re-runs the read when who-is-asking changes, because the
 * server's answer does: a signed-in reporter is handed their own unmoderated
 * reports alongside the public set (backend `list_reports`), and signing out
 * has to drop them again rather than keep showing a copy the server would no
 * longer serve.
 */
export function useSafetyData(online: boolean, accountKey: string | null): SafetyData {
  const [closures, setClosures] = useState<Copy<RemoteClosure> | null>(null)
  const [reports, setReports] = useState<Copy<RemoteReport> | null>(null)

  useEffect(() => {
    if (!API_CONFIGURED || !online) return

    let cancelled = false

    // Two independent reads on purpose - see the module header.
    void fetchClosures()
      .then((list) => {
        if (!cancelled) setClosures({ list, at: new Date() })
      })
      .catch(() => {
        // Kept: the last copy plus its age is the honest state, and the
        // reads are retried on the next connectivity or account change.
      })

    void fetchReports()
      .then((list) => {
        if (!cancelled) setReports({ list, at: new Date() })
      })
      .catch(() => {
        // Same.
      })

    return () => {
      cancelled = true
    }
  }, [online, accountKey])

  return {
    closures: closures?.list ?? [],
    closuresSyncedAt: closures?.at ?? null,
    reports: reports?.list ?? [],
    reportsSyncedAt: reports?.at ?? null,
  }
}
