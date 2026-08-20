// The hiker's own pace, as an adjustment to the standard estimate (#880).
//
// features/PERSONALIZED_PACE.md §1 specifies three layers in order of
// authority - base (Naismith), manual (this), learned (fitted from
// observations, #881). This is the middle one, and it is the only one that
// needs nothing from the hiker but an opinion.
//
// WHY THIS IS A NEW FUNCTION AND NOT A CHANGE TO naismith.ts
//
// That document is firm about it and is right. `naismithTime()` has no
// `descentFt` parameter, and its own comment says why: "not just 'ignored if
// passed' but structurally absent, so a future call site can't accidentally
// wire descent in without touching this function's signature first." A
// naismithTime() that silently started scaling its answer by a stored
// preference would be the same class of change the guard exists to prevent.
// So the base rule stays exactly what it was, and this sits beside it.
//
// THE MULTIPLIER IS A PROPERTY OF A WALK, NOT OF A PROFILE
//
// Worth stating because the obvious reading is wrong. The two coefficients
// scale Naismith's two terms independently, so a hiker who is slow on the flat
// and standard on climbs reads 1.3x on a towpath and 1.05x on a staircase.
// There is no single number that describes their profile, and any screen
// printing one has to compute it for the walk in front of it.
//
// A CORRUPT COEFFICIENT ROUNDS TOWARD THE STANDARD, NEVER TOWARD FASTER
//
// lib/preferences.ts repairs unknown ENUM values and has nothing for numbers -
// `anonymity_window_days` goes from storage to the share sheet unchecked. That
// is tolerable for a share window and is not tolerable here: these two numbers
// move every time estimate in the app, including the one a hiker uses to
// decide whether they beat the dark. So every value is clamped on the way in,
// and anything unreadable falls back to the standard rather than to whatever
// was stored.

import { naismithMinutes, formatNaismithMinutes, type NaismithInput } from './naismith'

/** 5 km/h - Naismith's flat term, in the unit the control uses. */
export const STANDARD_FLAT_PACE_MPH = 5 / 1.609344

/** One hour per 600 m of ascent - Naismith's second term. */
export const STANDARD_ASCENT_METERS_PER_HOUR = 600

/**
 * Naismith's own two terms, as numbers a hiker can move.
 *
 * Deliberately the SAME two quantities the rule already has rather than an
 * abstract multiplier, so "standard" is exactly representable and the controls
 * mean something a hiker can reason about: how fast do I walk, and how much
 * does climbing cost me.
 */
export interface PaceProfile {
  /** Flat walking speed, miles per hour. */
  flatPaceMph: number
  /** Metres of ascent per extra hour. SMALLER is a steeper penalty. */
  ascentMetersPerHour: number
  /**
   * Extra minutes per 1,000 m of DESCENT. Zero is no penalty (#900).
   *
   * NOT metres-per-hour like the ascent term above, and the asymmetry is the
   * point. That term is Naismith's own - "one hour per 600 m" - so it keeps his
   * units. Descent is not in Naismith at all, so there is no inherited form to
   * preserve, and copying the idiom would buy symmetry at the cost of two real
   * problems: no natural value would mean "no penalty", and zero metres-per-hour
   * is a division by zero.
   *
   * Minutes-per-1,000 m has neither. Zero means none, sits exactly on the
   * control's grid, and needs no sentinel - so a fresh install is still
   * Naismith to the last decimal.
   *
   * ONLY EVER ADDS TIME. See STANDARD_DESCENT_MINUTES_PER_1000M below.
   */
  descentMinutesPer1000m: number
}

/**
 * No descent penalty, which is Naismith - and a penalty is the only direction
 * this control has.
 *
 * PERSONALIZED_PACE.md names both: "gentle downhill is faster than flat, and
 * steep sustained downhill is SLOWER than flat while wrecking your knees." One
 * coefficient can only do one of them.
 *
 * CLAUDE.md decides which: "Round toward caution, and say which way you
 * rounded. Naismith gets no descent credit - a known weakness of the rule, left
 * in place deliberately and documented so the next agent does not 'improve' it
 * into an optimistic number."
 *
 * So this only ever ADDS time. A hiker who is genuinely quick downhill cannot
 * say so, and that is the deliberate cost: a credit is the optimistic
 * direction, on the number somebody uses to decide whether they beat the dark.
 * Wanting that direction means revisiting the rule in the open, not widening a
 * slider.
 */
