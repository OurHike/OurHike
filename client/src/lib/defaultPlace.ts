// Where this hiker hikes, kept on this phone (#1373, first run's frame 1b).
//
// "So we can put a trail in front of you before you turn location on - and
// fall back to it whenever GPS cannot get a fix." The answer is a place a
// hiker named - a park, a town, a trailhead - and it does two jobs: it is the
// map's fallback centre when there is no fix and no remembered camera, and it
// is what Today's "Hikes near you" is near when nothing else says where the
// hiker is.
//
// ITS OWN STORE, NOT A UserPreferences KEY, and that is a privacy rule before
// it is a correctness one. The permission step's own promise is that
// "location is read on this phone and never sent anywhere", and a default
// location is a location: a key on the synced blob would put where somebody
// lives on a server the moment they signed in to file a blowdown. So it lives
// where lib/hikerMode.ts lives - idb-keyval, read once at launch - and the
// synced schema (backend `extra="forbid"`, #242) never learns it exists.
// "Kept on this phone. Change it any time in More → You." is the sentence
// under the field, and this file is what makes it true.
//
// A SNAPSHOT, NOT A REFERENCE. The chosen place is copied in full rather than
// stored as an id into places.json, because that artifact can change under a
// phone - a park renamed, a trailhead retired - and the fallback centre must
// keep working the morning the release moves. The id rides along so a screen
// can still find the live row when there is one.
//
// NEVER A FIX. What lib/positionLine.ts prints, what the follow cards
// measure from, and what a report carries are all the phone's own fixes and
// only those (App.tsx's fixAt: "never a stale point, never Springer"). This
// place feeds the camera and the ranking and nothing that claims to know
// where the hiker is standing.

import { del, get, set } from 'idb-keyval'
import type { Place } from './places'

export const DEFAULT_PLACE_KEY = 'ourhike:default-place'

/** The kept snapshot: the place's own fields, with what a map needs. */
export type DefaultPlace = Pick<Place, 'id' | 'name' | 'kind' | 'lon' | 'lat'> &
  Partial<Pick<Place, 'state' | 'category' | 'bbox' | 'within'>>

/** A stored value made safe to use, whatever wrote it. Anything short of a
 *  named point is treated as absent rather than trusted - a fallback centre
 *  at NaN is a map that fails to open. */
export function normaliseDefaultPlace(stored: unknown): DefaultPlace | null {
  if (typeof stored !== 'object' || stored === null) return null
  const row = stored as Record<string, unknown>
  const lon = row.lon
  const lat = row.lat
  if (
    typeof row.id !== 'string' ||
    row.id === '' ||
    typeof row.name !== 'string' ||
    row.name === '' ||
    typeof row.kind !== 'string' ||
    typeof lon !== 'number' ||
    typeof lat !== 'number' ||
    !Number.isFinite(lon) ||
    !Number.isFinite(lat) ||
    Math.abs(lon) > 180 ||
    Math.abs(lat) > 90
  ) {
    return null
  }
  const place: DefaultPlace = {
    id: row.id,
    name: row.name,
    kind: row.kind as DefaultPlace['kind'],
    lon,
    lat,
  }
  if (typeof row.state === 'string' && row.state !== '') place.state = row.state
  if (typeof row.category === 'string' && row.category !== '')
    place.category = row.category
  if (typeof row.within === 'string' && row.within !== '') place.within = row.within
  if (
    Array.isArray(row.bbox) &&
    row.bbox.length === 4 &&
    row.bbox.every((part) => typeof part === 'number' && Number.isFinite(part))
  ) {
    place.bbox = row.bbox as [number, number, number, number]
  }
  return place
}

/** The snapshot of a live index row - the fields a map and a label need,
 *  and none of the measurement that goes stale with the next publish. */
export function snapshotPlace(place: Place): DefaultPlace {
  const snapshot: DefaultPlace = {
    id: place.id,
    name: place.name,
    kind: place.kind,
    lon: place.lon,
    lat: place.lat,
  }
  if (place.state !== undefined) snapshot.state = place.state
  if (place.category !== undefined) snapshot.category = place.category
  if (place.within !== undefined) snapshot.within = place.within
  if (place.bbox !== undefined) snapshot.bbox = place.bbox
  return snapshot
}

export async function loadDefaultPlace(): Promise<DefaultPlace | null> {
  return normaliseDefaultPlace(await get(DEFAULT_PLACE_KEY))
}

export async function saveDefaultPlace(place: DefaultPlace): Promise<DefaultPlace> {
  await set(DEFAULT_PLACE_KEY, place)
  return place
}

export async function clearDefaultPlace(): Promise<void> {
  await del(DEFAULT_PLACE_KEY)
}

/**
 * The camera a place opens on: its box when it has one, so a park or a trail
 * is fitted rather than centred on a point somewhere inside it; else the
 * point at a planning zoom.
 *
 * @unvalidated 12 is the zoom at which a trailhead's surroundings - the lot,
 * the first mile of trail, the road in - fill a phone; nobody has opened the
 * map on a stored place yet. What would settle it is which zoom a hiker
 * pinches to from here on their first map open, which nothing measures.
 */
export const DEFAULT_PLACE_ZOOM = 12

export function defaultPlaceCamera(
  place: DefaultPlace,
):
  | { bounds: readonly [number, number, number, number] }
  | { center: readonly [number, number]; zoom: number } {
  if (place.bbox !== undefined) return { bounds: place.bbox }
  return { center: [place.lon, place.lat], zoom: DEFAULT_PLACE_ZOOM }
}
