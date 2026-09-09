// The multi-day plan: SEGMENTS.md's Hike → Segment tree carrying
// HIKE_PLANNING.md's three additions, and nothing else (#756).
//
// THE SHAPE, and how it maps onto the tree. SEGMENTS.md's leaves are days,
// and consecutive days are contiguous by construction - day N ends exactly
// where day N+1 starts, a zero being a day that ends where it started. So
// the storage is the boundaries themselves: n+1 stops carry n days, each
// day's own metadata rides in a parallel list, and the contiguity that a
// start/end-per-day shape would have to re-validate on every read is here
// unrepresentable instead. Sections are NOT stored - "a section is derived,
// not drawn" (HIKE_PLANNING.md, "The model") - they fall out of the resupply
// flags below. The hiker-override grouping that document also allows is not
// built yet; until it is, a section and a food carry are the same span.
//
// WHERE IT LIVES: the same IndexedDB as everything else, its own key, its
// own module - the plannedHike.ts pattern, and for plannedHike.ts's reasons
// (a plan is not a display preference, and preference keys are mirrored by a
// backend schema that rejects invented ones, #242). ~24 KB for a full
// thru-hike, which is why nothing here talks to a server (HIKE_PLANNING.md
// Q6). This does NOT replace `ourhike:hike`: the v1 pair keeps driving the
// direction-dependent safety surfaces, and wiring those to a plan instead is
// its own decision with its own review, not a side effect of saving one.
//
// THE GUARDRAIL, stated where the model is defined because the model is
// where it would be broken: nothing in this file computes "ahead", "behind",
// or any comparison of walked reality against planned intent. Value #1
// forbids prescriptive gamification, and a planner is two design decisions
// from a schedule that scolds. The plan is a hiker's own paper log with
// arithmetic attached.

import { del, get, set } from 'idb-keyval'
import type { HikeDirection } from '../chrome/Header'

export const PLAN_KEY = 'ourhike:plan'

/** A place a day starts or ends, on the pipeline's mile axis (#753) - the
 *  same measurement every figure in the plan is computed on. */
export interface PlanStop {
  mile: number
  /** Display name, resolved when the stop was chosen. Absent for a dropped
   *  point, which is named by its mile marker at render time. */
  name?: string
  /** The POI this stop is, when it is one. Kept so a later feature can
   *  follow the reference; display never requires it. */
  poiId?: string
  /**
   * Supplies are picked up here. A property of the STOP, not of a day: a
   * resupply happens at a place, and can land mid-walking-day as easily as
   * at the end of one (HIKE_PLANNING.md, "The model").
   */
  resupply: boolean
}

/** One day's own facts - everything about it that is not a boundary. */
export interface PlanDayMeta {
  /** Stable identity, for React keys today and SEGMENTS.md's completion
   *  model when the cascade arrives (#758). */
  id: string
  /**
   * ISO date (yyyy-mm-dd), or absent - thru-hikers plan loosely, and
   * SEGMENTS.md made the date optional for exactly that reason. Stored on
   * the DAY rather than derived from one start date, because the cascade
   * (#758) moves the calendar in pieces: a shift moves every date after
   * today and none before it, which no single start date can carry. Dated
   * plans are dated throughout; the validator refuses a mix.
   */
  date?: string
  /** This day does not move - a booked hostel, a mail drop with a date on
   *  it. The cascade re-plans between pins and never through one. */
  pinned: boolean
  /** The app chose this day and the hiker has not touched it - the
   *  timeline's quiet "auto" marker. Flips false on the first edit; back to
   *  true only where the cascade has since re-planned the day, which is the
   *  app choosing it again rather than the marker leaking. */
  generated: boolean
  /**
   * This day was walked. A record, not a plan any more (SEGMENTS.md's
   * completion model): its boundaries say where it actually ran, nothing may
   * edit it, and the cascade only ever touches days after it. Walked days
   * form a prefix - days are walked in order - and the validator holds that.
   */
  walked?: boolean
  /**
   * What this day's distance was before a cascade re-planned it, in miles.
   * A fact about the plan, never a verdict on the hiker - the timeline
   * prints it as "was 17.1 mi" and nothing more.
   */
  wasDistanceMi?: number
  /**
   * This day is a REST the rhythm asked for (#798), rather than a day that
   * happens to be short.
   *
   * A zero is already recognisable from its boundaries - it starts and ends
   * at one stop - but a nearo is a walking day of four miles, which is
   * indistinguishable from a walking day of four miles. The flag is the
   * only thing that can tell a screen the difference between "the trail
   * gave you a short day" and "you asked for one".
   */
  rest?: boolean
  /**
   * The line the hiker wrote for themselves about this day (#966), from the
   * day summary's "add a line for future you".
   *
   * THEIRS, AND THE ONLY PROSE ON A DAY. Everything else in this interface
   * is something the app worked out; this is the one field the app never
   * writes, never parses and never shows to anybody else. It is stored on
   * the day rather than in a separate log for the reason `date` is: the
   * cascade moves days around, and a memory that came unstuck from the day
   * it belongs to would attach itself to whatever ended up at that index.
   *
   * Capped at DAY_NOTE_MAX_CHARS on the way in and on the way back out of
   * storage - see validatePlan, which drops an over-long or non-string
   * value rather than refusing the whole plan, because a plan whose days
   * are all there is worth more than one line of prose.
   */
  note?: string
}

