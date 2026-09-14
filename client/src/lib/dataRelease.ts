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
 * 2026-09-14 IS IN PRODUCTION, and this line moving is the sentence the last
 * one promised. The pin was `2026-09-10` from #1374 until the v1.3.0 release
 * train ran its production leg, and that entry said what would happen: the
 * release `publish-vector-data.yml` minted "must match this line or this line
 * moves again". It did not match, because nothing chooses a release id -
 * `lib/releases.next_release_id` returns `date.today()`, and
 * `publish-vector-data.yml` takes no id input, so a production publish on the
 * 14th could only ever write `releases/2026-09-14/`. The id is an outcome of
 * when the build ran, never a thing a branch can ask for.
 *
 * WHY PINNING IT IS SAFE, measured 2026-09-14 rather than assumed, because the
 * client was validated against UA's `2026-09-10` and this is a different
 * folder: production's `2026-09-14` holds **1,958 artifacts against UA
 * 2026-09-10's 1,943, and the set difference in the direction that matters is
 * empty** - there is no artifact UA carried that production does not. The 15
 * extra are production's own (`background*.pmtiles` and six southern
 * `n38`/`n39` cells). Both files #1372 added resolve: `places.json` and
 * `trail_graph_cells.json` are 200 at
 * `https://data.ourhike.org/releases/2026-09-14/`.
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
 * @see pipeline/DATA_RELEASES.md §4, pipeline/R2_LAYOUT.md
 */
export const DATA_RELEASE = '2026-09-14'

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
