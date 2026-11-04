// The blaze card's icon set (#1962, features/CHALLENGES_BLAZE_CARD.md): one
// stroke glyph per kind of item, on a 24-unit box, the set the design frames
// draw (features/design/blaze-card/BlazeCard.dc.html). Twenty-six from the
// frame plus `pen`, which item-icons.json uses for six writing items and the
// frame fell back to `learn` for - a pencil is the honest glyph, and the
// frame's fallback was the mock's bug rather than its intent (maintainer, poll
// 2026-11-04, shown the pencil on the expanded card: keep it).
//
// Paths are string literals this repository wrote, drawn with `<path d>`; no
// markup from a network or a store reaches the DOM through here. The icon per
// item is data: each item's `icon` in challenges.json, which the exporter
// holds to exactly these names (pipeline/lib/challenges.py ICON_NAMES) and
// blazeIcons.test.ts holds this list to the exporter's.

export const BLAZE_ICONS = {
  blaze: 'M9 3h6v18H9z',
  book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
  boots:
    'M7 14c-2 0-3-2-3-4.5S5 4 7 4s3 3 3 5.5S9 14 7 14z M5 16h4v3a2 2 0 0 1-4 0z M17 18c-2 0-3-2-3-4.5S15 8 17 8s3 3 3 5.5-1 4.5-3 4.5z M15 20h4v1a2 2 0 0 1-4 0z',
  bridge: 'M2 20V9 M22 20V9 M2 14h20 M6 14v6 M12 14v6 M18 14v6 M2 9c4-5 16-5 20 0',
  camera: 'M4 8h3l2-3h6l2 3h3v12H4z M12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
  film: 'M4 4h16v16H4z M4 8h16 M4 16h16 M8 4v16 M16 4v16',
  food: 'M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2 M7 2v20 M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3z M21 15v7',
  heart:
    'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8z',
  leaf: 'M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8 0 5.5-4.8 10-10 10z M2 21c0-3 1.9-5.5 5-6.5',
  learn: 'M22 10 12 5 2 10l10 5 10-5z M6 12v5c3 3 9 3 12 0v-5',
  map: 'M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z M9 3v15 M15 6v15',
  megaphone:
    'M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1z M15.5 8.5a5 5 0 0 1 0 7 M18.5 5.5a9 9 0 0 1 0 13',
  mountain: 'M8 3l4 8 5-5 5 15H2L8 3z',
  museum: 'M3 21h18 M4 21V10 M20 21V10 M2 10l10-7 10 7H2z M8 21v-6 M12 21v-6 M16 21v-6',
  mystery: 'M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.7 M12 17h.01',
  pen: 'M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z M15 5l4 4',
  people:
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M22 21v-2a4 4 0 0 0-3-3.9 M16 3.1a4 4 0 0 1 0 7.8',
  podcast:
    'M3 18v-6a9 9 0 0 1 18 0v6 M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z',
  quiz: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.7 M12 17h.01',
  shelter: 'M3 21h18 M4 21V9l8-6 8 6v12 M4 9h16 M8 21v-8h8v8',
  sunrise:
    'M12 2v3 M4.2 7.2l2.1 2.1 M19.8 7.2l-2.1 2.1 M2 16h20 M6 16a6 6 0 0 1 12 0 M4 20h16',
  tent: 'M3.5 21 14 3 M20.5 21 10 3 M2 21h20 M12 21v-6',
  tools: 'M2 22l10-10 M11 7c3-3 7-3 10 0 M13 9l-2-2 M17 13l-2-2 M12 12l4-4',
  tower: 'M8 21l2-14h4l2 14 M6 7h12 M7 4h10v3H7z M9 14h6 M8 21h8',
  town: 'M3 21h18 M5 21V7l7-4 7 4v14 M9 10h2 M13 10h2 M9 14h2 M13 14h2 M10 21v-4h4v4',
  trash: 'M3 6h18 M8 6V4h8v2 M19 6l-1 14H6L5 6 M10 11v5 M14 11v5',
  water: 'M12 2.7c4 4.5 6 7.9 6 11a6 6 0 0 1-12 0c0-3.1 2-6.5 6-11z',
} as const

export type BlazeIconName = keyof typeof BLAZE_ICONS

export const BLAZE_ICON_NAMES = Object.keys(BLAZE_ICONS).sort() as BlazeIconName[]

/** The glyph for a name the data may carry; a name this build does not know
 *  draws the learn glyph rather than nothing, so a newer artifact on an older
 *  shell still shows a tile. */
export function blazeIconPath(name: string | null): string {
  return name !== null && name in BLAZE_ICONS
    ? BLAZE_ICONS[name as BlazeIconName]
    : BLAZE_ICONS.learn
}
