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
// The photo slot is held to the same rule. The pipeline can now carry
// imagery (fetch_poi_images.py matches openly-licensed, recent Wikimedia
// Commons photos to POIs), but most waypoints will never have an eligible
// photo - so `photoUrl` stays optional and the empty slot shows the
// category's own silhouette on its accent: honest iconography, not a stock
// photo pretending to be the shelter. When a photo does ship, its credit
// line ships with it - naming the photographer and licence is the condition
// CC BY/BY-SA attach to using the photo at all, and dating it is this app's
// own honesty-about-uncertainty rule (OurHikeValues.md #4) applied to
// somebody else's camera.
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
import { poiPhotos, type PoiPhoto } from '../lib/trailData'

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
   * How many people the shelter sleeps, when the pipeline could publish a
   * number for it.
   *
   * Optional twice over: only shelters have one at all, and ATC's layer does
   * not carry capacity, so the figure comes from a list joined on by
   * pipeline/build_shelter_capacity.py that leaves some shelters blank on
   * purpose. Absent means unknown - the line is omitted rather than shown
   * empty, because a hiker deciding whether to push on to the next shelter
   * is better served by no answer than by a made-up one.
   */
  capacity?: number
  /**
   * One sentence about the place - what it is built of, what it has, when it
   * went up - for shelters and campsites.
   *
   * The pipeline composes it from ATC's inventory columns, so it is a run of
   * stated facts rather than anybody's prose, and where ATC's maintainers
   * wrote a note of their own it is quoted as theirs. Optional: no other
   * waypoint type has one, and a phone that downloaded before it existed has
   * none at all.
   */
  description?: string
  /**
   * A photo of the place, when one exists.
   *
   * Published as photo_* properties on the POI artifacts (pipeline
   * fetch_poi_images.py + export_poi.py: openly-licensed Wikimedia Commons
   * photos with a recent EXIF capture date, matched by proximity). Most
   * waypoints have no eligible photo, and a photo is optional either way:
   * its absence is the placeholder, never a broken image or a withheld card.
   */
  photoUrl?: string
  /** The Commons file page - full licence terms, history, original file.
   *  The credit line links here when present. */
  photoPage?: string
  /** Who took it. For CC BY/BY-SA photos the pipeline guarantees this is
   *  set - naming the author is the condition of use, not a courtesy. */
  photoAuthor?: string
  /** The licence's short name, e.g. "CC BY-SA 4.0". */
  photoLicense?: string
  /** EXIF capture date, ISO "YYYY-MM-DD". Shown as a month: a photo's age
   *  is a fact the hiker gets, same rule as the unverified sentence. */
  photoTaken?: string
  /** Every photo this waypoint has, the one above included as the first
   *  (#471). Read through `poiPhotos`, never directly - a phone that
   *  downloaded its map before #471 has the flat fields and no list. */
  photos?: PoiPhoto[]
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

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/**
 * "Jun 2025" from an ISO capture date - month precision is honest about what
 * an EXIF date is worth and short enough for a credit line. Formatted by
 * hand rather than through Date: "2025-06-18" parsed as a Date is UTC
 * midnight, which toLocaleDateString renders as the previous month's last
 * day in any western-hemisphere timezone.
 */
function photoMonth(taken: string | undefined): string | null {
  if (taken === undefined) return null
  const match = /^(\d{4})-(\d{2})/.exec(taken)
  if (match === null) return null
  const month = Number(match[2])
  if (month < 1 || month > 12) return null
  return `${MONTHS[month - 1]} ${match[1]}`
}

/**
 * The whole credit line, or null when there is nothing to say. Author and
 * licence are the parts CC attribution requires; the month is this app's own
 * honesty rule applied to the photo. A photo can legitimately have no
 * author (public domain) - the line simply shortens.
 */
