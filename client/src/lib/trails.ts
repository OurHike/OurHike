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
  /** What a through-route badge prints beside the mark when the full name
   *  would not fit (map/trailBadges.ts's TRAIL_BADGE_TEXT_SIZE, #1307) - the
   *  design handoff's own "L.P." for the Long Path, extended to the other
   *  three registry trails on the same community-shorthand convention
   *  rather than a mechanical truncation of the full name. */
  shortName: string
}

export const TRAILS: Record<string, Trail> = {
  AT: { id: 'AT', name: 'Appalachian Trail', logo: atLogo, shortName: 'A.T.' },
  LP: { id: 'LP', name: 'Long Path', logo: lpLogo, shortName: 'L.P.' },
  PCT: { id: 'PCT', name: 'Pacific Crest Trail', logo: pctLogo, shortName: 'PCT' },
  CDT: { id: 'CDT', name: 'Continental Divide Trail', logo: cdtLogo, shortName: 'CDT' },
}

/**
 * Published spellings that mean a trail this registry already names, folded
 * to lower case, mapped to the TRAILS key they mean.
 *
 * ONE ENTRY, AND IT IS ATC'S. Measured 2026-08-23 against the live bucket
 * (the count is in map/trailLabels.test.ts): all 3,025 centerline segments
 * carry "Appalachian National Scenic Trail", which is the trail's formal
 * federal designation and the only name ATC's layer publishes. It is nobody's
 * word for it on a sheet headed "Appalachian Trail", and lib/lineDetail.ts
 * had already special-cased exactly this string for exactly that reason. The
 * maintainer asked on 2026-09-16 for the app to say "Appalachian Trail"
 * wherever a hiker reads it, so the special case became this table and the
 * remaining display paths were routed through it.
 *
 * AN ALIAS IS NOT A GUESS. Only a spelling somebody has seen in a published
 * feed goes here, and only mapped to a trail TRAILS already names - never a
 * substring rule, never a truncation. That is `trailForName`'s own refusal
 * below, for the same reason: "Long Path Link Trail" is a different trail. A
 * publisher's spelling for a trail this registry does NOT name is left
 * exactly as it arrived, which is what keeps a state park's forty lines out
 * of this and stops the rename becoming a licence to rewrite other people's
 * data.
 *
 * WHERE THE LONG NAME SURVIVES ON PURPOSE. The pipeline keeps it, because
 * pipeline/lib/hike_route_builder.py's `normalise_name` is explicit that a
 * name is "carried as its publisher spells it, and this is the key the two
 * spellings meet under" - the exported artifact stays traceable to the row
 * ATC published. So this is a display choice taken at the last step before a
 * hiker reads it, not a rewrite of the data behind it.
 */
const PUBLISHED_ALIASES: Record<string, string> = {
  'appalachian national scenic trail': 'AT',
}

/** The registry trail a published spelling aliases, for an already-folded
 *  name. Undefined for every name that is not in the table above. */
function aliasedTrail(folded: string): Trail | undefined {
  const id = PUBLISHED_ALIASES[folded]
  return id === undefined ? undefined : TRAILS[id]
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
 *
 * PUBLISHED_ALIASES is read after the registry's own names, so ATC's spelling
 * finds the A.T. too. No caller reaches that today - lib/lineDetail.ts looks
 * the A.T. up by the app's own trail name, never by `line.name`, and its
 * comment says what would have to change first - so this is consistency with
 * `displayTrailName` rather than a defect anybody has seen. A name and a mark
 * that disagree about whether a spelling is the A.T. is the bug worth not
 * having.
 */
export function trailForName(name: string | null | undefined): Trail | undefined {
  if (name === null || name === undefined) return undefined
  const wanted = name.trim().toLowerCase()
  if (wanted === '') return undefined
  return (
    Object.values(TRAILS).find((trail) => trail.name.toLowerCase() === wanted) ??
    aliasedTrail(wanted)
  )
}

/**
 * The name to SHOW for a published trail name: this registry's name where the
 * publisher's spelling is one it knows, the publisher's own spelling
 * everywhere else, and null where there is no name to show at all.
 *
 * The one place the rename happens, so the badge, the legend's "Trails in
 * view" row and the line sheet cannot drift apart on what the same trail is
 * called - the reason map/trailsInView.ts measures the badge and the list off
 * one pass rather than two.
 *
 * Empty and whitespace-only names come back null rather than '', matching
 * what the callers already do with a nameless line: they omit it, because a
 * name this map invented is a fact about somebody else's data that nobody
 * stands behind (map/trailLabels.test.ts says the same about "Unnamed").
 */
export function displayTrailName(name: string | null | undefined): string | null {
  if (name === null || name === undefined) return null
  const trimmed = name.trim()
  if (trimmed === '') return null
  return aliasedTrail(trimmed.toLowerCase())?.name ?? trimmed
}
