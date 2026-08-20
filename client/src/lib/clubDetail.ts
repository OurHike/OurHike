// What the sheet says about the stretch of trail under a hiker's finger, when
// the map's subject is who maintains it (#598, features/CORRIDOR_VIEW.md).
//
// The same division lineDetail.ts keeps, and for the same reason: every
// sentence is decided here, where it is testable without a canvas, and
// chrome/ClubSheet.tsx only lays them out. Nothing in this file knows what
// MapLibre is.
//
// ABSENCE IS A SENTENCE, NOT A BLANK
//
// 38.5 miles of the A.T. carry no club in ATC's centerline. That stretch gets a
// heading of its own - "Club not recorded" - and says plainly that the source
// cannot name one. It never says nobody maintains it: somebody almost certainly
// does, and OurHikeValues.md #4 is the reason the difference is worth two
// sentences rather than a shrug.
//
// NO DATES, AND THAT IS A GAP RATHER THAN A CHOICE
//
// features/CORRIDOR_VIEW.md's mock-up shows this sheet carrying two dated
// provenance lines - "ATC centerline, 4 Aug 2026" against "ATC club sections,
// 15 Aug 2024" - because WHICH club is decided by a layer edited nine days ago
// and how it is SPELLED by one edited two years ago, and a hiker reading a club
// name is entitled to know which half they are looking at.
//
// The dates now arrive in the artifact (#852). `export_club_sections.py` reads
// each layer's `dataLastEditDate` from the raw manifest fetch_all.py already
// writes, and publishes it under `source_edited` keyed by layer.
//
// Before that they were measured by hand when #594 was written and lived in a
// docstring, so this file named its sources and stopped - printing a date
// nobody published would have been the confident-claim-nobody-checked failure
// CLAUDE.md's evidence rule exists to prevent. That restraint is still here,
// one step further along: a release that carries no date for a layer prints
// none, and the line falls back to naming the source alone. It is the same
// sentence it was, not a shorter one - so an artifact downloaded before #852,
// or a layer whose edit-date lookup failed upstream, degrades to exactly the
// behaviour this file already had rather than to a gap.

import { clubRunAtMile, type ClubRun, type ClubSections } from './clubSections'
import { unattributedTotal } from './clubSections'
import { formatDistance } from './units'
import type { UnitSystem } from './units'
import { walkedWithin, type MileRange } from './walkedMiles'

export interface ClubDetail {
  /** The club's full name, or "Club not recorded". */
  heading: string
  /** "PATC · Mid-Atlantic". Null where there is no club to identify, and the
   *  region is dropped rather than faked when the stale polygon layer carries
   *  none for this club. */
  subtitle: string | null
  /** "mi 940.2 – 1,180.9" - the run under the finger. Mile markers, so they
   *  do not convert with the unit preference (lib/units.ts's opening rule). */
  rangeLine: string
  /** "240.7 mi maintained, in 2 sections" - the club's whole share of the
   *  trail, not just the piece tapped. Null for an unrecorded stretch, which
   *  is nobody's share of anything. */
  extentLine: string | null
  /** "ATC's centerline does not name a club along here." Null where it does. */
  absenceLine: string | null
  /** "38.5 mi of the trail are like this, in 27 runs." Null where a club is
   *  named - and null too when nothing is unattributed, so a future release
   *  that names every mile stops claiming a scale it no longer has. */
  scaleLine: string | null
  /** "Who maintains it: the ATC’s trail centerline". */
  attributionSourceLine: string | null
  /** "Club name: the ATC’s club-section map". Null for an unrecorded stretch,
   *  where no name was taken from anywhere. */
  nameSourceLine: string | null
  /**
   * "You have walked 12.4 mi of this section" - #598's `visited`, answered on
   * the phone about the phone's own fixes (lib/walkedMiles.ts).
   *
   * Null when the hiker has walked none of it, which is most people on most of
   * the trail. A "0 mi" line would be a nag rather than a fact, and this app
   * does not tell anybody how much of the A.T. they have not done.
   *
   * "Section" and not "stretch": the word belongs to the offline download unit
   * (#552), and this sheet already uses "section" for a club's own pieces.
   */
  walkedLine: string | null
}

/**
 * The two layers `club_sections.json` names, in words.
 *
 * Kept here rather than in chrome/poiSources.ts because these are LINE
 * sources, not POI ones, and that file's ids are the pipeline's `unify_poi`
 * values. The wording follows its rule though: say what the layer actually is,
 * so a reader can weigh it.
 */
