// What a tapped pin says about itself (WIREFRAMES.md's POI detail, `6a`-`6b`).
//
// Only what the app actually holds, and no more. Every line here is a fact the
// download carried; there is no "last confirmed" line, because no published
// artifact carries a confirmation date yet - and a "Last confirmed: unknown"
// row would read as a data glitch rather than as the truth, which is that
// nobody has built the mechanism for a hiker to confirm anything (WIREFRAMES.md
// §11, features/DATA_NUDGES.md - both post-MVP).
//
// The one line that is not a bare fact is the unverified sentence, and it is
// the reason this sheet is worth having. The pin already says it with a broken
// rim (map/poiIcons.ts), which is a channel someone has to have learned to
// read. OurHikeValues.md #4 asks for uncertainty in words as well - "a smaller
// feature set hikers can trust beats a flashy one they have to second-guess" -
// so tapping the pin is where the words are.
//
// Not a modal. The map behind it stays live and pannable, and claiming
// `aria-modal` would tell a screen-reader user the rest of the screen is inert
// when it is not. Same call ClosureSheet makes.

import { typeLabel } from './legendLabels'
import { sourceLabel } from './poiSources'

export interface PoiDetail {
  id: string
  name: string
  type: string
  lat: number
  lon: number
  confidence: 'high' | 'low'
  /**
   * Which published source listed it - see poiSources.ts.
   *
   * Optional because a phone that downloaded before the client started
   * reading this field has POIs in IndexedDB without one, and re-downloading
   * a corridor to gain a provenance line is not a trade worth forcing. The
   * line is simply omitted until the next download.
   */
  source?: string
  /**
   * Distance along the trail, when the centerline index could place it.
   *
   * Same optionality as SearchablePoi's, and for the same reason: it comes
   * from the trail lines, which are a separate download that can legitimately
   * be missing. A shelter with no mile is still worth a sheet.
   */
  mile?: number
}

export interface PoiSheetProps {
  poi: PoiDetail
  onClose: () => void
}

function mile(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/**
 * Five decimal places is about a metre, which is finer than any of these
 * points is surveyed and exactly what someone reading a position out over a
 * radio needs.
 *
 * A plain hyphen-minus, never a typographic one: these numbers exist to be
 * copied into another device, and U+2212 is rejected by most of them.
 */
function coordinates(lat: number, lon: number): string {
  return `${lat.toFixed(5)}, ${lon.toFixed(5)}`
}

export function PoiSheet({ poi, onClose }: PoiSheetProps) {
  const source = sourceLabel(poi.source)

  return (
    <div className="poi-sheet" role="dialog" aria-label="Waypoint">
      {/* The legend's own head, deliberately: three sheets now open at the
          bottom of this screen and a hiker should not have to find a
          differently-placed close button on each one. */}
      <div className="legend__head">
        <h2 className="legend__title">{poi.name}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close waypoint details</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="poi-sheet__type">{typeLabel(poi.type)}</p>

      {poi.mile !== undefined && (
        <p className="poi-sheet__mile">{`mi ${mile(poi.mile)}`}</p>
      )}

      {poi.confidence === 'low' && (
        <p className="poi-sheet__unverified" role="note">
          Unverified — nobody has confirmed this one is really there.
        </p>
      )}

      <p className="poi-sheet__coords">
        <span className="visually-hidden">Latitude, longitude: </span>
        {coordinates(poi.lat, poi.lon)}
      </p>

      {source !== null && <p className="poi-sheet__source">{`From ${source}.`}</p>}
    </div>
  )
}
