// True once the browser has had a chance to paint the shell (#1302).
//
// The launch effects that fetch things - conditions, cell indexes, suggested
// hikes, the service worker's update check - used to start in the same commit
// as the first render, about thirty requests competing with the first frame
// for one connection and one thread. None of them changes what the first
// frame IS; every line they feed renders "unknown" until they land anyway.
// So they wait for this: a frame after the first commit, which is the
// earliest moment the shell can be on screen.
//
// One frame and not "idle": `requestIdleCallback` is absent in Safari and
// can wait seconds on a busy page, and a closure line that arrives seconds
// late is a cost a hiker notices. A frame is the width of the paint and no
// more.

import { useEffect, useState } from 'react'

export function useAfterFirstFrame(): boolean {
  const [painted, setPainted] = useState(false)
  useEffect(() => {
    if (typeof requestAnimationFrame === 'function') {
      const frame = requestAnimationFrame(() => setPainted(true))
      return () => cancelAnimationFrame(frame)
    }
    // No frames to wait for - a worker-less environment or an old WebView -
    // so the next turn of the event loop is the closest thing.
    const timer = setTimeout(() => setPainted(true), 0)
    return () => clearTimeout(timer)
  }, [])
  return painted
}
