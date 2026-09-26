import { describe, it, expect } from 'vitest'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { createPropertyExpression, latest } from '@maplibre/maplibre-gl-style-spec'
import {
  attachMapAppearance,
  buildMapStyle,
  BLAZE_LINE_LAYER_IDS,
  TRAIL_CASING_LAYER_IDS,
} from './style'

/**
 * Switching the blaze colours on has to leave the map exactly as it would
 * have been built (2026-09-20).
 *
 * THE BUG THIS EXISTS FOR, reported by the maintainer: "When I turn on the
 * Blaze Color, it displays as grey and hides some trails. Until I zoom
 * out/in, then it displays correctly."
 *
 * `attachMapAppearance` repaints a live map property by property rather than
 * rebuilding it, which is the right call - a rebuild drops every tile - and
 * which means the switch is only as complete as its list of writes. Anything
 * `buildMapStyle` bakes in from the appearance and `attachMapAppearance` does
 * not rewrite is frozen at whatever the style was FIRST built with, and stays
 * wrong until something rebuilds the style.
 *
 * The map's own comment already claimed this was closed - "the match
 * expression goes back exactly as buildMapStyle spelled it" - so what was
 * missing was not the intent but the check. This is the check, and it is
 * written as a diff rather than as a list of properties, so a NEW
 * appearance-dependent property added to buildMapStyle fails here on the day
 * it is added rather than on the day a hiker reports it.
 *
 * THE REPORT CAME BACK ON 2026-09-26, and the diff below was not where it
 * lived (#1698). Every write was correct; what drew the grey was MapLibre
 * itself, throwing mid-frame when a blaze layer's `line-dasharray` changed
 * between per-feature and absent (map/style.ts's blazeDashArray has the
 * trace). A mock map cannot throw the way a renderer does, so the last block
 * here pins the rule that keeps the renderer out of that state, and
 * e2e/data/blazeSwitch.spec.ts taps the switch on a real one.
 */

/** The least map `attachMapAppearance` can be driven against. */
function mockMap(style: ReturnType<typeof buildMapStyle>): {
  map: MapLibreMap
  paint: Map<string, Record<string, unknown>>
  layout: Map<string, Record<string, unknown>>
} {
  const ids = new Set(style.layers.map((layer) => layer.id))
  const paint = new Map<string, Record<string, unknown>>()
  const layout = new Map<string, Record<string, unknown>>()
  const map = {
    getLayer: (id: string) => (ids.has(id) ? { id } : undefined),
    getSource: () => undefined,
    setPaintProperty: (id: string, property: string, value: unknown) => {
      paint.set(id, { ...(paint.get(id) ?? {}), [property]: value })
    },
    setLayoutProperty: (id: string, property: string, value: unknown) => {
      layout.set(id, { ...(layout.get(id) ?? {}), [property]: value })
    },
    on: () => {},
    off: () => {},
  } as unknown as MapLibreMap
  return { map, paint, layout }
}

const DEFAULT_SHEET = { theme: 'light', blazeColorsShown: false } as const
const HUES = { theme: 'light', blazeColorsShown: true } as const
const LINES = [...BLAZE_LINE_LAYER_IDS, ...TRAIL_CASING_LAYER_IDS]

/** Every appearance-dependent property a line layer carries when freshly built. */
const WATCHED = ['line-color', 'line-width', 'line-dasharray'] as const

