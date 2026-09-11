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
// IT CHECKS THE PINNED RELEASE, not `latest`. `lib/dataRelease.ts`'s
// DATA_RELEASE is the id every artifact resolves under, and a release folder
// is immutable once written - so this both proves the bucket is reachable and
// pins which bytes the run is about.

import { DATA_RELEASE } from '../../src/lib/dataRelease'

/** Where the app under test reads its data from, in the two shapes this
 *  suite runs in: the bucket directly (CI), or through the sandbox's
 *  same-origin proxy (playwright.config.ts's BYO_ORIGIN comment). */
function manifestUrl(): string | null {
  const origin = process.env.FLOW_DATA_ORIGIN ?? ''
  if (origin !== '') {
    return `${origin.replace(/\/+$/, '')}/data/environments/ua/releases/${DATA_RELEASE}/manifest.json`
  }
  const base = process.env.VITE_DATA_BASE_URL ?? ''
  if (base === '') return null
  return `${base.replace(/\/+$/, '')}/releases/${DATA_RELEASE}/manifest.json`
}

export default async function preflight(): Promise<void> {
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
      `The bucket answered ${response.status} for the pinned release, so this run ` +
        `says nothing about the build. Asked ${url}. Either the release id in ` +
        `lib/dataRelease.ts (${DATA_RELEASE}) is not in this environment - which is ` +
        `the case pages.yml and ua.yml each guard for their own base - or the ` +
        `bucket is having a bad day.`,
    )
  }

  // Read it rather than trusting the status: a bucket that serves an error
  // page with a 200 is a thing that happens, and "the manifest parses and
  // names artifacts" is the claim this step is actually making.
  const manifest = (await response.json()) as { artifacts?: Record<string, unknown> }
  const count = Object.keys(manifest.artifacts ?? {}).length
  if (count === 0) {
    throw new Error(
      `The pinned release's manifest parsed but names no artifacts, so there is ` +
        `nothing for these tests to read. Asked ${url}.`,
    )
  }
  console.log(`[flow-data] ${DATA_RELEASE} answered with ${count} artifacts — ${url}`)
}
