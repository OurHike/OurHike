// Vite's types, named here because tsconfig.e2e.json compiles this file for
// e2e/support/dataPreflight.ts without them, and this file reads
// import.meta.env (configuredBase, below).
/// <reference types="vite/client" />

/**
 * Which published dataset this build reads. Two parts (pipeline/ELT.md,
 * "Versions and channels"; the maintainer, 2026-10-16).
 *
 * THE POINTER. Each data environment's `channels.json`, in the bucket beside
 * its `latest.json`, names per schema version the release folder its phones
 * read: `{"ua": {"v1": "<id>"}}`. That bucket copy is the only copy; no file
 * in this repository names it. pipeline/channels.py moves it:
 * build-reference.yml's last job moves UA's once a monthly build has passed
 * every check it runs, and promote-data.yml, behind the production
 * environment's reviewer, copies a release UA was tested on into production
 * and moves production's. Each move is appended to `channels_history.json`
 * beside it. A phone reads the pointer on a first run before it renders
 * (lib/dataChannel.ts's firstRunRelease) and takes the release it names; on
 * every later launch it reads it again (readDataChannel), and a newer release
 * becomes the phone's from the NEXT launch, never mid-session, with the hiker
 * asked before data they hold is replaced (lib/dataRefresh.ts; #919 — A
 * published data fix reaches no phone that already has the app, because the
 * download asks whether there is trail data and never which).
 *
 * THE FLOOR, `DATA_RELEASE` below: the known-good release a session reads
 * when it has no verified pointer entry and cannot get one - a first run
 * that is offline, or whose pointer is missing, malformed, slow or names a
 * release that does not resolve, or a phone whose record was forgotten
 * because its release's own manifest answered 404. So it moves only when the
 * data format does (a new DATA_SCHEMA_VERSION), or when the folder it names
 * stops being one a phone can use; moving the data a phone reads is the
 * pointer's job, not a commit's.
 *
 * IT MUST RESOLVE IN EVERY ENVIRONMENT A BUILD DEPLOYS AGAINST: UA is a
 * prefix in the same bucket with its own `releases/` tree, so the two sets of
 * ids drift (measured 2026-09-09: production 14 releases, UA 31, 10 in
 * common). `pages.yml` and `ua.yml` each assert this folder's manifest
 * resolves against their OWN base and fits a launch (check 22) before
 * deploying, and the same of the release their uploaded pointer names, so a
 * wrong floor costs a red deploy rather than a hiker's map.
 *
 * WHY 2026-10-10-2. build-reference.yml run 2 (38044889854) staged it in UA
 * on 2026-10-10, from the dbt path, green in every job with all 41 parity
 * families matching. Measured 2026-10-15 against its folder: 4,449
 * artifacts; its network sketch 2,710,574 bytes, under
 * lib/artifactBudget.ts's LAUNCH_ARTIFACT_BUDGET_BYTES, where 2026-10-03-2's
 * was 41,216,145 and every UA phone declined it (review 5528343443 on
 * PR #1805); check 22 passes, the largest file a phone fetches whole being
 * trail_graph_cell_n37w108.json at 29,993,542; check 2 finds 32 of the 35
 * keys config.ts declares, the other three the background tiers packages.ts
 * withdraws; check 20 finds every cell its four cell indexes name; and all
 * 199 hikes in suggested_hikes.json have their detail. Production held no
 * release at all when this was written (measured 2026-10-09, after the
 * bucket move of 2026-10-02 copied nothing), so pages.yml refuses a
 * production deploy of this floor until promote-data.yml has copied it there.
 *
 * WHY A RELEASE ID IS WHAT IT IS: lib/releases.next_release_id mints
 * `<date>` and `<date>-2`, `-3` for later publishes the same day, each folder
 * complete and immutable, so the folder to name is the LAST one of a day's
 * publishes, not the first (measured 2026-09-16: `releases/2026-09-16/` held a
 * fresh basemap and the previous release's copies of everything else).
 * `pipeline/tests/test_release_pin_contract.py` asserts this id is shaped
 * like one a publish could write; only the deploy guards check it exists.
 *
 * @see pipeline/DATA_RELEASES.md §4, pipeline/R2_LAYOUT.md
 */
export const DATA_RELEASE = '2026-10-10-2'

