// The category icons, as path data rather than as a dependency (#1133).
//
// The design handoff specifies Lucide line icons and says "in the app, install
// `lucide-react`". These are those icons, copied from `lucide-icons/lucide@main`
// - the SVGs themselves, unredrawn - and inlined here instead.
//
// WHY NOT THE PACKAGE. This app is offline-first in a way that has already
// cost it once: design-system/tokens/typography.css records a first paint of
// 12,956 ms because the stylesheet reached for Google Fonts, and the fix was
// to vendor the files. A bundled npm package is not that failure - it ships in
// the build and fetches nothing - so the argument here is smaller and worth
// stating honestly rather than borrowing that one's weight:
//
//   - Ten icons is 2,314 bytes of path data (measured 2026-08-27, the string
//     literals below). `lucide-react` is a dependency, a lockfile entry, a
//     supply-chain surface and an upgrade to think about, for ten shapes that
//     will not change.
//   - map/poiIcons.ts already holds this repo's icon geometry as data in TS.
//     A second, different answer to "where do icons live" is the cost.
//
// If a later screen wants thirty of them, take the package and delete this;
// the sums change at that point and this comment is the record of where the
// line was.
//
// LICENCE. Lucide is ISC, which permits use and redistribution with the notice
// kept. Path data is the licensed artifact here, so the notice travels with
// it:
//
//   Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as
//   part of Feather (MIT). All other copyright (c) for Lucide are held by
//   Lucide Contributors 2022. Licensed under the ISC licence.
//
// STROKE WIDTH IS NOT BAKED IN. Lucide draws at 2; the handoff asks for 1.5,
// which is a rendering decision rather than a property of the shape - so it
// lives on the element that draws these, not in the strings below.

export type ReportIconName =
  | 'tree-pine'
  | 'waves-horizontal'
  | 'trash-2'
  | 'tent-tree'
  | 'paw-print'
  | 'sprout'
  | 'octagon-x'
  | 'shield-alert'
  | 'heart-handshake'
  | 'camera'

/** The inside of each 24x24 `viewBox`, verbatim from Lucide. */
export const REPORT_ICONS: Record<ReportIconName, string> = {
  'tree-pine':
    '<path d="m17 14 3 3.3a1 1 0 0 1-.7 1.7H4.7a1 1 0 0 1-.7-1.7L7 14h-.3a1 1 0 0 1-.7-1.7L9 9h-.2A1 1 0 0 1 8 7.3L12 3l4 4.3a1 1 0 0 1-.8 1.7H15l3 3.3a1 1 0 0 1-.7 1.7H17Z"></path> <path d="M12 22v-3"></path>',
  'waves-horizontal':
    '<path d="M2 12q2.5 2 5 0t5 0 5 0 5 0"></path> <path d="M2 19q2.5 2 5 0t5 0 5 0 5 0"></path> <path d="M2 5q2.5 2 5 0t5 0 5 0 5 0"></path>',
  'trash-2':
    '<path d="M10 11v6"></path> <path d="M14 11v6"></path> <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"></path> <path d="M3 6h18"></path> <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>',
  'tent-tree':
    '<circle cx="4" cy="4" r="2"></circle> <path d="m14 5 3-3 3 3"></path> <path d="m14 10 3-3 3 3"></path> <path d="M17 14V2"></path> <path d="M17 14H7l-5 8h20Z"></path> <path d="M8 14v8"></path> <path d="m9 14 5 8"></path>',
  'paw-print':
    '<circle cx="11" cy="4" r="2"></circle> <circle cx="18" cy="8" r="2"></circle> <circle cx="20" cy="16" r="2"></circle> <path d="M9 10a5 5 0 0 1 5 5v3.5a3.5 3.5 0 0 1-6.84 1.045Q6.52 17.48 4.46 16.84A3.5 3.5 0 0 1 5.5 10Z"></path>',
  sprout:
    '<path d="M14 9.536V7a4 4 0 0 1 4-4h1.5a.5.5 0 0 1 .5.5V5a4 4 0 0 1-4 4 4 4 0 0 0-4 4c0 2 1 3 1 5a5 5 0 0 1-1 3"></path> <path d="M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4"></path> <path d="M5 21h14"></path>',
  'octagon-x':
    '<path d="m15 9-6 6"></path> <path d="M2.586 16.726A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2h6.624a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586z"></path> <path d="m9 9 6 6"></path>',
  'shield-alert':
    '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"></path> <path d="M12 8v4"></path> <path d="M12 16h.01"></path>',
  'heart-handshake':
    '<path d="M19.414 14.414C21 12.828 22 11.5 22 9.5a5.5 5.5 0 0 0-9.591-3.676.6.6 0 0 1-.818.001A5.5 5.5 0 0 0 2 9.5c0 2.3 1.5 4 3 5.5l5.535 5.362a2 2 0 0 0 2.879.052 2.12 2.12 0 0 0-.004-3 2.124 2.124 0 1 0 3-3 2.124 2.124 0 0 0 3.004 0 2 2 0 0 0 0-2.828l-1.881-1.882a2.41 2.41 0 0 0-3.409 0l-1.71 1.71a2 2 0 0 1-2.828 0 2 2 0 0 1 0-2.828l2.823-2.762"></path>',
  camera:
    '<path d="M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z"></path> <circle cx="12" cy="13" r="3"></circle>',
}
