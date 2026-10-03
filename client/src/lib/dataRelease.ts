// Vite's types, named here because tsconfig.e2e.json compiles this file for
// e2e/support/dataPreflight.ts without them, and this file reads
// import.meta.env (configuredBase, below).
/// <reference types="vite/client" />

/**
 * Which published dataset this build reads, and since decision 44 the answer
 * has two parts (pipeline/ELT.md, "Versions and channels (decision 44), as
 * stage 4 builds them").
 *
 * THE POINTER. A committed `channels.json` at the repository root names, per
 * data environment and per schema version, the release folder a phone reads:
 * `{"production": {"v1": "<id>"}, "ua": {"v1": "<id>"}}`. Phones read the
 * copy at the data base, beside `latest.json`, never this commit's, and only
 * the release train puts it there, by running `publish.py --channels`
 * (RELEASING.md §10: no workflow runs that yet). Moving an entry is a reviewed
 * commit, so the 2026-09-09 reason for a committed pin below still holds: the
 * dataset changes only with a commit, a review and history. What changes is
 * that the commit no longer needs an app release. lib/dataChannel.ts's
 * `readDataChannel` reads the uploaded copy; what it names becomes this
 * phone's release from its NEXT launch, never mid-session.
 *
 * THE COMPILED FALLBACK, `DATA_RELEASE` below, is what a session reads when
 * this phone has never recorded a pointer it could verify: a first run, a
 * phone that has never reached `channels.json`, or a record that did not
 * survive. It is kept for exactly that, and `pages.yml` and `ua.yml` still
 * assert it resolves, because a first run that cannot reach the pointer reads
 * it.
 *
 * WHY A COMMITTED CONSTANT rather than a repository variable, which is the
 * one question DATA_RELEASES.md left open and the maintainer settled on
 * 2026-09-09: a variable would let the dataset every hiker receives change
 * with no commit, no review and no history. A constant puts the release in
 * `git log`, makes it revertable with `git revert`, and puts it structurally
 * out of reach of every pipeline workflow - they all run `contents: read`.
 * `channels.json` is the same argument made for a file a phone can read
 * without an app release.
 *
 * WHAT MERGING IT DOES, amended from §4's first draft by RELEASING.md: the
 * merge deploys to UA, and a tagged release is what puts the new dataset in
 * front of hikers. So this constant selects a dataset; promoting it still
 * gets a real client fetching it through a real browser first.
 *
 * THE ID MUST EXIST IN BOTH DATA ENVIRONMENTS, which §4 does not say and
 * which is a consequence of features/DATA_ENVIRONMENTS.md arriving after it.
 * UA is a prefix in the same bucket with its own `releases/` tree, written by
 * its own publishes, so the two sets drift - measured 2026-09-09, production
 * held 14 releases and UA 31, with only 10 ids in common. A pin naming an id
 * one environment lacks fails that environment's deploy.
 *
 * Nothing here has to remember that: `pages.yml` and `ua.yml` each assert
 * this folder's manifest resolves against their OWN base before deploying, so
 * a wrong pin costs a red deploy rather than a hiker's map. They assert the
 * same of `channels.json`'s entry for this build's schema version, and that
 * the copy uploaded at that base, where one is, names the same release.
 *
 * 2026-09-24-2 IS v1.3.2's DATA, minted by that release train on 2026-09-24.
 * Production's -1 is the vector data (both DEM variants had published flat
 * before it, so its folder carries them) and -2 the basemap: the last folder
 * of the day again, for the reason below. UA held no 2026-09-24 folder at all
 * when production minted these - its ids are its own sequence - so the train
 * ran two UA publishes that day to mint UA's -1 and -2 before this line moved,
 * rather than pin an id one environment lacked. Production's folder also
 * carries the elevation and profile cells now: its vector publish ran with
 * `include_elevation: true`, which the 2026-09-16-4 entry below names as the
 * one thing that would close that gap.
 *
 * 2026-09-16-4 WAS IN BOTH ENVIRONMENTS, minted by the v1.3.1 release train.
 * The pin was `2026-09-14` - v1.3.0's data - until that line moved, and the
 * previous entry's point still holds: nothing chooses a release id.
 * `lib/releases.next_release_id` returns `date.today()`, and no publishing
 * workflow takes an id input.
 *
 * WHY THE `-4` SUFFIX, which is the part that surprised the session that cut
 * this release. A release folder is IMMUTABLE, so `next_release_id` reads the
 * ids already used and a second publish on one day gets `-2` rather than
 * overwriting the morning's. Four production publishes on 2026-09-16 therefore
 * minted four folders, each complete because `_stage_release` copies EVERY
 * artifact from its flat key rather than a delta:
 *
 *   -1  basemap          -3  vector data (trails, POIs, hikes, graph)
 *   -2  dem_light        -4  dem canonical
 *
 * So the pinnable folder is the LAST one of the day, not the first, and a
 * session that pins `releases/<today>/` before every family has published
 * ships a folder holding whatever had landed by the morning. Measured on
 * 2026-09-16: `releases/2026-09-16/` held a fresh basemap and byte-identical
 * copies of v1.3.0's trails, POIs, hikes, graph and both DEMs.
 *
 * WHY PINNING IT IS SAFE, measured 2026-09-16 rather than assumed. Both
 * environments return 200 for `releases/2026-09-16-4/manifest.json`, and
 * production's folder holds **2,158 artifacts** against UA's 3,166. That
 * difference is NOT empty in the direction the 2026-09-14 entry above called
 * the one that matters, and it is worth naming rather than rounding to safe:
 *
 *   505  trail_graph_elevation_cell_*.json   UA only
 *   505  trail_graph_profile_cell_*.json     UA only
 *     1  suggested_hikes_detail_*.json       UA only (201 against 200)
 *
 * The 1,010 elevation and profile cells are the STATUS QUO rather than a
 * regression: production carried zero of them at `2026-09-14` too, the
 * elevation leg is opt-in and this release's publishes ran with
 * `include_elevation: false`. lineClimb.ts answers `none` for a line with no
 * climb figures, which is the state its own tests and
 * `preview-shots/long-path-line-sheet.mjs` already describe. The one extra
 * hike detail is two independent builds minutes apart; each environment's
 * `suggested_hikes.json` references its own folder's details, so neither
 * client asks for a file its own release lacks.
 *
 * WHAT WOULD MAKE THAT SENTENCE STRONGER, and does not exist: a production
 * publish with `include_elevation: true`, which would cost ~40 minutes and is
 * the only way the two environments hold the same set. Nobody has decided
 * whether production should carry elevation at all - it never has.
 *
 * WHAT WOULD HAVE CAUGHT THE MISMATCH EARLIER, and does not exist:
 * `pipeline/tests/test_release_pin_contract.py` asserts this id is *shaped*
 * like one a publish could write, never that either environment actually
 * carries it. Only `pages.yml`'s pre-deploy guard does that, which is late -
 * it is a red deploy rather than a red test. @unvalidated whether a test
 * could check it honestly at all: a suite that reads the live bucket would
 * fail on a network blip and would couple `pytest` to R2's availability,
 * which is why the guard sits where it does. What would settle it: deciding
 * whether the release train should assert the pin resolves before it tags,
 * which is cheaper than either and is nobody's file yet.
 *
 * THE PIN MOVED TO 2026-10-03 ahead of production, on the branch of
 * PR #1805 — dlt → dbt re-platform as one go/no-go change. UA's refill
 * (publish-vector-data.yml run 37097659154) replaced UA's tree, so
 * `2026-09-24-2` no longer resolves there and client-tests.yml's flow-data
 * job read a 404. Measured 2026-10-03: UA's `releases/2026-10-03/manifest.json`
 * answers 200 with 2,875 artifacts, none of them elevation or profile cells
 * (the refill ran without the elevation leg, as every publish before it did);
 * production answers 404. So pages.yml's guard refuses a production deploy
 * until the release train promotes the folder, the order DATA_RELEASES.md §4
 * asks for, and pr-preview.yml previews UA for this pin (#1374).
 *
 * THEN TO 2026-10-03-2, the same day, because 2026-10-03 had no climb and
 * flow-data's nine elevation tests failed on it. publish-vector-data.yml run
 * 37114537637 ran with include_elevation and staged 2026-10-03-2: 4,436
 * artifacts in UA, 1,561 of them elevation or profile files, among them
 * elevation_profile.json and trail_graph_elevation.json (Measured 2026-10-03).
 *
 * @see pipeline/DATA_RELEASES.md §4, pipeline/R2_LAYOUT.md
 */
