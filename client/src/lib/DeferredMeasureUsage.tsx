// The only part of usage measurement the first frame carries (#1902): this
// loader, which imports lib/MeasureUsage.tsx once App has mounted and renders
// it when it arrives.
//
// Not a `screens/deferred.ts` entry, deliberately: a deferred screen that
// fails to load throws into the error boundary, which is right for a screen a
// hiker asked for and wrong here. A chunk that never arrives costs the counts
// and nothing else - measurement is the first thing a phone may lose
// (features/EVENTING.md §1 rule 4).
//
// Moments before it arrives are missed rather than queued: a screen changed
// in the first second of a launch is not counted, and neither would a plan
// made in it be (App's handle is empty until then). Everything else - the
// visit, a map already in view, a sign-in already finished - is read from
// state when the hook first runs. The install is the exception, and the
// reason this file holds one value: on a fresh install the chunk comes from
// the network, and a hiker who taps "Skip — take me to the map" before it
// arrives has finished first run by the time the hook asks. So whether this
// launch began unfinished is captured here, the first render preferences are
// known, and handed down in place of the live answer.

import { type ComponentType, createElement, useEffect, useState } from 'react'

import type { MeasureUsageProps } from './MeasureUsage'

export function DeferredMeasureUsage({ input, onMeasure }: MeasureUsageProps) {
  const [Loaded, setLoaded] = useState<ComponentType<MeasureUsageProps> | null>(null)
  // Kept from the first render with preferences known - React's "adjusting
  // state when a prop changes", so no effect and no ref read during render.
  const [newInstall, setNewInstall] = useState<boolean | null>(null)
  if (newInstall === null && input.ready) setNewInstall(input.newInstall)
  useEffect(() => {
    let live = true
    import('./MeasureUsage').then(
      (module) => {
        if (live) setLoaded(() => module.MeasureUsage)
      },
      () => {
        // No counting this launch.
      },
    )
    return () => {
      live = false
    }
  }, [])
  if (Loaded === null) return null
  return createElement(Loaded, {
    input: { ...input, newInstall: newInstall ?? input.newInstall },
    onMeasure,
  })
}