/**
 * How long the hiker's own line may be.
 *
 * @unvalidated 280 is picked, not measured. It is a sentence or two - the
 * length the wireframe's "the ponies were unbothered" sits at - and the
 * ceiling exists so a plan that syncs cannot become unbounded prose. What
 * would settle it: what people actually write, once anybody has written
 * any. Nothing on screen counts down toward it; a hiker who hits it is
 * writing a journal entry, and this was never the place for one.
 */
export const DAY_NOTE_MAX_CHARS = 280

/**
 * How far a nearo is allowed to walk.
 *
 * Lives here rather than in lib/restRhythm.ts, where it was written and
 * where it is still used to place a rest: it is the definition of what
 * `rest` means on a walking day, so every mutator below that changes a
 * day's distance has to know it, and restRhythm.ts imports plan.ts rather
 * than the other way round.
 *
 * @unvalidated 6 miles is picked, not measured. A nearo is understood on
 * this trail as a short day into or out of town - most of a rest, with a
 * couple of hours of walking in it - and six miles is the roundest number
 * inside every description of one I could find. Nobody has checked it
 * against what hikers actually walk on those days.
 *
 * What would settle it: the distribution of day lengths that hikers
 * themselves call nearos, which this app will start to have once #789's
 * recorded stretches and the day log accumulate. Until then the window errs
 * SHORT - a window too small falls back to a zero, which is a rest either
 * way, while one too large turns a rest day into an ordinary day of
 * walking and calls it a rest.
 */
export const NEARO_MAX_MI = 6

/**
 * Whether a day running `fromMile` → `toMile` can still be the rest its
 * `rest` flag claims - a zero, or a nearo inside the window above (#1031).
 *
 * THE FLAG IS A CLAIM ABOUT A DISTANCE, and four operations here and in
 * lib/cascade.ts move a day's boundaries: absorb and shift re-plan the
 * stretch under metas that keep their ordinal slot, `removeDay` folds a
 * removed day's miles into its neighbour, and `callItADay` moves tomorrow's
 * start to wherever the hiker actually stopped. Measured before the fix, on
 * a 15-mile-target plan with a nearo rhythm: those four put the badge on
 * days of 17.1, 8.1, 21.8 and 10.4 miles, and screens/Plan.tsx printed
 * "nearo · your rest day" against each of them.
 *
 * So every one of them runs the flag back through this, and a day that is
 * no longer a rest loses it. The rest itself is not re-placed - the plan
 * keeps its `rhythm`, so a re-lay reproduces the rests, and whether the
 * cascade should instead carry each one onto the new boundaries is #1031's
 * open half and a decision that moves days rather than labels.
 */
export function stillARest(fromMile: number, toMile: number): boolean {
  return Math.abs(toMile - fromMile) <= NEARO_MAX_MI
}

/** `meta` with a `rest` flag that has stopped being true dropped - see
 *  {@link stillARest}. Returns the same object when there is nothing to
 *  drop, so an unchanged day stays referentially unchanged. */
