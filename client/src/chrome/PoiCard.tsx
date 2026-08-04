// What a tapped pin says about itself (WIREFRAMES.md Interactions), as a card
// floating beside the pin rather than a sheet docked at the bottom edge.
//
// The move is not cosmetic. A bottom sheet answers "what did I tap" with a
// name and asks the hiker to match it back to the map; a card anchored to the
// pin answers with position - it hangs off the exact point it describes, and
// tracks it through every pan and zoom the way MapLibre's own popups do. The
// anchoring maths lives in poiCardPlacement.ts, pure and tested; this file
// wires it to the live map.
//
// Only what the app actually holds, and no more. Every line here is a fact
// the download carried; there is no "last confirmed" line, because no
// published artifact carries a confirmation date yet - and a "Last confirmed:
// unknown" row would read as a data glitch rather than as the truth, which is
// that nobody has built the mechanism for a hiker to confirm anything
// (WIREFRAMES.md §11, features/DATA_NUDGES.md - both post-MVP).
//
// The photo slot is held to the same rule. No published source carries
// imagery yet, so `photoUrl` is optional and the slot shows the category's
// own silhouette on its accent - honest iconography, not a stock photo
// pretending to be the shelter. The day a source publishes photos, the data
// fills the slot without this component changing shape.
//
// The one line that is not a bare fact is the unverified sentence, and it is
// the reason this card is worth having. The pin already says it with a broken
// rim (map/poiIcons.ts), which is a channel someone has to have learned to
// read. OurHikeValues.md #4 asks for uncertainty in words as well - "a smaller
// feature set hikers can trust beats a flashy one they have to second-guess" -
// so tapping the pin is where the words are.
//
// Not a modal. The map behind it stays live and pannable - panning is how the
// card is USED, it rides along with its pin - and claiming `aria-modal` would
// tell a screen-reader user the rest of the screen is inert when it is not.
// Same call ClosureSheet makes.

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { typeLabel } from './legendLabels'
import { sourceLabel } from './poiSources'
import { placePoiCard, type CardPlacement } from './poiCardPlacement'
import { POI_COLORS, POI_FALLBACK_COLOR, poiGlyphPath } from '../map/poiIcons'
import type { PoiType } from '../lib/config'

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
   * be missing. A shelter with no mile is still worth a card.
   */
  mile?: number
  /**
   * A photo of the place, when one exists.
   *
   * No published source carries one yet - the pipeline's POI schema has no
   * imagery field - so today this is always undefined and the card always
   * shows the category placeholder. The field exists so the contract is
   * settled now: a photo is optional, and its absence is a placeholder, never
   * a broken image or a withheld card.
   */
  photoUrl?: string
}

