// Tests for the rest rhythm (#798).
//
// The load-bearing ones are the REFUSALS: a rest never lands on the record,
// never on the last day, and a nearo never becomes tomorrow. Everything
// else is arithmetic that a reader can check by counting rows.

import { describe, expect, it } from 'vitest'

import { applyRhythm, NEARO_MAX_MI } from './restRhythm'
import { buildPlan, planDayViews, type HikePlan } from './plan'
import type { StoredPoi } from './trailData'

/** Stops every 10 miles, which the planner would have chosen. */
function plan(days: number, rhythm?: HikePlan['rhythm'], startDate?: string): HikePlan {
  const built = buildPlan(
    Array.from({ length: days + 1 }, (_, index) => ({
      mile: index * 10,
      name: `Stop ${index * 10}`,
      resupply: false,
    })),
    { miles: 10 },
    startDate,
  )
  return rhythm === undefined ? built : { ...built, rhythm }
}

const poi = (mile: number, name: string): StoredPoi => ({
  id: `p${mile}`,
  type: 'shelter',
  name,
  lat: 0,
  lon: 0,
  confidence: 'high',
  mile,
})

/** A shelter 4 miles past every boundary - inside the nearo window. */
const POIS = [poi(24, 'Four Past'), poi(54, 'Four Past Again'), poi(31, 'Just Past')]

describe('applyRhythm', () => {
  it('does nothing at all without a rhythm', () => {
    const before = plan(10)
    expect(applyRhythm(before, POIS)).toBe(before)
  })

  it('drops a zero in after every n walking days', () => {
    const after = applyRhythm(plan(10, { everyDays: 3, kind: 'zero' }), [])
    const views = planDayViews(after)

    // 10 walking days, a zero after the 3rd, 6th and 9th - and none after
    // the 10th, because a rest on the day you go home is nobody resting.
    expect(views).toHaveLength(13)
    expect(views.map((day) => day.zero)).toEqual([
      false,
      false,
      false,
      true,
      false,
      false,
      false,
      true,
      false,
      false,
      false,
      true,
      false,
    ])
  })

  it('does not let a rest trigger the next rest', () => {
    // A rhythm of 1 with rests counting as walking days would never
    // terminate. Neither a zero nor a nearo moves the count.
    const after = applyRhythm(plan(3, { everyDays: 1, kind: 'zero' }), [])
    expect(planDayViews(after)).toHaveLength(5) // walk, rest, walk, rest, walk
  })

  it('walks a nearo to a real place, and the day after is shorter for it', () => {
    const after = applyRhythm(plan(4, { everyDays: 2, kind: 'nearo' }), POIS)
    const views = planDayViews(after)

    const nearo = views[2]
    expect(nearo.zero).toBe(false)
    expect(nearo.end.name).toBe('Four Past')
    expect(Math.abs(nearo.end.mile - nearo.start.mile)).toBe(4)

    // The day after runs from where the nearo stopped, so it is 6 rather
    // than 10 - true, and the timeline prints it.
    expect(Math.abs(views[3].end.mile - views[3].start.mile)).toBe(6)
  })

  it('falls back to a zero when nothing is inside the window', () => {
    // Same rhythm, no POIs at all: still a rest, and honestly a zero.
    const after = applyRhythm(plan(4, { everyDays: 2, kind: 'nearo' }), [])
    expect(planDayViews(after)[2].zero).toBe(true)
  })

  it('never lets a nearo walk past tomorrow’s stop', () => {
    // A shelter 4 miles on is inside the window, but this plan's days are
    // only 3 miles long - walking to it would not be a rest, it would be
    // tomorrow.
    const short = buildPlan(
      [
        { mile: 20, resupply: false },
        { mile: 23, resupply: false },
        { mile: 26, resupply: false },
        { mile: 29, resupply: false },
      ],
      { miles: 3 },
    )
    const after = applyRhythm({ ...short, rhythm: { everyDays: 1, kind: 'nearo' } }, POIS)
    expect(planDayViews(after)[1].zero).toBe(true)
  })

  it('keeps a nearo inside its own window', () => {
    // The nearest stop beyond is real but far; the window is what makes a
    // nearo a nearo rather than an ordinary day with a label on it.
    const far = [poi(20 + NEARO_MAX_MI + 5, 'Too Far')]
    const after = applyRhythm(plan(4, { everyDays: 2, kind: 'nearo' }), far)
    expect(planDayViews(after)[2].zero).toBe(true)
  })

  it('moves the calendar for everything after each rest', () => {
    const after = applyRhythm(plan(4, { everyDays: 2, kind: 'zero' }, '2026-05-12'), [])
    expect(after.days.map((day) => day.date)).toEqual([
      '2026-05-12',
      '2026-05-13',
      '2026-05-14', // the zero
      '2026-05-15',
      '2026-05-16',
    ])
  })

  it('never rests on the record, or on the day after it', () => {
    const before = plan(6, { everyDays: 2, kind: 'zero' })
    before.days[0].walked = true
    before.days[1].walked = true
    const after = applyRhythm(before, [])
    const views = planDayViews(after)

    // The count runs over the walked days too, so the rhythm stays in step
    // across a half-walked trip. The rest that fell due at the end of the
    // record is not inserted there - it lands at the first boundary that is
    // nobody's record, which is the end of the first unwalked day.
    expect(views[0].walked).toBe(true)
    expect(views[1].walked).toBe(true)
    expect(views[2].zero).toBe(false)
    expect(views[3].zero).toBe(true)
    // ...and then carries on every two walking days, minus the last day.
    expect(views.filter((day) => day.zero)).toHaveLength(2)
    expect(views[views.length - 1].zero).toBe(false)
  })

  it('marks a rest as one, so a nearo is not just a short day', () => {
    const after = applyRhythm(plan(4, { everyDays: 2, kind: 'nearo' }), POIS)
    expect(after.days[2].rest).toBe(true)
    expect(after.days[2].generated).toBe(false)
    expect(after.days.filter((day) => day.rest === true)).toHaveLength(1)
  })
})
