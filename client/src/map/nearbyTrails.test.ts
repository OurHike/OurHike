import { describe, it, expect } from 'vitest'
import {
  CHOSEN_SYSTEM_SOURCES,
  CHOSEN_TRAIL_OPACITY,
  NEARBY_TRAIL_OPACITY,
  isNearbyTrail,
  nearbyTrailOpacity,
  nearbyTrailOpacityExpression,
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
  const [op, condition, whenGhosted, whenChosen] = nearbyTrailOpacityExpression()
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
    const [, condition] = nearbyTrailOpacityExpression()
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
    const expression = nearbyTrailOpacityExpression()
    expect(expression[expression.length - 1]).toBe(CHOSEN_TRAIL_OPACITY)
  })
})

describe('the two source lists that must agree', () => {
  it('holds every through-route the style paints at the primary width', () => {
    // The pin CHOSEN_SYSTEM_SOURCES's docstring promises. A through-route
    // that is not in the chosen system would be drawn widest AND ghosted -
    // the map's two channels contradicting each other about which trail it is
    // about, which is worse than either channel being absent.
    for (const source of PRIMARY_TRAIL_SOURCES) {
      expect(CHOSEN_SYSTEM_SOURCES).toContain(source)
    }
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
