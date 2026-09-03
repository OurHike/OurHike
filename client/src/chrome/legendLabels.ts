// Display names for legend rows, kept out of Legend.tsx so that file exports
// only a component (React Fast Refresh breaks on modules that mix the two).
//
// This is NOT the full category list - WIREFRAMES.md puts that in Settings.
// The legend only ever names what is actually on screen, so an entry here is a
// label for a type the map can render, not a declaration that it exists.

export const TYPE_LABELS: Record<string, string> = {
  water: 'Water',
  shelter: 'Shelter',
  campsite: 'Campsite',
  resupply: 'Resupply',
  town: 'Town',
  parking: 'Parking',
  trailhead: 'Trailhead',
  crossing: 'Crossing',
  viewpoint: 'Viewpoint',
  // "Privy" rather than "Toilet" or "Restroom": it is what the sign on the
  // trail says, what ATC calls the layer, and what a hiker asking for one
  // will say out loud.
  privy: 'Privy',
  closure: 'Closure',
  'serious-warning': 'Serious warning',
}

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type
}