describe('turning the blaze colours on restores what buildMapStyle would draw', () => {
  it('rewrites every appearance-dependent paint property on every line layer', () => {
    // Built under the DEFAULT - which is what ships - then switched to the
    // hues the way a hiker's tap does it, and compared against the style that
    // would have been built under the hues from the start. Any difference is
    // a property frozen at the default's value on a map showing the hues.
    const shipped = buildMapStyle({
      background: 'offline_topo',
      ...DEFAULT_SHEET,
    } as never)
    const wanted = buildMapStyle({ background: 'offline_topo', ...HUES } as never)
    const { map, paint } = mockMap(shipped)

    attachMapAppearance(map, HUES)

    const frozen: string[] = []
    const compared: string[] = []
    for (const id of LINES) {
      const built = shipped.layers.find((layer) => layer.id === id)
      const target = wanted.layers.find((layer) => layer.id === id)
      if (built === undefined || target === undefined) continue
      for (const property of WATCHED) {
        const before = (built.paint as Record<string, unknown> | undefined)?.[property]
        const after = (target.paint as Record<string, unknown> | undefined)?.[property]
        // Only properties the appearance actually moves are this test's
        // business; one that is identical either way cannot be frozen wrong.
        if (JSON.stringify(before) === JSON.stringify(after)) continue
        compared.push(`${id}.${property}`)
        const written = paint.get(id)
        const has = written !== undefined && property in written
        if (!has) {
          frozen.push(`${id}: ${property} never rewritten`)
          continue
        }
        if (JSON.stringify(written[property]) !== JSON.stringify(after)) {
          frozen.push(`${id}: ${property} rewritten to the wrong value`)
        }
      }
    }

    expect(frozen).toEqual([])
    // AND THE DIFF HAS TO HAVE DIFFED SOMETHING. A comparison that finds no
    // appearance-dependent property passes trivially, and the first draft of
    // this test did exactly that - it passed `appearance:` as a nested key,
    // which buildMapStyle does not read, so it compared the default sheet
    // against itself. 20 properties move today; the floor is set well under
    // that so ordinary changes do not trip it, and a drop to zero does.
    expect(compared.length).toBeGreaterThan(12)
  })

  it('shows every casing again, which is what a near-white blaze is read by', () => {
    // The other half of the maintainer's report - "hides some trails". Under
    // the default no casing draws; under the hues the A.T.'s blaze is
    // near-white and the casing IS its edge, so a casing left hidden is a
    // trail that has effectively gone from the map rather than one that looks
    // slightly different.
    const shipped = buildMapStyle({
      background: 'offline_topo',
      ...DEFAULT_SHEET,
    } as never)
    const { map, layout } = mockMap(shipped)

    attachMapAppearance(map, HUES)

    for (const id of TRAIL_CASING_LAYER_IDS) {
      if (shipped.layers.find((layer) => layer.id === id) === undefined) continue
      expect({ id, visibility: layout.get(id)?.['visibility'] }).toEqual({
        id,
        visibility: 'visible',
      })
    }
  })
})

describe('no appearance change alters what kind of dash a blaze layer carries (#1698)', () => {
  /** Every sheet the switch, the theme and red light can reach. */
  const SHEETS = {
    'day, default red': { theme: 'light', blazeColorsShown: false },
    'day, hues': { theme: 'light', blazeColorsShown: true },
    'night, default red': { theme: 'dark', blazeColorsShown: false },
    'night, hues': { theme: 'dark', blazeColorsShown: true },
    'red light over the default': {
      theme: 'dark',
      mapStyle: 'night_hike',
      redLight: true,
      blazeColorsShown: false,
    },
    'red light over the hues': {
      theme: 'dark',
      mapStyle: 'night_hike',
      redLight: true,
      blazeColorsShown: true,
    },
  } as const

  /** What MapLibre makes of a `line-dasharray` value: `source` when it is
   *  decided per feature, `constant` for a plain array, and nothing at all
   *  for an absent one. The kind, not the value, is what this is about. */
  function dashKind(value: unknown): string {
    if (value === undefined) return 'absent'
    const parsed = createPropertyExpression(
      value as never,
      'paint.line-dasharray',
      latest.paint_line['line-dasharray'] as never,
    )
    if (parsed.result === 'error') return 'invalid'
    return parsed.value.kind
  }

  it('builds every blaze layer with a per-feature dash on every sheet', () => {
    // The kind has to be the SAME on every sheet, not merely present:
    // MapLibre 6.7.0 draws a frame between a change of kind and the tiles
    // re-laid out for it, and that frame is the one that threw. `source` on
    // every sheet is the one answer that never changes.
    const kinds: string[] = []
    for (const [sheet, appearance] of Object.entries(SHEETS)) {
      const built = buildMapStyle({ background: 'offline_topo', ...appearance } as never)
      for (const id of BLAZE_LINE_LAYER_IDS) {
        const found = built.layers.find((layer) => layer.id === id)
        if (found === undefined) continue
        const dash = (found.paint as Record<string, unknown> | undefined)?.[
          'line-dasharray'
        ]
        kinds.push(`${sheet} / ${id}: ${dashKind(dash)}`)
      }
    }
    expect(kinds.length).toBeGreaterThan(0)
    expect(kinds.filter((row) => !row.endsWith(': source'))).toEqual([])
  })

  it('repaints every blaze layer with a per-feature dash, from every sheet to every other', () => {
    const wrong: string[] = []
    let writes = 0
    for (const [from, start] of Object.entries(SHEETS)) {
      for (const [to, next] of Object.entries(SHEETS)) {
        if (from === to) continue
        const shipped = buildMapStyle({ background: 'offline_topo', ...start } as never)
        const { map, paint } = mockMap(shipped)
        attachMapAppearance(map, next as never)
        for (const id of BLAZE_LINE_LAYER_IDS) {
          const written = paint.get(id)
          if (written === undefined || !('line-dasharray' in written)) continue
          writes++
          const kind = dashKind(written['line-dasharray'])
          if (kind !== 'source') wrong.push(`${from} -> ${to} / ${id}: ${kind}`)
        }
      }
    }
    // A repaint that wrote no dash at all would pass the loop above.
    expect(writes).toBeGreaterThan(0)
    expect(wrong).toEqual([])
  })
})
