import { SHARED_GROUND_EXCLUDED } from './sharedGround'
import { describe, it, expect } from 'vitest'
import { TRAILS } from '../lib/trails'
import {
  CHOSEN_SYSTEM_SOURCES,
  CHOSEN_TRAIL_OPACITY,
  NEARBY_TRAIL_OPACITY,
  chosenSystemFilter,
  isNearbyTrail,
  nearbyTrailFilter,
  nearbyTrailOpacity,
  nearbyTrailOpacityExpression,
  chosenSystemSources,
} from './nearbyTrails'
import {
  BLAZE_LAYER_ID,
  PRIMARY_TRAIL_SOURCES,
  TRAIL_CASING_LAYER_ID,
  buildMapStyle,
} from './style'

const STYLE_OPTIONS = {
  topoArchiveUrl: 'pmtiles://archive.pmtiles',
  trailsUrl: 'blob:trails',
}

/** One layer's paint, or a failure naming the layer - so a renamed layer reads
 *  as "no layer" rather than as an undefined paint property. */
function paintOf(layerId: string): Record<string, unknown> {
  const found = buildMapStyle(STYLE_OPTIONS).layers.find((layer) => layer.id === layerId)
  if (found === undefined) throw new Error(`no layer "${layerId}" in the style`)
  return found.paint as Record<string, unknown>
}

/**
 * The suite has no MapLibre evaluator, so this interprets the expression the
 * builder produces rather than pretending to run it - following MapLibre's own
 * semantics for the three operators involved: `to-string` renders null as
 * `""`, `all` is a conjunction, and `in` is set membership.
 *
 * Writing it as an interpreter rather than a shape assertion is what made it
 * useful: the first version of the expression was `['case', ['in', …], full,
 * ghosted]`, and this caught that it paints a source-less feature DIM while
 * nearbyTrailOpacity() calls it full-strength. A test that only checked the
 * structure would have agreed with the bug.
 */
function evaluateOpacityExpression(source: string | null): number {
  const [op, condition, whenGhosted, whenChosen] =
    nearbyTrailOpacityExpression() as unknown[]
  expect(op).toBe('case')

  const [allOp, notEmpty, notChosen] = condition as unknown[]
  expect(allOp).toBe('all')

  // MapLibre's `to-string` renders a missing or null property as "".
  const rendered = source ?? ''

  const [neqOp, , empty] = notEmpty as unknown[]
  expect(neqOp).toBe('!=')
  const isNotEmpty = rendered !== (empty as string)

  const [notOp, inExpr] = notChosen as unknown[]
  expect(notOp).toBe('!')
  const members = ((inExpr as unknown[])[2] as ['literal', string[]])[1]
  const isNotChosen = !members.includes(rendered)

  return (isNotEmpty && isNotChosen ? whenGhosted : whenChosen) as number
}

describe('which trails are ghosted', () => {
  it('keeps the chosen trail and its own spurs at full strength', () => {
    for (const source of CHOSEN_SYSTEM_SOURCES) {
      expect(isNearbyTrail(source)).toBe(false)
      expect(nearbyTrailOpacity(source)).toBe(CHOSEN_TRAIL_OPACITY)
    }
  })

  it('ghosts another organization’s trail', () => {
    // The one nearby line source registered today (pipeline/sources.json's
    // `oprhp_trails`, the NYS Parks statewide layer #768/#771 admitted).
    expect(isNearbyTrail('oprhp_trails')).toBe(true)
    expect(nearbyTrailOpacity('oprhp_trails')).toBe(NEARBY_TRAIL_OPACITY)
  })

  it('ghosts a source this build has never heard of, rather than letting it compete', () => {
    // The conservative direction, argued in the module: an unrecognised line
    // drawn full-strength competes with the chosen trail for the one thing
    // this channel says. Dim, it is merely context - which is what it is
    // until somebody admits it deliberately.
    expect(isNearbyTrail('nynjtc_trails')).toBe(true)
    expect(isNearbyTrail('some_import_from_2027')).toBe(true)
  })

  it('draws a feature with NO source at full strength, because that is a fault and not a nearby trail', () => {
    // Asymmetric on purpose. A pipeline fault drawn dim is a trail quietly
    // de-emphasised on a safety surface; drawn full-strength it is at worst
    // over-prominent, and it is visible, which is how it gets fixed.
    for (const missing of [null, undefined, '']) {
      expect(isNearbyTrail(missing)).toBe(false)
      expect(nearbyTrailOpacity(missing)).toBe(CHOSEN_TRAIL_OPACITY)
    }
  })

  it('is dim enough to be unmistakable and strong enough to keep its hue', () => {
    // Not a validated number - see the constant's @unvalidated note and #105.
    // What this pins is the pair of properties the value was picked FOR, so a
    // later tweak that breaks either one fails here rather than on a ridge:
    // visibly weaker than the chosen trail, and not so faint it stops being a
    // colour a hiker can name.
    expect(NEARBY_TRAIL_OPACITY).toBeLessThan(CHOSEN_TRAIL_OPACITY)
    expect(NEARBY_TRAIL_OPACITY).toBeGreaterThan(0.25)
  })
})

