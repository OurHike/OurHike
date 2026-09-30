// A backend and an auth project that exist only as `page.route` handlers -
// for the `@backend` tests, which run against a second build of the app that
// has an API base and a Supabase project baked into it.
//
// WHY A SECOND BUILD. Everything else in e2e/ runs against a build with no
// `VITE_API_BASE_URL` and no `VITE_SUPABASE_URL`, which is a real state (a
// phone before anybody configured a backend) and the one lib/api.ts's
// `API_CONFIGURED` and lib/supabase.ts's `AUTH_CONFIGURED` answer "no" to. In
// that build the outbox never tries to send (lib/outboxSync.ts returns before
// flushing), sign-in never reaches the code step, and the org console can only
// be driven through the demo organization, whose data never touches the
// network. #1643 - The org console's permission matrix skips ten endpoints,
// and the position mark and outbox drain have no end-to-end test - named all
// three as undriven. Vite inlines both variables at build time, so the only
// way to have them set is a build that set them: playwright.config.ts serves
// one on BACKEND_PORT to the `phone-backend` project.
//
// SAME ORIGIN, ON PURPOSE. Both bases point at paths on the build's own
// origin, so every request the app makes to "the backend" or "Supabase" is a
// same-origin request that `page.route` answers. A cross-origin base would
// bring CORS preflights into every test, which is a thing the real deployment
// has to get right and not a thing these tests are about.
//
// NOTHING UNANSWERED REACHES A SERVER. The server under these paths is `vite
// preview`, whose SPA fallback answers any path with index.html and a 200 -
// the exact "cheerful 200 with an HTML body" lib/api.ts's own comment warns
// is indistinguishable from success. So `stubBackend` answers every path
// under both prefixes, and anything a test did not name gets a 503.

import type { BrowserContext, Page, Request } from '@playwright/test'
import { setSignal } from './signal'

/** A port of its own, beside the hermetic build's 5173/4173, and the same
 *  in both worlds so a trace from CI names the port a local run used. */
export const BACKEND_PORT = process.env.CI ? 4174 : 5174
export const BACKEND_ORIGIN = `http://localhost:${BACKEND_PORT}`

export const API_PREFIX = '/__e2e-api'
export const SUPABASE_PREFIX = '/__e2e-supabase'

/** What the backend-shaped build is built with. The anon key is not a key:
 *  nothing here checks it, and supabase-js only requires one to be present. */
export const BACKEND_BUILD_ENV = {
  VITE_API_BASE_URL: `${BACKEND_ORIGIN}${API_PREFIX}`,
  VITE_SUPABASE_URL: `${BACKEND_ORIGIN}${SUPABASE_PREFIX}`,
  VITE_SUPABASE_ANON_KEY: 'e2e-anon-key',
}

export interface Recorded {
  method: string
  /** The path under the API or Supabase prefix, with its query string. */
  path: string
  body: unknown
}

export interface Reply {
  status: number
  body?: unknown
}

/** `METHOD /path` (no query string), and the reply it gets. */
export type Routes = Record<string, Reply | ((request: Request) => Reply)>