export const DATA_RELEASE = '2026-10-03-2'

/**
 * The schema version of the phone files this build reads (decision 44): the
 * entry it takes from `channels.json`. `v1` is today's shape; a build that
 * reads a v2 changes this, and only then does it read `v2`'s entry.
 */
export const DATA_SCHEMA_VERSION = 'v1'

/** The pointer's key at the data base, beside `latest.json` and outside every
 *  release folder for the same reason: it says which version is current. */
export const CHANNELS_KEY = 'channels.json'

/**
 * Where the last pointer entry this phone read and verified is kept: the
 * record in IndexedDB, and a mirror of it under the same name in localStorage.
 *
 * WHY A MIRROR. A session's release has to be known the moment the first
 * release URL is built, synchronously, and IndexedDB answers a tick later.
 * The shell already solves that shape this way: features/LAUNCH_BUDGET.md §4.3,
 * "mirrored to `localStorage` for a synchronous read ... with IndexedDB
 * staying the record and the mirror correcting itself a tick later if the two
 * disagree". Here the correction is for the next launch, because a session
 * that changed release mid-way would verify one release's bytes against
 * another's manifest.
 */
export const CHANNEL_RECORD_KEY = 'ourhike:data-channel'

/** One verified pointer entry, as it is kept. */
export interface ChannelRecord {
  release: string
  /** DATA_SCHEMA_VERSION when it was read: a build of another schema version
   *  ignores the record rather than read a release of the wrong shape. */
  schema: string
  /** The data environment it was read for, from the base URL. */
  environment: string
  /** When it was read and verified, epoch ms. */
  at: number
}

