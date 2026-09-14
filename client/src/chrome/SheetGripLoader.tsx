import { useEffect, useState, type ComponentType, type RefObject } from 'react'

/**
 * Fetch the grip when a planning sheet actually opens, rather than before the
 * first frame.
 *
 * WHY THIS FILE EXISTS, which is worth a paragraph because a loader for a
 * 28 px handle looks like ceremony. `chrome/SheetGrip.tsx` landed in the
 * `main` chunk and put the eager bundle at 256,181 bytes against
 * features/LAUNCH_BUDGET.md §3's 256,000-byte ceiling - 181 bytes over, on CI,
 * 2026-09-14. The 181 bytes are not what matters; where they were is. Eager
 * JavaScript is everything the document parses before any `import()`, and the
 * grip is not first-frame code by any reading: it cannot be used until a hiker
 * has opened the day-hike builder, which is two taps and a tab away from the
 * screen the budget is about.
 *
 * So this is not a workaround for a byte count. It is the byte count doing its
 * job - asking "is this needed before the first frame?" of something whose
 * answer is plainly no.
 *
 * A plain dynamic import rather than `lazy` and a `Suspense` boundary: there
 * is nothing to fall back to and nothing to wait for. The sheet renders
 * without a grip for the frame or two the fetch takes, which is exactly how
 * the sheet behaved before the grip existed, and the module is in the service
 * worker's precache (`generateSW`) so on any launch after the first that fetch
 * is local.
 */
type GripProps = {
  sheet: RefObject<HTMLElement | null>
  label: string
  edge?: 'top' | 'bottom'
}

export function SheetGripLoader(props: GripProps) {
  const [Grip, setGrip] = useState<ComponentType<GripProps> | null>(null)

  useEffect(() => {
    let mounted = true
    void import('./SheetGrip')
      .then((module) => {
        // The store-a-component-in-state trap: setState treats a function as
        // an updater, so a bare `setGrip(module.default)` would call the
        // component with the previous state as its props and store whatever
        // it returned.
        if (mounted) setGrip(() => module.default)
      })
      .catch(() => {
        // A chunk that will not load leaves the sheet without a grip, which is
        // exactly how the sheet behaved before the grip existed - so there is
        // nothing to tell a hiker and nothing to retry. Swallowing it is the
        // behaviour, not a shrug.
        //
        // It also has to be CAUGHT rather than left to float. A dynamic import
        // started by a mounted component can resolve after a test has finished
        // and its environment has been torn down, and vite's module runner
        // then throws `TypeError: URL is not a constructor` reaching for a
        // `URL` global jsdom has already taken away. Every test still passes
        // and vitest still exits 1, because 34 unhandled rejections are 34
        // unhandled rejections - which is how CI failed on 70c00467.
      })
    return () => {
      mounted = false
    }
  }, [])

  if (Grip === null) return null
  return <Grip {...props} />
}
