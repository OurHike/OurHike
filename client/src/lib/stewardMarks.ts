// The 33 stewards' own trail markers, and the only module that names them.
//
// WHY THIS IS ITS OWN FILE AND NOT lib/trails.ts. App.tsx imports TRAILS, so
// every row of that table is parsed before the first frame. Putting these 32
// names and URLs there measured 257,725 bytes of eager JavaScript against
// features/LAUNCH_BUDGET.md §3's 256,000 - over by 1,725, where the same
// build without them passes at 253,337. A marker a hiker sees only after
// tapping a line has no business in the launch path, so this module is
// reached through `import()` from chrome/LineSheet.tsx and lands in its own
// chunk. Measured 2026-09-30; `npm run build` prints the number.
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