export interface PoiCardProps {
  poi: PoiDetail
  /**
   * The live map the card is anchored on.
   *
   * Null is tolerated rather than forbidden - the shell learns about the map
   * from an effect, so there is an instant where a card could exist first.
   * With no map there is no anchor, and the card renders unpositioned at the
   * canvas origin: still readable, still closable, correctly placed one
   * projection later.
   */
  map: MapLibreMap | null
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

/**
 * The card's screen position, re-projected on every camera move.
 *
 * Layout effect rather than effect, so the first placement lands before the
 * first paint - the card must never flash at the canvas origin on its way to
 * the pin. Measuring the card in the same pass is safe for the same reason:
 * by the time this runs the DOM holds the final content, and reading
 * `offsetWidth` forces layout synchronously.
 */
function usePinAnchor(
  map: MapLibreMap | null,
  poi: PoiDetail,
  card: RefObject<HTMLDivElement | null>,
): CardPlacement | null {
  const [placement, setPlacement] = useState<CardPlacement | null>(null)

  useLayoutEffect(() => {
    if (map === null) return

    const update = () => {
      // Unreachable, and kept for the type checker: the ref is attached to
      // the element this hook's caller always renders, and effects run after
      // it is in the DOM.
      /* v8 ignore next */
      if (card.current === null) return

      const canvas = map.getCanvas()
      const next = placePoiCard(
        map.project([poi.lon, poi.lat]),
        { width: card.current.offsetWidth, height: card.current.offsetHeight },
        // The canvas's CSS size, which is the coordinate space `project`
        // answers in - `canvas.width` is that times the device pixel ratio.
        { width: canvas.clientWidth, height: canvas.clientHeight },
      )
      // 'move' fires every animation frame of a pan; only re-render for a
      // placement that actually moved.
      setPlacement((previous) =>
        previous !== null && previous.left === next.left && previous.top === next.top
          ? previous
          : next,
      )
    }

    update()
    map.on('move', update)
    map.on('resize', update)
    return () => {
      map.off('move', update)
      map.off('resize', update)
    }
    // `poi`, not `poi.lon`/`poi.lat`: a mile arriving late or a source line
    // appearing changes the card's HEIGHT, and a placement measured against
    // the old height would leave a flipped card overlapping its pin.
  }, [map, poi, card])

  return placement
}

export function PoiCard({ poi, map, onClose }: PoiCardProps) {
  const cardRef = useRef<HTMLDivElement | null>(null)
  const placement = usePinAnchor(map, poi, cardRef)
  const source = sourceLabel(poi.source)

  // A photo that 404s becomes the placeholder, not a broken-image glyph over
  // the name. State resets when the URL changes: a fresh download pointing at
  // a working photo should get to show it.
  const [photoFailed, setPhotoFailed] = useState(false)
  useEffect(() => setPhotoFailed(false), [poi.photoUrl])

  const accent =
    poi.type in POI_COLORS ? POI_COLORS[poi.type as PoiType] : POI_FALLBACK_COLOR
  const showPhoto = poi.photoUrl !== undefined && !photoFailed

  return (
    <div
      ref={cardRef}
      className="poi-card"
      role="dialog"
      aria-label="Waypoint"
      style={{
        // A transform rather than left/top, so following a pan is a
        // composite step per frame instead of a relayout per frame.
        transform:
          placement === null
            ? undefined
            : `translate(${placement.left}px, ${placement.top}px)`,
        // The category accent, for the placeholder's wash and glyph. Inline
        // because only this file knows the type; the stylesheet cannot.
        ['--poi-accent' as string]: accent,
      }}
    >
      <div className="poi-card__media">
        {showPhoto ? (
          <img
            className="poi-card__photo"
            data-testid="poi-card-photo"
            src={poi.photoUrl}
            // Empty on purpose: the app knows nothing about the photo beyond
            // which waypoint it belongs to, and the name is the next line
            // down. Announcing "photo of {name}" would say the name twice.
            alt=""
            onError={() => setPhotoFailed(true)}
          />
        ) : (
          <div className="poi-card__placeholder" data-testid="poi-card-placeholder">
            <svg
              className="poi-card__glyph"
              viewBox="0 0 1 1"
              aria-hidden="true"
              focusable="false"
            >
              <path d={poiGlyphPath(poi.type)} fillRule="evenodd" />
            </svg>
          </div>
        )}

        <button type="button" className="poi-card__close" onClick={onClose}>
          <span className="visually-hidden">Close waypoint details</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <div className="poi-card__body">
        <h2 className="poi-card__name">{poi.name}</h2>

        {/* One line, two facts, separate elements: the mile stays mono like
            every other mile on this screen, and the dot between them is
            punctuation for eyes only. */}
        <p className="poi-card__meta">
          <span>{typeLabel(poi.type)}</span>
          {poi.mile !== undefined && (
            <>
              <span aria-hidden="true">·</span>
              <span className="poi-card__mile">{`mi ${mile(poi.mile)}`}</span>
            </>
          )}
        </p>

        {poi.confidence === 'low' && (
          <p className="poi-card__unverified" role="note">
            Unverified — nobody has confirmed this one is really there.
          </p>
        )}

        <p className="poi-card__coords">
          <span className="visually-hidden">Latitude, longitude: </span>
          {coordinates(poi.lat, poi.lon)}
        </p>

        {source !== null && <p className="poi-card__source">{`From ${source}.`}</p>}
      </div>
    </div>
  )
}