function parsed(request: Request): unknown {
  const text = request.postData()
  if (text === null) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

/**
 * What `stubBackend` hands back: every request that arrived, in order, and
 * whether the stub is currently behaving as if there were no signal.
 */
export interface Backend {
  seen: Recorded[]
  offline: boolean
}

/**
 * Answer every request under both prefixes, and record each one.
 *
 * `routes` is keyed `METHOD /path`, where the path is what follows the
 * prefix (`POST /reports`, `POST /auth/v1/otp`). `seen` is the list of
 * everything that arrived, in order, for a test to count - which is the
 * point: "sent exactly once" is a claim about this list, not about a screen.
 *
 * A REQUEST MADE WITH NO SIGNAL IS REFUSED HERE, NOT BY THE BROWSER. Measured
 * 2026-09-23 in the sandbox's Chromium: with `context.setOffline(true)` in
 * force, a `fetch` the page makes still reaches `page.route` and is fulfilled
 * - the first run of the app-failure test below recorded a POST "sent" from a
 * phone with no signal. So the stub keeps its own `offline` flag, set by
 * `setBackendSignal`, and aborts with `internetdisconnected` while it is up,
 * which is the error an unrouted request gets from an offline context.
 */
export async function stubBackend(page: Page, routes: Routes = {}): Promise<Backend> {
  const backend: Backend = { seen: [], offline: false }
  for (const prefix of [API_PREFIX, SUPABASE_PREFIX]) {
    await page.route(`**${prefix}/**`, async (route) => {
      if (backend.offline) {
        await route.abort('internetdisconnected')
        return
      }
      const request = route.request()
      const url = new URL(request.url())
      const path = url.pathname.slice(url.pathname.indexOf(prefix) + prefix.length)
      backend.seen.push({
        method: request.method(),
        path: `${path}${url.search}`,
        body: parsed(request),
      })

      const entry = routes[`${request.method()} ${path}`]
      const reply: Reply =
        entry === undefined
          ? { status: 503, body: { detail: 'not stubbed by this test' } }
          : typeof entry === 'function'
            ? entry(request)
            : entry
      await route.fulfill({
        status: reply.status,
        contentType: 'application/json',
        body: JSON.stringify(reply.body ?? {}),
      })
    })
  }
  return backend
}

/**
 * support/signal.ts's `setSignal`, with the stub told first.
 *
 * FIRST IN BOTH DIRECTIONS. Going offline, so nothing slips through between
 * the flip and the flag. Coming back, because the `online` event is what
 * starts lib/outboxSync.ts's flush, and a flush that met a stub still
 * refusing would fail, leave the item queued, and wait for a next change
 * that never comes.
 */
export async function setBackendSignal(
  page: Page,
  context: BrowserContext,
  backend: Backend,
  { on }: { on: boolean },
): Promise<void> {
  backend.offline = !on
  await setSignal(page, context, { on })
}

/** The requests a test cares about, by method and path prefix. */
export function sent(
  seen: readonly Recorded[],
  method: string,
  path: string,
): Recorded[] {
  return seen.filter((entry) => entry.method === method && entry.path.startsWith(path))
}

/** An unsigned JWT with the three claims anything might read. Nothing here
 *  verifies it - the backend that would is a route handler. */
function fakeJwt(sub: string, email: string): string {
  const encode = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString('base64url')
  return [
    encode({ alg: 'HS256', typ: 'JWT' }),
    encode({ sub, email, role: 'authenticated', aud: 'authenticated', exp: 4102444800 }),
    'e2e-signature',
  ].join('.')
}

/** The session supabase-js stores and reads back, for one invented person.
 *  `expires_at` is 2100-01-01, so the client never tries to refresh it. */
export function fakeSession(email = 'hiker@example.org') {
  const id = '00000000-0000-4000-8000-00000000e2e0'
  return {
    access_token: fakeJwt(id, email),
    refresh_token: 'e2e-refresh-token',
    token_type: 'bearer',
    expires_in: 3600,
    expires_at: 4102444800,
    user: {
      id,
      aud: 'authenticated',
      role: 'authenticated',
      email,
      app_metadata: { provider: 'email', providers: ['email'] },
      user_metadata: {},
      created_at: '2026-09-01T00:00:00Z',
    },
  }
}

/**
 * Signed in before the app boots - supabase-js's own storage key for this
 * origin (`sb-<first label of the Supabase host>-auth-token`, which for
 * `localhost` is `sb-localhost-auth-token`), holding a session that does not
 * expire. The app restores it at startup exactly as it restores a real one.
 */
export async function seedSession(
  page: Page,
  email = 'hiker@example.org',
): Promise<void> {
  await page.addInitScript(
    ([key, value]) => {
      window.localStorage.setItem(key, value)
    },
    ['sb-localhost-auth-token', JSON.stringify(fakeSession(email))] as const,
  )
}
