// React binding for dataSaver.ts, shaped exactly like useOnline.ts: read the
// value once, subscribe to the event that changes it, unsubscribe on teardown.
//
// The subscription is what makes this a hook rather than a one-off read.
// `saveData` is not fixed for the life of a session - a hiker who notices the
// map eating data can turn Data Saver on from the notification shade without
// leaving the app, and the map should follow within the same breath rather
// than at the next cold start.

import { useEffect, useState } from 'react'
import { dataSaverConnection, dataSaverEnabled } from './dataSaver'

export function useDataSaver(): boolean {
  const [saveData, setSaveData] = useState(dataSaverEnabled)

  useEffect(() => {
    const connection = dataSaverConnection()
    // Absent on iOS, where the Network Information API does not exist. The
    // initial read above already answered false; there is simply nothing to
    // subscribe to, which is a supported state rather than a failure.
    if (connection?.addEventListener === undefined) return

    const update = () => setSaveData(dataSaverEnabled())
    connection.addEventListener('change', update)
    return () => connection.removeEventListener?.('change', update)
  }, [])

  return saveData
}
