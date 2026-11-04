// A data bucket that exists only as `page.route` handlers - for the `@bucket`
// tests, which run against a third build of the app that has a data base URL
// baked into it.
//
// WHY A THIRD BUILD. The hermetic build has no `VITE_DATA_BASE_URL`, which is
// a real state (a phone before anybody configured a bucket) and the one
// lib/config.ts's `DATA_CONFIGURED` answers "no" to. In that build
// lib/publishedConditions.ts's `readPublished` returns before any request, so
// conditions/notices.json, hazard_areas.json and trail_closures.json are
// never asked for and a `page.route` on them has nothing to answer - which is
// why the planned-hike notices, the hazard areas and the club closures could
// not be driven in `e2e/` even after the cutover (#1880) published the files.
// The preview-shot recipes route the same files in and work because the
// preview build carries a bucket. Vite inlines the variable at build time, so
// the only way to have it set is a build that set it: playwright.config.ts
// serves one on BUCKET_PORT to the `phone-bucket` project, the same shape
// e2e/support/backend.ts gave the API (#1643).
//
// SAME ORIGIN, ON PURPOSE, as the backend stub: the base points at a path on
// the build's own origin, so every artifact the app asks the bucket for is a
// same-origin request that `page.route` answers, and CORS never enters into
// it.
//
// NOTHING UNANSWERED REACHES THE SERVER. `vite preview`'s SPA fallback answers
// any path with index.html and a 200 - the "cheerful 200 with an HTML body"
// lib/api.ts warns about, which `readPublished` would try to parse as JSON.
// So `stubBucket` answers every path under the prefix, and anything a test
// did not name gets a 404: the state a bucket is in for a file nobody
// published, which every reader already handles (a kept copy, or null).
//
// WHAT THE APP ASKS SUCH A BUCKET FOR AT LAUNCH, all answered 404 unless a
// test says otherwise: channels.json (so the pinned DATA_RELEASE is read),
// the release manifest, trails_overview.geojson (the preload vite.config.ts
// emits for a configured bucket), the trail line, stewards.json, and every
// conditions file. A test that needs the phone to hold a release seeds one
// (preview-shots/fixtures/stewards.mjs's `seedStewards`, which also routes
// stewards.json after this stub - a later route wins, so its answer stands).

import type { Page, Request } from '@playwright/test'

/** A port of its own, beside the hermetic build's 5173/4173 and the
 *  backend build's 5174/4174, and the same in both worlds so a trace from CI
 *  names the port a local run used. */
export const BUCKET_PORT = process.env.CI ? 4175 : 5175
export const BUCKET_ORIGIN = `http://localhost:${BUCKET_PORT}`

export const BUCKET_PREFIX = '/__e2e-bucket'

/** What the bucket-shaped build is built with. */
export const BUCKET_BUILD_ENV = {
  VITE_DATA_BASE_URL: `${BUCKET_ORIGIN}${BUCKET_PREFIX}`,
}

export interface BucketRequest {
  method: string
  /** The artifact's own key (`conditions/notices.json`, `stewards.json`),
   *  with the release folder lib/config.ts's `dataUrl` puts in front of a
   *  release artifact taken off, so a test names a file the way
   *  lib/config.ts and the pipeline name it. */
  key: string
}

export interface BucketReply {
  status: number
  /** JSON-encoded on the way out. Absent on a 404 or a HEAD. */
  body?: unknown
}

/**
 * What a key answers with: the document itself, or a function for a test that
 * needs to hold an answer back, count the asks, or answer differently each
 * time (closureSurfaces.spec.ts's superseded download).
 */
export type BucketFile = object | ((request: Request) => BucketReply | Promise<BucketReply>)

export type BucketFiles = Record<string, BucketFile>

/** What `stubBucket` hands back: every request that arrived, in order. */
export interface Bucket {
  seen: BucketRequest[]
}

/** The artifact key a bucket URL asks for. */
export function bucketKey(url: URL): string {
  const path = url.pathname.slice(url.pathname.indexOf(BUCKET_PREFIX) + BUCKET_PREFIX.length)
  return path.replace(/^\/(releases\/[^/]+\/)?/, '')
}

/**
 * Answer every request under the bucket prefix, and record each one.
 *
 * `files` is keyed by artifact key. A HEAD is answered with the key's status
 * and no body, which is what lib/publishedNotices.ts's `noticesListed` asks
 * with. An answer the page has given up on - a download aborted by
 * lib/useConditions.ts's effect cleanup (#1892) - has nowhere to go, and the
 * fulfil's own error is swallowed here: that is the case a holding handler
 * exists to produce, not a failure of the stub.
 */
export async function stubBucket(page: Page, files: BucketFiles = {}): Promise<Bucket> {
  const bucket: Bucket = { seen: [] }
  await page.route(`**${BUCKET_PREFIX}/**`, async (route) => {
    const request = route.request()
    const key = bucketKey(new URL(request.url()))
    bucket.seen.push({ method: request.method(), key })

    const file = files[key]
    const reply: BucketReply =
      file === undefined
        ? { status: 404 }
        : typeof file === 'function'
          ? await file(request)
          : { status: 200, body: file }
    const body =
      request.method() === 'HEAD' || reply.body === undefined ? '' : JSON.stringify(reply.body)
    try {
      await route.fulfill({ status: reply.status, contentType: 'application/json', body })
    } catch {
      // The page aborted the request before this answer: nothing to deliver.
    }
  })
  return bucket
}

/** The requests for one key, by method. */
export function asked(seen: readonly BucketRequest[], method: string, key: string): BucketRequest[] {
  return seen.filter((entry) => entry.method === method && entry.key === key)
}
