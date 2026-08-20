// Data staleness tiers. See WIREFRAMES.md's Data staleness section: a third
// visual channel, independent of confidence (whether a POI was ever
// verified to exist - a separate concern rendered elsewhere, e.g. a dashed
// pin outline). This module answers only "when did a human last confirm
// this was fine".
//
// THE PRODUCER EXISTS NOW (#256): field notes (features/FIELD_NOTES.md),
// whose roll-up feeds `lastConfirmed` from the most recent visible
// observation - lib/noteRollup.ts. The consumers are the pin treatment
// (map/poiLayers.ts), the waypoint lanes, and the card's last-confirmed
// line (lib/stalenessDisplay.ts).
//
// NEVER-CONFIRMED IS ITS OWN TIER, NOT `stale` - maintainer decision,
// 2026-08-20 (recorded on #256). WIREFRAMES.md §11 wrote null as stale,
// and wiring that to a map with no confirmations yet would render every
// pin stale on day one - "nothing here is trustworthy" as the opening
// screen, which is #256's own warning. So `never` is a fourth answer:
// shelters, campsites and resupply render neutral until somebody has
// confirmed them once, and the fresh/ageing/stale ladder applies only to
// places with a confirmation history - "stale" keeps the meaning "was
// confirmed, went quiet". Water is the deliberate exception, decided the
// same night: a never-confirmed water source carries a subtle "no recent
// word" invite for everyone, because the OSM/USGS water data is unverified
// by FEATURES.md's own admission and water is the type where an unknown
// costs a hiker most. That per-type split lives in the consumer
// (stalenessDisplay.ts), not here - this module does not know types.
//
// @unvalidated - the two thresholds. WIREFRAMES.md §11 writes them as
// "≤ ~14 days" and "~14-60 days" and DATA_NUDGES.md names the tiers without
// numbers, so the tildes are the whole provenance: they are a mock-up's round
// figures, not a finding about how long a spring's condition stays true. What
// would settle them is field-note data now that there can be some - how fast
// a confirmation actually stops predicting what a hiker finds, which plausibly
// differs by POI type (a shelter does not dry up in August; a spring does).
// Until then they must not be quoted anywhere as a claim about the world.

export type StalenessTier = 'fresh' | 'ageing' | 'stale' | 'never'

const FRESH_MAX_DAYS = 14
const AGEING_MAX_DAYS = 60

export function stalenessTier(lastConfirmed: Date | null): StalenessTier {
  if (lastConfirmed === null) return 'never'

  const ageDays = (Date.now() - lastConfirmed.getTime()) / (24 * 60 * 60 * 1000)

  if (ageDays <= FRESH_MAX_DAYS) return 'fresh'
  if (ageDays <= AGEING_MAX_DAYS) return 'ageing'
  return 'stale'
}