export function keepingRest(
  meta: PlanDayMeta,
  fromMile: number,
  toMile: number,
): PlanDayMeta {
  if (meta.rest !== true || stillARest(fromMile, toMile)) return meta
  const { rest: _spent, ...rest } = meta
  return rest
}

/**
 * A rest every `everyDays` walking days (#798).
 *
 * A hiker who takes a zero every Sunday plans one, and a generator that
 * only ever emits walking days makes them add seven by hand to a fifty-day
 * plan and lose them all on the next re-lay. Stored on the plan so a re-lay
 * reproduces the rhythm instead of forgetting it.
 *
 * TWO KINDS, because "a rest day" means two different things to two hikers:
 * a ZERO walks nothing, and a NEARO walks a few miles into or out of town.
 * A nearo falls back to a zero where no stop lies inside the window - and
 * says which it is rather than pretending.
 *
 * WHAT THIS IS NOT: an opinion. Nothing suggests a rhythm, warns that seven
 * days without one is a lot, marks a plan without one as incomplete, or
 * counts the rests taken. A plan that scores its own rest days is two
 * decisions from a streak (OurHikeValues.md #1).
 */
export interface RestRhythm {
  /** A rest after this many WALKING days. Zeros and nearos do not count
   *  toward it - otherwise a rest would trigger the next one. */
  everyDays: number
  kind: 'zero' | 'nearo'
}

/** What the generator aimed at. Two shapes rather than a number and a unit
 *  flag, so a target can never be read in the wrong unit. */
export type PlanTarget = { walkingHours: number } | { miles: number }

export interface HikePlan {
  target: PlanTarget
  /** n+1 boundaries carrying n days: days[i] runs stops[i] → stops[i+1]. */
  stops: PlanStop[]
  days: PlanDayMeta[]
  /** The rest rhythm this plan was laid out with, if any (#798). Kept so a
   *  re-lay reproduces it; absent on every plan written before it existed,
   *  and on every plan whose hiker did not ask for one. */
  rhythm?: RestRhythm
}

/**
 * A plan, or null if this value cannot describe one. Refused rather than
 * corrected, exactly like plannedHike(): this validates values an earlier
 * build may have written, and a shape that cannot carry the invariants must
 * not reach the arithmetic that assumes them.
 */
