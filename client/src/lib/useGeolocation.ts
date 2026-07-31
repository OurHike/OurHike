// The GPS watch behind the position readout.
//
// `enableHighAccuracy` is on deliberately, despite the battery cost. Under
// tree cover a coarse fix can be hundreds of feet out, and a mile marker that
// is wrong by a quarter mile at a junction is worse than no mile marker - the
// whole point of the number is deciding which way to turn.
//
// A denied permission is a settled state, not an error to retry. Watching
// anyway would prompt repeatedly and drain the battery for a fix that will
// never arrive, so `denied` simply stops.

import { useEffect, useState } from 'react'
import type { LonLat } from './trailPosition'

export type GeolocationState =
  | { status: 'unsupported' }
  | { status: 'idle' }
  | { status: 'locating' }
  | { status: 'denied' }
  | { status: 'unavailable' }
  | { status: 'located'; at: LonLat; accuracyFeet: number; fixedAt: Date }

const METERS_TO_FEET = 3.28084

export function useGeolocation(enabled: boolean): GeolocationState {
  const [state, setState] = useState<GeolocationState>({ status: 'idle' })

  useEffect(() => {
    if (!enabled) {
      setState({ status: 'idle' })
      return
    }
    if (!('geolocation' in navigator)) {
      setState({ status: 'unsupported' })
      return
    }

    setState({ status: 'locating' })

    const id = navigator.geolocation.watchPosition(
      (position) =>
        setState({
          status: 'located',
          at: { lon: position.coords.longitude, lat: position.coords.latitude },
          accuracyFeet: position.coords.accuracy * METERS_TO_FEET,
          fixedAt: new Date(position.timestamp),
        }),
      (error) =>
        setState(
          error.code === error.PERMISSION_DENIED
            ? { status: 'denied' }
            : { status: 'unavailable' },
        ),
      { enableHighAccuracy: true, maximumAge: 5_000, timeout: 30_000 },
    )

    return () => navigator.geolocation.clearWatch(id)
  }, [enabled])

  return state
}
