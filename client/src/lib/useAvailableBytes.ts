// React binding for storageHealth.ts's `estimateAvailableBytes`, so a level the
// phone cannot hold can say so where it is chosen (#555).
//
// Shaped like useDataSaver.ts and useOnline.ts - read the value, subscribe to
// what changes it, unsubscribe on teardown - with one difference that is the
// whole reason this file needs a comment: THERE IS NO EVENT FOR THIS. The
// Storage API publishes nothing when usage moves, so the subscription is to the
// two moments a hiker's free space plausibly changed:
//
//   visibilitychange   they left to free space and came back. On iOS that is
//                      the actual remedy - deleting photos happens in Settings,
//                      not in this tab - so the rung has to come back on return
//                      rather than at the next cold start.
//   refresh()          the app itself deleted something. Downloads.tsx knows
//                      when, and #554 measured that the browser's own accounting
//                      may never notice, which is exactly when an app-driven
//                      re-read is the only thing that will.
//
// A capability read, never a platform check. The issue this closes is about iOS,
// where WebKit's per-origin allowance starts near a gigabyte and the Fine tier
// is 1.18 GB - but sniffing the UA for that would be wrong twice over: it would
// be false on an iPad with room, and it would miss an Android phone with none.
// dataSaver.ts is the precedent, and `null` here is its "the API is absent"
// answer: unknown, so refuse nothing.

import { useCallback, useEffect, useState } from 'react'
import { estimateAvailableBytes } from './storageHealth'

export interface AvailableBytes {
  /** What the browser says is free, or null where it will not say - and null
   *  means "offer everything", never "offer nothing". */
  bytes: number | null
  /** Re-read now. For the caller that just changed the answer itself. */
  refresh: () => void
}

export function useAvailableBytes(): AvailableBytes {
  const [bytes, setBytes] = useState<number | null>(null)

  // A counter rather than calling the reader directly, so `refresh` is stable
  // across renders and every read goes through the one effect that knows how to
  // cancel itself.
  const [asked, setAsked] = useState(0)
  const refresh = useCallback(() => setAsked((count) => count + 1), [])

  useEffect(() => {
    let cancelled = false
    void estimateAvailableBytes().then((answer) => {
      if (!cancelled) setBytes(answer)
    })
    return () => {
      cancelled = true
    }
  }, [asked])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [refresh])

  return { bytes, refresh }
}
