import { describe, it, expect } from 'vitest'
import {
  mapCredits,
  MOHONK_CREDIT,
  NYNJTC_CREDIT,
  OPENFREEMAP_CREDIT,
  OPRHP_CREDIT,
  OSM_CREDIT,
  USGS_TOPO_CREDIT,
} from './credits'
import { ELEVATION_ATTRIBUTION } from './terrain'
import { buildMapStyle } from './style'

// The corner used to be two composed strings naming every source the app could
// possibly draw. What that put on a fresh install's screen was five clauses,
// "© OpenStreetMap contributors" printed twice, and a credit for a 314 MB
// archive that was not on the phone. So the two properties asserted here are
// the two that were broken: nothing is said twice, and nothing is credited
// that is not drawing.

const STYLE_OPTIONS = {
  topoArchiveUrl: 'pmtiles://corridor',
  trailsUrl: '/data/trails.geojson',
  terrain: { demUrl: 'dem://tiles', contourTilesUrl: 'contours://tiles' },
}

/** Every distinct credit the built style's sources declare. */
function styleCredits(background: 'hiking_topo_live' | 'usgs_topo_offline'): Set<string> {
  const sources = buildMapStyle({ ...STYLE_OPTIONS, background }).sources
  const declared = new Set<string>()

  for (const source of Object.values(sources) as { attribution?: string }[]) {
    // Split, because a source declares everything IT brings on one line -
    // the vector sheet brings OpenFreeMap's terms and ODbL together - while
    // the corner says them one at a time.
    for (const credit of (source.attribution ?? '').split(' · ')) {
      if (credit !== '') declared.add(credit)
    }
  }

  return declared
}

describe('mapCredits', () => {
  it('never says the same thing twice', () => {
    // The duplicate this replaces was not a typo. Two composed strings each
    // correctly named OpenStreetMap - the sheet's licence and the app data's -
    // and joining them printed it twice. Any later overlap does the same, so
    // the property is asserted rather than the one pair that caused it.
    for (const background of ['hiking_topo_live', 'usgs_topo_offline'] as const) {
      for (const hasRasterArchive of [true, false]) {
        const credits = mapCredits({ background, hasRasterArchive })

        expect(new Set(credits).size).toBe(credits.length)
      }
    }
  })

  it('leads with OpenStreetMap in every state, because that is the line that survives collapsing', () => {
    // MapAttribution shows credits[0] and hides the rest behind a tap on a
    // phone. ODbL is the licence with the prominence requirement, so it has to
    // be the one that stays - and it has to stay FIRST in every state, or the
    // summary line would reshuffle as a download lands.
    for (const background of ['hiking_topo_live', 'usgs_topo_offline'] as const) {
      for (const hasRasterArchive of [true, false]) {
        expect(mapCredits({ background, hasRasterArchive })[0]).toBe(OSM_CREDIT)
      }
    }
  })

  it('does not credit USGS on a phone with no corridor raster on it', () => {
    // The reported bug, at its plainest: a fresh install draws no USGS tile
    // anywhere, and said "USGS US Topo" in the corner regardless.
    expect(
      mapCredits({ background: 'hiking_topo_live', hasRasterArchive: false }),
    ).not.toContain(USGS_TOPO_CREDIT)
    expect(
      mapCredits({ background: 'usgs_topo_offline', hasRasterArchive: false }),
    ).not.toContain(USGS_TOPO_CREDIT)
  })

  it('credits USGS once the archive is on the phone, under either background', () => {
    // Under the live sheet too: style.ts stacks the sheet OVER the raster
    // rather than replacing it, and the sheet's fills do not cover the whole
    // canvas - the archive shows through, so it is being drawn.
    expect(
      mapCredits({ background: 'hiking_topo_live', hasRasterArchive: true }),
    ).toContain(USGS_TOPO_CREDIT)
    expect(
      mapCredits({ background: 'usgs_topo_offline', hasRasterArchive: true }),
    ).toContain(USGS_TOPO_CREDIT)
  })

  it('credits the live sheet and its elevation only while the live sheet is drawn', () => {
    const live = mapCredits({ background: 'hiking_topo_live' })
    expect(live).toContain(OPENFREEMAP_CREDIT)
    expect(live).toContain(ELEVATION_ATTRIBUTION)

    // The offline background makes NO background request at all
    // (MAP_OPTIONS.md §1), so there is nothing of either to credit.
    const offline = mapCredits({ background: 'usgs_topo_offline' })
    expect(offline).not.toContain(OPENFREEMAP_CREDIT)
    expect(offline).not.toContain(ELEVATION_ATTRIBUTION)
  })

  it('says only what a source in the style declares - the corner cannot invent a credit', () => {
    for (const background of ['hiking_topo_live', 'usgs_topo_offline'] as const) {
      const declared = styleCredits(background)

      for (const credit of mapCredits({ background, hasRasterArchive: true })) {
        expect(declared).toContain(credit)
      }
    }
  })

  it('credits the trail stewards only when their trails are drawn', () => {
    // OPRHP's attribution is a CONDITION of using their data - "any maps...
    // created using OPRHP data must include proper credit" - so its absence
    // when their lines ARE drawn is a breach, not an untidy corner. NYNJTC's
    // and Mohonk Preserve's are not conditions (both ship on the maintainer's
    // authorisation, not stated terms), but the same "say what is drawn" rule
    // applies to a courtesy as much as to a licence.
    const drawn = mapCredits({ background: 'usgs_topo_offline', hasNearbyTrails: true })

    expect(drawn).toContain(OPRHP_CREDIT)
    expect(drawn).toContain(NYNJTC_CREDIT)
    expect(drawn).toContain(MOHONK_CREDIT)
  })

  it('names none of the stewards on a phone that has none of their trails', () => {
    // The failure this module was written to fix, in its licence-shaped form:
    // a corner claiming OPRHP data is on screen when the artifact 404'd is
    // false about the one thing a hiker could check. Today this is the
    // ordinary state on any phone whose release predates the network.
    const absent = mapCredits({ background: 'usgs_topo_offline' })

    expect(absent).not.toContain(OPRHP_CREDIT)
    expect(absent).not.toContain(NYNJTC_CREDIT)
    expect(absent).not.toContain(MOHONK_CREDIT)
  })

  it('says everything the style declares, once a phone is holding all of it', () => {
    // The other direction, and the one that stops a source being added in
    // style.ts and going uncredited in the corner. Asserted with the archive
    // AND the nearby-trail network present, since "holding all of it" means
    // every source in the style is actually drawing - #950 added a source and
    // this flag is the half of it the corner depends on.
    for (const background of ['hiking_topo_live', 'usgs_topo_offline'] as const) {
      const credits = new Set(
        mapCredits({ background, hasRasterArchive: true, hasNearbyTrails: true }),
      )

      for (const declared of styleCredits(background)) {
        expect(credits).toContain(declared)
      }
    }
  })
})
