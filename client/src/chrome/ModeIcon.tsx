// The three mode glyphs (#1373, the flow review's ModeIcon): a sun for a day
// hike, a half-turned disc for a long hike, a shovel for volunteering.
//
// One home for the three silhouettes, so the switch, the read-out above the
// tab bar and the volunteer pin on the map all draw the same shape - the
// review's argument for turning the workday pin into this shovel is exactly
// that "the mark on the map and the word in the switch are the same thing".
// The paths are the design's own geometry, kept in a unit box the way
// map/poiIcons.ts keeps its polygons, and scaled by `size` at the call site.
//
// Decorative, always. Every place one of these appears already names the mode
// in text beside it ("Day hike", "Long hike", "Volunteer"), and a screen
// reader announcing the word twice is worse than once.

import type { HikerMode } from '../lib/hikerMode'

export interface ModeIconProps {
  mode: HikerMode
  /** Rendered size in CSS pixels. 19 is the switch's; the read-out uses 18. */
  size?: number
  className?: string
}

const SUN = (
  <>
    <path
      fill="currentColor"
      fillRule="evenodd"
      d="M0.19 0.5 A0.31 0.31 0 1 0 0.81 0.5 A0.31 0.31 0 1 0 0.19 0.5 Z M0.355 0.43 A0.052 0.052 0 1 0 0.459 0.43 A0.052 0.052 0 1 0 0.355 0.43 Z M0.541 0.43 A0.052 0.052 0 1 0 0.645 0.43 A0.052 0.052 0 1 0 0.541 0.43 Z M0.34 0.575 Q0.5 0.695 0.66 0.575 Q0.5 0.655 0.34 0.575 Z"
    />
    <g fill="currentColor">
      <path d="M0.5 0.0 L0.57 0.15 L0.43 0.15 Z" />
      <path d="M0.5 1.0 L0.43 0.85 L0.57 0.85 Z" />
      <path d="M0.0 0.5 L0.15 0.43 L0.15 0.57 Z" />
      <path d="M1.0 0.5 L0.85 0.57 L0.85 0.43 Z" />
      <path d="M0.13 0.13 L0.3 0.19 L0.19 0.3 Z" />
      <path d="M0.87 0.87 L0.7 0.81 L0.81 0.7 Z" />
      <path d="M0.87 0.13 L0.81 0.3 L0.7 0.19 Z" />
      <path d="M0.13 0.87 L0.19 0.7 L0.3 0.81 Z" />
    </g>
  </>
)

const LONG = (
  <>
    <path
      d="M0.5 0.06 A0.44 0.44 0 0 1 0.5 0.94 A0.22 0.44 0 0 1 0.5 0.06 Z"
      fill="currentColor"
    />
    <circle
      cx="0.5"
      cy="0.5"
      r="0.44"
      fill="none"
      stroke="currentColor"
      strokeWidth="0.055"
    />
  </>
)

const SHOVEL = (
  <g fill="currentColor" transform="rotate(-20 0.5 0.5)">
    <path d="M0.34 0.10 L0.66 0.10 L0.66 0.22 L0.34 0.22 Z" />
    <rect x="0.44" y="0.20" width="0.12" height="0.36" rx="0.05" />
    <path d="M0.26 0.54 L0.74 0.54 Q0.74 0.82 0.5 0.90 Q0.26 0.82 0.26 0.54 Z" />
  </g>
)

const GLYPHS: Record<HikerMode, React.ReactNode> = {
  day: SUN,
  long: LONG,
  volunteer: SHOVEL,
}

export function ModeIcon({ mode, size = 19, className }: ModeIconProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 1 1"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
      data-mode={mode}
      style={{ display: 'block' }}
    >
      {GLYPHS[mode]}
    </svg>
  )
}
