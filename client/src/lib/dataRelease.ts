/**
 * Which published dataset this build reads.
 *
 * Bumping the constant below IS the release (DATA_RELEASES.md §4). Nothing
 * else selects a dataset: no workflow input, no repository variable, no
 * scheduled job. A pipeline run can write `releases/<id>/` all it likes and
 * not one hiker sees it until this line changes and that change is merged.
 *
 * WHY A COMMITTED CONSTANT rather than a repository variable, which is the
 * one question DATA_RELEASES.md left open and the maintainer settled on
 * 2026-09-09: a variable would let the dataset every hiker receives change
 * with no commit, no review and no history. A constant puts the release in
 * `git log`, makes it revertable with `git revert`, and puts it structurally
 * out of reach of every pipeline workflow - they all run `contents: read`.
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
 * a wrong pin costs a red deploy rather than a hiker's map.
 *
 * @see pipeline/DATA_RELEASES.md §4, pipeline/R2_LAYOUT.md
 */
export const DATA_RELEASE = '2026-09-08'

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
const ROOT_SCOPED_PREFIXES = ['conditions/', 'photos/'] as const
const ROOT_SCOPED_KEYS = ['latest.json'] as const

/** Whether `key` is served from the pinned release folder. */
export function isReleaseScoped(key: string): boolean {
  if ((ROOT_SCOPED_KEYS as readonly string[]).includes(key)) return false
  return !ROOT_SCOPED_PREFIXES.some((prefix) => key.startsWith(prefix))
}

/** Where `key` lives, relative to the bucket base. */
export function releasePath(key: string): string {
  return isReleaseScoped(key) ? `releases/${DATA_RELEASE}/${key}` : key
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
 */
export const RELEASE_MANIFEST_PATH = `releases/${DATA_RELEASE}/manifest.json`
