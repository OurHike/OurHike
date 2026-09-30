// The 34 trail markers the badge and the line sheet can draw, and the only
// module that names them. 32 are a steward's own and are keyed both ways
// below; the other two are lib/trails.ts registry trails that only the badge
// needs by slug - see STEWARD_MARKS_BY_SLUG for why the two maps differ.
//
// WHY THIS IS ITS OWN FILE AND NOT lib/trails.ts. App.tsx imports TRAILS, so
// every row of that table is parsed before the first frame, and a marker a
// hiker sees only after tapping a line has no business there. So this module
// is reached through `import()` from chrome/LineSheet.tsx and lands in its
// own chunk.
//
// THE NUMBER THAT ARGUMENT WAS FIRST MADE WITH WAS AGAINST A BUDGET THAT NO
// LONGER EXISTS, and the correction is here rather than swapped silently
// because the figure reads like a forced move and is not one. Putting these
// names and URLs in lib/trails.ts measured 257,725 bytes of eager JavaScript
// where the same build without them passed at 253,337 - both real, both
// measured 2026-09-30. They were then compared against 256,000, which is
// 250 KB and was the budget until #1577 RAISED IT TO 300 KB on 2026-09-18.
// features/LAUNCH_BUDGET.md §3 has carried 300 since. Measured on this head:
// 256,493 bytes compressed against the real budget of 307,200, so BOTH
// arrangements fit and the `import()` is a choice about what belongs in the
// launch path rather than the only way under a line. It is still the right
// choice for the reason in the paragraph above. `npm run build` prints the
// live number and the live budget together; read it rather than this comment.
//
// WHAT THE ROWS REST ON. Each marker is the steward's own, shipped by default
// on the maintainer's decision of 2026-09-30, with its source URL, basis and
// scope in pipeline/sources.json's `org_marks.trail_marks` and its claim
// state alongside. A steward who asks for theirs out gets the row set to
// `withdrawn`, and pipeline/tests/test_org_marks.py fails while the file is
// still here.
//
// KEYED BY THE TRAIL'S NAME, FOLDED, and matched exactly - never a substring,
// for lib/trails.ts's own reason: "Long Path Link Trail" is a different trail
// and must not wear the Long Path's mark.
//
// @unvalidated HOW MANY OF THESE A HIKER REACHES. The keys are each steward's
// own spelling of their trail. Whether any of them equals a name the
// usfs_trails layer publishes has not been measured - eleven of these trails
// are inside that layer (#1543's round-one probe counted them live), so the
// answer is between zero and eleven. What would settle it: read the distinct
// `name` values that export publishes and diff them against these keys. The
// exact match is why an unmatched key is a marker nobody sees rather than a
// wrong marker on a line.
import aztLogo from '../design-system/assets/trails/azt-logo.png'
import cdtLogo from '../design-system/assets/trails/cdt-logo.png'
import bartramLogo from '../design-system/assets/trails/bartram-logo.png'
import bmtLogo from '../design-system/assets/trails/bmt-logo.png'
import buckeyeLogo from '../design-system/assets/trails/buckeye-logo.svg'
import catamountLogo from '../design-system/assets/trails/catamount-logo.png'
import cohosLogo from '../design-system/assets/trails/cohos-logo.png'
import condorLogo from '../design-system/assets/trails/condor-logo.png'
import cumberlandLogo from '../design-system/assets/trails/cumberland-logo.svg'
import fltLogo from '../design-system/assets/trails/flt-logo.png'
import fnstLogo from '../design-system/assets/trails/fnst-logo.png'
import foothillsLogo from '../design-system/assets/trails/foothills-logo.png'
import getLogo from '../design-system/assets/trails/get-logo.png'
import iatLogo from '../design-system/assets/trails/iat-logo.png'
import longTrailLogo from '../design-system/assets/trails/long-trail-logo.svg'
import loyalsockLogo from '../design-system/assets/trails/loyalsock-logo.png'
import lshtLogo from '../design-system/assets/trails/lsht-logo.png'
import masonDixonLogo from '../design-system/assets/trails/mason-dixon-logo.png'
import mdhLogo from '../design-system/assets/trails/mdh-logo.png'
import mogollonLogo from '../design-system/assets/trails/mogollon-logo.png'
import nctLogo from '../design-system/assets/trails/nct-logo.png'
import netLogo from '../design-system/assets/trails/net-logo.png'
import nptLogo from '../design-system/assets/trails/npt-logo.png'
import ohtLogo from '../design-system/assets/trails/oht-logo.png'
import ouachitaLogo from '../design-system/assets/trails/ouachita-logo.png'
import ozarkTrailLogo from '../design-system/assets/trails/ozark-trail-logo.png'
import palmettoLogo from '../design-system/assets/trails/palmetto-logo.png'
import pctLogo from '../design-system/assets/trails/pct-logo.png'
import pnnstLogo from '../design-system/assets/trails/pnnst-logo.png'
import ridgeTrailLogo from '../design-system/assets/trails/ridge-trail-logo.png'
import sheltoweeLogo from '../design-system/assets/trails/sheltowee-logo.png'
import shtLogo from '../design-system/assets/trails/sht-logo.png'
import standingStoneLogo from '../design-system/assets/trails/standing-stone-logo.png'
import tahoeRimLogo from '../design-system/assets/trails/tahoe-rim-logo.png'