export const STANDARD_DESCENT_MINUTES_PER_1000M = 0

export const STANDARD_PACE: PaceProfile = {
  flatPaceMph: STANDARD_FLAT_PACE_MPH,
  ascentMetersPerHour: STANDARD_ASCENT_METERS_PER_HOUR,
  descentMinutesPer1000m: STANDARD_DESCENT_MINUTES_PER_1000M,
}

/**
 * What the flat-pace control may be set to, and in what steps.
 *
 * 1 to 4 mph in tenths, decided by the maintainer on #888 - the range there,
 * and the step asked for in review on #889. It replaces a placeholder that was
 * tagged @unvalidated for exactly this - picked to bracket the standard
 * generously, never measured - so these are somebody's number rather than
 * nobody's.
 *
 * FASTER THAN STANDARD IS ALLOWED, up to 4 mph against the standard's 3.107.
 * That is the decision, and the safeguard is not a clamp: it is that an
 * adjusted estimate always carries what it was adjusted from (#851), so a
 * pace set optimistic in week one cannot quietly become the number a hiker
 * plans their evening around.
 */
export const MIN_FLAT_PACE_MPH = 1
export const MAX_FLAT_PACE_MPH = 4
export const FLAT_PACE_STEP_MPH = 0.1

/**
 * What the climbing control may be set to.
 *
 * @unvalidated Unchanged and still picked rather than measured - #888 decided
 * the flat pace only. What would settle it is #881's observation store, which
 * is the same evidence the learned layer needs.
 */
export const MIN_ASCENT_METERS_PER_HOUR = 300
export const MAX_ASCENT_METERS_PER_HOUR = 900

/**
 * What the descent control may be set to (#900).
 *
 * Zero to an hour per 1,000 m, in five-minute steps. The floor is zero because
 * zero IS the standard, and the ceiling is an hour because past that a descent
 * costs more than the same climb, which no hiker's own account of themselves
 * supports.
 *
 * @unvalidated Picked, not measured. The maintainer chose to offer the control;
 * this range is mine, and #881's observation store is what would settle it.
 */
export const MIN_DESCENT_MINUTES_PER_1000M = 0
export const MAX_DESCENT_MINUTES_PER_1000M = 60
export const DESCENT_STEP_MINUTES = 5

function clamp(value: unknown, min: number, max: number, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  return Math.min(max, Math.max(min, value))
}

/**
 * A stored profile, made safe to compute with.
 *
 * Total by construction: every path returns two finite numbers inside the
 * bounds, so nothing downstream can produce NaN or a negative duration. A
 * value this cannot read becomes the STANDARD one, which is the only fallback
 * that is never an overstatement of how fast somebody walks.
 */
export function readPace(
  stored: Partial<Record<keyof PaceProfile, unknown>>,
): PaceProfile {
  return {
    flatPaceMph: clamp(
      stored.flatPaceMph,
      MIN_FLAT_PACE_MPH,
      MAX_FLAT_PACE_MPH,
      STANDARD_FLAT_PACE_MPH,
    ),
    ascentMetersPerHour: clamp(
      stored.ascentMetersPerHour,
      MIN_ASCENT_METERS_PER_HOUR,
      MAX_ASCENT_METERS_PER_HOUR,
      STANDARD_ASCENT_METERS_PER_HOUR,
    ),
    descentMinutesPer1000m: clamp(
      stored.descentMinutesPer1000m,
      MIN_DESCENT_MINUTES_PER_1000M,
      MAX_DESCENT_MINUTES_PER_1000M,
      STANDARD_DESCENT_MINUTES_PER_1000M,
    ),
  }
}

