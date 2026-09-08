// A small registry of the long-distance trails this app can name, so a
// trail's name is never a bare string with no logo to go with it. OurHike
// itself only ever hikes the AT today (App.tsx has one hardcoded trail, not
// a picker), but keeping the lookup keyed rather than inlining a single
// <img> meant that the day a second trail's data actually loaded, its logo
// was already here. That day came with #1288: the Long Path's lines and
// waypoints ship from NYNJTC's data, and the line sheet names the trail a
// hiker tapped - so `trailForName` is how a tapped "Long Path" finds its
// mark without the sheet knowing which trails have one.
//
// THE MARKS ARE THIRD-PARTY TRADEMARKS IN A PUBLIC AGPL TREE, and each one's
// permission is recorded in pipeline/sources.json's `org_marks` block
// (`trail_mark_in_tree` on the org's row), which is where #933 says the
// answer lives - a comment here is the summary, not the record:
//
//   - The AT mark is the official Appalachian Trail / National Scenic Trail
//     marker, supplied directly by the repo owner - it carries its own TM
//     mark, so its use here is that decision, not one made from this
//     codebase.
//   - The Long Path mark is NYNJTC's own logo, at the URL the maintainer
//     supplied on 2026-09-08 with the ask to add it, on the maintainer's
//     authorisation and the relationship with NYNJTC they named for the
//     trail's data the same day. Not a grant from NYNJTC.
//
// PCT and CDT still have placeholder marks of OurHike's own design, since
// PCTA's and CDTC's official logos aren't sourced here - swap in licensed
// art for those if that's ever secured.

import atLogo from '../design-system/assets/trails/at-logo.png'
import lpLogo from '../design-system/assets/trails/lp-logo.png'
import pctLogo from '../design-system/assets/trails/pct-logo.svg'
import cdtLogo from '../design-system/assets/trails/cdt-logo.svg'

export interface Trail {
  id: string
  name: string
  logo: string
}

export const TRAILS: Record<string, Trail> = {
  AT: { id: 'AT', name: 'Appalachian Trail', logo: atLogo },
  LP: { id: 'LP', name: 'Long Path', logo: lpLogo },
  PCT: { id: 'PCT', name: 'Pacific Crest Trail', logo: pctLogo },
  CDT: { id: 'CDT', name: 'Continental Divide Trail', logo: cdtLogo },
}

/**
 * The trail a published line's name refers to, or undefined.
 *
 * By NAME rather than by id, because that is the only handle a nearby line
 * carries: the network artifact publishes each steward's own `name` for the
 * line ("Long Path", the value pipeline/sources.json's `owns_route_names`
 * keys the route on) and no trail id. Exact after trimming and case-folding,
 * never a substring - "Long Path Link Trail" is a different trail and must
 * not wear the Long Path's mark.
 */
export function trailForName(name: string | null | undefined): Trail | undefined {
  if (name === null || name === undefined) return undefined
  const wanted = name.trim().toLowerCase()
  if (wanted === '') return undefined
  return Object.values(TRAILS).find((trail) => trail.name.toLowerCase() === wanted)
}
