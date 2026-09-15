// Published routes, as bytes on the phone (#1284).
//
// `suggested_hikes.json` rides the published-data path every other artifact
// rides: fetched from the bucket when there is signal, kept in IndexedDB so
// the shelf answers with none, validated on BOTH ways through because a
// stored document is no more trustworthy than a fetched one. The kept copy
// goes through lib/conditionsCache.ts - the mechanism the conditions
// artifacts already use, with the same 2 MB ceiling and the same never-throw
// posture - rather than a second cache with a different set of failure modes.
//
// NEVER FATAL, copied from lib/publishedConditions.ts: an unreachable bucket,
// a 404 from a release that predates the artifact (which today is every
// release - see config.ts's SUGGESTED_HIKES_KEY), a malformed document, all
// yield "nothing to suggest", and the Today section collapses. This is a
// source of suggestions, not a second thing to be offline from.
//
// JUNK COSTS THE RECORD, NEVER THE LIST, which is lib/dayHikes.ts's asymmetry
// applied to a document somebody else wrote: one unreadable route is dropped
// and the rest are shown. What can cost a route is exactly what the surfaces
// cannot do without - an identity, a name, its ends, and a NAMED publisher,
// because naming who wrote a route is the premise of showing it at all
// (features/SUGGESTED_HIKES.md). Everything else degrades to its honest
// absence: an unreadable rating is no rating, a broken transit block is no
// transit (absent means nothing published, never "none exists"), a climb the
// document cannot spell is `undefined` - the app never knew - and never 0.

import {
  DATA_CONFIGURED,
  SUGGESTED_HIKES_KEY,
  dataUrl,
  suggestedHikeDetailKey,
} from './config'
import { recallPublished, rememberPublished } from './conditionsCache'
import { validClimb, validSegments } from './dayHikes'
import {
  AUTHOR_KINDS,
  DIFFICULTIES,
  ROUTE_GRADES,
  ROUTE_PROVENANCES,
  type AuthorKind,
  type Difficulty,
  type RouteGrade,
  type RouteProvenance,
  type SuggestedHike,
  type SuggestedHikeDetail,
  type SuggestedHikePhoto,
  type SuggestedHikePublication,
  type SuggestedHikeStart,
  type SuggestedHikeTransit,
} from './suggestedHikes'

/** No document, or nothing readable in one. A shared constant so a hook can
 *  hand back the same array and a memo keyed on it stays put. */
export const NO_SUGGESTED_HIKES: readonly SuggestedHike[] = []

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