describe('the expression and the function agree', () => {
  it('gives the same answer as nearbyTrailOpacity for every kind of source', () => {
    // The two exist because a paint property needs an expression and the
    // tests, the sheet and any later caller need a function. They are only
    // safe as two if they cannot disagree.
    const cases = [...CHOSEN_SYSTEM_SOURCES, 'oprhp_trails', 'unheard_of', null]
    for (const source of cases) {
      expect(evaluateOpacityExpression(source)).toBe(nearbyTrailOpacity(source))
    }
  })

  it('builds its membership list from CHOSEN_SYSTEM_SOURCES rather than a copy', () => {
    const [, condition] = nearbyTrailOpacityExpression() as unknown[]
    const notChosen = (condition as unknown[])[2] as unknown[]
    const inExpr = notChosen[1] as unknown[]
    const members = (inExpr[2] as ['literal', string[]])[1]
    expect(members).toEqual([...CHOSEN_SYSTEM_SOURCES])
  })

  it('puts FULL opacity in the default branch, so an unanswerable case is never ghosted', () => {
    // The regression guard for the bug the interpreter above caught. Whatever
    // the condition grows into, the branch a feature falls into when the
    // condition cannot answer for it must be the chosen trail's opacity - a
    // fault is over-prominent and visible, never quietly dimmed.
    const expression = nearbyTrailOpacityExpression() as unknown[]
    expect(expression[expression.length - 1]).toBe(CHOSEN_TRAIL_OPACITY)
  })
})

describe('the two source lists that must agree', () => {
  it('keeps the A.T.’s own line at the primary width while it is chosen', () => {
    // The direction that still has to hold, now that a second through-route
    // exists: whatever is actually TAKEN must never draw thinner than a
    // through-route that is not. The reverse - every primary-width source is
    // in the chosen system - held only while `centerline` was the one
    // through-route there was, and #1307 ended that on purpose: the Long
    // Path draws at primary width and stays out of CHOSEN_SYSTEM_SOURCES,
    // because width says "through-route or spur" and the split's weight
    // below the seam and its ghosting - not width - are what say which
    // through-route is walked. WIREFRAMES.md §3
    // names the cost and accepts it: "with two through-routes drawn, width
    // answers 'through-route or spur' and stops answering 'which trail is
    // this' - still a hue-independent channel, but a coarser one."
    expect(CHOSEN_SYSTEM_SOURCES).toContain('centerline')
    expect(PRIMARY_TRAIL_SOURCES).toContain('centerline')
  })

  it('lets a through-route join the primary tier without being chosen', () => {
    // The Long Path (#1307): a real member of PRIMARY_TRAIL_SOURCES that
    // CHOSEN_SYSTEM_SOURCES has never heard of, and is not expected to
    // until a hike can actually be tracked on it (lib/hikes.ts's
    // trailHasMileAxis, #1317).
    expect(PRIMARY_TRAIL_SOURCES).toContain('nynjtc_long_path')
    expect(CHOSEN_SYSTEM_SOURCES).not.toContain('nynjtc_long_path')
  })
})

describe('the style actually paints it', () => {
  it('ghosts the blaze layer', () => {
    expect(paintOf(BLAZE_LAYER_ID)['line-opacity']).toEqual(
      nearbyTrailOpacityExpression(),
    )
  })

  it('composes the casing’s own softness with the ghosting rather than replacing it', () => {
    // Replacing the casing's 0.7 would give a ghosted line a FIRMER edge than
    // the chosen trail's - the opposite of what the channel is for.
    expect(paintOf(TRAIL_CASING_LAYER_ID)['line-opacity']).toEqual([
      '*',
      0.7,
      nearbyTrailOpacityExpression(),
    ])
  })

  it('leaves an A.T.-only download looking exactly as it did before', () => {
    // The regression this whole reading of §1 was chosen to avoid. Every
    // source an A.T.-only build draws is in the chosen system, so the
    // expression returns full opacity for all of them and the launched map is
    // unchanged for a hiker who has downloaded no network ground.
    const atOnlySources = ['centerline', 'side_trails']
    for (const source of atOnlySources) {
      expect(evaluateOpacityExpression(source)).toBe(CHOSEN_TRAIL_OPACITY)
    }
  })
})

