// Cutting the signal, and waiting until the app has actually noticed.
//
// WHY THIS IS NOT JUST `context.setOffline(true)`. That call flips the
// BROWSER CONTEXT. The app reads something else: `lib/useOnline.ts` seeds
// itself from `navigator.onLine` when it first renders and afterwards
// changes only when a `window` `offline` event fires. `App.tsx` calls it
// once and threads the answer down as a prop, so the value the screens read
// was decided at boot - and a test that serves the page first (it has to;
// an offline context cannot load the app at all) has already seeded `true`
// by the time it cuts the connection.
//
// So between `setOffline` returning and the screen re-rendering there is an
// event in flight, and nothing in the call guarantees it has landed. On
// WebKit it sometimes had not: `firstRunStates.spec.ts:245` failed on its
// first attempt AND its retry with `element(s) not found`, twice on one
// branch, while passing on the two heads between - the signature of a race
// rather than a regression. The screen had rendered the ONLINE sentence,
// which is the honest thing for it to do when nobody has told it otherwise.
//
// A longer `toBeVisible` window would not have saved it. The state was
// wrong, not late: with the event lost there is no later moment at which
// the sentence appears. So this waits on the event itself, observed from
// inside the page, which is the thing `useOnline` is listening for.

import type { BrowserContext, Page } from '@playwright/test'

/** A flag this module sets on `window`, read back through `waitForFunction`. */
const LANDED = '__ourhikeSignalEvent'

type Marked = Window & { [LANDED]?: 'online' | 'offline' }

/**
 * Cut or restore the signal, returning once the page's own `window` has
 * received the matching event.
 *
 * The listener is installed BEFORE the context flips, because an event
 * already delivered cannot be waited for afterwards. `useOnline`'s own
 * listener was registered when `App` mounted, so both receive the same
 * event and React has been told by the time this resolves.
 */
export async function setSignal(
  page: Page,
  context: BrowserContext,
  { on }: { on: boolean },
): Promise<void> {
  const want = on ? 'online' : 'offline'

  await page.evaluate((event) => {
    const marked = window as Marked
    delete marked.__ourhikeSignalEvent
    window.addEventListener(
      event,
      () => {
        marked.__ourhikeSignalEvent = event as 'online' | 'offline'
      },
      { once: true },
    )
  }, want)

  await context.setOffline(!on)

  await page.waitForFunction(
    (event) => (window as Marked).__ourhikeSignalEvent === event,
    want,
  )
}
