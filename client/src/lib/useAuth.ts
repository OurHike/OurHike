// The signed-in account, as React state.
//
// Starts null and stays null for the whole first paint. That is the honest
// default rather than a placeholder: signed out is the state the entire app
// is built to work in, so rendering it while the stored session is read costs
// nothing a hiker would notice, and gates no screen behind a spinner.
//
// Sign-in completes by returning from a provider redirect - a fresh page load,
// not a resolved promise in the tab that left. The subscription is what
// notices that, which is why this hook listens rather than only asking once.

import { useEffect, useState } from 'react'
import { currentAccount, subscribeToAccount, type Account } from './auth'

export function useAccount(): Account | null {
  const [account, setAccount] = useState<Account | null>(null)

  useEffect(() => {
    let live = true
    let reported = false

    // Ordering matters: subscribe first, then ask. Doing it the other way
    // round leaves a window between the answer and the subscription in which
    // a session restored from a redirect would be missed, and the hiker would
    // look signed out until something else happened to re-render.
    const unsubscribe = subscribeToAccount((next) => {
      reported = true
      if (live) setAccount(next)
    })

    void currentAccount().then((restored) => {
      // The subscription's answer always wins once it has given one, and
      // that includes when it said "nobody". Treating only a non-null
      // subscription result as newer would let a slow read of stored session
      // put a hiker back to looking signed in straight after signing out.
      if (live && !reported) setAccount(restored)
    })

    return () => {
      live = false
      unsubscribe()
    }
  }, [])

  return account
}
