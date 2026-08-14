// Data staleness tiers. See WIREFRAMES.md's Data staleness section: a third
// visual channel, independent of confidence (whether a POI was ever
// verified to exist - a separate concern rendered elsewhere, e.g. a dashed
// pin outline). This module answers only "when did a human last confirm
// this was fine" - never confirmed at all (null) is stale, same as
// confirmed too long ago.

// NOTHING CALLS THIS YET, and that is the state #256 - "The POI staleness
// tiers have no producer and no consumer" - is open about. No published POI
// carries a confirmation date: export_poi.py has no such column and neither
// ATC nor opentrail.org has one to give, so wiring these tiers to the map
// today would render every pin `stale` (null is stale, below) and read as
// "nothing here is trustworthy" on day one. The producer is v2's field notes
// (features/FIELD_NOTES.md, ROADMAP.md's v2 section). This module is a
// spec-holder until then; #256 asks for that to be said where the module
// lives, which is what this paragraph is.
//
// @unvalidated - the two thresholds. WIREFRAMES.md §11 writes them as
// "≤ ~14 days" and "~14-60 days" and DATA_NUDGES.md names the tiers without
// numbers, so the tildes are the whole provenance: they are a mock-up's round
// figures, not a finding about how long a spring's condition stays true. What
// would settle them is field-note data once there is any - how fast a
// confirmation actually stops predicting what a hiker finds, which plausibly
// differs by POI type (a shelter does not dry up in August; a spring does).
// Until then they must not be quoted anywhere as a claim about the world.

export type StalenessTier = 'fresh' | 'ageing' | 'stale'

const FRESH_MAX_DAYS = 14
const AGEING_MAX_DAYS = 60

export function stalenessTier(lastConfirmed: Date | null): StalenessTier {
  if (lastConfirmed === null) return 'stale'

  const ageDays = (Date.now() - lastConfirmed.getTime()) / (24 * 60 * 60 * 1000)

  if (ageDays <= FRESH_MAX_DAYS) return 'fresh'
  if (ageDays <= AGEING_MAX_DAYS) return 'ageing'
  return 'stale'
}