export const CLUB_SOURCE_LABELS: Record<string, string> = {
  centerline: 'the ATC’s trail centerline',
  trail_club_sections: 'the ATC’s club-section map',
  half_mile_points_from_springer: 'the ATC’s half-mile markers',
}

function sourceLabel(key: string | null): string | null {
  if (key === null) return null
  // An unregistered key comes back as itself, the call chrome/poiSources.ts
  // makes: a raw key is a poor label and still says more than silence.
  return CLUB_SOURCE_LABELS[key] ?? key
}

/** "4 Aug 2026" from an ISO day, or null for anything else - never today's
 *  date, which would be a claim nobody made. */
function formatEditedDay(iso: string | undefined): string | null {
  if (iso === undefined || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null
  const [year, month, day] = iso.split('-').map(Number)
  const months = [
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
  const name = months[month - 1]
  if (name === undefined) return null
  return `${day} ${name} ${year}`
}

/**
 * "the ATC's trail centerline, 4 Aug 2026", or the label alone.
 *
 * The date is appended, never substituted: a release that does not carry one
 * prints the sentence this file printed before #852 rather than a gap. That is
 * what lets an older download and a failed upstream lookup both degrade to
 * something true instead of something missing.
 */
function sourcePhrase(
  key: string | null,
  edited: Readonly<Record<string, string>>,
): string | null {
  const label = sourceLabel(key)
  if (label === null) return null
  const day = key === null ? null : formatEditedDay(edited[key])
  return day === null ? label : `${label}, ${day}`
}

/** A mile marker, grouped with one decimal - the rendering lineDetail.ts,
 *  PoiCard and the position line all give a mile, so every surface in the app
 *  shows one number. */
function formatMileMarker(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many
}

/**
 * Everything the sheet can say about one tapped stretch.
 *
 * Returns null only when the tap fell outside the published corridor - which
 * is a different fact from an unattributed mile, and gets no sheet rather than
 * an empty one. lib/clubSections.ts's clubRunAtMile is what tells them apart.
 */
export function buildClubDetail(
  sections: ClubSections,
  timeline: readonly ClubRun[],
  mile: number,
  units: UnitSystem,
  walked: readonly MileRange[] = [],
): ClubDetail | null {
  const run = clubRunAtMile(timeline, mile)
  if (run === null) return null

  // Below a tenth of a mile shows nothing: a line reading "0.0 mi" claims
  // less than silence does and reads as a scold.
  const walkedMiles = walkedWithin(walked, run)
  const walkedLine =
    walkedMiles < 0.05
      ? null
      : `You have walked ${formatDistance(walkedMiles, units)} of this section.`

  const rangeLine = `mi ${formatMileMarker(run.startMile)} – ${formatMileMarker(run.endMile)}`
  const attributionSourceLine = (() => {
    const phrase = sourcePhrase(sections.sources.attribution, sections.sourceEdited)
    return phrase === null ? null : `Who maintains it: ${phrase}`
  })()

  if (run.club === null) {
    const { miles, runs } = unattributedTotal(sections)
    return {
      heading: 'Club not recorded',
      subtitle: null,
      rangeLine,
      extentLine: null,
      // Named from the source rather than asserted flatly: it is the ATC's
      // centerline that cannot say, and the sheet should not be read as this
      // app having decided nobody looks after the place.
      absenceLine: 'ATC’s centerline does not name a club along here.',
      scaleLine:
        runs === 0
          ? null
          : `${formatDistance(miles, units)} of the trail are like this, in ${runs} ${plural(runs, 'run', 'runs')}.`,
      attributionSourceLine,
      nameSourceLine: null,
      walkedLine,
    }
  }

  const club = run.club
  const sectionCount = club.runs.length
  const namePhrase = sourcePhrase(sections.sources.names, sections.sourceEdited)

  return {
    heading: club.name,
    // The region is dropped when the two-year-old polygon layer carries none,
    // rather than printed as an empty half of a sentence.
    subtitle: club.region === null ? club.acronym : `${club.acronym} · ${club.region}`,
    rangeLine,
    extentLine: `${formatDistance(club.miles, units)} maintained, in ${sectionCount} ${plural(sectionCount, 'section', 'sections')}`,
    absenceLine: null,
    scaleLine: null,
    attributionSourceLine,
    // Only worth saying when it is a DIFFERENT layer from the attribution -
    // which today it always is, and the whole reason the exporter publishes
    // the two separately. If a future release ever decided both from one
    // source, two lines naming it twice would imply a corroboration that is
    // not there.
    nameSourceLine:
      namePhrase === null || sections.sources.names === sections.sources.attribution
        ? null
        : `Club name: ${namePhrase}`,
    walkedLine,
  }
}
