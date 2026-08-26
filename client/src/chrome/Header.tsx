// The map's identity plate and its two icon buttons - a read-only zone,
// floating since #1054.
//
// This used to be a band across the top of the screen (WIREFRAMES.md §2);
// the redesign gives the map the whole viewport and floats only what must be
// legible at a glance: trail + state, the mile, and the strip of flags where
// the map admits what it doesn't know. WIREFRAMES.md's words were "Nothing
// else lives here," and that is still honoured literally in the new shape -
// the plate takes exactly one slot, typed to one thing, and the reasoning
// for THAT is below rather than gone.
//
// Two absolutely-positioned pieces, one component: the plate top-left, the
// legend and search buttons top-right. They render inside the map canvas so
// the .map-screen--entering rules hide them structurally during first run,
// the way every other canvas overlay is hidden (chrome.css).

import type { ReactNode } from 'react'

export type HikeDirection = 'NOBO' | 'SOBO'

export interface HeaderProps {
  trailName: string
  /** The trail's own mark, from the TRAILS registry (lib/trails.ts).
   *  Omitted rather than defaulted to a generic icon: a trail with no known
   *  logo gets no logo, not a placeholder pretending to be one. */
  trailLogo?: string
  /** Omitted until the fix is placed in a state. */
  state?: string
  /**
   * The position line, already decided (lib/positionLine.ts).
   *
   * A string rather than the mile, and that is the change #312 asked for.
   * This used to take `mile?: number` and render "Looking for GPS…" whenever
   * it was absent - one sentence covering six situations, three of which
   * never resolve, so a hiker whose permission was denied or whose onboarding
   * skipped the location step was told to keep waiting for the rest of the
   * install's life. Which of those is true is the shell's knowledge, not the
   * chrome's, so the sentence is decided there and read here.
   *
   * Never empty: the slot always says something, because a blank where the
   * mile goes is the same silence with better manners.
   */
  position: string
  /**
   * The status strip, rendered into the plate - the ONE slot this component
   * has, and it is typed by intent rather than left open: the strip is the
   * single owner of the flag logic and its suppression rules
   * (chrome/StatusStrip.tsx), moving it here is #1054's change, and dropping
   * any flag it renders is the regression that strip exists to prevent. This
   * is not an invitation to hang other chrome off the plate - the old "takes
   * no children and exposes no slot" rule survives as "takes exactly this".
   */
  strip: ReactNode
  onOpenLegend: () => void
  onOpenSearch: () => void
}

export function Header({
  trailName,
  trailLogo,
  state,
  position,
  strip,
  onOpenLegend,
  onOpenSearch,
}: HeaderProps) {
  return (
    <>
      <header className="map-plate">
        <div className="map-plate__identity">
          {trailLogo !== undefined && (
            <img
              className="map-plate__trail-logo"
              src={trailLogo}
              alt=""
              aria-hidden="true"
            />
          )}
          <div className="map-plate__read">
            <p className="map-plate__eyebrow">
              {state === undefined ? trailName : `${trailName} · ${state}`}
            </p>
            <p className="map-plate__position">{position}</p>
          </div>
        </div>
        {strip}
      </header>

      <div className="map-header__actions">
        {/* --legend so the desktop layout can hide it: at that width the
            legend is a permanent panel, and a button that opens something
            already open does nothing. */}
        <button
          type="button"
          className="map-header__button map-header__button--legend"
          onClick={onOpenLegend}
        >
          <span className="visually-hidden">Legend</span>
          <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20">
            <path
              d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>

        <button type="button" className="map-header__button" onClick={onOpenSearch}>
          <span className="visually-hidden">Search</span>
          <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20">
            <circle
              cx="11"
              cy="11"
              r="7"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
            <path
              d="m20 20-3.5-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
    </>
  )
}
