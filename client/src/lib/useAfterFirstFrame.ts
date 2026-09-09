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
//
// AND A TIMER BESIDE IT, WHICH IS THE PART THAT IS NOT OPTIONAL. A browser
// does not run animation frames in a document that is hidden, and a hidden
// launch is an ordinary one: a phone restoring its tabs, a link opened in the
// background, an installed app resumed with the screen still off. Waiting on
// a frame alone would mean such a launch fetched no conditions, no cell
// index and no suggested hikes AT ALL until somebody looked at it - and the
// first thing they would then see is a screen that had learned nothing while
// it sat there. So whichever of the two comes first releases the gate, and
// the timer is the one that fires in the dark.

import { useEffect, useState } from 'react'

/**
 * How long to wait for a frame that may never come.
 *
 * @unvalidated - picked, not measured. It is long enough that a visible
 * launch is released by its frame (which arrives in a handful of
 * milliseconds) rather than by this, and short enough that a hidden launch
 * has its data by the time a phone comes out of a pocket. What would settle
 * it is the marks in lib/launchMarks.ts read off a real device that launched
 * hidden, which nothing has yet done.
 */
export const FIRST_FRAME_FALLBACK_MS = 250

export function useAfterFirstFrame(): boolean {
  const [painted, setPainted] = useState(false)
  useEffect(() => {
    let done = false
    const release = () => {
      if (done) return
      done = true
      setPainted(true)
    }
    const timer = setTimeout(release, FIRST_FRAME_FALLBACK_MS)
    // Absent in a worker-less environment and in an old WebView, where the
    // timer above is the whole mechanism.
    const frame =
      typeof requestAnimationFrame === 'function' ? requestAnimationFrame(release) : null
    return () => {
      clearTimeout(timer)
      if (frame !== null) cancelAnimationFrame(frame)
    }
  }, [])
  return painted
}