function finiteNonNegative(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

function validDifficulty(candidate: unknown): Difficulty | null {
  return (DIFFICULTIES as readonly unknown[]).includes(candidate)
    ? (candidate as Difficulty)
    : null
}

function validAuthorKind(candidate: unknown): AuthorKind | null {
  return (AUTHOR_KINDS as readonly unknown[]).includes(candidate)
    ? (candidate as AuthorKind)
    : null
}

/** A transit block, or undefined - which reads as "nothing published". The
 *  line and the walk are what the card prints, so both are needed; the stop
 *  may be empty (a line that goes to the trailhead itself). */
function validTransit(candidate: unknown): SuggestedHikeTransit | undefined {
  if (typeof candidate !== 'object' || candidate === null) return undefined
  const transit = candidate as Partial<SuggestedHikeTransit>
  const line = nonEmptyString(transit.line)
  const walkMiles = finiteNonNegative(transit.walkMiles)
  if (line === null || walkMiles === null) return undefined
  return {
    line,
    toStop: typeof transit.toStop === 'string' ? transit.toStop : '',
    walkMiles,
    source: typeof transit.source === 'string' ? transit.source : '',
  }
}

/** A photo, or undefined. The credit and the licence are what make a photo a
 *  data surface rather than decoration (features/POI_PHOTOS.md), so a photo
 *  that arrives without either is not shown.
 *
 *  The pipeline publishes a photo as a BUCKET KEY - `photos/<digest>.jpg`,
 *  the content-addressed store the POI cards already draw from
 *  (pipeline/export_suggested_hikes.py, #1290) - so a key is resolved
 *  against the data base URL here, exactly as a POI's `photo_key` is. An
 *  absolute URL passes through unchanged, for a publisher that hosts its own. */
function validPhoto(candidate: unknown): SuggestedHikePhoto | undefined {
  if (typeof candidate !== 'object' || candidate === null) return undefined
  const photo = candidate as Partial<SuggestedHikePhoto>
  const url = nonEmptyString(photo.url)
  const credit = nonEmptyString(photo.credit)
  const licence = nonEmptyString(photo.licence)
  if (url === null || credit === null || licence === null) return undefined
  return { url: /^[a-z]+:\/\//i.test(url) ? url : dataUrl(url), credit, licence }
}

function stringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined
  const kept = value.filter(
    (item): item is string => typeof item === 'string' && item.trim() !== '',
  )
  return kept.length > 0 ? kept : undefined
}

/** The publication line, or undefined. `submittedBy` is the whole point of
 *  it - a line that names nobody says nothing - so its absence drops the
 *  block, while the two dates degrade to null on their own. */
function validPublication(candidate: unknown): SuggestedHikePublication | undefined {
  if (typeof candidate !== 'object' || candidate === null) return undefined
  const line = candidate as Partial<SuggestedHikePublication>
  const submittedBy = nonEmptyString(line.submittedBy)
  if (submittedBy === null) return undefined
  return {
    submittedBy,
    submittedOn: nonEmptyString(line.submittedOn),
    verifiedOn: nonEmptyString(line.verifiedOn),
  }
}

/** The start, or undefined. Both numbers or neither: half a coordinate
 *  points at the Atlantic, and a screen offering directions to it would be
 *  worse than one offering none. */
function validProvenance(candidate: unknown): RouteProvenance | undefined {
  return (ROUTE_PROVENANCES as readonly unknown[]).includes(candidate)
    ? (candidate as RouteProvenance)
    : undefined
}

function validRouteGrade(candidate: unknown): RouteGrade | undefined {
  return (ROUTE_GRADES as readonly unknown[]).includes(candidate)
    ? (candidate as RouteGrade)
    : undefined
}

function validStart(candidate: unknown): SuggestedHikeStart | undefined {
  if (typeof candidate !== 'object' || candidate === null) return undefined
  const start = candidate as Partial<SuggestedHikeStart>
  const { lat, lon } = start
  if (typeof lat !== 'number' || !Number.isFinite(lat) || Math.abs(lat) > 90)
    return undefined
  if (typeof lon !== 'number' || !Number.isFinite(lon) || Math.abs(lon) > 180)
    return undefined
  return { lat, lon, basis: nonEmptyString(start.basis) }
}

/**
 * The detail block, or undefined when the document carries nothing for it.
 *
 * EVERY FIELD DEGRADES ALONE. A junk `url` costs the link and not the
 * prose; an unreadable publication line costs that line and not the
 * paragraphs. This is `validateSuggestedHike`'s own asymmetry one level
 * down: what a surface cannot print, it does not print, and nothing here is
 * load-bearing enough to cost the route.
 */
function validDetail(candidate: unknown): SuggestedHikeDetail | undefined {
  if (typeof candidate !== 'object' || candidate === null) return undefined
  const raw = candidate as Record<string, unknown>
  const publishedMiles = finiteNonNegative(raw.publishedMiles)
  const detail: SuggestedHikeDetail = {
    ...(nonEmptyString(raw.url) !== null ? { url: nonEmptyString(raw.url)! } : {}),
    ...(publishedMiles !== null && publishedMiles > 0 ? { publishedMiles } : {}),
    ...(stringList(raw.overview) !== undefined
      ? { overview: stringList(raw.overview) }
      : {}),
    ...(stringList(raw.description) !== undefined
      ? { description: stringList(raw.description) }
      : {}),
    ...(validPublication(raw.publication) !== undefined
      ? { publication: validPublication(raw.publication) }
      : {}),
    ...(validStart(raw.start) !== undefined ? { start: validStart(raw.start) } : {}),
    ...(nonEmptyString(raw.routeType) !== null
      ? { routeType: nonEmptyString(raw.routeType)! }
      : {}),
    ...(nonEmptyString(raw.park) !== null ? { park: nonEmptyString(raw.park)! } : {}),
    ...(stringList(raw.trails) !== undefined ? { trails: stringList(raw.trails) } : {}),
    ...(nonEmptyString(raw.hikerNote) !== null
      ? { hikerNote: nonEmptyString(raw.hikerNote)! }
      : {}),
    // WHERE THE LINE CAME FROM (#1427). Read like every other field here -
    // junk costs the field and never the route - but unlike the others its
    // absence is load-bearing: a card may not draw an inferred route in the
    // voice of a published one, and "the document did not say" has to stay
    // distinguishable from "the publisher walked it".
    ...(validProvenance(raw.routeProvenance) !== undefined
      ? { routeProvenance: validProvenance(raw.routeProvenance) }
      : {}),
    ...(validRouteGrade(raw.routeGrade) !== undefined
      ? { routeGrade: validRouteGrade(raw.routeGrade) }
      : {}),
    ...(stringList(raw.routeNotes) !== undefined
      ? { routeNotes: stringList(raw.routeNotes) }
      : {}),
  }
  return Object.keys(detail).length > 0 ? detail : undefined
}

/** One published route, or null when what is junk is the route itself. */
export function validateSuggestedHike(candidate: unknown): SuggestedHike | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const hike = candidate as Partial<SuggestedHike>
  const id = nonEmptyString(hike.id)
  const name = nonEmptyString(hike.name)
  if (id === null || name === null) return null
  // Zero is a claim ("this walk covers no ground"), not an absence, and
  // nothing here can recompute it without the publisher's graph.
  const miles = finiteNonNegative(hike.miles)
  if (miles === null || miles === 0) return null
  const segments = validSegments(hike.segments)
  if (segments === null) return null

  const author =
    typeof hike.author === 'object' && hike.author !== null
      ? (hike.author as Partial<SuggestedHike['author']>)
      : null
  const kind = author === null ? null : validAuthorKind(author.kind)
  const authorName = author === null ? null : nonEmptyString(author.name)
  if (kind === null || authorName === null) return null

  const climb = validClimb(hike.climb)
  const transit = validTransit(hike.transit)
  const photo = validPhoto(hike.photo)
  // The exporter writes the detail fields FLAT beside the shelf's, rather
  // than nested, because they are all facts about one route. They are read
  // into one optional block here so a screen can ask "is there a detail to
  // show" once instead of ten times.
  // So THE WHOLE RECORD is what goes in, not a `detail` key - there isn't
  // one on the wire. A fixture that invented one produced a detail screen
  // with no publisher's length, no start, no prose and no link back, and the
  // preview shot was the only thing that caught it; the tests below now pin
  // the flat shape against exactly that mistake.
  const detail = validDetail(candidate)

  return {
    id,
    name,
    miles,
    // Omitted rather than set to undefined, as DayHikeFigures does, so that
    // "the document never said" and "the document said null" stay apart.
    ...(climb === undefined ? {} : { climb }),
    difficulty: validDifficulty(hike.difficulty),
    author: { kind, name: authorName },
    ...(transit === undefined ? {} : { transit }),
    ...(photo === undefined ? {} : { photo }),
    ...(detail === undefined ? {} : { detail }),
    segments,
  }
}

