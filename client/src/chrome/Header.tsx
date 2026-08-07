// The map screen's header - a read-only zone (WIREFRAMES.md §2).
//
// Trail + state eyebrow, current mile + direction in mono, and on the right
// exactly two icon buttons: legend, then search. WIREFRAMES.md's words are
// "Nothing else lives here." That is worth honouring literally: this is the
// most valuable strip on the screen and the obvious place for scope to creep,
// so the component takes no children and exposes no slot.

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
  onOpenLegend: () => void
  onOpenSearch: () => void
}

export function Header({
  trailName,
  trailLogo,
  state,
  position,
  onOpenLegend,
  onOpenSearch,
}: HeaderProps) {
  return (
    <header className="map-header">
      <div className="map-header__identity">
        {trailLogo !== undefined && (
          <img
            className="map-header__trail-logo"
            src={trailLogo}
            alt=""
            aria-hidden="true"
          />
        )}
        <div className="map-header__read">
          <p className="map-header__eyebrow">
            {state === undefined ? trailName : `${trailName} · ${state}`}
          </p>
          <p className="map-header__position">{position}</p>
        </div>
      </div>

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
    </header>
  )
}
