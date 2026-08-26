// Tests for plan.ts - the multi-day plan's model (#756).
//
// The boundary-shaped storage is the thing most worth pinning: n+1 stops
// carry n days, so every mutation has to leave that arithmetic true or the
// whole plan is refused on next load. The other load-bearing decisions -
// zeros as same-stop days, day numbers that skip zeros, food carries that
// include them - are each asserted against the scenario the wireframes
// drew.

import { describe, expect, it, vi } from 'vitest'

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
}))

import { get, set } from 'idb-keyval'
import {
  buildPlan,
  DAY_NOTE_MAX_CHARS,
  dateOfDay,
  foodCarries,
  insertZeroAfter,
  keepingRest,
  LONG_CARRY_DAYS,
  loadPlan,
  PLAN_KEY,
  planDayViews,
  planDirection,
  planSections,
  removeDay,
  NEARO_MAX_MI,
  savePlan,
  setDayNote,
  stillARest,
  togglePinned,
  toggleResupply,
  validatePlan,
  type HikePlan,
  type PlanStop,
} from './plan'

const stop = (mile: number, extra: Partial<PlanStop> = {}): PlanStop => ({
  mile,
  resupply: false,
  ...extra,
})

/** Damascus → Atkins as the wireframes sketch it: three walking days, a
 *  zero at Grayson Highlands, and a resupply at the far end. */
function wireframePlan(): HikePlan {
  const plan = buildPlan(
    [
      stop(470.8, { name: 'Damascus', resupply: true }),
      stop(486.2, { name: 'Lost Mountain Shelter' }),
      stop(503.3, { name: 'Thomas Knob Shelter' }),
      stop(516.1, { name: 'Old Orchard Shelter' }),
      stop(525.7, { name: 'Atkins', resupply: true }),
    ],
    { walkingHours: 7 },
    '2026-05-12',
  )
  return insertZeroAfter(plan, 1)
}

describe('validatePlan', () => {
  it('accepts what buildPlan builds', () => {
    const plan = wireframePlan()
    expect(validatePlan(plan)).toEqual(plan)
  })

  it('refuses a boundary count that cannot carry the days', () => {
    const plan = wireframePlan()
    expect(validatePlan({ ...plan, days: plan.days.slice(1) })).toBeNull()
    expect(validatePlan({ ...plan, stops: plan.stops.slice(1) })).toBeNull()
  })

  it('refuses a single boundary - one stop carries no day', () => {
    expect(validatePlan({ target: { miles: 15 }, stops: [stop(5)], days: [] })).toBeNull()
  })

  it('refuses a stop with no honest mile', () => {
    const plan = wireframePlan()
    const stops = [...plan.stops]
    stops[0] = { ...stops[0], mile: Number.NaN }
    expect(validatePlan({ ...plan, stops })).toBeNull()
  })

  it('refuses a target in no unit, and keeps the unit it was given', () => {
    const plan = wireframePlan()
    expect(validatePlan({ ...plan, target: {} })).toBeNull()
    expect(validatePlan({ ...plan, target: { miles: 15 } })?.target).toEqual({
      miles: 15,
    })
    expect(validatePlan({ ...plan, target: { walkingHours: 7 } })?.target).toEqual({
      walkingHours: 7,
    })
  })

  it('refuses a date that is not a date, and a calendar with holes in it', () => {
    const plan = wireframePlan()
    const badDate = plan.days.map((day, i) =>
      i === 0 ? { ...day, date: 'May 12' } : day,
    )
    expect(validatePlan({ ...plan, days: badDate })).toBeNull()

    // Half-dated: the plan cannot answer "when do I finish".
    const halfDated = plan.days.map((day, i) =>
      i === 2 ? { id: day.id, pinned: day.pinned, generated: day.generated } : day,
    )
    expect(validatePlan({ ...plan, days: halfDated })).toBeNull()

    // Backwards: no shift can know which order was meant.
    const backwards = plan.days.map((day, i) =>
      i === 1 ? { ...day, date: '2020-01-01' } : day,
    )
    expect(validatePlan({ ...plan, days: backwards })).toBeNull()
  })

  it('refuses a walked day after an unwalked one - days are walked in order', () => {
    const plan = wireframePlan()
    const holed = plan.days.map((day, i) => (i === 2 ? { ...day, walked: true } : day))
    expect(validatePlan({ ...plan, days: holed })).toBeNull()

    const prefix = plan.days.map((day, i) => (i <= 1 ? { ...day, walked: true } : day))
    expect(validatePlan({ ...plan, days: prefix })).not.toBeNull()
  })

  it('drops a rest flag a pre-#1031 build stranded on a long day', () => {
    // Every plan already on a phone was written by a build whose cascade
    // could leave this behind, and a plan is not re-planned on load - so
    // this boundary is the only place one written months ago is met.
    const plan = wireframePlan()
    const stranded = plan.days.map((day, i) => (i === 0 ? { ...day, rest: true } : day))
    const loaded = validatePlan({ ...plan, days: stranded })

    expect(loaded).not.toBeNull()
    // Day 0 is Damascus → Lost Mountain, 15.4 miles. Nobody rested.
    expect(loaded!.days[0].rest).toBeUndefined()
    // And the plan itself survives - a wrong label is never worth the days.
    expect(loaded!.days).toHaveLength(plan.days.length)
  })

  it('keeps a rest flag the boundaries still support', () => {
    const plan = wireframePlan()
    // Day 2 is the zero at Thomas Knob - a rest by its boundaries alone.
    const rested = plan.days.map((day, i) => (i === 2 ? { ...day, rest: true } : day))
    expect(validatePlan({ ...plan, days: rested })!.days[2].rest).toBe(true)
  })
})