/**
 * Every readable route in a published document.
 *
 * The document is `{ hikes: [...] }`, with an optional `generated_at` nothing
 * reads yet - a route's age is not a claim the cards make, unlike a closure's.
 * Anything that is not that shape is an empty list, never a throw.
 */
export function validateSuggestedHikes(document: unknown): SuggestedHike[] {
  if (typeof document !== 'object' || document === null) return []
  const entries = (document as { hikes?: unknown }).hikes
  if (!Array.isArray(entries)) return []
  const hikes: SuggestedHike[] = []
  const seen = new Set<string>()
  for (const entry of entries) {
    const hike = validateSuggestedHike(entry)
    // Two records under one id would be two cards for one route, and React
    // keys on the id; the first one published wins.
    if (hike === null || seen.has(hike.id)) continue
    seen.add(hike.id)
    hikes.push(hike)
  }
  return hikes
}

/**
 * The number a hike's detail is published under, from its shelf id.
 *
 * A shelf id is `<source>:<number>` - "nynjtc_hike_finder:50". The published
 * object is `50.json`, keyed on the number alone so the URL does not carry
 * the pipeline's own naming, and so a colon never has to survive a path.
 *
 * Null for an id with no number after the colon, which no exporter writes -
 * it is here so a malformed shelf record asks for nothing rather than
 * fetching a URL built out of a broken string.
 *
 * DIGITS, NOT MERELY "SOMETHING AFTER THE COLON", because this string becomes
 * an object name in the bucket and lib/r2_keys.py's NAME_PATTERN allows no
 * hyphens. The retired scraper's ids looked like
 * `nynjtc_favorite_hikes:hike-vista-loop-trail`; one of those would build
 * `suggested_hikes_detail_hike-vista-loop-trail.json`, a name that could
 * never have been published under it. Null is the honest answer for an id
 * this scheme cannot address, and the screen already reads null as "nothing
 * more to show".
 */
export function detailKeyFor(id: string): string | null {
  const number = id.slice(id.lastIndexOf(':') + 1).trim()
  if (number === '' || number === id.trim()) return null
  return /^[0-9]+$/.test(number) ? number : null
}

/**
 * One hike's prose, from the bucket, kept for next time (#1473).
 *
 * NULL IS ORDINARY AND MEANS "NOTHING MORE TO SHOW", not an error. The screen
 * has always treated every detail field as optional - absent is what the
 * publisher did not say - so a phone with no signal, a 404, or an object that
 * will not parse all land on the state the screen was already built for. That
 * property is what makes fetching prose on demand safe rather than a new way
 * for the screen to break.
 *
 * Kept raw, like the shelf: the same validation runs on the way back out, and
 * only after it has parsed, so a broken object never replaces a good one.
 */
