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
// TWO HEIGHTS, AND ONLY THE FIRST ONE IS TETHERED (#941). What is written
// above is the PEEK, which is what a tap opens: the name, the category, the
// mile, the existence sentence where it is true, one condition line, and the
// two ends of that type's scale as buttons. It is small enough to leave the
// map around it readable, which is what makes hanging off a pin worth doing.
//
// The card used to be that AND the whole record - the photograph, the history,
// the composer, the description, the coordinates, the provenance - in one
// column with no fold, so a hiker who tapped a spring got a 16:10 photo box
// and a paragraph about OpenStreetMap above the one-tap answer they had
// stopped to give. That is now one deliberate pull away, in place: a sheet
// against the canvas's bottom edge on a phone, a column docked to the map's
// right on a desktop. The opened card is NOT tethered - it points at nothing,
// so it claims nothing - and `usePinAnchor` is told so rather than left
// measuring a sheet against a pin every frame of a pan.
//
// One continuous scroll rather than lanes, which was a choice between two
// drawn options: conditions, then the composer, then the quiet stuff. Lanes
// would have filed the unverified sentence under an "About" tab, and an
// existence claim about a water source is not a thing to make a hiker go
// looking for.
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
// WHICH IS WHY THE PEEK NEVER SHOWS A PHOTOGRAPH. The credit is the price of
// showing the photo at all, and the peek has no line to spend on an
// institutional attribution string. So the peek shows the silhouette for
// every waypoint, photo or not, and the photograph and its credit arrive
// together on the pull - or not at all. A thumbnail with the credit "one tap
// away" would be the licence breach with extra steps.
//
// The one line that is not a bare fact is the unverified sentence, and it is
// the reason this card is worth having. The pin already says it with a broken
// rim (map/poiIcons.ts), which is a channel someone has to have learned to
// read. OurHikeValues.md #4 asks for uncertainty in words as well - "a smaller
// feature set hikers can trust beats a flashy one they have to second-guess" -
// so tapping the pin is where the words are.
//
// ONE CARD FOR A PLACE WITH PARTS. A shelter, its privy and its campsite are
// one site drawing one pin (#524, map/poiSites.ts), so since that landed the
// members have had no pin to tap and no gesture anywhere in the app reached
// them. The strip of chips is that gesture (#526, features/POI_SITES.md §5):
// every part of the site, each carrying the icon the map draws for it, and
// tapping one swaps the card to that part's own detail - its photo and
// gallery, its description, its coordinates, its unverified line.
//
// The strip lives in the OPENED card since #941, not on the peek. A hiker who
// tapped a shelter pin is answering a question about the shelter; picking a
// different part of the site out of it is the next thing they do, and the peek
// has two lines and cannot be both. Every part is still one pull and one tap
// away, which is the same number of taps it was before the peek existed - the
// pull replaced the scroll that used to be in front of the strip.
//
// The part you are on is a chip too, first in the row and marked as current.
// The issue's own sketch listed only the members, on the reasoning that the
// anchor is the card you are already reading; including it makes the row a
// complete picture of the place rather than a list with one part missing from
// it, and - since tapping a chip replaces the body - it is also the way back.
//
// Not a modal, at either height. The map behind it stays live and pannable -
// panning is how the PEEK is used, it rides along with its pin, and the opened
// card leaves the map above it visible on a phone and beside it on a desktop
// on purpose - and claiming `aria-modal` would
// tell a screen-reader user the rest of the screen is inert when it is not.
// Same call ClosureSheet makes.

import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { typeLabel } from './legendLabels'
import { isNoteScopedType } from '../lib/fieldNotes'
import { sourceLabel } from './poiSources'
import { placePoiCard, type CardPlacement } from './poiCardPlacement'
import { poiColor, poiGlyphPath } from '../map/poiIcons'
import { MapIcon } from '../map/MapIcon'
import { siteDistanceFeet } from '../map/poiSites'
import { describeNearby, type NearbyPart } from '../lib/nearbyClause'
import { waypointDistance } from '../lib/waypointDistance'
import type { HikeDirection } from './Header'
import { formatShortDistance, type UnitSystem } from '../lib/units'
import { PhotoUnusable, preparePhoto } from '../lib/reportPhoto'
import { exifCaptureDate } from '../lib/exifDate'
import { CARD_PHOTO_EDGE, type OwnPhotoSource } from '../lib/poiPhotos'
import { useOwnPhotos, type OwnCardPhoto } from '../lib/useOwnPhotos'
import { useCommunityPhotos } from '../lib/useCommunityPhotos'
import { enqueueAction } from '../lib/outbox'
import { syncOutbox } from '../lib/outboxSync'
import { FieldNoteSection, type FieldNoteContext } from './FieldNoteSection'
import { remainingLabel, sharePhase, takenClaimForShare } from '../lib/photoShare'
import { PoiShareSheet } from './PoiShareSheet'
import type { PoiPhotoSummary } from '../lib/api'

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
   * How far the nearest water source is, in feet, by ATC's own measurement
   * (pipeline/build_water_distance.py).
   *
   * Carried by shelters, campsites, and the water members the pipeline
   * synthesizes onto their sites from the same figure (#694). Those members
   * inherit the site's coordinates because ATC states how far and never
   * where - which is exactly why partDistance prefers this number over a
   * coordinate-derived one: measuring the inherited position would print
   * "0 m" for a distance the data actually knows. Absent means nobody has
   * published one, never "no water" - the capacity rule.
   */
  waterDistanceFt?: number
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
   * What is around this one, when it anchors a site: a privy, a campsite, the
   * water ATC's own index puts nearest (#614, #625).
   *
   * A phrase and a distance per part rather than the finished sentence the
   * pipeline used to publish - `describeNearby` writes the sentence, in the
   * units this hiker chose, which is a question no artifact composed months ago
   * could have answered. Absent on every POI that anchors nothing, and on any
   * copy downloaded before the field existed.
   */
  nearby?: NearbyPart[]
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
  /**
   * Every photo of this place, card photo first, when there is more than one.
   *
   * ATC's facility layers carry up to ten per POI. Absent for a single photo
   * and for any release published before galleries existed - the flat fields
   * above are then the whole story, and the card renders exactly as it did.
   */
  photos?: CardPhoto[]
}