describe('the layer split (#1283): two filters that are exact complements', () => {
  /**
   * MapLibre semantics for the operators the filters use, interpreted the
   * way evaluateOpacityExpression above is: `to-string` renders a missing
   * property as "", `in` is set membership, `!` negates.
   */
  function passes(filter: unknown[], source: string | null, shared = false): boolean {
    const [op, ...rest] = filter
    if (op === 'all')
      return rest.every((clause) => passes(clause as unknown[], source, shared))
    if (op === '!') return !passes(rest[0] as unknown[], source, shared)
    // `has concurrent_with`: the mark of a shared-ground half (#1384).
    if (op === 'has') return shared
    expect(op).toBe('in')
    const members = (rest[1] as ['literal', string[]])[1]
    return members.includes(source ?? '')
  }

  const cases = [
    ...CHOSEN_SYSTEM_SOURCES,
    'oprhp_trails',
    'usfs_trails',
    'unheard_of',
    '',
    null,
  ]

  it('puts the two halves of a shared stretch in neither (#1384)', () => {
    // A half carries a source like any line and draws as map/sharedGround.ts's
    // own two layers; in either split layer it would also be a plain centred
    // line under the two-tone.
    for (const source of cases) {
      expect(passes(chosenSystemFilter(), source, true), String(source)).toBe(false)
      expect(passes(nearbyTrailFilter(), source, true), String(source)).toBe(false)
    }
  })

  it('puts every source in exactly one of the two layers', () => {
    // Neither in both (a line drawn twice over itself, at two weights) nor
    // in neither (a line that vanishes). The split is only honest as a
    // partition.
    for (const source of cases) {
      const taken = passes(chosenSystemFilter(), source)
      const untaken = passes(nearbyTrailFilter(), source)
      expect(taken).not.toBe(untaken)
    }
  })

  it('draws the chosen system on the taken side and everything else on the untaken one', () => {
    for (const source of CHOSEN_SYSTEM_SOURCES) {
      expect(passes(chosenSystemFilter(), source)).toBe(true)
    }
    expect(passes(nearbyTrailFilter(), 'oprhp_trails')).toBe(true)
    expect(passes(nearbyTrailFilter(), 'unheard_of')).toBe(true)
  })

  it('sends a source-less feature to the untaken side, and says why', () => {
    // The one place the split rounds the other way from the opacity rule: a
    // line nobody can source has not earned the claim of being the chosen
    // trail. It still paints at full opacity on that layer, so the fault is
    // visible rather than quietly dimmed - the module says so.
    expect(passes(nearbyTrailFilter(), null)).toBe(true)
    expect(passes(nearbyTrailFilter(), '')).toBe(true)
  })

  it('builds both from CHOSEN_SYSTEM_SOURCES rather than a copy', () => {
    // ['all', <membership>, SHARED_GROUND_EXCLUDED] since #1384 - the
    // membership clause is the one the chosen system decides.
    const membership = chosenSystemFilter()[1] as unknown[]
    const members = (membership[2] as ['literal', string[]])[1]
    expect(members).toEqual([...CHOSEN_SYSTEM_SOURCES])
    expect(nearbyTrailFilter()).toEqual([
      'all',
      ['!', membership],
      SHARED_GROUND_EXCLUDED,
    ])
  })
})

describe('nothing taken (#1306)', () => {
  // The handoff's `chosenSystemSources`, "was a constant": null on first
  // launch is the all-untaken state, and the A.T. is the only trail with a
  // system to answer for today.
  it('answers the A.T. system for the A.T. and nothing for nothing', () => {
    expect(chosenSystemSources(TRAILS.AT.id)).toEqual(CHOSEN_SYSTEM_SOURCES)
    expect(chosenSystemSources(null)).toEqual([])
    expect(chosenSystemSources('PCT')).toEqual([])
  })

  it('puts every line on the untaken side when nothing is taken', () => {
    // An empty membership list matches nothing, so the two filters stay
    // complements and the taken side is simply empty.
    const taken = chosenSystemFilter([]) as unknown[]
    const membership = taken[1] as unknown[]
    expect((membership[2] as ['literal', string[]])[1]).toEqual([])
    expect(nearbyTrailFilter([])).toEqual([
      'all',
      ['!', membership],
      SHARED_GROUND_EXCLUDED,
    ])
  })

  it('ghosts nothing when nothing is taken, since there is no system to belong to', () => {
    expect(nearbyTrailOpacityExpression([])).toBe(CHOSEN_TRAIL_OPACITY)
    for (const source of [
      'centerline',
      'side_trails',
      'oprhp_trails',
      'unknown',
      '',
      null,
    ]) {
      expect(isNearbyTrail(source, [])).toBe(false)
      expect(nearbyTrailOpacity(source, [])).toBe(CHOSEN_TRAIL_OPACITY)
    }
  })

  it('still ghosts against the taken system, as before', () => {
    expect(isNearbyTrail('oprhp_trails', CHOSEN_SYSTEM_SOURCES)).toBe(true)
    expect(nearbyTrailOpacity('oprhp_trails', CHOSEN_SYSTEM_SOURCES)).toBe(
      NEARBY_TRAIL_OPACITY,
    )
    expect(nearbyTrailOpacityExpression(CHOSEN_SYSTEM_SOURCES)).toEqual(
      nearbyTrailOpacityExpression(),
    )
  })
})
