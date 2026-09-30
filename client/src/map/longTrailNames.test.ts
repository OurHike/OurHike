import { describe, it, expect } from 'vitest'
import {
  longTrailDisplayName,
  longTrailForName,
  longTrailHasMarker,
  neverShout,
  LONG_TRAIL_NAME_COUNT,
} from './longTrailNames'
import { badgeMarkImageId, BADGE_SOURCES, stewardMarkImageId } from './trailBadges'

// Which published line name is which long trail (#1543), and the two defects
// the table caught in the badge's own mark resolver.

describe('longTrailForName', () => {
  it('holds all 127 measured spellings, so a dropped row goes red here', () => {
    // 33 until #1776, which added 94 usfs_trails spellings. The jump is one
    // trail's doing more than the other three's together: USFS publishes the
    // Pacific Crest Trail under 81 names - PCNST, PCT: MT HOOD, PCT SECTION
    // 2 through 38 and the rest - and the pipeline now folds them into one
    // identity before it decides what is a through route, so a spelling
    // missing from this table is a stretch of trail drawn as anonymous haze
    // rather than only a badge that does not draw.
    expect(LONG_TRAIL_NAME_COUNT).toBe(127)
  })

  it('resolves the Forest Service shout-case a hiker never sees', () => {
    // USFS publishes in capitals and the steward writes it in title case.
    // The whole point of the table is that both are the one trail.
    expect(longTrailForName('SHELTOWEE TRACE')).toBe('sheltowee')
    expect(longTrailForName('Sheltowee Trace')).toBe('sheltowee')
    expect(longTrailForName('OZARK HIGHLANDS TRAIL')).toBe('oht')
    expect(longTrailForName('MAAH DAAH HEY')).toBe('mdh')
  })

  it('resolves a trail its steward and the Forest Service name differently', () => {
    // The association calls it the Ouachita Trail; USFS calls it by its
    // National Recreation Trail designation. One trail, two spellings.
    expect(longTrailForName('OUACHITA NRT')).toBe('ouachita')
    expect(longTrailForName('Ouachita Trail')).toBeNull()
  })

  it('folds five spellings of the Continental Divide onto one trail', () => {
    for (const spelling of [
      'CONTINENTAL DIVIDE',
      'CONTINENTAL DIVIDE NST',
      'CONTINENTAL DIVIDE TRAIL',
      'CONTINENTAL DIVIDE NAT SCENIC',
      'CONTINENTAL DIVIDE NATION SCEN',
    ]) {
      expect(longTrailForName(spelling)).toBe('cdt')
    }
  })

  it('resolves one trail three organizations each publish', () => {
    // The Finger Lakes Trail arrives from USFS, NY State Parks and NY DEC.
    for (const spelling of [
      'FINGER LAKES',
      'Finger Lakes Trail',
      '7 - Finger Lakes Trail',
    ]) {
      expect(longTrailForName(spelling)).toBe('flt')
    }
  })

  it('leaves a spur, a connector and a road section as ordinary lines', () => {
    // Exact after folding, never a prefix. Every one of these is published
    // by a layer this app draws, and none of them is the trail.
    for (const notATrail of [
      'Northville-Placid Trail Spur',
      'BARTRAM NRT - CHEOAH RD',
      'Finger Lakes Trail Spur',
      'SHELTOWEE CONNECTOR',
      'ARIZONA TRAIL CANELO HILLS',
    ]) {
      expect(longTrailForName(notATrail)).toBeNull()
    }
  })

  it('refuses the fifteen look-alikes the geographic check rejected', () => {
    // Each of these is a real line in a layer this app draws, whose name
    // matches a long trail and whose location says it is a different trail:
    // a NY State Parks "Long Trail" 200 miles from Vermont, a "PALMETTO" in
    // California, a "CUMBERLAND" in Colorado. The evidence is in
    // pipeline/reference/trail_name_aliases.json's `rejected` block.
    //
    // SIXTEEN UNTIL #1776, WHICH RESOLVED ONE RATHER THAN OVERTURNING IT.
    // 'CDNST - COLORADO' was refused as a COLORADO TRAIL candidate, and the
    // rejection said why: it is the Continental Divide trail in Colorado.
    // That is now where it is listed, so it resolves to `cdt` here and no
    // longer belongs in a list of things that resolve to nothing. Bare
    // 'COLORADO' stays, still unresolved and still refused.
    for (const lookAlike of [
      'Long Trail',
      'LONG',
      'PALMETTO',
      'CUMBERLAND',
      'BUCKEYE',
      'FOOTHILLS',
      'CATAMOUNT',
      'BAKER',
      'HOT SPRINGS',
      'SUPERIOR',
      'BACKBONE',
      'BLACK CANYON',
      'LONE STAR',
      'COLORADO',
      'JOHN MUIR NATIONAL RECREATION',
    ]) {
      expect(longTrailForName(lookAlike)).toBeNull()
    }
    // The one that moved, asserted rather than merely absent from the list
    // above - a name dropped from a refusal list and nowhere else is a name
    // nothing checks.
    expect(longTrailForName('CDNST - COLORADO')).toBe('cdt')
  })

  it('trims and folds, because a published name carries whatever it carries', () => {
    expect(longTrailForName('  sheltowee trace  ')).toBe('sheltowee')
    expect(longTrailForName('')).toBeNull()
  })
})

