// Whether this install may offer a paid choice at all (#1876).
//
// THE WEBSITE ALWAYS MAY; A STORE APP ONLY ON A US ACCOUNT. The maintainer,
// 2026-10-27: "$0-only outside the US", with the check built in this pull
// request, and on a non-US account no ask at all (frame A, followups mock).
// Both stores key their rule to the store account's country, not to where
// the hiker stands:
//   - Apple, App Review Guidelines 3.1.1(a): "In all other storefronts,
//     except for the United States storefront, where this prohibition does
//     not apply, apps and their metadata may not include buttons, external
//     links, or other calls to action that direct customers to purchasing
//     mechanisms other than in-app purchase" (read 2026-10-27);
//   - Google, Play Console Help on its US policies: the external-payment
//     allowances are for "users in the United States" (read 2026-10-27; the
//     page does not say how that is decided, and Play Billing's country is
//     the one signal an app has).
// So a hiker with a US account hiking in Canada may pay from the app, and
// one with a German account standing on the A.T. may not.
//
// FAILS CLOSED. No answer, an error, or no answer within `ASK_TIMEOUT_MS`
// reads as "not the United States": a store app that wrongly offers a paid
// choice risks the listing, and one that wrongly withholds it costs a hiker
// a trip to the website.
//
// The native halves are ios/App/App/StorefrontPlugin.swift and
// android/app/src/main/java/org/ourhike/app/StorefrontPlugin.java. CI
// compiles both (build-shells.yml); NOTHING HAS RUN THEM ON A PHONE.

import { useEffect, useState } from 'react'
import { Capacitor, registerPlugin } from '@capacitor/core'

export interface StorefrontLike {
  getCountry(): Promise<{ country?: string }>
}

// @unvalidated: five seconds is a guess at "long enough for StoreKit or Play
// Billing to answer on one bar". A slower answer only means no ask this
// launch, which is the safe way to be wrong.
export const ASK_TIMEOUT_MS = 5_000

/** Apple answers ISO 3166-1 alpha-3 ("USA"), Google alpha-2 ("US"). */
export function isUnitedStates(country: string | null | undefined): boolean {
  const code = (country ?? '').trim().toUpperCase()
  return code === 'US' || code === 'USA'
}

let registered: StorefrontLike | null = null
function lazyPlugin(): StorefrontLike {
  // Lazily, as lib/backgroundGeolocation.ts does: on the web the proxy
  // throws the moment it is called, and the web never calls it.
  registered ??= registerPlugin<StorefrontLike>('Storefront')
  return registered
}

/** Whether a paid choice may be offered here. Never rejects. */
export async function paidChoiceAllowed(
  native: boolean = Capacitor.isNativePlatform(),
  plugin: () => StorefrontLike = lazyPlugin,
  timeoutMs: number = ASK_TIMEOUT_MS,
): Promise<boolean> {
  if (!native) return true
  const timeout = new Promise<boolean>((resolve) =>
    setTimeout(() => resolve(false), timeoutMs),
  )
  const asked = plugin()
    .getCountry()
    .then(({ country }) => isUnitedStates(country))
    .catch(() => false)
  return Promise.race([asked, timeout])
}

// One answer per launch, shared: the gate and the Your support page each
// asked separately, and a store that answered one in time and timed out on
// the other left "Choose an amount" showing and doing nothing (the fourth
// #1885 review).
let launchAnswer: Promise<boolean> | null = null

/** `paidChoiceAllowed` as state: null while the store is being asked. */
export function usePaidChoiceAllowed(
  native: boolean = Capacitor.isNativePlatform(),
): boolean | null {
  const [allowed, setAllowed] = useState<boolean | null>(native ? null : true)
  useEffect(() => {
    if (!native) return
    let live = true
    launchAnswer ??= paidChoiceAllowed(native)
    void launchAnswer.then((answer) => {
      if (live) setAllowed(answer)
    })
    return () => {
      live = false
    }
  }, [native])
  return allowed
}
