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
 * 2026-09-16-4 IS IN BOTH ENVIRONMENTS, minted by the v1.3.1 release train.
 * The pin was `2026-09-14` - v1.3.0's data - until this line moved, and the
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
 * @see pipeline/DATA_RELEASES.md §4, pipeline/R2_LAYOUT.md
 */
export const DATA_RELEASE = '2026-09-16-4'

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
