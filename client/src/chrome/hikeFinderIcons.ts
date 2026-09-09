// The hike finder's four icons, as path data rather than as a dependency
// (#1284) - reporting/icons.ts's argument, applied to four more shapes.
//
// These are Lucide's own SVGs, copied from `lucide-icons/lucide@main` and
// unredrawn. Four icons is 641 bytes of path data (measured 2026-09-08, the
// string literals below); the package would be a dependency, a lockfile entry
// and a supply-chain surface for shapes that will not change. reporting/icons.ts
// records where the line is: "if a later screen wants thirty of them, take the
// package and delete this". Fourteen now, across the two files.
//
// LICENCE. Lucide is ISC, which permits use and redistribution with the notice
// kept. Path data is the licensed artifact here, so the notice travels with it:
//
//   Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as
//   part of Feather (MIT). All other copyright (c) for Lucide are held by
//   Lucide Contributors 2022. Licensed under the ISC licence.
//
// STROKE WIDTH IS NOT BAKED IN. The design draws these at 1.5 (2 on the
// check), which is a rendering decision rather than a property of the shape,
// so it lives on the element that draws them (chrome/HikeFinderIcon.tsx).

export type HikeFinderIconName = 'search' | 'bus' | 'locate-fixed' | 'check'

/** The inside of each 24x24 `viewBox`, verbatim from Lucide. */
export const HIKE_FINDER_ICONS: Record<HikeFinderIconName, string> = {
  search: '<circle cx="11" cy="11" r="8"></circle> <path d="m21 21-4.3-4.3"></path>',
  bus: '<path d="M8 6v6"></path> <path d="M15 6v6"></path> <path d="M2 12h19.6"></path> <path d="M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"></path> <circle cx="7" cy="18" r="2"></circle> <path d="M9 18h5"></path> <circle cx="16" cy="18" r="2"></circle>',
  'locate-fixed':
    '<path d="M2 12h3"></path> <path d="M19 12h3"></path> <path d="M12 2v3"></path> <path d="M12 19v3"></path> <circle cx="12" cy="12" r="7"></circle> <circle cx="12" cy="12" r="3"></circle>',
  check: '<path d="M20 6 9 17l-5-5"></path>',
}