export function validatePlan(candidate: unknown): HikePlan | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const plan = candidate as Partial<HikePlan>

  if (!Array.isArray(plan.stops) || !Array.isArray(plan.days)) return null
  if (plan.days.length !== Math.max(0, plan.stops.length - 1)) return null
  if (plan.stops.length === 1) return null

  for (const stop of plan.stops) {
    if (typeof stop !== 'object' || stop === null) return null
    if (!Number.isFinite(stop.mile) || stop.mile < 0) return null
    if (typeof stop.resupply !== 'boolean') return null
  }
  for (const day of plan.days) {
    if (typeof day !== 'object' || day === null) return null
    if (typeof day.id !== 'string' || day.id.length === 0) return null
    if (typeof day.pinned !== 'boolean' || typeof day.generated !== 'boolean') return null
    if (day.date !== undefined && !/^\d{4}-\d{2}-\d{2}$/.test(day.date)) return null
    if (day.walked !== undefined && typeof day.walked !== 'boolean') return null
    if (day.rest !== undefined && typeof day.rest !== 'boolean') return null
    if (day.wasDistanceMi !== undefined && !Number.isFinite(day.wasDistanceMi)) {
      return null
    }
  }

  // The hiker's own line is SANITISED rather than validated, which is the
  // same trade validateRhythm makes below and for the same reason: every
  // other field on a day carries an invariant the arithmetic assumes, and
  // this one carries none. A note that came back as a number, or longer
  // than the cap an older build did not enforce, costs its own line -
  // never the plan's days, which are the part nobody can retype.
  //
  // A SPENT REST FLAG IS SANITISED HERE TOO, and for a reason the note does
  // not have: the four mutators that could strand one were fixed in #1031,
  // but every plan already on a phone was written by a build without that
  // fix, and a plan is not re-planned on load. So the flag is re-checked
  // against the boundaries it is stored beside, which is the only place a
  // plan written months ago can be met. Sanitised rather than refused,
  // because a spent badge is a wrong label and never a broken invariant.
  const stops = plan.stops as PlanStop[]
  const days = plan.days.map((day, index) => {
    const kept = keepingRest(day, stops[index].mile, stops[index + 1].mile)
    const note = (kept as { note?: unknown }).note
    if (note === undefined) return kept
    if (typeof note !== 'string' || note.length === 0) {
      const { note: _dropped, ...rest } = kept
      return rest as PlanDayMeta
    }
    return note.length <= DAY_NOTE_MAX_CHARS
      ? kept
      : { ...kept, note: note.slice(0, DAY_NOTE_MAX_CHARS) }
  })

  // Dated throughout or not at all, and forward-only: a plan that is half a
  // calendar cannot answer "when do I finish", and one whose dates run
  // backwards cannot be shifted without inventing which of the two orders
  // was meant.
  const dated = plan.days.filter((day) => day.date !== undefined)
  if (dated.length !== 0 && dated.length !== plan.days.length) return null
  for (let i = 1; i < dated.length; i++) {
    if ((dated[i].date as string) <= (dated[i - 1].date as string)) return null
  }

  // Walked days form a prefix - days are walked in order, and a record with
  // a hole in it is a shape no operation here can produce.
  const firstUnwalked = plan.days.findIndex((day) => day.walked !== true)
  if (
    firstUnwalked !== -1 &&
    plan.days.slice(firstUnwalked).some((day) => day.walked === true)
  ) {
    return null
  }

  const target = plan.target as PlanTarget | undefined
  if (typeof target !== 'object' || target === null) return null
  const hours = (target as { walkingHours?: unknown }).walkingHours
  const targetMiles = (target as { miles?: unknown }).miles
  const validHours = typeof hours === 'number' && Number.isFinite(hours) && hours > 0
  const validMiles =
    typeof targetMiles === 'number' && Number.isFinite(targetMiles) && targetMiles > 0
  if (!validHours && !validMiles) return null

  return {
    target: validHours
      ? { walkingHours: hours as number }
      : { miles: targetMiles as number },
    stops: plan.stops as PlanStop[],
    days: days as PlanDayMeta[],
    ...(validateRhythm(plan.rhythm) === null
      ? {}
      : { rhythm: validateRhythm(plan.rhythm) as RestRhythm }),
  }
}

/**
 * A rhythm, or null.
 *
 * DROPPED rather than refused, which is the opposite of how this file
 * treats everything else - and deliberately. Every other field here carries
 * an invariant the arithmetic assumes; the rhythm carries none. It records
 * what was asked for once, and a plan whose rhythm is unreadable is still a
 * plan whose days are all there. Losing the days to save the label would be
 * the wrong trade.
 */
function validateRhythm(candidate: unknown): RestRhythm | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const rhythm = candidate as Partial<RestRhythm>
  if (rhythm.kind !== 'zero' && rhythm.kind !== 'nearo') return null
  if (typeof rhythm.everyDays !== 'number') return null
  if (!Number.isInteger(rhythm.everyDays) || rhythm.everyDays < 1) return null
  return { everyDays: rhythm.everyDays, kind: rhythm.kind }
}

/** Re-validated on the way out rather than trusted - the same call
 *  loadPlannedHike makes about the same class of value. */
export async function loadPlan(): Promise<HikePlan | null> {
  const stored = await get(PLAN_KEY)
  if (stored === undefined || stored === null) return null
  return validatePlan(stored)
}

export async function savePlan(plan: HikePlan): Promise<void> {
  await set(PLAN_KEY, plan)
}

/** A first-class action, like clearPlannedHike: abandoning a plan must never
 *  mean clearing the app's data, and no-plan is a state every screen
 *  already handles - it is where every hiker starts. */
export async function clearPlan(): Promise<void> {
  await del(PLAN_KEY)
}

/** A fresh plan over generated day boundaries, every day marked as the
 *  generator's own until the hiker touches it. With a start date, days are
 *  dated consecutively from it; without one, day numbers carry the order. */
export function buildPlan(
  stops: PlanStop[],
  target: PlanTarget,
  startDate?: string,
): HikePlan {
  return {
    target,
    stops,
    days: Array.from({ length: Math.max(0, stops.length - 1) }, (_, index) => ({
      id: crypto.randomUUID(),
      ...(startDate === undefined ? {} : { date: dateOfDay(startDate, index) }),
      pinned: false,
      generated: true,
    })),
  }
}