function photoCredit(photo: PoiPhoto): string | null {
  const parts = [photo.author, photo.license, photoMonth(photo.taken)].filter(
    (part): part is string => typeof part === 'string' && part !== '',
  )
  if (parts.length === 0) return null
  return `Photo: ${parts.join(' · ')}`
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

  // Every photo, not just the card one (#471). `poiPhotos` is what makes a
  // phone that downloaded before this keep working: it rebuilds a one-entry
  // list from the flat fields, which is what a single photo always meant.
  const photos = poiPhotos(poi)
  const [index, setIndex] = useState(0)
  // Back to the first whenever the card becomes a different waypoint.
  // Without this, opening a shelter with five photos, paging to the fifth and
  // then tapping a shelter with two would index past the end.
  useEffect(() => setIndex(0), [poi.id])
  const current = photos[index]

  // A photo that 404s becomes the placeholder, not a broken-image glyph over
  // the name. State resets when the URL changes - which is now also what
  // happens when a hiker pages, so one missing image does not condemn the
  // rest of the gallery to the placeholder.
  const [photoFailed, setPhotoFailed] = useState(false)
  useEffect(() => setPhotoFailed(false), [current?.url])

  const accent =
    poi.type in POI_COLORS ? POI_COLORS[poi.type as PoiType] : POI_FALLBACK_COLOR
  const showPhoto = current !== undefined && !photoFailed
  const credit = current === undefined ? null : photoCredit(current)

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
            src={current.url}
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

        {/* The credit rides the photo, never the placeholder: it is a fact
            about a photo on screen, and the licence's price for it being
            there. A link when the file page is known - full terms live
            there - and plain text when it is not, because a credit is owed
            either way. */}
        {showPhoto &&
          credit !== null &&
          (current.page !== undefined ? (
            <a
              className="poi-card__credit"
              href={current.page}
              target="_blank"
              rel="noreferrer"
            >
              {credit}
            </a>
          ) : (
            <span className="poi-card__credit">{credit}</span>
          ))}

        {/* Only when there is somewhere to go. 56 of 489 POIs have exactly
            one photo, and a pair of dead arrows on those is chrome that
            teaches a hiker the controls mean nothing.

            Wrapping at both ends rather than disabling: the gallery is a
            handful of pictures, not a list to get lost in, and a control
            that sometimes does nothing is worse on a cold morning with
            gloves than one that always does something.

            Gated on the LIST, not on the current photo having loaded. This
            is offline-first: a URL the cache no longer holds is routine, and
            hiding the controls behind `showPhoto` would let one missing
            image trap a hiker on the placeholder with the other photos
            unreachable. The arrows over a placeholder are the way out. */}
        {photos.length > 1 && (
          <div className="poi-card__photo-nav">
            <button
              type="button"
              className="poi-card__photo-step"
              onClick={() => setIndex((at) => (at - 1 + photos.length) % photos.length)}
            >
              <span className="visually-hidden">Previous photo</span>
              <span aria-hidden="true">‹</span>
            </button>
            {/* Announced politely rather than as a live region: a hiker
                stepping through photos is already looking at the card, and
                the count is context for the arrows rather than news. */}
            <span className="poi-card__photo-count" data-testid="poi-card-photo-count">
              {index + 1}/{photos.length}
            </span>
            <button
              type="button"
              className="poi-card__photo-step"
              onClick={() => setIndex((at) => (at + 1) % photos.length)}
            >
              <span className="visually-hidden">Next photo</span>
              <span aria-hidden="true">›</span>
            </button>
          </div>
        )}

        <button type="button" className="poi-card__close" onClick={onClose}>
          <span className="visually-hidden">Close waypoint details</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <div className="poi-card__body">
        <h2 className="poi-card__name">{poi.name}</h2>

        {/* One line, up to three facts, separate elements: the mile stays
            mono like every other mile on this screen, and the dots between
            them are punctuation for eyes only. */}
        <p className="poi-card__meta">
          <span>{typeLabel(poi.type)}</span>
          {poi.mile !== undefined && (
            <>
              <span aria-hidden="true">·</span>
              <span className="poi-card__mile">{`mi ${mile(poi.mile)}`}</span>
            </>
          )}
          {poi.capacity !== undefined && (
            <>
              <span aria-hidden="true">·</span>
              {/* "Sleeps 8", not "8": the bare number beside a mile reads as
                  another distance. */}
              <span>{`Sleeps ${poi.capacity}`}</span>
            </>
          )}
        </p>

        {poi.description !== undefined && (
          <p className="poi-card__description">{poi.description}</p>
        )}

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
