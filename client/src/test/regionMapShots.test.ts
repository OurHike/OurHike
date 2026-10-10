// Decision 31's map shot per region (pipeline/ELT.md, "The go/no-go gate"),
// preview-shots/map-region-*.mjs, held to the three things that keep the set
// honest and keep every frame safe to take again as the data changes.
//
// THE REGIONS ARE THE CODE'S: region_boxes() in
// pipeline/dbt/macros/lands_outside_its_region.sql. Every geometry mart holds
// each source's rows to one of those boxes, so they are what "each region the
// app's data covers" means here. Every box gets a recipe, and each recipe
// frames ground inside its box and outside every narrower box nested in it,
// so its frame is that box's own data rather than a neighbour's.
//
// THE ZOOM is below POI_PIN_MIN_ZOOM (map/poiLayerIds.ts): below it no
// waypoint draws as a pin or as a dot (map/poiLayers.ts's POI_DOT_MIN_ZOOM is
// the same constant), so no campsite of any kind is on the map in a region
// shot, whatever the bucket holds next month. A seam moved further out, or a
// recipe moved further in, fails here before it publishes a picture.
//
// THE DRIVE stores a camera readCamera() accepts, reloads, opens the Map tab
// and waits for the map, and does nothing else: the stand-in page below
// refuses any other call, so a recipe that signed in, searched, opened a
// report or pressed locate would fail here rather than in a pull request's
// comment.

import { beforeEach, describe, expect, it } from 'vitest'
import { readRepoFile } from './repoFile'
import { POI_PIN_MIN_ZOOM } from '../map/poiLayerIds'
import { CAMERA_MEMORY_KEY, readCamera, type RememberedCamera } from '../lib/cameraMemory'

interface RegionRecipe {
  region: string
  camera: RememberedCamera
  caption: string
  alt: string
  default: (page: unknown) => Promise<void>
}

interface RegionBox {
  region: string
  latMin: number
  latMax: number
  lonMin: number
  lonMax: number
}

const RECIPES = Object.entries(
  import.meta.glob('../../preview-shots/map-region-*.mjs', { eager: true }) as Record<
    string,
    RegionRecipe
  >,
).map(([path, recipe]) => ({ name: path.split('/').pop() ?? path, recipe }))

const REGION_MACRO = 'pipeline/dbt/macros/lands_outside_its_region.sql'

/** region_boxes()' rows, read from the macro: `('eastern', 30.0, 50.0, -90.0, -66.0)` is name, lat, lat, lon, lon. */
function regionBoxes(): RegionBox[] {
  const sql = readRepoFile(REGION_MACRO)
  const start = sql.indexOf('macro region_boxes()')
  const body = sql.slice(start, sql.indexOf('endmacro', start))
  const number = '(-?\\d+(?:\\.\\d+)?)'
  const row = new RegExp(
    `\\('([a-z_]+)',\\s*${number},\\s*${number},\\s*${number},\\s*${number}\\)`,
    'g',
  )
  return [...body.matchAll(row)].map(([, region, latMin, latMax, lonMin, lonMax]) => ({
    region,
    latMin: Number(latMin),
    latMax: Number(latMax),
    lonMin: Number(lonMin),
    lonMax: Number(lonMax),
  }))
}

const holds = (box: RegionBox, [lon, lat]: [number, number]) =>
  lat >= box.latMin && lat <= box.latMax && lon >= box.lonMin && lon <= box.lonMax

/** A box strictly inside `outer`: the narrower region whose ground `outer`'s own frames must stay out of. */
const nestedIn = (inner: RegionBox, outer: RegionBox) =>
  inner.region !== outer.region &&
  inner.latMin >= outer.latMin &&
  inner.latMax <= outer.latMax &&
  inner.lonMin >= outer.lonMin &&
  inner.lonMax <= outer.lonMax

describe('the region boxes the map shots follow', () => {
  it('reads the three boxes region_boxes() holds, so a reworded macro fails here rather than passing on none', () => {
    expect(regionBoxes().map((box) => box.region)).toEqual([
      'eastern',
      'national',
      'us_and_territories',
    ])
  })

  it('gives every region box at least one preview-shots/map-region-*.mjs recipe', () => {
    const shot = new Set(RECIPES.map(({ recipe }) => recipe.region))
    expect(
      regionBoxes()
        .filter((box) => !shot.has(box.region))
        .map((box) => box.region),
    ).toEqual([])
  })
})

describe.each(RECIPES)('$name', ({ recipe }) => {
  beforeEach(() => sessionStorage.clear())

  it('names a region box region_boxes() holds', () => {
    expect(regionBoxes().map((box) => box.region)).toContain(recipe.region)
  })

  it('opens the map below POI_PIN_MIN_ZOOM, where no waypoint, so no campsite, is drawn', () => {
    expect(recipe.camera.zoom).toBeLessThan(POI_PIN_MIN_ZOOM)
  })

  it("centres on its box's own ground: inside the box, outside every narrower box nested in it", () => {
    const boxes = regionBoxes()
    const box = boxes.find((candidate) => candidate.region === recipe.region)
    expect(box).toBeDefined()
    if (!box) return
    expect(holds(box, recipe.camera.center)).toBe(true)
    const nested = boxes.filter(
      (inner) => nestedIn(inner, box) && holds(inner, recipe.camera.center),
    )
    expect(nested.map((inner) => inner.region)).toEqual([])
  })

  it('stores only a camera readCamera() accepts, reloads, opens the Map tab and waits for the trail map', async () => {
    const calls: string[] = []
    const standIn = {
      evaluate: async (seed: (arg: unknown) => void, arg: unknown) => {
        calls.push('evaluate')
        seed(arg) // in jsdom, so what the browser would store is stored here
      },
      reload: async (options: unknown) => {
        calls.push(`reload ${JSON.stringify(options)}`)
      },
      getByRole: (role: string, options: { name: string | RegExp }) => ({
        click: async () => {
          calls.push(`click ${role} ${String(options.name)}`)
        },
        waitFor: async () => {
          calls.push(`wait for ${role} ${String(options.name)}`)
        },
      }),
    }
    const page = new Proxy(standIn, {
      get(target, property) {
        if (property in target) return target[property as keyof typeof target]
        throw new Error(
          `a region recipe calls page.${String(property)}, which its drive has no reason to`,
        )
      },
    })

    await recipe.default(page)

    expect(sessionStorage.length).toBe(1)
    expect(sessionStorage.key(0)).toBe(CAMERA_MEMORY_KEY)
    expect(readCamera()).toEqual(recipe.camera)
    expect(calls).toEqual([
      'evaluate',
      'reload {"waitUntil":"load"}',
      'click tab Map',
      'wait for region /trail map/i',
    ])
  })

  it('says in its caption which region it shows and that no campsite can be in the frame', () => {
    expect(recipe.caption).toContain(`Region \`${recipe.region}\``)
    expect(recipe.caption).toContain('no campsite can be in this frame')
    expect(recipe.alt).toContain('no waypoint pins')
  })
})
