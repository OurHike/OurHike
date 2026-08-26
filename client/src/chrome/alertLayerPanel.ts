// The one switch this app offers over a safety layer, and the reason it is
// safe to offer (#1047).
//
// WHAT "ALERTS" MEANS HERE. The three marks the map draws when something on
// the trail is wrong: OurHike's closure bands (map/closureLayers.ts), the
// ATC's own bands and dots (map/atcUpdateLayers.ts), and serious-warning pins
// (map/warningLayers.ts). One switch over all three rather than one each,
// because lib/atcUpdateStyle.ts draws an ATC band in the closure's exact
// colour, width and casing on purpose - "both mean the trail is shut" - so a
// control that took one off the canvas and left the other would look broken
// and, worse, would teach that the band still there is a different kind of
// thing.
//
// WHAT IT DOES NOT TOUCH, WHICH IS THE WHOLE REASON IT MAY EXIST. The header
// lines - "Trail closed 2.1 mi ahead", "2 serious warnings on your route",
// the advisory line - and the visually-hidden `aria-live` sentence above
// them are untouched, and structurally so: they reach chrome/MapScreen.tsx as
// already-rendered strings on their own props, and this flag is applied at
// the `<MapView>` call site, so nothing here is able to reach them. Nor does
// it touch the ATC notice list or its "new alerts" banner, which have their
// own silence (lib/atcAlertsBanner.ts).
//
// So what a hiker turns off is INK ON THE CANVAS, never the app's word about
// what is in front of them. That distinction is what makes this a decluttering
// control rather than a way to switch the safety net off, and it is the answer
// to features/MAP_OPTIONS.md's long-standing worry that hiding closures
// "conflicts directly with value #4".
//
// NOTHING IS STORED, AND THAT IS THE FEATURE. `useState`, deliberately - not
// lib/userPreferences.ts, not localStorage, not `waypoint_types_shown`. The
// maintainer's constraint on #1047 is the whole design: "we shouldnt let the
// throughhikers just turn that off for many days. The map should always open
// to the alerts being shown." A stored flag is precisely the thing that could
// last for many days, and a synced one could arrive on a second phone already
// off. chrome/waypointFiltersPanel.ts's own history is the argument in the
// other direction - #530 moved the category filter INTO storage because a
// hiker who hides privies means it - and the difference is that nobody's
// safety turns on a privy.
//
// "OPEN" HAS TO MEAN THE PHONE'S SENSE OF IT, NOT THE PROCESS'S. A cold start
// gets `true` from the initial state and a browser reload gets it from a fresh
// module. Neither covers the case this is actually built for: a thru-hiker's
// phone keeps this app alive for days, so "the next time you open the map" is
// a RESUME, not a launch. `visibilitychange` is what the platform gives for
// that, and it is the same subscription lib/useAvailableBytes.ts makes for the
// same reason - on iOS the moment a hiker comes back to the tab is the only
// moment worth re-reading anything.
//
// The gap that leaves, stated rather than papered over: an app held in the
// foreground continuously never fires the event, so a hide lasts as long as
// the screen stays awake. That is bounded by the screen timeout and the
// battery - minutes to an hour, not the days this exists to prevent - so no
// second timer is built. @unvalidated: nobody has watched a hiker do this, and
// what would settle it is field use reporting how long a hide actually wants
// to last. If it turns out hikers hide alerts and walk, the fix is an elapsed
// ceiling here, not a stored preference.

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { MapScreenProps } from './MapScreen'

/** The `MapScreenProps` fields this feature owns. See atcNoticesPanel.tsx for
 *  why a hook hands back a `Pick<>` the shell spreads rather than props the
 *  shell assembles. */
export type AlertLayerMapProps = Pick<MapScreenProps, 'alertsShown' | 'onToggleAlerts'>

export interface AlertLayerPanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: AlertLayerMapProps
}

export function useAlertLayerPanel(): AlertLayerPanel {
  // Shown. Every launch, every reload, and - see below - every return to the
  // app. The only thing that makes this false is a hiker's own tap.
  const [alertsShown, setAlertsShown] = useState(true)

  const handleToggleAlerts = useCallback(() => {
    setAlertsShown((current) => !current)
  }, [])

  useEffect(() => {
    const onVisible = () => {
      // Set unconditionally rather than guarded on the current value: React
      // bails out of a re-render when a `useState` is handed what it already
      // holds, so the ordinary case - coming back to an app that never had
      // alerts hidden - costs nothing, and the guard would only be a second
      // place for this rule to be got wrong.
      if (document.visibilityState === 'visible') setAlertsShown(true)
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  const mapScreen = useMemo<AlertLayerMapProps>(
    () => ({ alertsShown, onToggleAlerts: handleToggleAlerts }),
    [alertsShown, handleToggleAlerts],
  )

  return { mapScreen }
}