describe('storage', () => {
  it('re-validates on the way out rather than trusting the store', async () => {
    vi.mocked(get).mockResolvedValueOnce({ half: 'a plan' })
    expect(await loadPlan()).toBeNull()
  })

  it('round-trips under its own key', async () => {
    const plan = wireframePlan()
    await savePlan(plan)
    expect(vi.mocked(set)).toHaveBeenCalledWith(PLAN_KEY, plan)
    vi.mocked(get).mockResolvedValueOnce(plan)
    expect(await loadPlan()).toEqual(plan)
  })
})

describe('planDayViews', () => {
  it('numbers walking days and leaves zeros unnumbered', () => {
    const views = planDayViews(wireframePlan())
    expect(views.map((day) => day.dayNumber)).toEqual([1, 2, null, 3, 4])
    expect(views.map((day) => day.zero)).toEqual([false, false, true, false, false])
  })

  it('dates every day from the start date, zeros included', () => {
    const views = planDayViews(wireframePlan())
    expect(views.map((day) => day.date)).toEqual([
      '2026-05-12',
      '2026-05-13',
      '2026-05-14',
      '2026-05-15',
      '2026-05-16',
    ])
  })

  it('carries no dates when the plan has none - day numbers only', () => {
    const undated = buildPlan(wireframePlan().stops, { walkingHours: 7 })
    expect(planDayViews(undated).every((day) => day.date === null)).toBe(true)
  })
})

describe('dateOfDay', () => {
  it('walks across month ends in plain UTC arithmetic', () => {
    expect(dateOfDay('2026-05-30', 0)).toBe('2026-05-30')
    expect(dateOfDay('2026-05-30', 3)).toBe('2026-06-02')
  })
})

describe('planSections', () => {
  it('closes a span where a day ends at a resupply, zeros counted in the carry', () => {
    // The open question - does a zero count against the food carry - is
    // answered here the way the wireframes bracket it: yes, the direction
    // that errs toward carrying enough. One span Damascus → Atkins: five
    // days of food, one of them the zero.
    const sections = planSections(planDayViews(wireframePlan()))
    expect(sections).toHaveLength(1)
    expect(sections[0].foodDays).toBe(5)
    expect(sections[0].distanceMi).toBeCloseTo(525.7 - 470.8)
  })

  it('splits at a mid-plan resupply', () => {
    const plan = wireframePlan()
    // Thomas Knob's boundary is stop index 3 once the zero duplicated one.
    const withResupply = toggleResupply(plan, 3)
    const sections = planSections(planDayViews(withResupply))
    expect(sections).toHaveLength(2)
    expect(sections[0].foodDays).toBe(3)
    expect(sections[1].foodDays).toBe(2)
  })
})