/** lib/r2_keys.RELEASE_ID_PATTERN, the ids lib/releases.next_release_id
 *  writes: `2026-09-24`, and `2026-09-24-2` for a second the same day.
 *  Exported, as BASE_ENVIRONMENT, mirrorStore, asRecord and readMirror below
 *  are, for lib/dataChannel.ts and nothing else. */
export const RELEASE_ID = /^\d{4}-\d{2}-\d{2}(-\d+)?$/

/**
 * Whether release id `a` was minted before `b`, in the order
 * lib/releases.next_release_id mints them: by date, then by the same-day
 * suffix, where the unsuffixed id is the first of its day and `-2` the
 * second. The suffix is compared as a number, so `2026-09-24-10` comes after
 * `2026-09-24-2`, which a string compare gets backwards. False when either is
 * not an id, because then neither is known to be older.
 */
export function releaseSortsBefore(a: string, b: string): boolean {
  const first = RELEASE_ID.exec(a)
  const second = RELEASE_ID.exec(b)
  if (first === null || second === null) return false
  const [dayA, dayB] = [a.slice(0, 10), b.slice(0, 10)]
  if (dayA !== dayB) return dayA < dayB
  const nth = (suffix: string | undefined) =>
    suffix === undefined ? 1 : Number(suffix.slice(1))
  return nth(first[1]) < nth(second[1])
}

/**
 * The data environment a base URL serves. A non-production environment's
 * tree is `environments/<name>/` in the bucket (pipeline/lib/data_env.py's
 * `prefix_for`), and ua.yml builds UA against exactly that; production is the
 * bucket root. A base that is neither, such as a field-test server, reads as
 * production's, and its own `channels.json` (or its absence) is what answers.
 */