/**
 * Whether a profile is the standard rule, within floating-point noise.
 *
 * NOT REACHABLE BY DRAGGING, and that is deliberate rather than an oversight.
 * The standard flat pace is 5 km/h - 3.1069 mph - which does not sit on the
 * tenths grid the control offers: the nearest stop is 3.1, seven thousandths
 * below. So once a hiker moves the flat slider, "Reset to standard" is the
 * only way back to exactly the rule.
 *
 * At 3.1 the printed estimate is identical to the standard's - 130.5 minutes
 * against 130.3 on the preview's walk, both ≈2h 10m - so the baseline line
 * correctly says nothing while the Reset control correctly still offers itself.
 * Those two are answering different questions: "is this a different answer"
 * and "is this exactly the rule".
 *
 * The alternative would be snapping the standard onto the grid, and that is
 * the wrong trade: a fresh install would then disagree with the rule it claims
 * to use, which is the whole property the two-term design protects.
 */
export function isStandardPace(pace: PaceProfile): boolean {
  return (
    Math.abs(pace.flatPaceMph - STANDARD_FLAT_PACE_MPH) < 1e-9 &&
    Math.abs(pace.ascentMetersPerHour - STANDARD_ASCENT_METERS_PER_HOUR) < 1e-9 &&
    Math.abs(pace.descentMinutesPer1000m - STANDARD_DESCENT_MINUTES_PER_1000M) < 1e-9
  )
}

const FEET_TO_METERS = 0.3048
const MINUTES_PER_HOUR = 60

/**
 * What a walk has to say about itself for this estimator.
 *
 * `NaismithInput` plus an OPTIONAL descent, rather than widening that type:
 * naismith.ts keeps `descentFt` structurally absent so a call site cannot wire
 * one in without changing a signature, and that guard is worth more than the
 * convenience of one shared shape. Callers with no descent figure - a spur's
 * round trip is net zero - simply omit it and pay nothing.
 *
 * Negative values are floored at zero rather than trusted: a caller passing a
 * signed elevation delta would otherwise buy time back, which is exactly the
 * credit this control does not offer.
 */
export interface PaceInput extends NaismithInput {
  descentFt?: number
}

/**
 * Moving time under this hiker's own coefficients, in minutes.
 *
 * Same two-term shape as naismithMinutes() - distance over a speed, plus an
 * hour per so much ascent - with the two constants replaced. Descent gets no
 * credit here either, deliberately: PERSONALIZED_PACE.md puts descent in the
 * LEARNED layer, where it comes from evidence, and a manual control nobody can
 * answer honestly would be the optimistic direction again.
 *
 * Raw minutes rather than a formatted string, for the reason naismith.ts
 * exports both: route.ts sums a day before formatting once, and rounding each
 * leg first would let the printed total drift from the printed legs.
 */
export function paceMinutes(input: PaceInput, pace: PaceProfile): number {
  const safe = readPace(pace)
  const distanceMinutes = (input.distanceMi / safe.flatPaceMph) * MINUTES_PER_HOUR
  const ascentMinutes =
    ((input.ascentFt * FEET_TO_METERS) / safe.ascentMetersPerHour) * MINUTES_PER_HOUR
  // Descent, and only ever upward. A caller with no descent figure - or one on
  // the standard profile - pays nothing, which keeps a fresh install exactly
  // Naismith.
  const descentM = Math.max(0, input.descentFt ?? 0) * FEET_TO_METERS
  const descentMinutes = (descentM / 1000) * safe.descentMinutesPer1000m
  return distanceMinutes + ascentMinutes + descentMinutes
}

/**
 * An estimate that cannot be rendered without saying whose it is.
 *
 * The baseline and the adjusted figure travel in ONE object on purpose. #851's
 * decision is that no surface may print an adjusted time without showing what
 * it was adjusted from, and the cheapest way to hold that is to make the two
 * impossible to separate at the type level: a caller with `text` in hand
 * necessarily has `relativeLine` too.
 */
export interface PaceEstimate {
  /** Minutes under the hiker's own pace. Always present. */
  minutes: number
  /** "≈2h 50m" - what the screen shows. */
  text: string
  /**
   * "was ≈2h 10m · 1.3× standard", or NULL at the standard pace.
   *
   * Null rather than "1.0× standard": a caveat on every line reads exactly
   * like a caveat on none, and this one has to keep its weight for the hikers
   * who did move a control.
   */
  relativeLine: string | null
}

