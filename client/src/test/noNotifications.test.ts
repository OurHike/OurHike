import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

// THE CLAIM ON THE PRIVACY POLICY, ENFORCED (#1398).
//
// site/public/Privacy/index.html tells a hiker, in bold:
//
//   > OurHike sends no notifications at all.
//
// That is a stronger and rarer thing to be able to say than "exactly one",
// and this file is what makes it checkable rather than a promise. The page
// says a check exists; this is the check.
//
// WHY IT HAD TO BE REWRITTEN RATHER THAN RESTORED. The policy used to claim
// "exactly one kind of notification: the off-trail alert", vouched for by
// "a single function allowed to send a notification, and an automated check
// [that] reads the whole codebase and fails the build if anything else tries
// to". All three of those were true when written and none survived: the
// wrong-way feature was removed in #93/#308 (features/HIKER_SAFETY.md §5),
// `client/src/lib/push.ts` went with it, and so did `push.test.ts` - the
// suite that did the scanning. A privacy policy overstating what an app does
// with a hiker's attention and position, vouching for it with a test that had
// been deleted, is the exact shape CLAUDE.md's "say what a claim rests on"
// section exists to prevent, arrived at sideways rather than by anyone
// asserting something false.
//
// So the guarantee comes back with the sentence it guarantees, one grade
// stronger, because the app it describes got simpler rather than more
// complicated: there is no allowed sender to make an exception for.
//
// WHAT THIS CATCHES: a module reaching for the Notification API, the Push
// API, or a service worker's `showNotification`. That is the whole surface a
// web app has for putting something on a hiker's lock screen.
//
// WHAT IT DOES NOT CATCH, said plainly so nobody trusts it further than it
// goes: a native notification raised from the Capacitor shells rather than
// from this bundle (`client/ios/`, `client/android/`) - neither is TypeScript
// and neither is scanned here - and anything reached through a string built
// at runtime. The first is the real gap and is worth knowing about: if a
// shell ever gains a notification plugin, this test stays green and the
// policy becomes wrong again. `@unvalidated` in that one direction; what
// would settle it is the same scan over the two shells' own sources, which
// nobody has written because neither has ever carried a plugin.

// A FOURTH COPY OF THE TREE WALK, and that is a known cost rather than an
// oversight. `unitDisplay.test.ts`, `themeTokens.test.ts` and
// `mapChromeContrast.test.ts` each carry the same recursive readdir with the
// same `.tsx?` filter and the same exclusions, so the next change to what
// counts as shipped source - a new top-level directory, `.mts`, a generated
// file to skip - has to be found in four places, and a copy that drifts
// silently NARROWS a guard rather than failing. Worth extracting; not worth
// extracting here, where it would mean editing three test files this change
// has no other reason to touch. `test/repoFile.ts` is not the home either -
// it reads files OUTSIDE the client tree, which is a different job.
const ROOT = resolve(process.cwd(), 'src')

/** Every TypeScript module the app ships, tests and this directory aside. */
function sourceFiles(dir = ROOT): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return sourceFiles(full)
    if (!/\.tsx?$/.test(full)) return []
    if (/\.test\.tsx?$/.test(full)) return []
    if (full.startsWith(join(ROOT, 'test'))) return []
    return [full]
  })
}

/** Every way a web app can put something on a hiker's lock screen. */
const SENDERS: ReadonlyArray<{ pattern: RegExp; what: string }> = [
  { pattern: /\bnew\s+Notification\s*\(/, what: 'the Notification constructor' },
  {
    pattern: /\bNotification\s*\.\s*requestPermission\b/,
    what: 'Notification.requestPermission',
  },
  { pattern: /\bshowNotification\s*\(/, what: "a service worker's showNotification" },
  { pattern: /\bpushManager\b/, what: 'the Push API' },
  { pattern: /\bregisterProtocolHandler\s*\(/, what: 'registerProtocolHandler' },
]

describe('the app sends no notifications, which is what the privacy policy says', () => {
  it('has no module that can raise one', () => {
    const offenders: string[] = []
    for (const file of sourceFiles()) {
      const source = readFileSync(file, 'utf8')
      for (const { pattern, what } of SENDERS) {
        if (pattern.test(source)) {
          offenders.push(`${relative(ROOT, file)} reaches for ${what}`)
        }
      }
    }

    // If this fails, the fix is NOT to add an exception. site/public/Privacy
    // tells hikers this cannot happen, so either the feature goes or the page
    // changes in the same pull request - and a page that has to be weakened
    // is a product decision, not a test failure to route around.
    expect(offenders).toEqual([])
  })

  it('reads enough of the tree for that to mean something', () => {
    // A scanner that silently matched nothing would pass identically. The
    // floor is deliberately far below the real count (209 modules under
    // lib/ alone at the time of writing) so an ordinary refactor cannot
    // trip it, while a walk that broke and returned [] would.
    expect(sourceFiles().length).toBeGreaterThan(100)
  })
})
