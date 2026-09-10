// The figure that follows the pointer over a route being built, on a laptop
// (the maintainer's review of #1374). chrome/useRouteHover.ts says where;
// this draws it.
//
// WHAT IT PRINTS IS WHAT THE COLUMN PRINTS. The title is DayHikePanel's own
// routeTitle and the figures are the bar's - the same miles and the same
// ≈time, formatted by the same two functions - so hovering the line cannot
// disagree with reading the column. Nothing is derived here. The plate is
// inert to the pointer (`pointer-events: none` in chrome.css), so it never
// takes the tap it is describing.

import type { HoverPoint } from './useRouteHover'

export interface RouteHoverPlateProps {
  at: HoverPoint
  /** DayHikePanel's routeTitle, verbatim. */
  title: string
  /** The bar's own figures, joined: "6.4 mi · ≈3 h 20 walking". */
  figures: string
}

export function RouteHoverPlate({ at, title, figures }: RouteHoverPlateProps) {
  return (
    <div
      className="route-hover"
      role="status"
      aria-live="off"
      style={{ left: at.x, top: at.y }}
    >
      <span className="route-hover__eyebrow">Hovering</span>
      <span className="route-hover__title">{title}</span>
      <span className="route-hover__figures">{figures}</span>
    </div>
  )
}