/** How many times the standard estimate this walk now reads, for THIS walk. */
export function paceRatio(input: PaceInput, pace: PaceProfile): number | null {
  const base = naismithMinutes(input)
  if (base <= 0) return null
  return paceMinutes(input, pace) / base
}

/**
 * The estimate for one walk, with its baseline attached.
 *
 * The ratio is formatted to one decimal and only shown when it differs from
 * the standard once rounded - a "1.0× standard" caption on a profile a hiker
 * nudged by two percent is noise claiming to be information.
 */
export function paceEstimate(input: PaceInput, pace: PaceProfile): PaceEstimate {
  const safe = readPace(pace)
  const minutes = paceMinutes(input, safe)
  const text = formatNaismithMinutes(minutes)

  if (isStandardPace(safe)) return { minutes, text, relativeLine: null }

  const baseMinutes = naismithMinutes(input)
  const baseText = formatNaismithMinutes(baseMinutes)
  const ratio = baseMinutes > 0 ? minutes / baseMinutes : null

  // Nothing to compare against - a zero-length walk has no baseline, and a
  // ratio would be a division by zero dressed up as a fact.
  if (ratio === null) return { minutes, text, relativeLine: null }

  const rounded = Math.round(ratio * 10) / 10
  // The two figures round to the same printed time, so there is no difference
  // on screen to explain. Saying "was ≈2h 10m" next to "≈2h 10m" reads as a
  // malfunction.
  if (baseText === text) return { minutes, text, relativeLine: null }

  return {
    minutes,
    text,
    relativeLine: `was ${baseText} · ${rounded.toFixed(1)}× standard`,
  }
}

/**
 * WHERE THIS IS KEPT, AND WHY NOT WITH THE OTHER PREFERENCES
 *
 * Its own key, deliberately. `UserPreferences` is a SYNC target - the router
 * takes a whole-blob `PUT /preferences/me` with `extra="forbid"`, so one key
 * the server does not know costs the entire sync for every hiker, not one
 * field. backend/tests/test_preferences_contract.py exists because that drift
 * already happened once.
 *
 * But the deeper reason is PERSONALIZED_PACE.md §4, which puts the pace
 * profile outside sync on purpose: "This is not a sync target even when an
 * account exists", called out there as a deliberate exception to the
 * preferences-sync rule that "should be recorded as one." A pace profile is a
 * statement about a body. Adding it to the synced blob would have shipped that
 * exception in reverse, and the contract test is what caught it.
 *
 * localStorage rather than IndexedDB, matching lib/walkedMiles.ts: this is read
 * while a sheet renders, and an async read would mean a frame with the wrong
 * number on it.
 */
export const PACE_STORAGE_KEY = 'ourhike:pace'

/**
 * The stored profile, or the standard one.
 *
 * Every failure is the standard pace rather than a throw: unavailable storage,
 * unparseable JSON, a shape from a build that is not this one. `readPace` then
 * clamps whatever survived, so a hiker whose storage is corrupt gets Naismith
 * and no error rather than a wrong number.
 */
export function readStoredPace(): PaceProfile {
  try {
    const raw = localStorage.getItem(PACE_STORAGE_KEY)
    if (raw === null) return STANDARD_PACE
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return STANDARD_PACE
    return readPace(parsed as Partial<Record<keyof PaceProfile, unknown>>)
  } catch {
    return STANDARD_PACE
  }
}

/** Stores the profile, clamped first so nothing out of range is ever written. */
export function writeStoredPace(pace: PaceProfile): void {
  try {
    localStorage.setItem(PACE_STORAGE_KEY, JSON.stringify(readPace(pace)))
  } catch {
    // Ignored on purpose - see readStoredPace. A hiker who cannot persist a
    // preference should still get the estimate they just asked for.
  }
}

/** Forgets the profile, which returns every estimate to the standard rule. */
export function clearStoredPace(): void {
  try {
    localStorage.removeItem(PACE_STORAGE_KEY)
  } catch {
    // Ignored on purpose - see readStoredPace.
  }
}
