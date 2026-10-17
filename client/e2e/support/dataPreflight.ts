// Runs once before the data-backed suite and answers one question: did the
// bucket answer?
//
// WHY THIS EXISTS. `e2e/data/` reads a published release, so a failure there
// has two possible causes that look identical from a CI log - the build broke,
// or the bucket did. That ambiguity is the whole cost of pointing a test suite
// at a network, and it was named before the decision was taken (the
// maintainer's call, 2026-09-11). This is what keeps it small: one fetch
// before any test, so an outage is reported as an outage in one line rather
// than as thirty assertions failing one at a time and a reviewer working out
// which kind of red it is.
//
// IT CHECKS THE RELEASE THE APP WILL READ, not `latest`. Every test starts a
// fresh browser, so every test is a first run, and a first run takes the
// release its environment's channels.json names when that release resolves,
// and otherwise lib/dataRelease.ts's compiled DATA_RELEASE (the floor). This
// works that answer out the same way, once, and hands it to the specs as
// FLOW_DATA_RELEASE (Playwright passes a global setup's environment variables
// on to its workers). A release folder is immutable once written, so this both
// proves the bucket is reachable and pins which bytes the run is about,
// whether or not UA has a pointer yet.
//
// One difference is left, and named: the app gives up on the pointer after
// FIRST_RUN_READ_TIMEOUT_MS and reads the floor, where this waits longer. A
// test whose browser hit that deadline reads the floor while a spec asking
// releaseArtifactUrl reads the pointer's release; both resolve.

import {
  DATA_RELEASE,
  DATA_SCHEMA_VERSION,
  environmentOf,
  RELEASE_ID,
} from '../../src/lib/dataRelease'

/** The data base the app under test is built against, or null. */
function dataBase(): string | null {
  const origin = process.env.FLOW_DATA_ORIGIN ?? ''
  if (origin !== '') return `${origin.replace(/\/+$/, '')}/data/environments/ua`
  const base = process.env.VITE_DATA_BASE_URL ?? ''
  return base === '' ? null : base.replace(/\/+$/, '')
}

/** The release a first run of the app under test takes: FLOW_DATA_RELEASE
 *  once the preflight has set it, DATA_RELEASE before. */
function sessionRelease(): string {
  const chosen = process.env.FLOW_DATA_RELEASE ?? ''
  return RELEASE_ID.test(chosen) ? chosen : DATA_RELEASE
}

/** The release channels.json at `base` names for this build, when its
 *  manifest answers 200; otherwise null, and the app reads the floor. */
async function pointedRelease(base: string): Promise<string | null> {
  try {
    const response = await fetch(`${base}/channels.json`, {
      signal: AbortSignal.timeout(30_000),
      cache: 'no-store',
    })
    if (!response.ok) return null
    const document = (await response.json()) as Record<string, Record<string, unknown>>
    const entry = document?.[environmentOf(base)]?.[DATA_SCHEMA_VERSION]
    if (typeof entry !== 'string' || !RELEASE_ID.test(entry)) return null
    const manifest = await fetch(`${base}/releases/${entry}/manifest.json`, {
      method: 'HEAD',
      signal: AbortSignal.timeout(30_000),
    })
    return manifest.ok ? entry : null
  } catch {
    return null
  }
}

/**
 * Where the app under test reads its data from, in the two shapes this suite
 * runs in: the bucket directly (CI), or through the sandbox's same-origin
 * proxy (playwright.config.ts's BYO_ORIGIN comment).
 *
 * Exported because a spec occasionally needs a published artifact ITSELF
 * rather than what the app did with it — e2e/data/newerData.spec.ts reads the
 * release's tombstones to find a retired waypoint id, because writing one down
 * would be pinning a release rather than the app. One home for the URL shape,
 * so a spec and this preflight cannot come to disagree about where the bucket
 * is.
 */
export function releaseArtifactUrl(name: string): string | null {
  const base = dataBase()
  return base === null ? null : `${base}/releases/${sessionRelease()}/${name}`
}

/**
 * The pointer record (lib/dataRelease.ts's ChannelRecord) a phone that already
 * follows this run's pointer holds, or null when channels.json named no
 * release that resolves and the app reads the floor.
 *
 * For a spec that seeds a download record. lib/dataChannel.ts's
 * firstRunRelease treats any download record as "not a first run", so such a
 * phone reads the compiled floor on its first launch and records the pointer
 * for the next one: two launches, two releases, two different manifest
 * versions. A spec that compares what one launch offered with what the next
 * one does needs both launches on one release, and this record is how a
 * phone gets there before the first one.
 */
export function followedPointerRecord(): {
  release: string
  schema: string
  environment: string
  at: number
} | null {
  const base = dataBase()
  const chosen = process.env.FLOW_DATA_RELEASE ?? ''
  if (base === null || !RELEASE_ID.test(chosen)) return null
  return {
    release: chosen,
    schema: DATA_SCHEMA_VERSION,
    environment: environmentOf(base),
    at: 1_700_000_000_000,
  }
}

function manifestUrl(): string | null {
  return releaseArtifactUrl('manifest.json')
}

export default async function preflight(): Promise<void> {
  const base = dataBase()
  const pointed = base === null ? null : await pointedRelease(base)
  if (pointed !== null) process.env.FLOW_DATA_RELEASE = pointed
  console.log(
    pointed === null
      ? `[flow-data] no channels.json entry resolves, so the app reads the compiled floor, ${DATA_RELEASE}`
      : `[flow-data] channels.json names ${pointed}, which a first run takes over the floor, ${DATA_RELEASE}`,
  )
  const release = sessionRelease()
  const url = manifestUrl()
  if (url === null) {
    throw new Error(
      'FLOW_DATA=1 with no data source configured. Set VITE_DATA_BASE_URL to the ' +
        'bucket this build should read, or FLOW_DATA_ORIGIN to a server already ' +
        'serving the app and proxying it. See playwright.config.ts.',
    )
  }

  // A generous window and one attempt. A retry here would only make an outage
  // take longer to report, and this is not the place to be patient: the tests
  // after it each have their own timeout, and what this step exists to do is
  // fail FAST and legibly when the data is not there.
  let response: Response
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(30_000) })
  } catch (error) {
    throw new Error(
      `The bucket did not answer, so this run says nothing about the build. ` +
        `Asked ${url} and got: ${error instanceof Error ? error.message : String(error)}. ` +
        `The hermetic suite (the 'flow' job) is the one to read for whether the ` +
        `client is broken.`,
    )
  }

  if (!response.ok) {
    throw new Error(
      `The bucket answered ${response.status} for release ${release}, so this run ` +
        `says nothing about the build. Asked ${url}. Either that release is not in ` +
        `this environment - which is the case pages.yml and ua.yml each guard for ` +
        `their own base - or the bucket is having a bad day.`,
    )
  }

  // Read it rather than trusting the status: a bucket that serves an error
  // page with a 200 is a thing that happens, and "the manifest parses and
  // names artifacts" is the claim this step is actually making.
  const manifest = (await response.json()) as { artifacts?: Record<string, unknown> }
  const count = Object.keys(manifest.artifacts ?? {}).length
  if (count === 0) {
    throw new Error(
      `Release ${release}'s manifest parsed but names no artifacts, so there is ` +
        `nothing for these tests to read. Asked ${url}.`,
    )
  }
  console.log(`[flow-data] ${release} answered with ${count} artifacts — ${url}`)
}