/**
 * The schema version of the phone files this build reads: the
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
 *
 * DELETED, BOTH, in one case only: lib/dataChannel.ts's readDataChannel
 * forgets a recorded release whose own `releases/<id>/manifest.json` answers
 * exactly 404, so the next launch reads DATA_RELEASE.
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
 * The release this session reads: the pointer entry this phone last verified,
 * or, with none, the compiled floor - until a first run's pointer read
 * replaces the floor (adoptFirstRunRelease), which can only happen before the
 * first release URL is built. After that it never changes until the page
 * reloads.
 *
 * NEVER MID-SESSION, and that is the safety property rather than a
 * simplification. Every release URL the app builds comes from this one value,
 * and an artifact is verified against its release's manifest; a session that
 * moved release between building the two would reject bytes it fetched
 * correctly, or hold half of one release and half of another. So a pointer
 * read on any launch but a first run is recorded for the next one
 * (lib/dataChannel.ts's readDataChannel).
 *
 * `let`, not `const`, for adoptFirstRunRelease alone. An ES module export is
 * a live binding, so every importer reads the adopted value.
 */
export let SESSION_RELEASE: string = SESSION_RECORD?.release ?? DATA_RELEASE

/** Whether SESSION_RELEASE came from the pointer rather than the compiled
 *  floor. lib/dataRefresh.ts reads it: a session on the floor must not
 *  offer that floor over data a pointer brought (see availableRefresh). */
export let SESSION_FOLLOWS_POINTER: boolean = SESSION_RECORD !== null

/** Set once this session's release has been used to build a URL, or the app
 *  has started rendering (sealSessionRelease); adoptFirstRunRelease refuses
 *  from then on. */
let sealed = false

/** No first-run adoption after this. main.tsx calls it as it renders. */
export function sealSessionRelease(): void {
  sealed = true
}

/**
 * How long a first run waits for the pointer, and the release manifest it
 * names, before it renders on the compiled floor instead.
 *
 * @unvalidated - picked, not measured. The wait is a blank screen on a first
 * launch only, so it is short beside CHANNEL_READ_TIMEOUT_MS's 20 seconds
 * (lib/dataChannel.ts): a phone that installed the app a moment ago reached
 * the network, and two small reads either answer in well under this or are
 * on a captive portal that will never answer. What would settle it: first-run
 * timings for the pointer and manifest reads from real phones at real
 * trailheads, which nobody has collected.
 */
export const FIRST_RUN_READ_TIMEOUT_MS = 4_000

/**
 * Make `record` this session's release, on a first run only: true when it
 * did. Refused once anything has built a release URL or the app has started
 * rendering, once the session already follows a pointer, and for a record
 * that does not read as this build's (asRecord). lib/dataChannel.ts's
 * firstRunRelease calls it after the record is written and its release's
 * manifest has resolved.
 */
export function adoptFirstRunRelease(record: ChannelRecord): boolean {
  if (sealed || SESSION_FOLLOWS_POINTER || asRecord(record) === null) return false
  SESSION_RELEASE = record.release
  SESSION_FOLLOWS_POINTER = true
  RELEASE_MANIFEST_PATH = `releases/${record.release}/manifest.json`
  return true
}

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
// reaches a phone on its next fetch - and a list inside a release folder
// would reach nobody until a new release was staged and pointed at, which
// is a monthly build per episode.
const ROOT_SCOPED_PREFIXES = ['conditions/', 'photos/', 'archive/', 'podcasts/'] as const
const ROOT_SCOPED_KEYS = ['latest.json'] as const

/** Whether `key` is served from the pinned release folder. */
export function isReleaseScoped(key: string): boolean {
  if ((ROOT_SCOPED_KEYS as readonly string[]).includes(key)) return false
  return !ROOT_SCOPED_PREFIXES.some((prefix) => key.startsWith(prefix))
}

/** Where `key` lives, relative to the bucket base: under this session's
 *  release folder (SESSION_RELEASE), or at the root. Seals the session's
 *  release: a URL built from it is one a later adoption would contradict. */
export function releasePath(key: string): string {
  sealed = true
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
 * offers a newer build from the launch that follows the pointer to it. Fixed
 * once sealed, because the session's release never moves after that.
 */
export let RELEASE_MANIFEST_PATH = `releases/${SESSION_RELEASE}/manifest.json`

/** RELEASE_MANIFEST_PATH, for building a URL: seals the session's release as
 *  releasePath does. */
export function releaseManifestPath(): string {
  sealed = true
  return RELEASE_MANIFEST_PATH
}