/** Which way this plan runs, from its ends alone - the plannedHike.ts rule,
 *  for the plannedHike.ts reason. Null for an empty plan. */
export function planDirection(plan: HikePlan): HikeDirection | null {
  if (plan.stops.length < 2) return null
  const first = plan.stops[0].mile
  const last = plan.stops[plan.stops.length - 1].mile
  if (first === last) return null
  return last > first ? 'NOBO' : 'SOBO'
}

/** One day as the timeline reads it - the derived view over the stored
 *  boundaries. */
export interface PlanDayView {
  id: string
  /** Position in the plan, 0-based - the index every mutator below takes. */
  index: number
  /**
   * Walking-day number, 1-based, or null for a zero. Zeros hold a date and
   * a row and eat a day of food, and are still not a day anybody walked -
   * "DAY 24" on the wireframes counts the walking.
   */
  dayNumber: number | null
  /** yyyy-mm-dd, or null on an undated plan. */
  date: string | null
  start: PlanStop
  end: PlanStop
  zero: boolean
  pinned: boolean
  generated: boolean
  /** A record, not a plan any more - see PlanDayMeta.walked. */
  walked: boolean
  /** "was 17.1 mi", or null - see PlanDayMeta.wasDistanceMi. */
  wasDistanceMi: number | null
  /** A rest the rhythm asked for (#798) - see PlanDayMeta.rest. A zero can
   *  be a rest or just a zero somebody added; a nearo is only legible as
   *  one because of this. */
  rest: boolean
  /** The hiker's own line about this day, or null - see PlanDayMeta.note. */
  note: string | null
}

/** `startDate` plus `index` days, in plain date arithmetic - UTC throughout
 *  so a plan reads the same in every timezone a phone wanders through. */
export function dateOfDay(startDate: string, index: number): string {
  const [year, month, day] = startDate.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day + index))
  return date.toISOString().slice(0, 10)
}

export function planDayViews(plan: HikePlan): PlanDayView[] {
  let walkingDays = 0
  return plan.days.map((meta, index) => {
    const start = plan.stops[index]
    const end = plan.stops[index + 1]
    const zero = start.mile === end.mile
    if (!zero) walkingDays += 1
    return {
      id: meta.id,
      index,
      dayNumber: zero ? null : walkingDays,
      date: meta.date ?? null,
      start,
      end,
      zero,
      pinned: meta.pinned,
      generated: meta.generated,
      walked: meta.walked === true,
      wasDistanceMi: meta.wasDistanceMi ?? null,
      rest: meta.rest === true,
      note: meta.note ?? null,
    }
  })
}

/**
 * A span of days between two resupplies - the derived section, which is
 * also the food carry while hiker-overridden grouping remains unbuilt.
 *
 * `foodDays` counts every day in the span, zeros included. Whether a zero
 * in town should count against the carry is HIKE_PLANNING.md's open
 * question, explicitly not decided there; the wireframes bracket zeros
 * inside the carry, and counting them is the direction that errs toward a
 * hiker carrying enough rather than short - so that is the answer built,
 * as a decision a reviewer can reverse in one place.
 */
export interface PlanSection {
  days: PlanDayView[]
  distanceMi: number
  foodDays: number
}

/**
 * How many days of food a carry has to last, above which the weight is the
 * plan's biggest problem and saying so once is worth a line.
 *
 * @unvalidated 6 is picked, not measured. Six days is roughly where a
 * hiker's pack stops being a day pack with food in it, but nobody here has
 * checked that against anything. What would settle it: the distribution of
 * carry lengths across generated plans on this trail, which the planner can
 * produce as soon as anyone wants to count them.
 *
 * It is a NOTE and never a warning: a long carry is a fact about a stretch
 * of trail with no towns on it, not a mistake the hiker made.
 */
export const LONG_CARRY_DAYS = 6

/** One stretch of trail a single load of food has to cover (#799). */
export interface FoodCarry {
  from: { mile: number; name?: string }
  to: { mile: number; name?: string }
  /** Every day in the span, zeros and rests included - see PlanSection. */
  days: number
  /**
   * Supplies are picked up at the far end. False for the last carry of a
   * plan that simply runs out, which is the case worth saying out loud:
   * those days come out of the pack and nothing replaces them.
   */
  restockAtEnd: boolean
}