const STEWARD_MARKS: Readonly<Record<string, string>> = {
  'arizona trail': aztLogo,
  'bartram trail': bartramLogo,
  'benton mackaye trail': bmtLogo,
  'buckeye trail': buckeyeLogo,
  'catamount trail': catamountLogo,
  'cohos trail': cohosLogo,
  'condor trail': condorLogo,
  'cumberland trail': cumberlandLogo,
  'finger lakes trail': fltLogo,
  'florida trail': fnstLogo,
  'foothills trail': foothillsLogo,
  'grand enchantment trail': getLogo,
  'ice age trail': iatLogo,
  'long trail': longTrailLogo,
  'loyalsock trail': loyalsockLogo,
  'lone star hiking trail': lshtLogo,
  'mason-dixon trail': masonDixonLogo,
  'maah daah hey trail': mdhLogo,
  'mogollon rim trail': mogollonLogo,
  'north country trail': nctLogo,
  'new england trail': netLogo,
  'northville-placid trail': nptLogo,
  'ozark highlands trail': ohtLogo,
  'ouachita trail': ouachitaLogo,
  'ozark trail': ozarkTrailLogo,
  'palmetto trail': palmettoLogo,
  'pacific northwest trail': pnnstLogo,
  'bay area ridge trail': ridgeTrailLogo,
  'sheltowee trace': sheltoweeLogo,
  'superior hiking trail': shtLogo,
  'standing stone trail': standingStoneLogo,
  'tahoe rim trail': tahoeRimLogo,
}

/** The steward marker for a published line name, or null. Folded and trimmed,
 *  exact - the same refusal `trailForName` makes. */
export function stewardMarkForName(name: string): string | null {
  return STEWARD_MARKS[name.trim().toLowerCase()] ?? null
}

/** How many markers this module carries, for the test that guards the count
 *  against an import silently dropping out. */
export const STEWARD_MARK_COUNT = Object.keys(STEWARD_MARKS).length

/**
 * The markers keyed by the trail's slug, which is what the BADGE asks.
 *
 * TWO KEYS, AND THE REASON THEY DIFFER IS WHAT EACH CALLER HAS IN HAND.
 * chrome/LineSheet.tsx has a tapped line's published NAME and nothing else.
 * map/trailsInView.ts has already resolved that name to a trail through
 * map/longTrailNames.ts, so it has the SLUG - and the slug is the better key,
 * because one trail has up to five published spellings and they all mean this
 * one file.
 *
 * NOT THE SAME SET, by two rows: `cdt` and `pct` are here and are NOT in
 * STEWARD_MARKS above. Both are lib/trails.ts registry trails, so a tapped
 * line already finds them by name through `trailForName`, and LineSheet
 * prefers that answer (`detail.trailMark ?? stewardMark`). The badge is the
 * caller with no such fallback: map/trailBadges.ts's BADGE_MARK_BY_SOURCE is
 * keyed by SOURCE and holds only `centerline` and `nynjtc_long_path`, so a
 * USFS segment spelled "CONTINENTAL DIVIDE NST" or "PACIFIC CREST TRAIL"
 * reaches its mark only through this map.
 *
 * CDT WAS THE BUG THAT MADE THAT WORTH WRITING DOWN. map/longTrailNames.ts's
 * SLUGS_WITH_A_STEWARD_MARKER listed `cdt` while this map did not, so
 * `badgeMarkImageId` asked the sprite for `trail-mark-steward-cdt` - an id
 * nothing registered - and the badge on all 267 USFS Continental Divide
 * segments drew an empty slot beside its name, with cdt-logo.png sitting in
 * the tree unused by that path. Nothing failed anywhere visible, which is why
 * stewardMarks.test.ts now asserts every slug map/longTrailNames.ts claims a
 * marker for resolves to a file here.
 */
const STEWARD_MARKS_BY_SLUG: Readonly<Record<string, string>> = {
  azt: aztLogo,
  bartram: bartramLogo,
  bmt: bmtLogo,
  buckeye: buckeyeLogo,
  cdt: cdtLogo,
  catamount: catamountLogo,
  cohos: cohosLogo,
  condor: condorLogo,
  cumberland: cumberlandLogo,
  flt: fltLogo,
  fnst: fnstLogo,
  foothills: foothillsLogo,
  get: getLogo,
  iat: iatLogo,
  'long-trail': longTrailLogo,
  loyalsock: loyalsockLogo,
  lsht: lshtLogo,
  'mason-dixon': masonDixonLogo,
  mdh: mdhLogo,
  mogollon: mogollonLogo,
  nct: nctLogo,
  net: netLogo,
  npt: nptLogo,
  oht: ohtLogo,
  ouachita: ouachitaLogo,
  'ozark-trail': ozarkTrailLogo,
  palmetto: palmettoLogo,
  pct: pctLogo,
  pnnst: pnnstLogo,
  'ridge-trail': ridgeTrailLogo,
  sheltowee: sheltoweeLogo,
  sht: shtLogo,
  'standing-stone': standingStoneLogo,
  'tahoe-rim': tahoeRimLogo,
}

/** The steward marker for a long trail's slug, or null where no marker was
 *  found for it - Pinhoti's steward domain serves spam, and five of the
 *  trails this badges publish no per-trail symbol at all. */
export function stewardMarkForSlug(slug: string): string | null {
  return STEWARD_MARKS_BY_SLUG[slug] ?? null
}

/** Every slug with a marker, for the badge's image registration. */
export function stewardMarkSlugs(): readonly string[] {
  return Object.keys(STEWARD_MARKS_BY_SLUG)
}