describe('badgeMarkImageId', () => {
  it('prefers the registry mark, so one trail never draws two different files', () => {
    // `centerline` is the A.T. and carries the marker the repo owner
    // supplied. A USFS segment spelled "APPALACHIAN TRAIL" resolves to the
    // same trail, and both must draw that one mark.
    const fromSource = badgeMarkImageId('centerline', null)
    expect(fromSource).not.toBeNull()
    expect(badgeMarkImageId('centerline', 'at')).toBe(fromSource)
  })

  it('draws a steward marker for a long trail the registry does not know', () => {
    expect(badgeMarkImageId('usfs_trails', 'sheltowee')).toBe(
      stewardMarkImageId('sheltowee'),
    )
  })

  it('draws NOTHING for a badged trail whose steward published no marker', () => {
    // THE DEFECT THIS TEST EXISTS FOR. The first version minted
    // `trail-mark-steward-<slug>` for any badged trail, so the Great Western
    // Trail asked the sprite for an image nothing registers. The slot still
    // looked right - an unavailable image is dropped - but the feature
    // claimed a mark, which frees the placer to fall back to the bare-mark
    // form, whose entire content is that missing image. A badge that draws
    // nothing at all, and only on a crowded map.
    expect(longTrailForName('GREAT WESTERN TRAIL')).toBe('gwt')
    expect(longTrailHasMarker('gwt')).toBe(false)
    expect(badgeMarkImageId('usfs_trails', 'gwt')).toBeNull()
  })

  it('treats a missing field as no marker rather than building an id from it', () => {
    // The other half of the same defect: `longTrail === null` let `undefined`
    // through and produced `trail-mark-steward-undefined`.
    expect(badgeMarkImageId('usfs_trails', undefined)).toBeNull()
    expect(badgeMarkImageId('usfs_trails', null)).toBeNull()
    expect(badgeMarkImageId('usfs_trails', '')).toBeNull()
  })

  it('still answers nothing for an ordinary line, which is most of the map', () => {
    expect(
      badgeMarkImageId('usfs_trails', longTrailForName('SHELTOWEE CONNECTOR')),
    ).toBeNull()
    expect(badgeMarkImageId('dec_hiking_trails', null)).toBeNull()
  })

  it('keeps the two source-badged trails working exactly as before', () => {
    for (const source of BADGE_SOURCES) {
      expect(badgeMarkImageId(source, null)).not.toBeNull()
    }
  })
})

describe('what a badge prints', () => {
  // The Monadnock-Sunapee Greenway was here until 2026-09-30 and is not now:
  // the maintainer removed NH GRANIT outright (#1711) and the greenway was
  // reaching the map through it. Its row moved to `_removed` in
  // trail_name_aliases.json with the reason - the match was right, the layer
  // went.
  // The maintainer, on seeing the first frame: "Always proper case, not alll
  // caps". USFS publishes a GIS table's spelling and a hiker reads a trail's
  // name.

  it('gives every badged trail a name with no shouting in it', () => {
    // The guarantee, checked across the whole table rather than on the five
    // examples that prompted it.
    for (const slug of [
      'at',
      'pct',
      'cdt',
      'nct',
      'azt',
      'flt',
      'sht',
      'oht',
      'ouachita',
      'sheltowee',
      'pinhoti',
      'bmt',
      'bartram',
      'mdh',
      'tahoe-rim',
      'gwt',
      'bst',
      'jmt',
      'npt',
    ]) {
      const printed = longTrailDisplayName(slug)
      expect(printed).not.toBeNull()
      expect(printed).not.toBe((printed as string).toUpperCase())
    }
  })

  it('keeps the capital letters a mechanical title case would lose', () => {
    // Why the curated name beats `neverShout`: it comes from the steward.
    expect(longTrailDisplayName('bmt')).toBe('Benton MacKaye Trail')
    expect(longTrailDisplayName('pinhoti')).toBe('Pinhoti Trail')
    expect(longTrailDisplayName('nct')).toBe('North Country Trail')
  })

  it('never shouts even for a name no curated spelling covers', () => {
    // The last resort, for a trail badged before it is catalogued.
    expect(neverShout('SOME NEW TRAIL')).toBe('Some New Trail')
    expect(neverShout('PINHOTI NRT')).toBe('Pinhoti Nrt')
  })

  it('leaves a considered spelling alone, because lower case means somebody chose it', () => {
    for (const name of [
      'Long Path',
      'Northville-Placid Trail',
      'Benton MacKaye Trail',
      "Devil's Path",
    ]) {
      expect(neverShout(name)).toBe(name)
    }
  })
})

describe('neverShout on names it must not mangle', () => {
  it('keeps a possessive inside its own word', () => {
    // The first version split on the apostrophe because it matched [A-Za-z]+,
    // so "DEVIL'S PATH" came back "Devil'S Path" - a name nobody writes, on a
    // real Catskills trail. trailsInView.ts runs every named line through this,
    // so it is not confined to badged trails.
    expect(neverShout("DEVIL'S PATH")).toBe("Devil's Path")
    expect(neverShout("MARY'S ROCK")).toBe("Mary's Rock")
  })

  it('folds accented capitals instead of skipping them', () => {
    // [A-Za-z]+ did not match N-tilde or E-acute, so the letter stayed upper
    // and the fold restarted after it. The Forest Service's Southwestern
    // Region publishes plenty of both.
    expect(neverShout('CAÑON DEL AGUA')).toBe(
      'Cañon del agua'.replace('del agua', 'Del Agua'),
    )
    expect(neverShout('LA CIÉNEGA')).toBe('La Ciénega')
  })

  it('still leaves a considered spelling alone', () => {
    // The guard is any lower-case letter, and it has to see a lower-case
    // accented letter as lower-case too.
    expect(neverShout('Northville-Placid Trail')).toBe('Northville-Placid Trail')
    expect(neverShout('Cañon del Agua')).toBe('Cañon del Agua')
  })
})
