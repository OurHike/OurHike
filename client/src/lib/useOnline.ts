// Whether the phone thinks it has a connection.
//
// `navigator.onLine` is the browser's own answer and it is optimistic - it
// reports a captive portal or a bar of signal that carries no data as online.
// Everything that matters is written to survive being wrong about this
// (lib/outbox.ts queues regardless), so this drives what the status strip
// says, never whether a write is attempted.

import { useEffect, useState } from 'react'

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])

  return online
}
