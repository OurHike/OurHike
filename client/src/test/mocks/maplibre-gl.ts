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
  readonly controls: Array<{ control: AttachableControl; position?: string }> = []
  /** Every imperative camera move, in order - so a test can assert both the
   *  moves the shell does make (a search result) and the ones it does not (a
   *  GPS fix, which leaves the view alone). */
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
  /** Options each image was registered with, by id - `pixelRatio` is the
   *  difference between a crisp pin and a pin at double size. */
  readonly imageOptions = new Map<string, unknown>()
  /** Every paint property written, keyed `layerId/property`. */
  readonly paintProperties = new Map<string, unknown>()
  readonly layoutProperties = new Map<string, unknown>()
  /** The latest filter set on each layer, by layer id. */
  readonly filters = new Map<string, unknown>()
  /** Data pushed into each GeoJSON source, by source id. */
  readonly sourceData = new Map<string, unknown>()
  /**
   * Test-settable: what a rendered-feature query answers with.
   *
   * Keyed by layer id, because the question a tap asks is "is there a PIN
   * here" - a mock that answered the same features for every layer could not
   * fail for a handler that queried the whole map and opened a shelter sheet
   * on a tap on a contour line.
   */
  readonly renderedFeatures = new Map<string, unknown[]>()
  /** Every rendered-feature query, in order, with the geometry it was given -
   *  which is where the touch tolerance around a pin is observable. */
  readonly featureQueries: Array<{ geometry: unknown; layers: string[] }> = []
  /** Test-settable: which layers and sources the style is holding. Real
   *  MapLibre returns undefined for a layer that does not exist and throws if
   *  you write to it anyway, so callers have to cope with both - which means
   *  tests need to be able to produce both. */
  layerIds: string[] = []
  sourceIds: string[] = []
  /**
   * Explicit stand-ins for sources whose behaviour a test needs to observe,
   * by id - see MockVectorSource.
   *
   * The plain `sourceIds` list above covers the GeoJSON case, where the only
   * interesting thing is what got pushed in. A vector source is different:
   * retuning one is a read (what tiles is it on now?) followed by a
   * conditional write, so a test has to be able to seed the read. Registering
   * an object here wins over `sourceIds` for that id.
   */
  readonly sources = new Map<string, unknown>()
  /** Test-settable: real MapLibre only accepts images and paint writes once the
   *  style has loaded, and callers have to cope with both answers. */
  styleLoaded = false
  private readonly listeners = new Map<string, Listener[]>()
  private canvas: HTMLCanvasElement | undefined = undefined

  constructor(options: Record<string, unknown>) {
    this.options = options
    this.applyCamera(options)
    this.adoptStyleContents(options)
    MockMap.instances.push(this)
  }

  /**
   * Takes the layer and source ids from the style it was built with.
   *
   * Real MapLibre answers `getLayer`/`getSource` from the style it parsed, so
   * a mock that needs both a style AND a separate hand-written id list models
   * a map that can hold a layer it does not have. That gap is what let the
   * attach helpers look correct: their readiness question is "is this layer
   * there yet", and the mock could only ever answer "no". A test that wants
   * the not-yet state still gets it by assigning the lists directly.
   */
  private adoptStyleContents(options: Record<string, unknown>): void {
    const style = options.style as
      { layers?: Array<{ id?: unknown }>; sources?: Record<string, unknown> } | undefined
    if (style === undefined || style === null) return

    if (Array.isArray(style.layers)) {
      this.layerIds = style.layers
        .map((layer) => String(layer?.id))
        .filter((id) => id !== 'undefined')
    }
    if (style.sources !== undefined && style.sources !== null) {
      this.sourceIds = Object.keys(style.sources)
    }
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
    // `load` fires BECAUSE the style finished loading, so a mock that fires it
    // while still answering false to `isStyleLoaded()` models a state real
    // MapLibre is never in - and one that quietly breaks anything re-checking
    // later, which is every attach-on-ready helper in map/.
    if (event === 'load') this.styleLoaded = true
    for (const handler of [...(this.listeners.get(event) ?? [])]) handler(payload)
  }

  listenerCount(event: string): number {
    return (this.listeners.get(event) ?? []).length
  }

  addControl(control: AttachableControl, position?: string): this {
    this.controls.push({ control, position })
    control.onAdd(this)
    return this
  }

  hasControl(control: AttachableControl): boolean {
    return this.controls.some((c) => c.control === control)
  }

  removeControl(control: AttachableControl): this {
    // Real MapLibre splices the control out only if it is attached, but calls
    // onRemove() either way (Map.removeControl, maplibre-gl 6). That asymmetry
    // is the whole reason removing one twice is fatal rather than idle, so the
    // mock has to reproduce it - the previous `if (at !== -1)` around BOTH
    // steps made a double removal silently harmless here and nowhere else.
    const at = this.controls.findIndex((c) => c.control === control)
    if (at !== -1) this.controls.splice(at, 1)
    control.onRemove(this)
    return this
  }

  isStyleLoaded(): boolean {
    return this.styleLoaded
  }

  hasImage(id: string): boolean {
    return this.images.has(id)
  }

  addImage(id: string, image: unknown, options?: unknown): this {
    this.images.set(id, image)
    if (options !== undefined) this.imageOptions.set(id, options)
    return this
  }

  setPaintProperty(layerId: string, property: string, value: unknown): this {
    this.paintProperties.set(`${layerId}/${property}`, value)
    return this
  }

  setLayoutProperty(layerId: string, property: string, value: unknown): this {
    // Same convention as setFilter: real MapLibre does not silently accept a
    // write to a layer that is not there, and code that forgets to check
    // must fail here too.
    if (this.getLayer(layerId) === undefined) {
      throw new Error(`The layer '${layerId}' does not exist in the map's style.`)
    }
    this.layoutProperties.set(`${layerId}/${property}`, value)
    return this
  }

  getLayer(id: string): { id: string } | undefined {
    return this.layerIds.includes(id) ? { id } : undefined
  }

  setFilter(layerId: string, filter: unknown): this {
    // Real MapLibre throws rather than ignoring a write to a layer that is not
    // there, and code that forgets to check must fail here too.
    if (this.getLayer(layerId) === undefined) {
      throw new Error(`The layer '${layerId}' does not exist in the map's style.`)
    }
    this.filters.set(layerId, filter)
    return this
  }

  /**
   * Real `getSource` answers with the union of every source kind, so callers
   * have to feature-check what came back before using it - and this returns
   * three different shapes for exactly that reason.
   *
   * An explicitly registered stand-in wins, so a test that cares about a
   * vector source's tile URLs can seed them. Otherwise a source the style is
   * declared to hold answers as a GeoJSON one. Otherwise undefined, which is
   * both "no such source" and "the style has not loaded yet".
   */
  getSource(id: string): unknown {
    const registered = this.sources.get(id)
    if (registered !== undefined) return registered
    if (!this.sourceIds.includes(id)) return undefined
    return { setData: (data: unknown) => this.sourceData.set(id, data) }
  }

  /**
   * Real `queryRenderedFeatures` answers from what is actually drawn, so it
   * returns nothing for a layer the style does not hold - and fires an error
   * event rather than throwing, which is why a caller that forgets to check
   * gets a warning and no result rather than a crash.
   */
  queryRenderedFeatures(geometry?: unknown, options?: { layers?: string[] }): unknown[] {
    const layers = options?.layers ?? [...this.renderedFeatures.keys()]
    this.featureQueries.push({ geometry, layers })
    return layers.flatMap((layer) =>
      this.getLayer(layer) === undefined ? [] : (this.renderedFeatures.get(layer) ?? []),
    )
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
    // Detaching every control is the FIRST thing real Map.remove() does, and
    // modelling it is what makes a later removeControl() a second removal
    // rather than a first one.
    for (const { control } of this.controls) control.onRemove(this)
    this.controls.length = 0
    this.removed = true
  }

  /**
   * ONE canvas for the life of the map, as MapLibre has.
   *
   * A fresh element per call looked harmless and quietly swallowed every write
   * to `getCanvas().style` - which is the only way the map says "this pin is
   * tappable", so the cursor could never have been asserted, or noticed
   * missing.
   */
  getCanvas(): HTMLCanvasElement {
    this.canvas ??= document.createElement('canvas')
    return this.canvas
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

/** The slice of `IControl` the map calls back into. */
interface AttachableControl {
  onAdd(map: unknown): HTMLElement
  onRemove(map: unknown): void
}

class MockControl implements AttachableControl {
  readonly options?: Record<string, unknown>
  /**
   * The map this control is attached to - the mock's stand-in for the real
   * controls' `_map`, which every one of them sets in onAdd and DELETES in
   * onRemove after unsubscribing through it.
   *
   * That is why onRemove is not idempotent in MapLibre: called a second time
   * it reaches `this._map.off(...)` on an undefined map and throws. Modelled
   * here rather than left as a no-op, because a mock that tolerates a double
   * removal cannot fail for the bug that a double removal actually is.
   */
  private attachedTo: unknown = undefined

  constructor(options?: Record<string, unknown>) {
    this.options = options
  }

  onAdd(map: unknown): HTMLElement {
    this.attachedTo = map
    return document.createElement('div')
  }

  onRemove(): void {
    if (this.attachedTo === undefined) {
      throw new TypeError("Cannot read properties of undefined (reading 'off')")
    }
    this.attachedTo = undefined
  }
}

export class NavigationControl extends MockControl {}
export class GeolocateControl extends MockControl {}
export class ScaleControl extends MockControl {}
export class AttributionControl extends MockControl {}

export const addProtocol = vi.fn()
export const removeProtocol = vi.fn()

/**
 * Where MapLibre would fetch its worker from.
 *
 * Real MapLibre starts this EMPTY and, left empty, falls back to guessing a
 * path from its own module URL - which after bundling is the app chunk, next to
 * which no worker is ever published. Modelling the empty start is the whole
 * point: it is the state in which the shipped map drew nothing at all, and a
 * mock that pre-filled it could not tell the two apart.
 */
let workerUrl = ''

export function setWorkerUrl(value: string): void {
  workerUrl = value
}

export function getWorkerUrl(): string {
  return workerUrl
}

export { MockMap as Map }

/** Clear recorded state between tests. */
export function resetMapLibreMock(): void {
  MockMap.instances.length = 0
  addProtocol.mockClear()
  removeProtocol.mockClear()
  workerUrl = ''
}

export default {
  Map: MockMap,
  addProtocol,
  removeProtocol,
  setWorkerUrl,
  getWorkerUrl,
  NavigationControl,
  GeolocateControl,
  ScaleControl,
  AttributionControl,
}
