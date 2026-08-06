// The map's credit corner: what is on screen, and who it belongs to.
//
// WHAT IT SAYS is map/credits.ts's decision - this component is handed the
// sources actually being drawn and never works them out for itself. WHAT IT
// COSTS IN PIXELS is the decision here, and it is the reason this stopped
// being a `<p>` with a joined string in it.
//
// The strip is a row of its own beneath the canvas rather than an overlay in
// the corner (see chrome.css for why - MapLibre's scale bar already owns that
// corner), so every line it wraps to is a line of map a hiker does not get.
// The live sheet's credit ran to three sources; on a 360px phone at 10px that
// is two to three wrapped lines, permanently, on the screen someone navigates
// by. Trimming the text to what is genuinely on screen (credits.ts) took it
// from five clauses to three and is most of the fix. This is the rest of it.
//
// COLLAPSED, THE OSM LINE IS STILL THERE, and that is the whole basis on which
// collapsing is defensible. ODbL is the one licence here that demands
// prominence, so its credit is what the summary shows, always, in full, with
// no truncation and no ellipsis - the shorthand "© OSM" does not satisfy it
// and neither would half a line. The remaining credits sit one tap behind a
// control that is itself permanently on screen and labelled with how many
// there are. That is the same shape MapLibre's own compact AttributionControl
// takes, and it is the arrangement the OSMF attribution guidelines contemplate
// for a medium too small to carry the full statement inline.
//
// Native `<details>` rather than a state hook and an aria-expanded: the
// disclosure triangle, the keyboard behaviour and the screen-reader
// announcement all come with it, correct, for free.
//
// WHERE THERE IS ROOM, NOTHING IS HIDDEN. Above WEBSITE.md's 900px breakpoint
// the whole list fits on one line with space to spare, so the desktop renders
// it inline and there is nothing to expand. The disclosure exists because a
// phone is narrow, so it appears only where that is true.

export interface MapAttributionProps {
  /**
   * Every source on screen, most-required first - see map/credits.ts.
   *
   * The order is load-bearing: whatever is first is what stays visible when
   * this collapses, which is why credits.ts puts OpenStreetMap there and keeps
   * it there in every state.
   */
  credits: readonly string[]
  /** Render the full list on one line, with no disclosure - desktop widths. */
  inline?: boolean
}

/** How credits read as one line, matching the map's other chrome. */
const SEPARATOR = ' · '

export function MapAttribution({ credits, inline = false }: MapAttributionProps) {
  // Not reachable through mapCredits(), which always names OpenStreetMap. It
  // is guarded anyway because the alternative is an empty bordered strip that
  // looks like a rendering fault, and because a caller passing its own list is
  // the obvious next use of this component.
  if (credits.length === 0) return null

  // One credit is already one line. A disclosure over a single item would be a
  // tap target that reveals nothing.
  if (inline || credits.length === 1) {
    return <p className="map-attribution">{credits.join(SEPARATOR)}</p>
  }

  return (
    <details className="map-attribution">
      <summary className="map-attribution__summary">
        {credits[0]}
        {/* Hidden by CSS once open, where the list below says the same thing
            more precisely. It is a count rather than a label ("Sources")
            because the honest question a truncated credit line raises is
            "what else is being left out", and a number answers it without
            being opened. */}
        <span className="map-attribution__more">
          {SEPARATOR}
          {credits.length - 1} more
        </span>
      </summary>
      {/* The first credit is not repeated - it is the line directly above. */}
      <ul className="map-attribution__list">
        {credits.slice(1).map((credit) => (
          <li key={credit}>{credit}</li>
        ))}
      </ul>
    </details>
  )
}