describe('edits', () => {
  it('inserts a zero as a same-stop day and keeps the boundary arithmetic', () => {
    const plan = wireframePlan()
    expect(plan.stops).toHaveLength(6)
    expect(plan.days).toHaveLength(5)
    const zero = planDayViews(plan)[2]
    expect(zero.zero).toBe(true)
    expect(zero.start.name).toBe('Thomas Knob Shelter')
    expect(zero.end.name).toBe('Thomas Knob Shelter')
    expect(validatePlan(plan)).not.toBeNull()
  })

  it('removes a zero without disturbing its neighbours', () => {
    const plan = wireframePlan()
    const without = removeDay(plan, 2)
    expect(planDayViews(without).map((day) => day.zero)).toEqual([
      false,
      false,
      false,
      false,
    ])
    expect(without.days.map((day) => day.generated)).toEqual([true, true, true, true])
  })

  it('folds a removed walking day into the day after it, and says so', () => {
    const plan = wireframePlan()
    const without = removeDay(plan, 0)
    const first = planDayViews(without)[0]
    expect(first.start.name).toBe('Damascus')
    expect(first.end.name).toBe('Thomas Knob Shelter')
    expect(first.zero).toBe(false)
    // The day that absorbed the miles is no longer the generator's day.
    expect(without.days[0].generated).toBe(false)
  })

  it('will not remove the only day', () => {
    const one = buildPlan([stop(0), stop(10)], { miles: 10 })
    expect(removeDay(one, 0)).toBe(one)
  })

  it('pins mark a day as the hiker’s own', () => {
    const plan = wireframePlan()
    const pinned = togglePinned(plan, 2)
    expect(pinned.days[2].pinned).toBe(true)
    // Touching a day retires the quiet "auto" marker, and it never returns.
    expect(pinned.days[2].generated).toBe(false)
    expect(togglePinned(pinned, 2).days[2].generated).toBe(false)
  })

  it('drops the rest badge from a day that grew past a nearo (#1031)', () => {
    // A nearo the rhythm placed, then the day before it removed - so this
    // day absorbs those miles. Before #1031 the badge rode along, and the
    // timeline called a 21.8-mile day the hiker's rest day.
    const withNearo: HikePlan = {
      ...buildPlan(
        [stop(470.8), stop(486.2), stop(490.4), stop(516.1)],
        { miles: 15 },
        '2026-05-12',
      ),
    }
    withNearo.days[1] = { ...withNearo.days[1], rest: true }
    expect(planDayViews(withNearo)[1].rest).toBe(true)

    const folded = removeDay(withNearo, 0)
    const grown = planDayViews(folded)[0]
    expect(Math.abs(grown.end.mile - grown.start.mile)).toBeCloseTo(19.6, 1)
    expect(grown.rest).toBe(false)
    expect(validatePlan(folded)).not.toBeNull()
  })

  it('keeps the rest badge on a day that is still short enough', () => {
    const withNearo: HikePlan = {
      ...buildPlan([stop(470.8), stop(472.8), stop(476.0)], { miles: 15 }),
    }
    withNearo.days[1] = { ...withNearo.days[1], rest: true }
    // Folding day 0 in leaves 5.2 miles, inside the nearo window.
    const folded = removeDay(withNearo, 0)
    expect(planDayViews(folded)[0].rest).toBe(true)
  })

  it('flips resupply on the stop, which every day meeting it shares', () => {
    const plan = wireframePlan()
    const flagged = toggleResupply(plan, 3)
    expect(flagged.stops[3].resupply).toBe(true)
    expect(toggleResupply(flagged, 3).stops[3].resupply).toBe(false)
  })
})