/**
 * The food carries a plan implies, one per section.
 *
 * Derived from `planSections` rather than counted again, so the food block
 * and the timeline cannot disagree about a carry - the same rule the rest
 * of this file follows about storing nothing that can be derived.
 */
export function foodCarries(sections: readonly PlanSection[]): FoodCarry[] {
  return sections.map((section) => {
    const first = section.days[0]
    const last = section.days[section.days.length - 1]
    return {
      from: {
        mile: first.start.mile,
        ...(first.start.name === undefined ? {} : { name: first.start.name }),
      },
      to: {
        mile: last.end.mile,
        ...(last.end.name === undefined ? {} : { name: last.end.name }),
      },
      days: section.foodDays,
      restockAtEnd: last.end.resupply,
    }
  })
}

export function planSections(views: PlanDayView[]): PlanSection[] {
  const sections: PlanSection[] = []
  let current: PlanDayView[] = []

  const close = () => {
    if (current.length === 0) return
    sections.push({
      days: current,
      distanceMi: current.reduce(
        (sum, day) => sum + Math.abs(day.end.mile - day.start.mile),
        0,
      ),
      foodDays: current.length,
    })
    current = []
  }

  for (const day of views) {
    current.push(day)
    // A resupply at a day's end closes the span: the next day walks out of
    // that town on what was bought there.
    if (day.end.resupply) close()
  }
  close()

  return sections
}

// ---------------------------------------------------------------------------
// Edits. Each returns a new plan and leaves the argument alone; each marks
// the days it touched as no longer the generator's. Every one of them
// refuses to alter a walked day - the past is a record, not a plan
// (SEGMENTS.md's completion model, restated by HIKE_PLANNING.md's cascade),
// and the refusal lives here so no screen has to remember it.

function touched(meta: PlanDayMeta): PlanDayMeta {
  return meta.generated ? { ...meta, generated: false } : meta
}

/** How many leading days are walked records. The plan's "now" sits at the
 *  boundary this many stops in - which is also the first stop an edit may
 *  touch. */
export function walkedDayCount(plan: HikePlan): number {
  let count = 0
  while (count < plan.days.length && plan.days[count].walked === true) count += 1
  return count
}

/** The day being walked next - the first unwalked one - or null when the
 *  plan is entirely a record. "Today" by progression rather than by the
 *  calendar: the calendar is a label, where the hiker is is a fact. */
export function currentDayIndex(plan: HikePlan): number | null {
  const count = walkedDayCount(plan)
  return count < plan.days.length ? count : null
}

/** The same date, `delta` days along - plain UTC arithmetic. */
/** Exported for lib/restRhythm.ts, which inserts days into a dated plan and
 *  has to move the calendar the same way every other insertion here does. */
export function shiftDate(date: string, delta: number): string {
  const [year, month, day] = date.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + delta)).toISOString().slice(0, 10)
}

/**
 * A zero after day `index`: a new day from that day's end stop to itself.
 * It needs no kind field - a day with a date, a place and no distance, which
 * is the whole reason a zero has to be IN the tree rather than a gap
 * between days: a gap has no date and eats no food (HIKE_PLANNING.md).
 *
 * On a dated plan the zero takes the next date and every later day slips a
 * day - which is what taking a zero does to a calendar.
 */
export function insertZeroAfter(plan: HikePlan, index: number): HikePlan {
  if (index < 0 || index >= plan.days.length) return plan
  // After a walked day is fine - tomorrow can be a zero; the record itself
  // is untouched either way.
  const boundary = plan.stops[index + 1]
  const anchor = plan.days[index].date
  return {
    ...plan,
    stops: [
      ...plan.stops.slice(0, index + 2),
      // The duplicate does NOT inherit the resupply flag. Supplies are
      // picked up once, at the stop the hiker walked into; a second flag on
      // the same place would read as buying food twice there, and - because
      // planSections closes a span at every resupply - would cut the zero
      // out into a one-day carry of its own instead of leaving it inside
      // the carry it actually eats from (#799).
      { ...boundary, resupply: false },
      ...plan.stops.slice(index + 2),
    ],
    days: [
      ...plan.days.slice(0, index + 1),
      {
        id: crypto.randomUUID(),
        ...(anchor === undefined ? {} : { date: shiftDate(anchor, 1) }),
        pinned: false,
        generated: false,
      },
      ...plan.days
        .slice(index + 1)
        .map((meta) =>
          meta.date === undefined ? meta : { ...meta, date: shiftDate(meta.date, 1) },
        ),
    ],
  }
}

