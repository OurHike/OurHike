// A stand-in `navigator.geolocation` a spec drives by hand: a fix arrives
// when the spec says so, and goes away when the spec says so, the same way in
// every engine.
//
// WHY NOT PLAYWRIGHT'S OWN EMULATION, which support/seed.ts's seedFixAtMile()
// uses and which is the right tool for "the phone has a fix". Taking the fix
// AWAY is where the engines part. `context.setGeolocation(null)` is a
// different call in each: Chromium sends CDP's
// `Emulation.setGeolocationOverride` with no coordinates, which that
// protocol documents as "emulates position unavailable", and an active watch
// receives POSITION_UNAVAILABLE - measured 2026-09-23 in the sandbox's
// Chromium. WebKit sends Playwright's own `Playwright.setGeolocationOverride`
// with the geolocation left undefined (playwright-core 1.63's
// `setGeolocation`, `geolocation ? {...} : void 0`), which clears the override
// rather than reporting an error. CI's WebKit then gave the page a fix it had
// not been handed: on #1645's run 35927130277, `phone-webkit` could not find
// "No GPS fix" at all right after boot with `setGeolocation(null)` in force,
// and chrome/StatusStrip.tsx drops that flag only when App.tsx's
// `gps.status === 'located'`. Where that position came from inside WebKit is
// reasoned, not measured - this sandbox has no WebKit to run. What is
// established is that the null call does not mean "no fix" there, so a test
// built on it tests the engine's emulation, not the app.
//
// WHAT THIS REPLACES, AND WHAT IT DOES NOT. Only the object the app reads -
// lib/useGeolocation.ts calls `navigator.geolocation.watchPosition` and
// `clearWatch`, and lib/useGpsTrace.ts `getCurrentPosition` - so everything
// from the watch's callbacks inward is the app's real code, in the real
// bundle, in the real browser. What is not exercised is the platform's
// position source, which no emulation exercises either.

import type { Page } from '@playwright/test'
import { latOfMile } from './seed'

interface ShimControl {
  fix: (latitude: number, longitude: number) => void
  lose: () => void
}

type ShimmedWindow = Window & { __ourhikeGeolocation?: ShimControl }

/**
 * Install the stand-in before the app boots. With nothing delivered yet, a
 * watch sits waiting - the app's "Looking for GPS…" - exactly as a phone that
 * has not found the sky yet does.
 */
export async function installGeolocationShim(page: Page): Promise<void> {
  await page.addInitScript(() => {
    type Success = (position: GeolocationPosition) => void
    type Failure = (error: GeolocationPositionError) => void
    const watchers = new Map<number, { success: Success; failure?: Failure }>()
    let nextId = 1
    let last: GeolocationPosition | null = null

    const position = (latitude: number, longitude: number): GeolocationPosition =>
      ({
        coords: {
          latitude,
          longitude,
          accuracy: 10,
          altitude: null,
          altitudeAccuracy: null,
          heading: null,
          speed: null,
        },
        timestamp: Date.now(),
      }) as unknown as GeolocationPosition

    const unavailable = (): GeolocationPositionError =>
      ({
        code: 2,
        message: 'Position unavailable',
        PERMISSION_DENIED: 1,
        POSITION_UNAVAILABLE: 2,
        TIMEOUT: 3,
      }) as GeolocationPositionError

    const shim = {
      watchPosition(success: Success, failure?: Failure) {
        const id = nextId++
        watchers.set(id, { success, failure })
        if (last !== null) {
          const current = last
          setTimeout(() => success(current), 0)
        }
        return id
      },
      clearWatch(id: number) {
        watchers.delete(id)
      },
      getCurrentPosition(success: Success, failure?: Failure) {
        const current = last
        setTimeout(
          () => (current !== null ? success(current) : failure?.(unavailable())),
          0,
        )
      },
    }

    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      get: () => shim,
    })
    ;(window as ShimmedWindow).__ourhikeGeolocation = {
      fix(latitude, longitude) {
        last = position(latitude, longitude)
        for (const { success } of watchers.values()) success(last)
      },
      lose() {
        last = null
        for (const { failure } of watchers.values()) failure?.(unavailable())
      },
    }
  })
}

/** Hand every live watch a fix at a mile of the synthetic centerline -
 *  the same `latOfMile` seedFixAtMile() uses, so "mile 5" means one place. */
export async function shimFixAtMile(
  page: Page,
  mile: number,
  longitude = -77,
): Promise<void> {
  await page.evaluate(
    ([latitude, lon]) =>
      (window as ShimmedWindow).__ourhikeGeolocation?.fix(latitude, lon),
    [latOfMile(mile), longitude] as const,
  )
}

/** Lose the fix: every live watch gets POSITION_UNAVAILABLE, which is what a
 *  phone under a cliff gets, and not PERMISSION_DENIED, which is a setting. */
export async function shimLoseFix(page: Page): Promise<void> {
  await page.evaluate(() => (window as ShimmedWindow).__ourhikeGeolocation?.lose())
}
