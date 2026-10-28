import { expect, it } from 'vitest'
import {
  BEFORE_YOU_GO,
  CLOSE_AND_RESTORE,
  HARDEN,
  SOURCES,
  WHO_IS_COVERED,
  planFor,
} from './guide'

it('every step, note and check names an ATC document from SOURCES', () => {
  for (const item of [
    ...CLOSE_AND_RESTORE,
    ...HARDEN,
    ...WHO_IS_COVERED,
    ...BEFORE_YOU_GO,
  ]) {
    expect(SOURCES[item.source].url).toMatch(/^https:\/\/appalachiantrail\.org\//)
  }
})

it('keeps every quote short, because ATC allows quoting but not reproduction', () => {
  // 25 words is our ceiling for "a brief quote", not ATC's: their terms set no number.
  const quotes = [...CLOSE_AND_RESTORE, ...HARDEN, ...WHO_IS_COVERED]
    .map((s) => s.quote)
    .filter(Boolean)
  for (const quote of quotes) expect(quote!.split(/\s+/).length).toBeLessThanOrEqual(25)
})

it('planFor gives the close-and-restore steps, the harden steps, or none for an action that is not work', () => {
  expect(planFor('close_restore')).toBe(CLOSE_AND_RESTORE)
  expect(planFor('harden')).toBe(HARDEN)
  expect(planFor('monitor')).toEqual([])
  expect(planFor('adopt_note')).toEqual([])
})

it('marks restoring the ground as needing land-manager approval, as ATC does', () => {
  expect(
    CLOSE_AND_RESTORE.find((s) => s.title.startsWith('Restore the ground'))
      ?.needsApproval,
  ).toBe(true)
  expect(
    CLOSE_AND_RESTORE.find((s) => s.title === 'Hide the site')?.needsApproval,
  ).toBeFalsy()
})
