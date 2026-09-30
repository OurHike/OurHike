/**
 * The one line that picks the Plan tab's room, tested where it now lives.
 *
 * These three assertions moved here with the function from
 * `screens/PlanHome.test.tsx` (2026-09-18). What they check has not changed:
 * there are two rooms and three modes, and the third mode is not a third
 * room. lib/planRoom.ts says why the function left the screen.
 */

import { describe, expect, it } from 'vitest'
import { planRoomFor } from './planRoom'

describe('which room the Plan tab opens in', () => {
  it('takes its room from the app’s mode, and gives volunteer the day room', () => {
    // Not a third room: "today I'm volunteering" is a statement about the
    // day's work, not a kind of planning.
    expect(planRoomFor('long')).toBe('sections')
    expect(planRoomFor('day')).toBe('day')
    expect(planRoomFor('volunteer')).toBe('day')
  })
})