export function environmentOf(base: string): string {
  const match = /\/environments\/([a-z][a-z0-9_]*)\/*$/.exec(base)
  return match ? match[1] : 'production'
}

/**
 * The data base this build was given, normalised as config.ts normalises the
 * same variable. Read here rather than imported, because config.ts imports
 * this module. Spelled `import.meta.env.VITE_DATA_BASE_URL` exactly, which is
 * what Vite replaces at build time and vitest's stubEnv reaches; inside a
 * guard, because e2e/support/dataPreflight.ts loads this file in Node under
 * Playwright, where `import.meta.env` does not exist.
 */
function configuredBase(): string {
  try {
    return String(import.meta.env.VITE_DATA_BASE_URL ?? '').replace(/\/+$/, '')
  } catch {
    return ''
  }
}

export const BASE_ENVIRONMENT = environmentOf(configuredBase())

/** Guarded because merely reading `window.localStorage` throws in a hardened
 *  embedder, before any get or set is attempted (lib/cameraMemory.ts). */
export function mirrorStore(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** A stored record that convinces, or null. Validated field by field, on
 *  conditionsCache's principle: a stored value is no more trustworthy than a
 *  fetched one, and a malformed id here would be a release folder that 404s. */
export function asRecord(value: unknown): ChannelRecord | null {
  if (typeof value !== 'object' || value === null) return null
  const { release, schema, environment, at } = value as Record<string, unknown>
  if (typeof release !== 'string' || !RELEASE_ID.test(release)) return null
  if (schema !== DATA_SCHEMA_VERSION || environment !== BASE_ENVIRONMENT) return null
  if (typeof at !== 'number' || !Number.isFinite(at)) return null
  return { release, schema, environment, at }
}

export function readMirror(): ChannelRecord | null {
  try {
    const raw = mirrorStore()?.getItem(CHANNEL_RECORD_KEY)
    if (raw === null || raw === undefined) return null
    return asRecord(JSON.parse(raw))
  } catch {
    return null
  }
}

const SESSION_RECORD = readMirror()

/**
 * The release this session reads, decided once when this module loads and
 * never changed until the page reloads: the pointer entry this phone last
 * verified, or the compiled fallback when it has none.
 *
 * NEVER MID-SESSION, and that is the safety property rather than a
 * simplification. Every release URL the app builds comes from this one value,
 * and an artifact is verified against its release's manifest; a session that
 * moved release between building the two would reject bytes it fetched
 * correctly, or hold half of one release and half of another. So a pointer
 * read this launch is recorded for the next one (lib/dataChannel.ts's
 * readDataChannel).
 */
export const SESSION_RELEASE: string = SESSION_RECORD?.release ?? DATA_RELEASE

/** Whether SESSION_RELEASE came from the pointer rather than the compiled
 *  fallback. lib/dataRefresh.ts reads it: a session on the fallback must not
 *  offer that fallback over data a pointer brought (see availableRefresh). */
export const SESSION_FOLLOWS_POINTER: boolean = SESSION_RECORD !== null

/**
 * Keys that stay at the bucket root rather than moving into the release
 * folder - the exclusion `lib/releases.is_release_artifact` is written as, in
 * the one other place that has to agree with it.
 *
 * AN EXCLUSION, NOT AN ALLOWLIST, and for the reason the Python says: a new
 * artifact is release-scoped by default, so adding one cannot silently leave
 * it un-versioned. Three things are outside, each for its own reason:
 *
 *   conditions/  Safety data - closures, serious warnings, field notes - is
 *                rewritten in place on an hourly clock, and a closure that
 *                has reopened must STOP being served. An immutable folder
 *                cannot express that; it could only add a second answer
 *                beside the first. `is_release_artifact` excludes exactly
 *                this prefix, and 0 of the 262 artifacts in the live
 *                releases/2026-09-08/ manifest are under it.
 *
 *   photos/      Content-addressed: the key IS the sha256 of the bytes, so
 *                the immutability a release folder provides is already there
 *                and a copy per release would be pure duplication.
 *                publish.py uploads these separately from `artifacts`, and 0
 *                of that same 262 are under this prefix either.
 *
 *   latest.json  The pointer itself. Versioning the thing that says which
 *                version is current is a loop.
 *
 * @see pipeline/lib/releases.py, pipeline/publish.py
 */
// `archive/` joined the root on 2026-09-17 (#1574): one-time snapshots of
// third-party data a person writes by dispatching a workflow, never a
// release build - pipeline/lib/r2_keys.py's declaration of the prefix is the
// design record. Versioning one under a release would make a snapshot that
// cannot be rebuilt look like an artifact that can.
// `podcasts/` joined on 2026-09-26 (#1683): the episodes picked for each hike,
// written by pipeline/export_podcasts.py on a person's dispatch. The
// maintainer chose a LIVE list - an episode added to the reviewed file
// reaches a phone on its next fetch - and a list inside the pinned folder
// would reach nobody until this file's DATA_RELEASE moved, which is an app
// release per episode.
const ROOT_SCOPED_PREFIXES = ['conditions/', 'photos/', 'archive/', 'podcasts/'] as const
const ROOT_SCOPED_KEYS = ['latest.json'] as const

/** Whether `key` is served from the pinned release folder. */
export function isReleaseScoped(key: string): boolean {
  if ((ROOT_SCOPED_KEYS as readonly string[]).includes(key)) return false
  return !ROOT_SCOPED_PREFIXES.some((prefix) => key.startsWith(prefix))
}

/** Where `key` lives, relative to the bucket base: under this session's
 *  release folder (SESSION_RELEASE), or at the root. */
export function releasePath(key: string): string {
  return isReleaseScoped(key) ? `releases/${SESSION_RELEASE}/${key}` : key
}

/**
 * The manifest describing the pinned release's bytes.
 *
 * NOT the root `latest.json`, and that distinction is the pin's correctness
 * rather than tidiness. `latest.json` describes the FLAT keys, which move on
 * every publish; this build's bytes do not. Read the root manifest from a
 * pinned client and the two agree only until the next publish - after which
 * every artifact whose bytes changed fails the hash `trailData.ts` holds it
 * to, and the app rejects data it downloaded correctly.
 *
 * Measured 2026-09-09, before this landed: all 262 artifacts in
 * `releases/2026-09-08/manifest.json` hashed identically to root
 * `latest.json`, because that release WAS the most recent publish. The bug
 * was latent, not absent, and the next production publish is what would have
 * fired it.
 *
 * The release folder's own manifest carries the same `artifacts` shape, so
 * only the URL changes.
 *
 * SINCE DECISION 44 it is the session's release (SESSION_RELEASE), which is
 * what "lib/dataRefresh.ts reads the pointed-to build's manifest" comes to:
 * #919's update check reads this through lib/dataManifest.ts, so the row
 * offers a newer build from the launch that follows the pointer to it. A
 * constant still, because the session's release never moves.
 */
export const RELEASE_MANIFEST_PATH = `releases/${SESSION_RELEASE}/manifest.json`
