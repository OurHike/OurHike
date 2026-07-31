// The clock behind the status strip.
//
// Ticks once a minute rather than once a second: the strip shows a time to
// the minute, and waking React 60 times more often than the display can
// change is real battery on a phone that has to last three days.

import { useEffect, useState } from 'react'

export const CLOCK_INTERVAL_MS = 60_000

export function useClock(intervalMs: number = CLOCK_INTERVAL_MS): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])

  return now
}
