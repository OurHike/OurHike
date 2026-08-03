// Stand-in for the whole `maplibre-gl` module in tests.
//
// This is not a convenience mock. jsdom has no WebGL context, so a real
// `maplibregl.Map` cannot be constructed in this environment at all - without
// this, no map code is testable.
//
// It deliberately RECORDS every construction and every control added, because
// the facts most worth asserting about map setup are lifecycle facts: that
// exactly one LIVE map exists at a time (two would mean two WebGL contexts,
// two GPS watchers and doubled tile reads), and that unmount really tears one
// down rather than leaking it.

import { vi } from 'vitest'

type Listener = (...args: unknown[]) => void

export class MockMap {
  /** Every map ever constructed this test, in order - including ones since removed. */
  static instances: MockMap[] = []

  /** The maps that are still live (constructed and not yet `.remove()`d). */
  static get live(): MockMap[] {
    return MockMap.instances.filter((m) => !m.removed)
  }

  readonly options: Record<string, unknown>
  readonly controls: Array<{ control: unknown; position?: string }> = []
  /** Every imperative camera move, in order - so a test can assert the map
   *  was actually moved to the first GPS fix. */
  readonly cameraMoves: Array<Record<string, unknown>> = []
  removed = false
  /** Test-settable, since the shell derives the legend from it. */
  bounds = { west: -180, south: -85, east: 180, north: 85 }
  /** Seeded from the construction options and moved by jumpTo, so a test can
   *  read back where the camera actually ended up rather than only what it was
   *  asked to do. The shell reads this to remember the view across a tab. */
  center = { lng: 0, lat: 0 }
  zoom = 0
  /** Images registered on the style, by id. */
  readonly images = new Map<string, unknown>()
  /** Every paint property written, keyed `layerId/property`. */
  readonly paintProperties = new Map<string, unknown>()
  /**
   * Sources on the style, by id. Test-settable, and empty by default, because
   * real `getSource` returns undefined both before the style loads and for a
   * source the current style simply does not have - and code that retunes a
   * source has to cope with both.
   */
  readonly sources = new Map<string, unknown>()
  /** Test-settable: real MapLibre only accepts images and paint writes once the
   *  style has loaded, and callers have to cope with both answers. */
  styleLoaded = false
  private readonly listeners = new Map<string, Listener[]>()

  constructor(options: Record<string, unknown>) {
    this.options = options
    this.applyCamera(options)
    MockMap.instances.push(this)
  }

  private applyCamera(options: Record<string, unknown>): void {
    const { center, zoom } = options
    if (Array.isArray(center) && center.length === 2) {
      this.center = { lng: Number(center[0]), lat: Number(center[1]) }
    }
    if (typeof zoom === 'number') this.zoom = zoom
  }

  on(event: string, handler: Listener): this {
    this.listeners.set(event, [...(this.listeners.get(event) ?? []), handler])
    return this
  }

  off(event: string, handler: Listener): this {
    this.listeners.set(
      event,
      (this.listeners.get(event) ?? []).filter((h) => h !== handler),
    )
    return this
  }

  /** Test-only: fire an event that real MapLibre would fire itself. */
  emit(event: string, payload?: unknown): void {
    for (const handler of [...(this.listeners.get(event) ?? [])]) handler(payload)
  }

  listenerCount(event: string): number {
    return (this.listeners.get(event) ?? []).length
  }

  addControl(control: unknown, position?: string): this {
    this.controls.push({ control, position })
    return this
  }

  removeControl(control: unknown): this {
    const at = this.controls.findIndex((c) => c.control === control)
    if (at !== -1) this.controls.splice(at, 1)
    return this
  }

  isStyleLoaded(): boolean {
    return this.styleLoaded
  }

  hasImage(id: string): boolean {
    return this.images.has(id)
  }

  getSource(id: string): unknown {
    return this.sources.get(id)
  }

  addImage(id: string, image: unknown): this {
    this.images.set(id, image)
    return this
  }

  setPaintProperty(layerId: string, property: string, value: unknown): this {
    this.paintProperties.set(`${layerId}/${property}`, value)
    return this
  }

  jumpTo(options: Record<string, unknown>): this {
    this.cameraMoves.push(options)
    this.applyCamera(options)
    return this
  }

  getCenter() {
    return { ...this.center }
  }

  getZoom(): number {
    return this.zoom
  }

  getBounds() {
    return {
      getWest: () => this.bounds.west,
      getSouth: () => this.bounds.south,
      getEast: () => this.bounds.east,
      getNorth: () => this.bounds.north,
    }
  }

  remove(): void {
    this.removed = true
  }

  getCanvas(): HTMLCanvasElement {
    return document.createElement('canvas')
  }
}

/**
 * Stand-in for a VectorTileSource, enough of one to observe a retune: it holds
 * the tile URLs it was given and records every `setTiles` call, so a test can
 * tell "re-pointed once" apart from "re-pointed on every render."
 */
export class MockVectorSource {
  readonly setTilesCalls: string[][] = []
  tiles: string[]

  // Assigned in the body rather than declared as a parameter property: the
  // project builds with `erasableSyntaxOnly`, which rejects the shorthand.
  constructor(tiles: string[]) {
    this.tiles = tiles
  }

  setTiles(tiles: string[]): this {
    this.setTilesCalls.push(tiles)
    this.tiles = tiles
    return this
  }
}

class MockControl {
  readonly options?: Record<string, unknown>

  constructor(options?: Record<string, unknown>) {
    this.options = options
  }

  onAdd(): HTMLElement {
    return document.createElement('div')
  }
  onRemove(): void {}
}

export class NavigationControl extends MockControl {}
export class GeolocateControl extends MockControl {}
export class ScaleControl extends MockControl {}
export class AttributionControl extends MockControl {}

export const addProtocol = vi.fn()
export const removeProtocol = vi.fn()

export { MockMap as Map }

/** Clear recorded state between tests. */
export function resetMapLibreMock(): void {
  MockMap.instances.length = 0
  addProtocol.mockClear()
  removeProtocol.mockClear()
}

export default {
  Map: MockMap,
  addProtocol,
  removeProtocol,
  NavigationControl,
  GeolocateControl,
  ScaleControl,
  AttributionControl,
}
