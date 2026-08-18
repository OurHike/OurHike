// Buckets of the hiker's own choosing (#800) - "every Sunday", "with Dad",
// "2026 season".
//
// A GROUP IS NOT A HIKE, and the difference is load-bearing rather than
// taxonomic. A Hike (lib/hikes.ts) has two ends, and those ends are what
// make #790's ribbon and #791's gaps mean anything: subtract the walked
// ground from the ends and what is left is what you owe. A group has no
// ends. Forcing one into `Hike` would put a meaningless start and end on
// half the objects in the store and make every gap and ribbon path grow an
// "if it has ends" branch.
//
// So a trip has AT MOST ONE HIKE - its parent on the trail, the tree
// SEGMENTS.md describes - and ANY NUMBER OF GROUPS. That second half was
// settled by the maintainer on review, with the case that settles it: the
// same walk belongs to "the entire AT" and to "my section this year". A
// trip's Sunday-ness and its place on the trail are different facts, so
// they are stored as different things.

import { mergeSpans, spanLength, walkedSpans } from './hikes'
import { planDayViews } from './plan'
import type { Trip } from './trips'

export interface TripGroup {
  id: string
  name: string
  /** The trips in it. Order is not meaning - the screen sorts by date. */
  tripIds: string[]
}

export function validateTripGroup(candidate: unknown): TripGroup | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const group = candidate as Partial<TripGroup>
  if (typeof group.id !== 'string' || group.id.length === 0) return null
  if (typeof group.name !== 'string') return null
  if (!Array.isArray(group.tripIds)) return null
  return {
    id: group.id,
    name: group.name,
    tripIds: group.tripIds.filter((id): id is string => typeof id === 'string'),
  }
}

/** Every group holding this trip. Several is the normal case, not an edge
 *  one - which is the whole difference from `hikeOfTrip`. */
export function groupsOfTrip(groups: readonly TripGroup[], tripId: string): TripGroup[] {
  return groups.filter((group) => group.tripIds.includes(tripId))
}

/**
 * What a group knows about itself.
 *
 * Deliberately short. There is no total and no "to go", because a set with
 * no two ends has nothing to be a fraction of - and no percentage, no
 * streak, and no count of Sundays in a row. A bucket of weekly day hikes is
 * exactly where a streak would arrive uninvited (OurHikeValues.md #1), and
 * the test suite guards this screen for that reason.
 */
export interface GroupFigures {
  tripCount: number
  /**
   * Trail walked, as a UNION rather than a sum - the same rule
   * `hikeFigures` follows, and for the same reason: a mile walked twice is
   * one mile of trail. It does mean a hiker who walks Bear Mountain every
   * other Sunday sees it counted once, which under-reports the walking they
   * did. Reporting both would put two numbers on screen whose difference
   * reads as a score for repeating yourself, so this reports the one the
   * rest of the app already means by "walked".
   */
  walkedMi: number
  daysWalked: number
  /** The first and last dates anything in the group is dated with, or null
   *  when nothing in it carries a date. */
  from: string | null
  to: string | null
}

export function groupFigures(group: TripGroup, trips: readonly Trip[]): GroupFigures {
  const mine = trips.filter((trip) => group.tripIds.includes(trip.id))
  const walked = mergeSpans(mine.flatMap((trip) => walkedSpans(trip.plan)))

  const dates = mine
    .flatMap((trip) => planDayViews(trip.plan).map((day) => day.date))
    .filter((date): date is string => date !== null)
    .sort()

  return {
    tripCount: mine.length,
    walkedMi: spanLength(walked),
    daysWalked: mine.reduce(
      (sum, trip) => sum + trip.plan.days.filter((day) => day.walked === true).length,
      0,
    ),
    from: dates[0] ?? null,
    to: dates[dates.length - 1] ?? null,
  }
}

/** A group's trips, earliest first, undated ones last - the order somebody
 *  reading a season of day hikes expects, and the only order a set with no
 *  geography has any claim to. */
export function groupTrips(group: TripGroup, trips: readonly Trip[]): Trip[] {
  const mine = trips.filter((trip) => group.tripIds.includes(trip.id))
  return mine.sort((a, b) => {
    const aDate = firstDate(a)
    const bDate = firstDate(b)
    if (aDate === null && bDate === null) return 0
    if (aDate === null) return 1
    if (bDate === null) return -1
    return aDate.localeCompare(bDate)
  })
}

function firstDate(trip: Trip): string | null {
  for (const day of trip.plan.days) {
    if (day.date !== undefined) return day.date
  }
  return null
}