export async function fetchHikeDetail(
  id: string,
  signal?: AbortSignal,
): Promise<SuggestedHikeDetail | null> {
  if (!DATA_CONFIGURED) return null
  const number = detailKeyFor(id)
  if (number === null) return null
  try {
    const response = await fetch(dataUrl(suggestedHikeDetailKey(number)), { signal })
    if (!response.ok) return null
    const document: unknown = await response.json()
    if (typeof document !== 'object' || document === null) return null
    if (!saysItIs(document as Record<string, unknown>, id)) return null
    // KEPT BEFORE IT IS JUDGED, the way fetchSuggestedHikes keeps the shelf:
    // whether `validDetail` found a field worth printing is a question about
    // what to SHOW, not about whether the bytes arrived. A detail carrying
    // only its own id - a publisher who said nothing beyond the shelf - reads
    // as undefined here, and returning before this line would refetch it on
    // every single open, forever, for exactly the hikes with the least to
    // say. `saysItIs` is the one gate that stays in front: prose belonging to
    // another walk is not this walk's to keep.
    await rememberPublished(
      suggestedHikeDetailKey(number),
      document as Record<string, unknown>,
    )
    const detail = validDetail(document)
    if (detail === undefined) return null
    return detail
  } catch {
    return null
  }
}

/**
 * The last detail for this hike that reached the phone, validated again.
 *
 * ONE ENTRY PER HIKE SOMEBODY OPENED, and nothing prunes them - which is a
 * decision rather than an omission, given this whole split exists over a byte
 * ceiling. conditionsCache.ts's MAX_CACHED_BYTES is PER ARTIFACT, not per
 * store, so it bounds one detail and not the family: the largest of the 201
 * published on 2026-09-15 is 10,086 B, 0.48% of it. What bounds the family is
 * how many walks a hiker opened - all 385 would be about 2.3 MB, beside the
 * 1.18 GB a downloaded map occupies - and the thing bought with it is that an
 * already-read walk reads again with no signal.
 *
 * A hike dropped from a later export leaves its detail here forever. 6 kB of
 * prose nothing can reach, because the shelf record that names it is gone.
 */
export async function recallHikeDetail(id: string): Promise<SuggestedHikeDetail | null> {
  const number = detailKeyFor(id)
  if (number === null) return null
  const cached = await recallPublished(suggestedHikeDetailKey(number))
  if (cached === null || !saysItIs(cached.document, id)) return null
  return validDetail(cached.document) ?? null
}

/**
 * Whether this document admits to being the hike that was asked for.
 *
 * export_suggested_hikes.py writes `id` onto every detail object for exactly
 * this check - "a phone that asked for one and was handed another by a stale
 * cache or a mis-keyed upload would render the wrong prose under the right
 * name, silently". That sentence is only true if somebody reads the field,
 * and this is where it is read.
 *
 * WHAT THE WRONG ANSWER COSTS, and why this is not paranoia about a rename:
 * the prose is turn-by-turn directions. A hiker acting on another walk's
 * directions under this walk's name is the confidently-wrong answer
 * CLAUDE.md's safety section exists to prevent, and no field on the object
 * would look wrong while they did it.
 *
 * A document carrying NO id passes. Nothing this exporter has ever published
 * is missing one, but absent has always meant "the publisher did not say"
 * here, and refusing on absence would discard prose over a field that is not
 * itself evidence of a mix-up. Only a DISAGREEING id is a mix-up.
 */
function saysItIs(document: Record<string, unknown>, id: string): boolean {
  const said = document.id
  return typeof said !== 'string' || said === id
}

/** The last document that reached this phone, validated again, or null. */
export async function recallSuggestedHikes(): Promise<SuggestedHike[] | null> {
  const cached = await recallPublished(SUGGESTED_HIKES_KEY)
  return cached === null ? null : validateSuggestedHikes(cached.document)
}

/**
 * Ask the bucket, keep what it says, hand back the routes - or null when
 * nothing usable came back, in which case the caller keeps what it had.
 *
 * A 404 is the ordinary answer today and is null like everything else: it
 * must not clear the kept copy, because a bucket that stopped carrying the
 * artifact is not evidence the routes it carried were withdrawn.
 */
export async function fetchSuggestedHikes(
  signal?: AbortSignal,
): Promise<SuggestedHike[] | null> {
  if (!DATA_CONFIGURED) return null
  try {
    const response = await fetch(dataUrl(SUGGESTED_HIKES_KEY), { signal })
    if (!response.ok) return null
    const document: unknown = await response.json()
    if (typeof document !== 'object' || document === null) return null
    const hikes = validateSuggestedHikes(document)
    // Kept raw, so the same validation runs on the way back out; and only
    // once it has parsed, so a broken document never replaces a good one.
    await rememberPublished(SUGGESTED_HIKES_KEY, document as Record<string, unknown>)
    return hikes
  } catch {
    return null
  }
}
