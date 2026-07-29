// Data staleness tiers. See WIREFRAMES.md's Data staleness section: a third
// visual channel, independent of confidence (whether a POI was ever
// verified to exist - a separate concern rendered elsewhere, e.g. a dashed
// pin outline). This module answers only "when did a human last confirm
// this was fine" - never confirmed at all (null) is stale, same as
// confirmed too long ago.

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