/**
 * Remove day `index`, dropping its END boundary - so a removed zero simply
 * vanishes (its two boundaries were the same stop), a removed walking day
 * folds its miles into the day after it, and removing the last day shortens
 * the route to end where that day began. The day that absorbed the miles is
 * marked touched: it no longer covers the stretch the generator chose.
 * Later days pull a date earlier - the mirror of what inserting added.
 */
export function removeDay(plan: HikePlan, index: number): HikePlan {
  if (index < 0 || index >= plan.days.length) return plan
  if (plan.days.length === 1) return plan
  if (plan.days[index].walked === true) return plan
  const zero = plan.stops[index].mile === plan.stops[index + 1].mile
  const days = plan.days
    .filter((_, i) => i !== index)
    .map((meta, i) =>
      i >= index && meta.date !== undefined
        ? { ...meta, date: shiftDate(meta.date, -1) }
        : meta,
    )
  const absorber = zero || index >= days.length ? null : index
  const stops = plan.stops.filter((_, i) => i !== index + 1)
  return {
    ...plan,
    stops,
    days: days.map((meta, i) =>
      // The absorber grew by the removed day's miles, so a rest flag on it
      // is a claim about a distance that no longer exists (#1031).
      i === absorber
        ? keepingRest(touched(meta), stops[i].mile, stops[i + 1].mile)
        : meta,
    ),
  }
}

/**
 * Flip the resupply flag on stop `stopIndex` - one write, because a stop is
 * stored once however many days meet at it. Refused behind the plan's
 * "now": where supplies were bought is part of the record, and the earliest
 * stop still ahead of the hiker is the boundary their walked prefix ends at.
 */
export function toggleResupply(plan: HikePlan, stopIndex: number): HikePlan {
  if (stopIndex < 0 || stopIndex >= plan.stops.length) return plan
  if (stopIndex < walkedDayCount(plan)) return plan
  return {
    ...plan,
    stops: plan.stops.map((stop, i) =>
      i === stopIndex ? { ...stop, resupply: !stop.resupply } : stop,
    ),
  }
}

/**
 * Write (or clear) the hiker's own line on a day (#966).
 *
 * THE ONE MUTATOR THAT MAY TOUCH A WALKED DAY, and the exception is the
 * point rather than an oversight. Every other edit here refuses a walked
 * day because the past is a record - but a memory is written *about* the
 * past, after it, and the day summary exists precisely so somebody can
 * write one at camp. Nothing about the day's boundaries, dates or figures
 * changes; the record stays exactly as walked.
 *
 * It does not call `touched()` either. Writing down what the ponies did is
 * not editing the plan, and a generated day that gets a line is still a day
 * the app laid out - dropping the "auto" marker for it would make the
 * timeline claim an edit nobody made.
 *
 * Blank in, field gone: an empty or whitespace-only line is a hiker
 * clearing what they wrote, not storing an empty string.
 */
export function setDayNote(plan: HikePlan, index: number, note: string): HikePlan {
  if (index < 0 || index >= plan.days.length) return plan
  const trimmed = note.trim().slice(0, DAY_NOTE_MAX_CHARS)
  return {
    ...plan,
    days: plan.days.map((meta, i) => {
      if (i !== index) return meta
      if (trimmed.length === 0) {
        const { note: _cleared, ...rest } = meta
        return rest
      }
      return { ...meta, note: trimmed }
    }),
  }
}

export function togglePinned(plan: HikePlan, index: number): HikePlan {
  if (index < 0 || index >= plan.days.length) return plan
  if (plan.days[index].walked === true) return plan
  return {
    ...plan,
    days: plan.days.map((meta, i) =>
      i === index ? touched({ ...meta, pinned: !meta.pinned }) : meta,
    ),
  }
}
