// A small registry of the major US long-distance trails, so a trail's name
// is never a bare string with no logo to go with it. OurHike itself only
// ever hikes the AT today (App.tsx has one hardcoded trail, not a picker),
// but keeping the lookup keyed rather than inlining a single <img> means the
// day a second trail's data actually loads, its logo is already here.
//
// The AT mark is the official Appalachian Trail / National Scenic Trail
// marker, supplied directly by the repo owner - it carries its own TM mark,
// so its use here is that decision, not one made from this codebase. PCT and
// CDT still have placeholder marks of OurHike's own design, since PCTA's and
// CDTC's official logos aren't sourced here - swap in licensed art for those
// if that's ever secured.

import atLogo from '../design-system/assets/trails/at-logo.png'
import pctLogo from '../design-system/assets/trails/pct-logo.svg'
import cdtLogo from '../design-system/assets/trails/cdt-logo.svg'

export interface Trail {
  id: string
  name: string
  logo: string
}

export const TRAILS: Record<string, Trail> = {
  AT: { id: 'AT', name: 'Appalachian Trail', logo: atLogo },
  PCT: { id: 'PCT', name: 'Pacific Crest Trail', logo: pctLogo },
  CDT: { id: 'CDT', name: 'Continental Divide Trail', logo: cdtLogo },
}
