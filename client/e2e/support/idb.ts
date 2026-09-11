// The IndexedDB-seed-and-reload idiom features/FLOW_TESTING.md asks every
// spec to use, factored once. client/scripts/screenshot.mjs's skipFirstRun()
// and client/preview-shots/fixtures/longHike.mjs's seedLongHike() each write
// this same open/upgrade/put dance inline for the one key they need; this is
// that dance, for specs that need more than one.

import type { Page } from '@playwright/test'

/** idb-keyval's default store - every key client/src/lib writes
 *  (preferences, hiker mode, taken trail, trips) lives here. */
const DATABASE = 'keyval-store'
const STORE = 'keyval'

/**
 * Register a write into idb-keyval's store, to run on the page's *next*
 * navigation.
 *
 * `page.addInitScript`, not `page.evaluate` - a fresh Playwright page starts
 * on `about:blank`, an opaque origin IndexedDB refuses outright ("access to
 * the Indexed Database API is denied in this context", measured against
 * this exact call before this fix), so there is no real origin to write
 * into until the app has navigated at least once. An init script sidesteps
 * the ordering problem instead of requiring a throwaway navigation first:
 * it is registered now, and Playwright runs it - awaiting what it returns -
 * before the page's own scripts start, on every future navigation. That is
 * exactly the guarantee a seed-before-the-app-boots needs, and it is the
 * same mechanism client/scripts/screenshot.mjs's `skipFirstRun()` already
 * uses for its one key; this is it for as many as a spec needs.
 *
 * Left registered rather than one-shot: the entries close over this call's
 * arguments, so a later reload re-seeds the same values instead of losing
 * them, which is idempotent for every seed this suite writes.
 *
 * `database`/`store` travel through as data, not as a closure: the callback
 * below runs inside the browser, which cannot see this module's own
 * top-level bindings.
 *
 * Synchronous within the callback - every `put()` is issued before any of
 * them resolve - so the transaction cannot commit early between entries,
 * which is why a caller with several keys should pass them here together
 * rather than calling this once per key.
 */
export async function writeIDBEntries(
  page: Page,
  entries: ReadonlyArray<readonly [key: string, value: unknown]>,
): Promise<void> {
  if (entries.length === 0) return
  await page.addInitScript(
    ({ database, store, rows }) =>
      new Promise<void>((done, fail) => {
        const open = indexedDB.open(database)
        open.onupgradeneeded = () => open.result.createObjectStore(store)
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const objectStore = open.result
            .transaction(store, 'readwrite')
            .objectStore(store)
          let remaining = rows.length
          for (const [key, value] of rows) {
            const write = objectStore.put(value, key)
            write.onsuccess = () => {
              remaining -= 1
              if (remaining === 0) done()
            }
            write.onerror = () => fail(write.error)
          }
        }
      }),
    { database: DATABASE, store: STORE, rows: entries },
  )
}
