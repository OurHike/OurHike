import { describe, it, expect } from 'vitest'
import type { Map as MapLibreMap } from 'maplibre-gl'
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