describe('what a rest still is (#1031)', () => {
  it('is a zero, or a walk inside the nearo window', () => {
    expect(stillARest(100, 100)).toBe(true)
    expect(stillARest(100, 100 + NEARO_MAX_MI)).toBe(true)
    // Southbound counts the same way - the flag is about a distance.
    expect(stillARest(100, 100 - NEARO_MAX_MI)).toBe(true)
    expect(stillARest(100, 100 + NEARO_MAX_MI + 0.1)).toBe(false)
  })

  it('drops a spent flag and leaves everything else alone', () => {
    const meta = { id: 'a', pinned: false, generated: true, rest: true, note: 'hi' }
    const kept = keepingRest(meta, 0, 20)
    expect(kept.rest).toBeUndefined()
    expect(kept.note).toBe('hi')
    expect(kept.generated).toBe(true)
  })

  it('leaves a meta alone when there is nothing to drop', () => {
    const noFlag = { id: 'a', pinned: false, generated: true }
    expect(keepingRest(noFlag, 0, 20)).toBe(noFlag)
    const stillResting = { id: 'b', pinned: false, generated: true, rest: true }
    expect(keepingRest(stillResting, 0, 3)).toBe(stillResting)
  })
})

describe('planDirection', () => {
  it('reads from the ends, and withholds when there are none', () => {
    expect(planDirection(wireframePlan())).toBe('NOBO')
    const south = buildPlan([stop(100), stop(90)], { miles: 10 })
    expect(planDirection(south)).toBe('SOBO')
  })
})

describe('foodCarries (#799)', () => {
  /** Ten 10-mile days, resupply at the end of day 3 and day 7. */
  function withResupplies(): HikePlan {
    let plan = buildPlan(
      Array.from({ length: 11 }, (_, index) => ({
        mile: index * 10,
        name: `Stop ${index * 10}`,
        resupply: false,
      })),
      { miles: 10 },
    )
    plan = toggleResupply(plan, 3)
    plan = toggleResupply(plan, 7)
    return plan
  }

  it('is one carry per section, named at both ends', () => {
    const carries = foodCarries(planSections(planDayViews(withResupplies())))

    expect(carries).toHaveLength(3)
    expect(carries[0]).toMatchObject({
      from: { name: 'Stop 0' },
      to: { name: 'Stop 30' },
      days: 3,
      restockAtEnd: true,
    })
    expect(carries[1]).toMatchObject({ days: 4, restockAtEnd: true })
    // The last stretch buys nothing at its end - the plan simply runs out,
    // which is the case worth saying out loud.
    expect(carries[2]).toMatchObject({ days: 3, restockAtEnd: false })
  })

  it('is one long carry when nothing is bought anywhere', () => {
    const carries = foodCarries(
      planSections(
        planDayViews(
          buildPlan(
            [
              { mile: 0, resupply: false },
              { mile: 10, resupply: false },
              { mile: 20, resupply: false },
            ],
            { miles: 10 },
          ),
        ),
      ),
    )

    expect(carries).toHaveLength(1)
    expect(carries[0].days).toBe(2)
    expect(carries[0].restockAtEnd).toBe(false)
  })

  it('counts a zero against the carry it sits in, not as a carry of its own', () => {
    // The bug this fixes: the zero's duplicated boundary used to inherit
    // the resupply flag, which closed a second section containing just the
    // zero - so a rest day in town read as "1 day food" and vanished from
    // the carry it actually eats from.
    const plan = insertZeroAfter(
      toggleResupply(
        buildPlan(
          [
            { mile: 0, resupply: false },
            { mile: 10, resupply: false },
            { mile: 20, resupply: false },
            { mile: 30, resupply: false },
          ],
          { miles: 10 },
        ),
        1,
      ),
      0,
    )

    const carries = foodCarries(planSections(planDayViews(plan)))
    expect(carries).toHaveLength(2)
    expect(carries[0].days).toBe(1) // up to the resupply
    expect(carries[1].days).toBe(3) // the zero, and the two days after it
  })

  it('has a stated threshold for when a carry is worth mentioning', () => {
    // A number, not a rule the screens each invent for themselves.
    expect(LONG_CARRY_DAYS).toBeGreaterThan(0)
  })
})