export interface PoiCardProps {
  poi: PoiDetail
  /**
   * Every part of the site this waypoint belongs to, anchor first - built by
   * map/poiSites.ts's `siteRoster` and handed down by the shell, which is the
   * only layer holding the other POIs.
   *
   * Absent or a single entry means there is nothing to offer and the card
   * renders exactly as it did before sites existed: no strip, no group, no
   * change of any kind. That is the same backward-compatibility rule every
   * optional field above states - a phone that downloaded before #523 published
   * the grouping has no site keys at all, so its cards must be the old cards
   * rather than one chip that leads nowhere.
   */
  site?: readonly PoiDetail[]
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
  /**
   * Feet or metres, for every distance on this card (lib/units.ts).
   *
   * Handed down like MapScreen's own, and defaulted the way every other
   * `units` prop in the app is - a caller that has not thought about it gets
   * the trail's own units rather than a crash. It reaches two places, and they
   * are the two that used to disagree: the chips, and the nearby sentence.
   */
  units?: UnitSystem
  /**
   * The conditions section's world: this place's notes, the hiker's own
   * standing (reporter type, the #759 opt-in), and where a tap or an
   * escalation goes (chrome/FieldNoteSection.tsx). Absent means the shell
   * has not wired field notes - a test rendering the card alone, or a
   * screenshot - and the card renders exactly as it did before they
   * existed, which is the same backward-compatibility rule every optional
   * field above states.
   */
  noteContext?: FieldNoteContext
  /**
   * The hiker's own mile, for the "how far ahead" line (#953).
   *
   * Undefined wherever `positionLine` would not print a mile either - location
   * off, denied, no signal, still looking, no trail data, a fix that will not
   * place on the centerline - and the line is simply absent for all of them.
   * The header is where a hiker learns WHICH of those it is, in words chosen
   * per state; a card repeating that in six variants would be six more places
   * for the two to disagree.
   */
  hikerMile?: number
  /**
   * The settled walking direction, or undefined while the tracker has not
   * committed.
   *
   * The word this decides is a safety claim, not a decoration:
   * lib/waypointDistance.ts carries why it is the OBSERVED direction rather
   * than a declared hike's, and why "away" is what an uncommitted tracker
   * gets rather than a guess.
   */
  direction?: HikeDirection
  onClose: () => void
  /** Where the share sheet's portal lands - the map screen's root, so the
   *  sheet hides with the held map instead of floating over another tab
   *  (PoiShareSheet.tsx's header has the whole argument). Optional for the
   *  same bare-render reason every optional field above states. */
  sheetContainer?: HTMLElement | null
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
function photoCredit(photo: CardPhoto): string | null {
  const parts = [photo.author, photo.license, photoMonth(photo.taken)].filter(
    (part): part is string => typeof part === 'string' && part !== '',
  )
  if (parts.length === 0) return null
  return `Photo: ${parts.join(' · ')}`
}

/** One photo as the card renders it, whichever shape the POI carried. */
interface CardPhoto {
  url: string
  page?: string
  author?: string
  license?: string
  taken?: string
  /** Present when this is the hiker's own photo (rung 1 of the ladder) -
   *  what the manage strip needs to offer choose and remove, and what the
   *  credit line keys on to say "Your photo" instead of naming an author. */
  own?: OwnCardPhoto
  /** Present when this is a community photo (rung 2) - what the
   *  report-this-photo path needs (#579). */
  community?: PoiPhotoSummary
}

/**
 * Every photo this card can show, in order, card photo first.
 *
 * Two shapes converge here. A POI published before galleries existed has only
 * the flat `photo*` fields; one published after also carries `photos`, whose
 * first entry describes the same image. Normalising to one list means the
 * render path has a single shape and the controls appear exactly when there
 * is somewhere to go.
 */
function cardPhotos(poi: PoiDetail): CardPhoto[] {
  if (poi.photos !== undefined && poi.photos.length > 0) return poi.photos
  if (poi.photoUrl === undefined) return []
  return [
    {
      url: poi.photoUrl,
      ...(poi.photoPage !== undefined ? { page: poi.photoPage } : {}),
      ...(poi.photoAuthor !== undefined ? { author: poi.photoAuthor } : {}),
      ...(poi.photoLicense !== undefined ? { license: poi.photoLicense } : {}),
      ...(poi.photoTaken !== undefined ? { taken: poi.photoTaken } : {}),
    },
  ]
}

/** The credit-slot line for the hiker's own photo: no author to name, but
 *  dated in the same month voice as every other photo on the card. */
function ownCredit(photo: OwnCardPhoto): string {
  const month = photoMonth(photo.taken)
  return month === null ? 'Your photo' : `Your photo · ${month}`
}

/**
 * A picked photo waiting on the hiker's keep-or-discard (#571).
 *
 * Held entirely in memory: the store is only written on Keep, so Discard is
 * "nothing was written" rather than "written, then deleted" - the difference
 * the issue calls the part worth spending design on. Everything here is
 * revoked and dropped together, whichever way the review ends.
 */
interface PhotoReview {
  /** Object URL of the prepared rendering - the preview shows exactly the
   *  bytes a Keep would store, never the original it was made from. */
  url: string
  blob: Blob
  /** Capture date read from the ORIGINAL before the re-encode destroyed it. */
  taken: string | null
  source: OwnPhotoSource
  /** The original file, offered for saving when it was taken through the
   *  app's camera and so exists nowhere else (#573). Null for a library
   *  pick, whose original is already in the hiker's library. */
  originalUrl: string | null
  originalName: string
}

/**
 * The honest sentence under a hiker's own photo (#573), and it is two
 * sentences because the truth differs by path. POI_PHOTOS.md's not-an-archive
 * promise rests on "your library has the original" - true for a photo picked
 * from the library, false for one taken through the app's camera, where the
 * small copy may be the only copy that ever existed. The strip is where the
 * doc says which is which, "rather than a settings page nobody opens".
 */
function ownPhotoDisclosure(source: OwnPhotoSource): string {
  return source === 'library'
    ? 'A copy sized for this card — your library has the original.'
    : 'Taken in OurHike. Unless you saved the original, this small copy is the only one.'
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
 * One metre, in feet - pipeline/lib/poi_description.py's `MIN_PART_FT`, which
 * floors the distances the pipeline publishes for the same reason.
 *
 * A stated distance arrives unfloored (`water_distance_ft` is its own column,
 * not a nearby part), and a card claiming a hiker walks zero of anything to
 * reach water reads as a bug rather than as the very short walk it is
 * asserting. Stated in the coarser unit, so neither system rounds it away:
 * flooring at 1 ft would still print "0 m" for a metric hiker, which is the
 * defect arriving in the other unit. #694 floored it at a metre for exactly
 * this reason, back when this line printed only metres.
 */
const MIN_PART_FT = 3.28084

/**
 * How far a part of the site is from the pin, for its chip.
 *
 * FROM THE PIN, NOT FROM THE PART CURRENTLY OPEN. The pin is the one point on
 * this site the hiker can see, and it is where they are standing when they ask;
 * measuring from whichever chip was tapped last would rewrite every other
 * number in the row on every tap, which is churn in a strip that is meant to be
 * readable at a glance - and would change the strip's height in the process.
 *
 * "The pin" and not "the anchor", which this said until #607/#609 made them
 * different things: a site whose anchor the legend filters out gives the pin to
 * a member, and the number a hiker wants is the offset from what they can
 * actually see. See the note where the caller resolves it.
 *
 * MEASURED HERE RATHER THAN READ OFF THE ARTIFACT, and that is the reason:
 * `nearby`'s distances are measured from the ANCHOR, because that is the point
 * the pipeline knows a hiker can see. When the two are the same point - which
 * is every site the legend has not filtered - both come out of the same
 * equirectangular formula with the same constant, so the chip and the sentence
 * agree to well inside the rounding. When they are not, the chip is right and
 * the sentence is answering a different question, which is what it did before
 * this card existed.
 *
 * The hiker's own units since #625 (lib/units.ts). This was the single line in
 * the app exempt from that standard, held open while the same distances were
 * also published as prose in metres: converting one half would have put
 * `Privy · 130 ft` over a sentence saying 40 m. Both halves moved together in
 * the end, which is what the exemption was waiting for.
 *
 * A STATED DISTANCE BEATS A COORDINATE DISTANCE (#694). A water member the
 * pipeline synthesized from ATC's distance-to-water inherits the site's own
 * coordinates - ATC states how far, never where - so measuring it would print
 * "Water · 0 ft" beside a sentence saying 121 ft, the drift above in its worst
 * form. Such a member carries the stated figure as `waterDistanceFt`, and it
 * wins whenever present; real mapped members carry none and keep the measured
 * offset exactly as before.
 *
 * That figure needs no conversion here, which is the one simplification #625
 * hands #694: ATC states it in feet, the artifact publishes it in feet, and
 * feet is what lib/units.ts formats from. It reached this line as metres only
 * because this line printed metres.
 */
function partDistance(pin: PoiDetail, part: PoiDetail, units: UnitSystem): string {
  const feet =
    part.type === 'water' && part.waterDistanceFt !== undefined
      ? Math.max(MIN_PART_FT, part.waterDistanceFt)
      : siteDistanceFeet(pin, part)
  return formatShortDistance(feet, units)
}

/**
 * The card's screen position, re-projected on every camera move.
 *
 * Layout effect rather than effect, so the first placement lands before the
 * first paint - the card must never flash at the canvas origin on its way to
 * the pin. Measuring the card in the same pass is safe for the same reason:
 * by the time this runs the DOM holds the final content, and reading
 * `offsetWidth` forces layout synchronously.
 *
 * TWO POIS, AND THEY ARE NOT INTERCHANGEABLE. `anchor` is the point projected:
 * the one thing on this site with a pin, since #524 removed the members' own.
 * Projecting the shown part instead would hang the card off a position where
 * nothing is drawn - the mild form of the refusal features/POI_SITES.md makes
 * of spiderfying, which is that drawing a privy 80 px from where it is says
 * something untrue about where it is. `shown` is only ever a dependency, and it
 * is there because it changes the card's HEIGHT (see below).
 */
function usePinAnchor(
  map: MapLibreMap | null,
  anchor: PoiDetail,
  shown: PoiDetail,
  card: RefObject<HTMLDivElement | null>,
  /** Whether the card is still hanging off its pin. False once it has been
   *  pulled open (#941), which is a sheet or a docked column and is placed by
   *  the stylesheet - there is no pin-relative answer to give. */
  tethered: boolean,
): CardPlacement | null {
  const [placement, setPlacement] = useState<CardPlacement | null>(null)

  useLayoutEffect(() => {
    if (map === null || !tethered) return

    const update = () => {
      // Unreachable, and kept for the type checker: the ref is attached to
      // the element this hook's caller always renders, and effects run after
      // it is in the DOM.
      /* v8 ignore next */
      if (card.current === null) return

      const canvas = map.getCanvas()
      const next = placePoiCard(
        map.project([anchor.lon, anchor.lat]),
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
    // `anchor`, not `anchor.lon`/`anchor.lat`: a mile arriving late or a source
    // line appearing changes the card's HEIGHT, and a placement measured
    // against the old height would leave a flipped card overlapping its pin.
    //
    // `shown` is in here for that same reason and a much larger dose of it.
    // Tapping a chip is not a camera move, so nothing on the map fires and
    // nothing else would re-measure - the placement would keep the height of
    // the part the hiker just left until the next pan. A privy is several lines
    // shorter than its shelter (no capacity, usually no description, often no
    // photo credit), and a card placed BELOW its pin is positioned by its own
    // height, so a stale one sits over the pin it is describing.
  }, [map, anchor, shown, card, tethered])

  return placement
}

export function PoiCard({
  poi,
  site = [],
  map,
  units = 'imperial',
  noteContext,
  hikerMile,
  direction,
  onClose,
  sheetContainer,
}: PoiCardProps) {
  const cardRef = useRef<HTMLDivElement | null>(null)

  // THE ANCHOR IS NOT THE POINT THIS CARD HANGS OFF, AND THE DIFFERENCE IS NOT
  // COSMETIC. `siteRoster` puts the anchor first whichever part of the site it
  // was asked about, so `site[0]` is the site's own identity - what the place is
  // called - and that is the ONE thing it is used for below.
  //
  // Everything positional keys on `poi` instead, because `poi` is the point
  // CARRYING THE PIN. That is a precondition of this card, not a coincidence:
  // map/poiLayers.ts builds its features from `composeSites().drawn` and writes
  // the carrier's id, and a tap is the only thing that opens a card, so what the
  // shell selected is by construction what is drawn.
  //
  // AND THE CARRIER IS NOT ALWAYS THE ANCHOR. #607/#609 gave a site's members
  // their pins back when the legend filters the anchor out: hide shelters, and
  // the site redraws as its highest-priority drawn member, so tapping it selects
  // the PRIVY. Keying the projection on `site[0]` there would hang the card off
  // the shelter - a point with nothing drawn at it, 42 m away at the median,
  // which is 11 px at z14 and 165 px at z18 - which is the mild form of the
  // spiderfying features/POI_SITES.md refuses, and the exact failure keying on
  // the anchor was meant to avoid.
  //
  // So when #527 lets search open a member's card directly, `poi` will no longer
  // be the carrier and this card will have to be TOLD which point is - the shell
  // computes the composition and knows. It is not knowable from here, and
  // guessing `site[0]` is wrong in the case that already exists.
  const anchor = site[0] ?? poi

  // Which part of the site the card is showing. Held here rather than lifted to
  // the shell's `selectedPoiId`, which is fed to a map that has no pin for a
  // member to select and whose setter closes the legend on the way past.
  //
  // Reset on the waypoint, because MapScreen renders this card without a React
  // key: the state survives a change of pin, and opening a different shelter
  // must not land on the last one's privy.
  const [shownId, setShownId] = useState(poi.id)
  useEffect(() => setShownId(poi.id), [poi.id])

  // THE CARD OPENS SHUT (#941). A tap on a pin asks "what did I tap, and how
  // is it right now", and the peek is the whole answer to that; the record -
  // the history, the composer, the photograph, the coordinates, the
  // provenance - is one deliberate pull away.
  //
  // Reset on the waypoint for `shownId`'s reason, and it matters more here:
  // MapScreen renders this card without a React key, so a card left open on
  // one shelter would have the next pin's card open before its hiker asked
  // for it - and an opened card is a sheet, which is most of the map.
  const [open, setOpen] = useState(false)
  useEffect(() => setOpen(false), [poi.id])

  // The `?? poi` is load-bearing rather than defensive. On the render between a
  // new waypoint arriving and that reset effect firing, `shownId` still names
  // the previous site's privy - and falling back to the waypoint the shell asked
  // for makes that frame already correct instead of blank. The waypoint, not
  // `anchor`: what this card opens on is what was selected, which is the anchor
  // only until something selects a member (see above).
  const shown = site.find((part) => part.id === shownId) ?? poi

  // Tethered only while it peeks: an opened card has let go of its pin, so
  // there is nothing for the geometry to answer and re-measuring it on every
  // frame of a pan would re-render a sheet to move it nowhere.
  const placement = usePinAnchor(map, poi, shown, cardRef, !open)
  const source = sourceLabel(shown.source)
  // Whether the conditions surface will render anything - the same question
  // FieldNoteSection answers for itself by returning null, asked here because
  // the section heading, the peek's expand label and the opened card's
  // Conditions band all have to agree with it.
  const notesShown = noteContext !== undefined && isNoteScopedType(shown.type)
  // `shown`, not `poi`: tapping a chip swaps this card to that part's own
  // detail, and a part that anchors a site of its own - a campsite with a privy
  // beside it - has parts of its own to name. Read off whichever waypoint the
  // card is currently showing, like the description and the source line above.
  const nearby = describeNearby(shown.nearby, units)

  // The two regions a chip swaps, named so `aria-controls` can point at them.
  // Through `useId` rather than a pair of constants because ids have to be
  // unique in a document and nothing here can promise there is one card - a
  // test rendering two, or a compare view, would otherwise have both cards'
  // chips controlling the first card's boxes.
  const regionId = useId()
  const mediaId = `${regionId}media`
  const bodyId = `${regionId}body`

  // What to say out loud when a chip replaces the card under someone who cannot
  // see it happen. `aria-current` below is an ARIA *property*: a screen reader
  // announces it on ARRIVAL at the chip rather than when it flips - unlike
  // aria-pressed or aria-selected - so activating a chip otherwise moves the
  // heading, the coordinates, the provenance, the unverified sentence and the
  // photograph in complete silence. This is the half of screens/Tabs.tsx's
  // contract that role="tab"/role="tabpanel" would have given for free and that
  // the plain-button markup has to say for itself.
  //
  // Empty until a chip is tapped, and reset with the waypoint: a reader arriving
  // at a freshly opened card is about to be read the card, and a region already
  // holding "Showing X" would either say it twice or announce the last card's
  // part on this one.
  const [announced, setAnnounced] = useState('')
  useEffect(() => setAnnounced(''), [poi.id])

  // Rungs 1 and 2 of POI_PHOTOS.md's precedence ladder, ahead of everything
  // the artifacts carry. Rung 1: the hiker's own photos - "your own photo
  // always wins, and nothing can displace it", not a better-composed photo,
  // not a fresher one, so the merge is an unconditional prepend. Rung 2: the
  // community's, in the backend's own order (the club's pins first, then
  // newest), reaching this list only while the network has answered and
  // degrading silently to the ATC/Commons rungs when it has not (#578). The
  // ladder falls through only downward: a hiker who never added a photo, on
  // a phone that never reached the backend, gets exactly the list this line
  // built before either rung existed.
  const own = useOwnPhotos(shown.id)
  const community = useCommunityPhotos(shown.id)
  const photos: CardPhoto[] = [
    ...own.photos.map((photo) => ({ url: photo.url, taken: photo.taken, own: photo })),
    ...community.map((photo) => ({
      url: photo.url,
      // "YYYY-MM": month precision is all the public surface carries, and
      // photoMonth reads it as happily as a full date.
      taken: photo.taken_month,
      // Null while the photographer's anonymity window holds - withheld by
      // their request. The credit line then carries licence and month
      // without a name, which is provenance stated, not missing.
      ...(photo.attribution !== null ? { author: photo.attribution } : {}),
      license: photo.license,
      community: photo,
    })),
    ...cardPhotos(shown),
  ]

  // The keep-or-discard review for a just-picked photo (#571), plus the two
  // notes around it: "shrinking" while the re-encode runs, and the sentence
  // that says why a photo could not be taken in. The ref shadows the state
  // so discard can revoke whatever is CURRENTLY under review from effect
  // cleanups and late async arrivals without stale-closure risk.
  const [review, setReview] = useState<PhotoReview | null>(null)
  const reviewRef = useRef<PhotoReview | null>(null)
  const [preparing, setPreparing] = useState(false)
  const [photoNote, setPhotoNote] = useState<string | null>(null)
  const [removeArmed, setRemoveArmed] = useState(false)
  const cameraInput = useRef<HTMLInputElement | null>(null)
  const libraryInput = useRef<HTMLInputElement | null>(null)

  // Which part the card is on, readable from async completions: a photo
  // picked on the shelter must not attach its review to the privy a chip
  // swap landed on while the re-encode was running.
  const shownIdRef = useRef(shown.id)
  shownIdRef.current = shown.id

  const discardReview = useCallback(() => {
    const dropped = reviewRef.current
    if (dropped !== null) {
      URL.revokeObjectURL(dropped.url)
      if (dropped.originalUrl !== null) URL.revokeObjectURL(dropped.originalUrl)
    }
    reviewRef.current = null
    setReview(null)
  }, [])

  // The share sheet (#577) and the report chooser (#579), both scoped to
  // the part on screen the same way the review is.
  const [sharing, setSharing] = useState(false)
  const [reportChooser, setReportChooser] = useState(false)

  // Swapping parts or waypoints drops an unkept review - nothing was
  // written, so there is nothing to keep - and clears the notes with it.
  // The cleanup shape means unmounting revokes too.
  useEffect(() => {
    setPhotoNote(null)
    setRemoveArmed(false)
    setSharing(false)
    setReportChooser(false)
    return discardReview
  }, [shown.id, discardReview])

  const pick = async (file: File | null, source: OwnPhotoSource) => {
    if (file === null) return
    // A second pick replaces the first: one review at a time.
    discardReview()
    setPhotoNote(null)
    setPreparing(true)
    try {
      // The capture date comes off the ORIGINAL file, in parallel with the
      // re-encode that destroys it - see lib/exifDate.ts.
      const [blob, taken] = await Promise.all([
        preparePhoto(file, CARD_PHOTO_EDGE),
        exifCaptureDate(file),
      ])
      if (shownIdRef.current !== shown.id) return
      const next: PhotoReview = {
        url: URL.createObjectURL(blob),
        blob,
        taken,
        source,
        originalUrl: source === 'camera' ? URL.createObjectURL(file) : null,
        originalName: file.name === '' ? 'photo.jpg' : file.name,
      }
      reviewRef.current = next
      setReview(next)
    } catch (error) {
      setPhotoNote(
        error instanceof PhotoUnusable
          ? error.message
          : 'That photo could not be prepared. Try another.',
      )
    } finally {
      setPreparing(false)
    }
  }

  const keep = async () => {
    const kept = reviewRef.current
    if (kept === null) return
    try {
      await own.add({ blob: kept.blob, taken: kept.taken, source: kept.source })
      discardReview()
      // Land on the front of the gallery, where the newly kept photo is
      // (or, for an old import, where the newest of their photos is).
      setPhotoIndex(0)
    } catch {
      // Storage refused - quota, private browsing, no IndexedDB. The review
      // stays up so the hiker can still save the original or try again;
      // saying "kept" and losing it would be the worse failure.
      setPhotoNote('This phone could not store the photo, so nothing was kept.')
    }
  }

  const removeOwn = async (id: string) => {
    setRemoveArmed(false)
    try {
      await own.remove(id)
      setPhotoIndex(0)
    } catch {
      setPhotoNote('This phone could not remove the photo.')
    }
  }

  // The share, once the sheet's "Share with every hiker" is tapped (#577).
  // Two records in order: the phone's memory of the decision, then the
  // queued act - and the capture-date claim is coarsened to its month
  // before it is ever queued, so the sheet's "the picture and the month"
  // is made true here rather than trusted to a server's rendering.
  const shareOwn = async (photo: OwnCardPhoto, flagged: 'nudity' | 'faces' | null) => {
    setSharing(false)
    try {
      await own.setShared(photo.id, new Date().toISOString())
      await enqueueAction(
        {
          kind: 'poi_photo_share',
          poiId: shown.id,
          taken: takenClaimForShare(photo.takenClaim),
          // The on-device screen's finding (#837), straight off the share
          // sheet - here and nowhere else. Null when nothing was found OR
          // the check could not run; the two are indistinguishable by
          // design (lib/photoScreen.ts).
          flagged,
        },
        photo.blob,
      )
      setPhotoNote(
        flagged === 'nudity'
          ? // The sheet's "Send it for review" step already said why; this
            // repeats the schedule truthfully - review gates it, not the
            // clock alone.
            'Queued to send for review. It leaves when you have signal, and appears once a moderator has looked.'
          : 'Queued to share. It leaves when you have signal and goes live about two hours after that.',
      )
      void syncOutbox()
    } catch {
      setPhotoNote('This phone could not queue the share, so nothing was shared.')
    }
  }

  // The withdrawal - "Take it back" inside the cooling-off window, "Stop
  // sharing" after it. Same act either way; what differs is what it can
  // still achieve, and the note says which.
  const withdrawOwn = async (photo: OwnCardPhoto, undo: boolean) => {
    try {
      await own.setShared(photo.id, null)
      await enqueueAction({ kind: 'poi_photo_withdraw', poiId: shown.id })
      setPhotoNote(
        undo
          ? 'Taken back. Nobody ever had it, so nothing was released.'
          : 'OurHike will stop showing it. Copies already made under the licence are beyond reach.',
      )
      void syncOutbox()
    } catch {
      setPhotoNote('This phone could not queue that, so nothing changed.')
    }
  }

  // Report a community photo (#579). Queued like every write - the report
  // sheet's own honesty holds here: the photo stays on the card until a
  // club moderator has looked.
  const reportCommunity = async (
    photo: PoiPhotoSummary,
    reason: 'wrong_place' | 'person' | 'other',
  ) => {
    setReportChooser(false)
    try {
      await enqueueAction({
        kind: 'poi_photo_report',
        poiId: shown.id,
        photoId: photo.id,
        reason,
      })
      setPhotoNote(
        'Reported. This goes to the maintaining club, and the photo stays on the card until one of them has looked.',
      )
      void syncOutbox()
    } catch {
      setPhotoNote('This phone could not queue the report.')
    }
  }

  // Which photo of this place is on screen. Reset when the card changes to a
  // different waypoint - opening a shelter after paging to photo 4 of the
  // last one must start at its own first photo, not its fourth. Keyed on the
  // part SHOWN, not on the tapped pin, because tapping through to the privy is
  // that same situation: photo 4 of the shelter must not decide which
  // photograph of the privy comes up first.
  const [photoIndex, setPhotoIndex] = useState(0)
  useEffect(() => setPhotoIndex(0), [shown.id])

  // A two-tap Remove disarms when the hiker moves on to another photo.
  useEffect(() => setRemoveArmed(false), [photoIndex])

  // Guarded rather than trusted: a re-render with a shorter list (a fresh
  // download of the same waypoint) must not index off the end.
  const current = photos[Math.min(photoIndex, photos.length - 1)]

  // A photo that 404s becomes the placeholder, not a broken-image glyph over
  // the name. State resets when the URL changes: a fresh download pointing at
  // a working photo should get to show it, and so should stepping to the next
  // photo after a broken one.
  const [photoFailed, setPhotoFailed] = useState(false)
  useEffect(() => setPhotoFailed(false), [current?.url])

  const accent = poiColor(shown.type)
  const showPhoto = current !== undefined && !photoFailed
  // "Your photo" instead of an author for rung 1: the one photo on this card
  // that needs no credit, because the hiker is looking at their own picture -
  // but it is still dated, in the same month voice, because the honesty rule
  // does not soften just because the photographer is the person reading it.
  const credit =
    current === undefined
      ? null
      : current.own !== undefined
        ? ownCredit(current.own)
        : photoCredit(current)
  // The hiker's own photo currently on screen, when there is one and no
  // review is covering the media box - what the manage strip renders for.
  const ownShown = review === null && !photoFailed ? current?.own : undefined
  // The month a Keep would date the photo, or null when the original
  // carried no capture date (it is then dated by the day it is added).
  const reviewMonth = review === null ? null : photoMonth(review.taken ?? undefined)
  // Controls only where they lead somewhere. Wrapping rather than disabling at
  // the ends: two photos and a dead "next" is a worse answer than a loop.
  const hasGallery = photos.length > 1
  const step = (delta: number) =>
    setPhotoIndex((i) => (i + delta + photos.length) % photos.length)

  // A strip only where it says something. One chip is the card you are already
  // reading, which is a control that answers a question nobody asked.
  const parts = site.length > 1 ? site : []

  /* One line, up to four facts, separate elements: the mile stays mono like
     every other mile on this screen, and the dots between them are
     punctuation for eyes only.

     THIS LINE IS WHERE THE CHIP'S WORDS WENT. The strip is pins alone, so the
     category and the distance of the part being read are said once, here, and
     the heading beside it already carries that part's name.

     Hoisted out of the markup because BOTH heights print it (#941) - it is the
     second line of the peek and the second line of the opened card's header -
     and two copies of a four-fact line is two places for a fifth fact to be
     added to only one of. */
  /* How far along the trail this place is from the hiker, and which way (#953).
     The second line the design pass behind #941 drew and #942 shipped without,
     on the grounds that the number "would have to be invented" - half true, and
     the half that was not is that the distance is a subtraction of two miles the
     app already holds. lib/waypointDistance.ts owns the part that DID have to be
     earned, which is the word: "ahead" said to a southbounder walking away from
     a spring is the opposite of the truth, on the subject this app can least
     afford to be wrong about.

     Null for every state where it cannot be said - no fix, no mile for the
     place, or a distance that rounds to zero - and then this row is exactly what
     it was before. */
  const distanceLine = waypointDistance({
    ...(shown.mile === undefined ? {} : { waypointMile: shown.mile }),
    ...(hikerMile === undefined ? {} : { hikerMile }),
    ...(direction === undefined ? {} : { direction }),
    units,
  })

  const metaLine = (
    <p className="poi-card__meta">
      <span>{typeLabel(shown.type)}</span>
      {shown.mile !== undefined && (
        <>
          <span aria-hidden="true">·</span>
          <span className="poi-card__mile">{`mi ${mile(shown.mile)}`}</span>
        </>
      )}
      {/* Directly after the mile it is derived from, and before the facts about
          the PLACE - its capacity, the part being read. "mi 1,407.2 · 0.3 mi
          ahead" is one thought read left to right: where it is, and where that
          is from here.

          Mono with the mile beside it, which is chrome.css's standing rule for
          this line and not a new choice: the parts' distances are already in
          that list because "it is the same kind of claim, read the same way",
          and this is the same claim again. Fixed width also keeps the row from
          twitching as the figure counts down, which is the reason the header's
          mile is mono and pads to one decimal. */}
      {distanceLine !== null && (
        <>
          <span aria-hidden="true">·</span>
          <span className="poi-card__distance">{distanceLine}</span>
        </>
      )}
      {shown.capacity !== undefined && (
        <>
          <span aria-hidden="true">·</span>
          {/* "Sleeps 8", not "8": the bare number beside a mile reads as
                  another distance. */}
          <span>{`Sleeps ${shown.capacity}`}</span>
        </>
      )}
      {/* How far the part being read is from the pin - the same
              `partDistance` the chips used, measured from the same point, so
              nothing about the number changed when it moved down here. Absent on
              the pin's own part, exactly as it was absent from the pin's own
              chip: the card hangs off that point, and "0 ft away" from the thing
              you are standing on is noise.

              "away" rather than a bare figure, and rather than a phrasing of its
              own. A bare `131 ft` next to `mi 2189.4` reads as a second distance
              of the same kind - the hazard "Sleeps 8" is spelt out for two lines
              up. `describeNearby` already says "away" for this exact claim on
              this same card, so borrowing its word keeps one voice rather than
              inventing a second; what "away" leaves implicit there and here is
              the point measured FROM, which is the pin and not the hiker. That
              ambiguity is inherited, not introduced, and it is the one thing on
              this line worth revisiting if somebody reports reading it as
              distance-to-walk. */}
      {shown.id !== poi.id && (
        <>
          <span aria-hidden="true">·</span>
          <span className="poi-card__part-distance">
            {`${partDistance(poi, shown, units)} away`}
          </span>
        </>
      )}
    </p>
  )

  /* The existence claim, and the reason this card is worth having (see the
     header of this file). Hoisted for `metaLine`'s reason, and placed by the
     same rule in both heights: as high as the card goes.

     It is never behind the expand. A hiker cannot act on "nobody has confirmed
     this spring exists" if they have to pull the card open to find it, and
     OurHikeValues.md #4 is the whole argument for printing it at all. */
  const unverifiedLine =
    shown.confidence === 'low' ? (
      <p className="poi-card__unverified" role="note">
        Unverified — nobody has confirmed this one is really there.
      </p>
    ) : null

  /* The conditions section (FIELD_NOTES.md, #759's card surface) - what the
     field has said about this place and the one-tap way to answer back.
     `shown`, not `poi`: a chip swap is a different place with its own notes,
     exactly as the description is.

     A function of the height rather than two call sites, so the peek and the
     opened card cannot come to disagree about which place they are filing a
     note against. */
  const conditions = (variant: 'peek' | 'open') =>
    noteContext === undefined ? null : (
      <FieldNoteSection
        poiId={shown.id}
        poiType={shown.type}
        // The existence axis this card already renders one value of
        // (`unverifiedLine` above): a dispute about a place upstream never
        // confirmed is a weaker claim, and #876's sentence says so rather
        // than counting it the same.
        unverified={shown.confidence === 'low'}
        lat={shown.lat}
        lon={shown.lon}
        {...(shown.mile !== undefined ? { mile: shown.mile } : {})}
        variant={variant}
        context={noteContext}
      />
    )

  return (
    <div
      ref={cardRef}
      className={`poi-card ${open ? 'poi-card--open' : 'poi-card--peek'}`}
      role="dialog"
      aria-label="Waypoint"
      style={{
        // A transform rather than left/top, so following a pan is a
        // composite step per frame instead of a relayout per frame.
        //
        // Only while it peeks. The opened card has let go of its pin - it is
        // a sheet against the canvas's bottom edge on a phone and a column
        // docked to its right on a desktop - and a transform here would fight
        // the position chrome.css gives it.
        transform:
          open || placement === null
            ? undefined
            : `translate(${placement.left}px, ${placement.top}px)`,
        // The category accent, for the placeholder's wash and glyph. Inline
        // because only this file knows the type; the stylesheet cannot.
        ['--poi-accent' as string]: accent,
      }}
    >
      {/* At the card's level rather than inside the media box, which is where
          it used to live and no longer can: the opened card leads with its
          heading and puts the photograph below, so the corner the close
          button is drawn for is not the photo's any more. One button, one
          corner, both heights. */}
      <button type="button" className="poi-card__close" onClick={onClose}>
        <span className="visually-hidden">Close waypoint details</span>
        <span aria-hidden="true">×</span>
      </button>

      {open ? (
        <>
          <div className="poi-card__header">
            {/* The grabber is the control, not a decoration painted to look
                like one. A sheet that shows a handle and does nothing when it
                is used is worse than a sheet with no handle, and this is the
                way back to the peek. */}
            <button
              type="button"
              className="poi-card__grabber"
              data-testid="poi-card-collapse"
              aria-expanded={true}
              onClick={() => setOpen(false)}
            >
              <span className="visually-hidden">Show less</span>
            </button>
            <h2 className="poi-card__name">{shown.name}</h2>
            {metaLine}
          </div>

          {/* Everything the peek held back, in one scroll rather than behind
              lanes: conditions, then the composer, then the quiet stuff. A
              hiker looking for a fact should not have to work out which tab
              somebody filed it under. */}
          <div className="poi-card__scroll" data-testid="poi-card-scroll">
            <div className="poi-card__body" id={bodyId}>
              {/* Every part of this place, the one you are on included.

                  NOT a `role="tablist"`, and the argument for that has CHANGED
                  SHAPE under #941 - which is worth saying rather than leaving a
                  comment that reads as settled when it is not.

                  It used to be structural and airtight: the photo, the gallery and
                  the credit are as member-specific as the text is, and they were
                  ABOVE this strip, so a `tabpanel` could only have contained the
                  text while the image it claimed to control changed silently over
                  the hiker's head. The alternative named here was "reorder the card
                  to put the photo inside a panel", rejected because it moves the
                  media box off the card's top edge and re-parents the close button
                  out of the corner it is drawn for.

                  That reorder has now happened for a different reason. The opened
                  card leads with its heading, the strip is above the photograph,
                  and the close button has moved to the card's own corner - so a
                  wrapper round the media and the body IS available, and the
                  geometry no longer decides this.

                  It stays plain buttons and `aria-current` on the one you are
                  reading, and the reason is now a choice rather than a constraint:
                  the strip is one of two navigations on this card (the other is the
                  pull that opened it), and a `tablist`'s arrow-key contract is a
                  second keyboard model to learn on a surface that already has one.
                  @unvalidated - nobody has watched a screen-reader user work this
                  card, and if #105/#106's field testing reaches assistive tech,
                  this is the decision to bring back.

                  What screens/Tabs.tsx's pattern is reused for is the part that
                  matters either way, which is its rule: ONE panel rendered, not
                  three hidden with CSS. There is one media box and one body here,
                  both driven from `shown`, so a part nobody is looking at has no
                  gallery buttons in the tab order and nothing for a screen reader
                  to announce.

                  The rest of that pattern's contract is what the two things after the
                  strip put back: `aria-controls` naming both regions a chip drives -
                  the objection above is to a tabpanel WRAPPER, and does not reach an
                  attribute that takes an ID-reference LIST - and a live region that
                  actually produces the announcement, since `aria-current` changing is
                  not one. */}
              {parts.length > 0 && (
                <div
                  className="poi-card__chips"
                  role="group"
                  // The anchor's own name, which is what the pipeline publishes as
                  // `site_name` (features/POI_SITES.md §3). Taken from the anchor
                  // itself - the same point the first chip stands for - so the two
                  // cannot disagree about what this place is called.
                  aria-label={`Parts of ${anchor.name}`}
                >
                  {parts.map((part) => {
                    // "This is the part you are on", which since the words came off
                    // every chip is read in one place only - `aria-current`, and the
                    // inset ring chrome.css hangs off it. It was two readings while the
                    // selected chip also spelt itself out, and they could drift: a chip
                    // wearing the current ring with its label hidden is a pin with a
                    // circle round it and nothing saying what it is. Now the ring is the
                    // whole of the marking, and the words for that part are on the meta
                    // line below rather than in the strip.
                    const isShown = part.id === shown.id

                    return (
                      <button
                        key={part.id}
                        type="button"
                        className="poi-card__chip"
                        data-testid="poi-card-chip"
                        // `aria-current`, the "one of a set of related items you are on"
                        // attribute, rather than `aria-pressed`: these are not toggles,
                        // and exactly one of them is true at a time.
                        aria-current={isShown}
                        // Both boxes, because a chip really does swap both, and a list
                        // is what the attribute is for. It is the programmatic link
                        // between the control and what it changes that the plain-button
                        // markup would otherwise be missing.
                        aria-controls={`${mediaId} ${bodyId}`}
                        onClick={() => {
                          setShownId(part.id)
                          setAnnounced(`Showing ${part.name}`)
                        }}
                      >
                        <MapIcon
                          className="poi-card__chip-icon"
                          type={part.type}
                          // The rim, unlike the legend's (Legend.tsx passes none, on the
                          // grounds that a key says what a category's symbol IS and a
                          // symbol that changed as you panned would not be a key). A
                          // chip is not a key: it stands for one privy, so the broken
                          // rim is a fact about that privy, the same fact its own panel
                          // spells out in words once you tap it.
                          confidence={part.confidence}
                        />
                        {/* EVERY CHIP IS ITS PIN, THE ONE YOU ARE READING INCLUDED.

                            #711 took the words off the UNSELECTED chips and left the
                            selected one spelling itself out, and its own table named what
                            that left behind: `Campsite · 181 ft` was 172 px of the 364 a
                            five-part strip still wanted out of 240. Finishing the job has
                            two consequences worth stating.

                            The strip goes back to FIXED GEOMETRY, which #711 knowingly
                            spent. The current-chip marker is an inset ring (chrome.css)
                            precisely so that marking a chip does not resize it; a chip
                            that grew when selected undid that, and the row shifted
                            sideways under the thumb that had just tapped it.

                            And the whole strip fits at every site size the trail has.
                            Measured in Chromium 1194 at the card's real width against this
                            file's own fixtures plus the four-fact case the meta line needs
                            below (2026-08-16), as chip boxes plus gaps rather than
                            scrollWidth - which floors at the container and hides the
                            headroom, so #711's "240" for a fitting case and its "240" for
                            the container are the same number by accident:

                              3 parts, as it opens        180 -> 140   fits (was: fits)
                              3 parts, campsite open      244 -> 140   fits
                              5 parts, as it opens        276 -> 236   fits
                              5 parts, campsite open      348 -> 236   fits

                            Five 44 px chips and four 4 px gaps is 236 of 240, so five
                            parts - the largest site on the trail (features/POI_SITES.md
                            §5) - is the last size that fits, with 4 px to spare. SIX would
                            ask 284 and scroll, and nothing here changes what happens then:
                            `overflow-x: auto` with no scrollbar is reachable and not
                            discoverable, which is #711's bug returning at a site size that
                            does not exist yet. That is the number to re-run this against
                            if #529's water gap closes and sites grow.

                            HIDING THE SELECTED CHIP'S WORDS COSTS NOTHING, which is why
                            this is small rather than a trade. Its category was already on
                            the meta line below and its name in the heading above; the one
                            fact that lived nowhere else is its distance, and that moves
                            down to the meta line rather than going away.

                            `visually-hidden` rather than `display: none`, unchanged from
                            #711: the words stay in the accessibility tree, so the button's
                            name is still "Privy 131 ft" and nothing a screen reader does
                            here changes at all. What a sighted hiker gives up is unchanged
                            too, and still real - a chip is a symbol they have to recognise
                            until they tap it. @unvalidated, and inherited rather than
                            introduced: that a 44 px pin is legible and hittable with a
                            gloved thumb in sun is the field test HIKER_SAFETY.md §5
                            declines to guess at, which #711 flagged for the chips it had
                            already made pins and this extends to one more per card. */}
                        <span className="poi-card__chip-label visually-hidden">
                          {typeLabel(part.type)}
                          {part.id !== poi.id && (
                            <>
                              {/* The middot is punctuation for eyes only, as it is on
                                  the meta line - but a button's accessible name is its
                                  contents CONCATENATED, and with the separator hidden
                                  there is nothing left between the two facts: this
                                  announced "Privy40 m" until the spaces were made real
                                  text nodes of their own. They cost nothing visually,
                                  because a flex container drops a whitespace-only run
                                  instead of making an item of it, and the gap is what
                                  does the spacing - which is why the span wrapping them
                                  is a flex container of its own and not a plain
                                  inline. */}{' '}
                              <span aria-hidden="true">·</span>{' '}
                              <span className="poi-card__chip-distance">
                                {partDistance(poi, part, units)}
                              </span>
                            </>
                          )}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}

              {/* The announcement itself, empty until a chip is tapped. Rendered
                  whenever there is a strip rather than conditionally on there being
                  something to say: a live region has to be in the DOM BEFORE its text
                  changes, or the change is the region appearing and nothing is read.
                  Visually hidden because the swap is not news to anyone who can see
                  the card - they watched it happen. */}
              {parts.length > 0 && (
                <p className="visually-hidden" role="status">
                  {announced}
                </p>
              )}

              <div className="poi-card__media" id={mediaId}>
                {/* A just-picked photo under review covers the media box: the
                  preview IS the prepared rendering a Keep would store, so what
                  the hiker approves is what they get, byte for byte. Nothing has
                  been written yet - Discard drops it from memory. */}
                {review !== null ? (
                  <img
                    className="poi-card__photo"
                    data-testid="poi-card-review-photo"
                    src={review.url}
                    alt="Photo you just picked, not yet kept"
                  />
                ) : showPhoto ? (
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
                  <div
                    className="poi-card__placeholder"
                    data-testid="poi-card-placeholder"
                  >
                    <svg
                      className="poi-card__glyph"
                      viewBox="0 0 1 1"
                      aria-hidden="true"
                      focusable="false"
                    >
                      <path d={poiGlyphPath(shown.type)} fillRule="evenodd" />
                    </svg>
                  </div>
                )}

                {/* The credit rides the photo, never the placeholder: it is a fact
                  about a photo on screen, and the licence's price for it being
                  there. A link when the file page is known - full terms live
                  there - and plain text when it is not, because a credit is owed
                  either way. */}
                {review === null &&
                  showPhoto &&
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

                {/* Only when there is more than one photo. The count is the honest
                  part: "2 of 7" says how much more there is without making anyone
                  tap to find out, and it is what tells a hiker on a ridge whether
                  the gallery is worth the data.

                  This used to require `showPhoto` too, on the reasoning that paging
                  a placeholder leads nowhere (#481). That is true when EVERY photo
                  has failed, and the gate fired when the CURRENT one had - which for
                  a freshly opened card is always the first. So a shelter whose photo
                  1 was missing from the cache showed a placeholder with no controls,
                  and its other six photographs were unreachable. Offline-first makes
                  that routine rather than rare: a URL the cache no longer holds is
                  the ordinary condition here, not an error.

                  Gated on the list instead, so the arrows over a placeholder are the
                  way out of a bad image rather than chrome over a blank. */}
                {review === null && hasGallery && (
                  <div className="poi-card__gallery">
                    <button
                      type="button"
                      className="poi-card__gallery-step"
                      data-testid="poi-card-photo-prev"
                      onClick={() => step(-1)}
                    >
                      <span className="visually-hidden">Previous photo</span>
                      <span aria-hidden="true">‹</span>
                    </button>
                    <span
                      className="poi-card__gallery-count"
                      data-testid="poi-card-photo-count"
                    >
                      {Math.min(photoIndex, photos.length - 1) + 1} of {photos.length}
                    </span>
                    <button
                      type="button"
                      className="poi-card__gallery-step"
                      data-testid="poi-card-photo-next"
                      onClick={() => step(1)}
                    >
                      <span className="visually-hidden">Next photo</span>
                      <span aria-hidden="true">›</span>
                    </button>
                  </div>
                )}

                {/* Keep or throw away, over the preview where the decision is being
                  made. Two full-height targets rather than small chrome: this is
                  the control #571 wants reachable with a gloved thumb in sunlight
                  (#105), and mis-hitting Discard costs a re-take, not a photo -
                  nothing is written until Keep. */}
                {review !== null && (
                  <div className="poi-card__review-bar">
                    <button
                      type="button"
                      className="poi-card__review-keep"
                      data-testid="poi-card-keep"
                      onClick={() => void keep()}
                    >
                      Keep
                    </button>
                    <button
                      type="button"
                      className="poi-card__review-discard"
                      data-testid="poi-card-discard"
                      onClick={discardReview}
                    >
                      Discard
                    </button>
                  </div>
                )}
              </div>

              {/* The strip under the hiker's own photo: the honesty sentence #573
                  puts here deliberately - "in the photo strip rather than a
                  settings page nobody opens" - and the two verbs #575 adds. "Show
                  on card" only where it changes anything: the first photo is
                  already the card photo. Remove takes a second tap to mean it,
                  because the stored copy of a camera capture may be the only copy
                  there is, and a gloved mis-hit must not be what deletes it. */}
              {ownShown !== undefined && (
                <div className="poi-card__own" data-testid="poi-card-own-strip">
                  <p className="poi-card__own-note">
                    {ownPhotoDisclosure(ownShown.source)}
                  </p>
                  <div className="poi-card__own-actions">
                    {current !== photos[0] && (
                      <button
                        type="button"
                        className="poi-card__own-action"
                        data-testid="poi-card-choose"
                        // Index first, choose second: choose() reorders the list
                        // synchronously, so both land in this handler's batch and
                        // the card repaints once, already showing the chosen
                        // photo at the front. Waiting for the store round-trip
                        // before moving the index would flash the old first
                        // photo in between.
                        onClick={() => {
                          setPhotoIndex(0)
                          void own.choose(ownShown.id)
                        }}
                      >
                        Show on card
                      </button>
                    )}
                    <button
                      type="button"
                      className="poi-card__own-action"
                      data-testid="poi-card-remove"
                      onClick={() =>
                        removeArmed ? void removeOwn(ownShown.id) : setRemoveArmed(true)
                      }
                    >
                      {removeArmed ? 'Tap again to remove' : 'Remove'}
                    </button>
                  </div>

                  {/* The share verb (#577), and after a share, the truth about
                      which phase it is in. Inside the cooling-off window taking
                      it back is a complete undo - nobody ever had it - and the
                      strip stops making that claim at the earliest moment it
                      could be stale (lib/photoShare.ts). */}
                  {ownShown.shared === undefined ? (
                    <button
                      type="button"
                      className="poi-card__own-action poi-card__own-share"
                      data-testid="poi-card-share"
                      onClick={() => setSharing(true)}
                    >
                      Share this photo
                    </button>
                  ) : (
                    (() => {
                      const phase = sharePhase(ownShown.shared)
                      return phase.phase === 'cooling' ? (
                        <>
                          <p
                            className="poi-card__own-note"
                            data-testid="poi-card-share-state"
                          >
                            {`Shared — goes live in about ${remainingLabel(phase.remainingMinutes)}. Until then, taking it back is a complete undo.`}
                          </p>
                          <button
                            type="button"
                            className="poi-card__own-action"
                            data-testid="poi-card-unshare"
                            onClick={() => void withdrawOwn(ownShown, true)}
                          >
                            Take it back
                          </button>
                        </>
                      ) : (
                        <>
                          <p
                            className="poi-card__own-note"
                            data-testid="poi-card-share-state"
                          >
                            Shared with every hiker, under CC BY-SA 4.0.
                          </p>
                          <button
                            type="button"
                            className="poi-card__own-action"
                            data-testid="poi-card-unshare"
                            onClick={() => void withdrawOwn(ownShown, false)}
                          >
                            Stop sharing
                          </button>
                        </>
                      )
                    })()
                  )}
                </div>
              )}

              {/* Somebody else's photo, on rung 2: the one thing a hiker can do
                  about it is put it in front of the maintaining club (#579). The
                  chooser's three reasons are the report sheet's, and the honesty
                  line renders in the note after queueing. */}
              {review === null && current?.community !== undefined && (
                <div className="poi-card__own" data-testid="poi-card-community-strip">
                  {reportChooser ? (
                    <>
                      <p className="poi-card__own-note">What is wrong with it?</p>
                      <div className="poi-card__report-options">
                        <button
                          type="button"
                          className="poi-card__own-action"
                          data-testid="poi-card-report-wrong-place"
                          onClick={() =>
                            void reportCommunity(current.community!, 'wrong_place')
                          }
                        >
                          It is not this place
                        </button>
                        <button
                          type="button"
                          className="poi-card__own-action"
                          data-testid="poi-card-report-person"
                          onClick={() =>
                            void reportCommunity(current.community!, 'person')
                          }
                        >
                          Somebody in it didn’t agree to this
                        </button>
                        <button
                          type="button"
                          className="poi-card__own-action"
                          data-testid="poi-card-report-other"
                          onClick={() =>
                            void reportCommunity(current.community!, 'other')
                          }
                        >
                          It should not be public
                        </button>
                        <button
                          type="button"
                          className="poi-card__own-action"
                          onClick={() => setReportChooser(false)}
                        >
                          Cancel
                        </button>
                      </div>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="poi-card__own-action"
                      data-testid="poi-card-report"
                      onClick={() => setReportChooser(true)}
                    >
                      Report this photo
                    </button>
                  )}
                </div>
              )}

              {/* "The affordance sits on the card and waits" - two quiet buttons,
                  no prompt, no streak, no count (features/DATA_NUDGES.md under
                  value #1). Two rather than one because the paths differ in the
                  one fact #573's honesty line turns on: a library pick has its
                  original in the library, a camera capture may exist nowhere
                  else. The inputs are real file inputs so the OS brings its own
                  camera and picker; `capture` is a hint desktop browsers ignore,
                  which degrades to the picker - the conservative wording, not a
                  broken control. */}
              {review === null && (
                <div className="poi-card__add-photo">
                  <button
                    type="button"
                    className="poi-card__add-button"
                    data-testid="poi-card-take-photo"
                    onClick={() => cameraInput.current?.click()}
                  >
                    Take a photo
                  </button>
                  <button
                    type="button"
                    className="poi-card__add-button"
                    data-testid="poi-card-add-photo"
                    onClick={() => libraryInput.current?.click()}
                  >
                    Add from your photos
                  </button>
                </div>
              )}
              <input
                ref={cameraInput}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/heic"
                capture="environment"
                hidden
                data-testid="poi-card-camera-input"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null
                  // Cleared so picking the same file twice fires change twice - a
                  // hiker who discards and changes their mind picks it again.
                  event.target.value = ''
                  void pick(file, 'camera')
                }}
              />
              <input
                ref={libraryInput}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/heic"
                hidden
                data-testid="poi-card-library-input"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null
                  event.target.value = ''
                  void pick(file, 'library')
                }}
              />

              {preparing && (
                <p className="poi-card__photo-note" role="status">
                  Shrinking the photo…
                </p>
              )}
              {photoNote !== null && (
                <p className="poi-card__photo-note" role="alert">
                  {photoNote}
                </p>
              )}

              {/* What a Keep would do, said before it is done: the size is the
                  measured size of the exact bytes on screen, and the capture date
                  is shown where one was found so a wrong guess is caught at the
                  cheapest moment. GPS never made it into this copy - the re-encode
                  is the mechanism, reportPhoto.ts. */}
              {review !== null && (
                <p className="poi-card__photo-note" role="status">
                  {`Keep stores this ${Math.max(1, Math.round(review.blob.size / 1024))} KB copy on this phone${
                    reviewMonth === null ? '' : `, dated ${reviewMonth}`
                  }. Location details are not in it.`}
                </p>
              )}

              {/* #573's web half: a photo taken through the app's camera exists
                  nowhere else, so the full-resolution original is offered HERE,
                  while it is still in hand. A browser cannot write to the photo
                  library; a download is what the platform allows, and the strip's
                  wording stays conditional either way. Library picks get no offer -
                  their original is already where it belongs. */}
              {review !== null && review.originalUrl !== null && (
                <p className="poi-card__photo-note">
                  <a
                    href={review.originalUrl}
                    download={review.originalName}
                    data-testid="poi-card-save-original"
                  >
                    Save the original to this phone
                  </a>
                  {' — OurHike keeps only the small copy.'}
                </p>
              )}

              {/* The unverified sentence leads whether or not there is a
                  conditions section under it - a viewpoint nobody confirmed
                  gets the band with no heading, because "Conditions" is a
                  promise about water, shelter, campsites and resupply and
                  this file must not make it about anything else. */}
              {(notesShown || unverifiedLine !== null) && (
                <section className="poi-card__section">
                  {notesShown && <h3 className="poi-card__section-title">Conditions</h3>}
                  {unverifiedLine}
                  {conditions('open')}
                </section>
              )}

              {/* Where the coordinates and the provenance went. They are
                  facts about where the pin CAME FROM, and #941's complaint
                  was that they outranked the answer the hiker tapped the pin
                  for - so they are last, under a heading that says what they
                  are, rather than gone. */}
              <section className="poi-card__section">
                <h3 className="poi-card__section-title">About this place</h3>
                {shown.description !== undefined && (
                  <p className="poi-card__description">{shown.description}</p>
                )}

                {/* What is around this one, as its own paragraph rather than appended
                    to the description above (#625).

                    The pipeline spliced it onto the end of that sentence while it
                    composed the words; now that the phone composes them, keeping it
                    there would mean concatenating two strings from two places to make
                    one paragraph - and a description that failed to compose (a shelter
                    ATC states nothing about) would take the privy down with it. Two
                    paragraphs render identically when both are present, and each stands
                    up when the other is missing. */}
                {nearby !== null && <p className="poi-card__nearby">{nearby}</p>}

                {/* One line, because they are one fact: this point, and who
                    listed it. Two paragraphs was the card spending two lines
                    on the least urgent thing it knows. */}
                <p className="poi-card__coords">
                  <span className="visually-hidden">Latitude, longitude: </span>
                  {coordinates(shown.lat, shown.lon)}
                  {source !== null && (
                    <>
                      <span aria-hidden="true"> · </span>
                      <span className="poi-card__source">{`from ${source}`}</span>
                    </>
                  )}
                </p>
              </section>
            </div>
          </div>
        </>
      ) : (
        <div className="poi-card__peek" data-testid="poi-card-peek">
          <div className="poi-card__peek-head">
            {/* THE CATEGORY'S OWN SILHOUETTE, NEVER A PHOTOGRAPH, and the
                reason is the credit rather than the layout. A CC BY / BY-SA
                photo is OurHike's to show only while the credit shows with
                it, and there is no line of the peek to spend on an
                institutional attribution string. The photograph and its
                credit are one pull away, together, which is the only way
                either of them is allowed on screen. */}
            <div className="poi-card__thumb" data-testid="poi-card-thumb">
              <svg
                className="poi-card__glyph"
                viewBox="0 0 1 1"
                aria-hidden="true"
                focusable="false"
              >
                <path d={poiGlyphPath(shown.type)} fillRule="evenodd" />
              </svg>
            </div>
            <div className="poi-card__peek-text">
              <h2 className="poi-card__name">{shown.name}</h2>
              {metaLine}
            </div>
          </div>

          {unverifiedLine}
          {conditions('peek')}

          {/* One deliberate pull, named for what is behind it. "Notes &
              details" only where there are notes: a viewpoint carries no
              conditions section, and promising one is how a control teaches
              a hiker not to trust its labels. */}
          <button
            type="button"
            className="poi-card__expand"
            data-testid="poi-card-expand"
            aria-expanded={false}
            onClick={() => setOpen(true)}
          >
            {notesShown ? 'Notes & details' : 'Details'}
            <span className="poi-card__expand-caret" aria-hidden="true">
              ▲
            </span>
          </button>
        </div>
      )}

      {/* The share sheet (#577), over the live map through a portal - see
          PoiShareSheet.tsx for why the card cannot host it in place. */}
      {sharing && ownShown !== undefined && (
        <PoiShareSheet
          photoUrl={ownShown.url}
          photoBlob={ownShown.blob}
          photoBytes={ownShown.blob.size}
          photoMonth={photoMonth(ownShown.taken) ?? ''}
          poiName={shown.name}
          onShare={(flagged) => void shareOwn(ownShown, flagged)}
          onClose={() => setSharing(false)}
          container={sheetContainer}
        />
      )}
    </div>
  )
}
