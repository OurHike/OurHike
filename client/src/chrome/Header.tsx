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
  /** Omitted until the fix is placed in a state. */
  state?: string
  /**
   * Current position along the trail, in miles. Omitted before there is a GPS
   * fix, and omitted rather than zeroed: "mi 0.0" is Springer Mountain, which
   * is a confident claim about somewhere the hiker is almost certainly not.
   */
  mile?: number
  /** Omitted until enough movement has happened to tell which way. */
  direction?: HikeDirection
  onOpenLegend: () => void
  onOpenSearch: () => void
}

/**
 * Always one decimal place, with a thousands separator: "1,407.2".
 * Fixed precision keeps the number from changing width as the hiker walks,
 * which would otherwise make the whole header twitch.
 */
function formatMile(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

export function Header({
  trailName,
  state,
  mile,
  direction,
  onOpenLegend,
  onOpenSearch,
}: HeaderProps) {
  return (
    <header className="map-header">
      <div className="map-header__read">
        <p className="map-header__eyebrow">
          {state === undefined ? trailName : `${trailName} · ${state}`}
        </p>
        <p className="map-header__position">
          {mile === undefined
            ? 'Looking for GPS…'
            : `mi ${formatMile(mile)}${direction === undefined ? '' : ` · ${direction}`}`}
        </p>
      </div>

      <div className="map-header__actions">
        <button type="button" className="map-header__button" onClick={onOpenLegend}>
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