describe("the hiker's own line on a day (#966)", () => {
  const dayPlan = () =>
    buildPlan([stop(470.8), stop(486.2), stop(503.3)], { miles: 15 }, '2026-05-12')

  it('stores what was written, and shows it on the view', () => {
    const kept = setDayNote(dayPlan(), 0, 'the ponies were unbothered')
    expect(kept.days[0].note).toBe('the ponies were unbothered')
    expect(planDayViews(kept)[0].note).toBe('the ponies were unbothered')
    expect(planDayViews(kept)[1].note).toBeNull()
  })

  it('may be written on a WALKED day - the one edit the past accepts', () => {
    // Every other mutator refuses a walked day. This one exists because a
    // memory is written about the past, after it, which is what the day
    // summary is for.
    const walked = { ...dayPlan() }
    walked.days = walked.days.map((day, i) => (i === 0 ? { ...day, walked: true } : day))
    const kept = setDayNote(walked, 0, 'mile 500 came and went')
    expect(kept.days[0].note).toBe('mile 500 came and went')
    // ...and it changes nothing else about the record.
    expect(kept.days[0].walked).toBe(true)
    expect(kept.stops).toEqual(walked.stops)
    expect(kept.days[0].date).toBe(walked.days[0].date)
  })

  it('does not drop the "auto" marker - writing a memory is not an edit', () => {
    const generated = dayPlan()
    expect(generated.days[0].generated).toBe(true)
    expect(setDayNote(generated, 0, 'good water at the gap').days[0].generated).toBe(true)
  })

  it('clears the field on a blank line rather than storing an empty string', () => {
    const kept = setDayNote(dayPlan(), 0, 'something')
    expect(setDayNote(kept, 0, '   ').days[0].note).toBeUndefined()
    expect('note' in setDayNote(kept, 0, '').days[0]).toBe(false)
  })

  it('trims and caps what it stores', () => {
    const long = 'x'.repeat(DAY_NOTE_MAX_CHARS + 50)
    expect(setDayNote(dayPlan(), 0, `  spaced  `).days[0].note).toBe('spaced')
    expect(setDayNote(dayPlan(), 0, long).days[0].note).toHaveLength(DAY_NOTE_MAX_CHARS)
  })

  it('ignores an index that is not a day', () => {
    const plan = dayPlan()
    expect(setDayNote(plan, -1, 'nope')).toBe(plan)
    expect(setDayNote(plan, 99, 'nope')).toBe(plan)
  })

  it('costs its own line and never the plan when storage returns junk', () => {
    // validateRhythm's trade, applied to the other field carrying no
    // invariant: a plan whose days are all there is worth more than one
    // line of prose an older build wrote wrong.
    const plan = dayPlan() as HikePlan & { days: Record<string, unknown>[] }
    const withNumber = validatePlan({
      ...plan,
      days: plan.days.map((day, i) => (i === 0 ? { ...day, note: 42 } : day)),
    })
    expect(withNumber).not.toBeNull()
    expect(withNumber?.days).toHaveLength(2)
    expect(withNumber?.days[0].note).toBeUndefined()

    const overLong = validatePlan({
      ...plan,
      days: plan.days.map((day, i) =>
        i === 0 ? { ...day, note: 'y'.repeat(DAY_NOTE_MAX_CHARS + 10) } : day,
      ),
    })
    expect(overLong?.days[0].note).toHaveLength(DAY_NOTE_MAX_CHARS)
  })

  it('survives a save/load round trip', async () => {
    const kept = setDayNote(dayPlan(), 1, 'cold night at the knob')
    await savePlan(kept)
    vi.mocked(get).mockResolvedValueOnce(vi.mocked(set).mock.calls.at(-1)?.[1])
    expect((await loadPlan())?.days[1].note).toBe('cold night at the knob')
  })
})
