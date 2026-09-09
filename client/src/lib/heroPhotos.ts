// The first-run backdrops: every hero-eligible photograph of the Appalachian
// Trail this project has reviewed, served one-at-random.
//
// Grew from seventeen to forty-eight with #1084, and the layout change is why.
// One photo shipped first - the maintainer's own pick - and was sent back the
// same day ("too bright green and too busy... maybe just use all the options
// you provided me earlier"), so the pool became that gallery review's whole
// option list. #1084 then let the photograph FILL a desktop window instead of
// showing a 4:1 band of it (desktop.css), which changed what a photograph in
// here has to be good enough for: the frame is now seen entire, at up to
// 1920px wide, rather than a slice through its middle.
//
// So this pass added thirty-five and removed four. The four are the ones that
// note in the previous version of this file named as rendering softer than the
// rest, kept then because the maintainer had asked for all of them, and no
// longer defensible once the photograph is the whole screen:
//
//   08-roan-grassy-bald.jpg   638x477     upscaled 3.0x on a 1920px window
//   09-the-humps-roan.jpg     800x593     upscaled 2.4x
//   10-roan-sunset.jpg        1400x2295   portrait; 15% of it survived a
//                                         landscape window
//   15-big-bald.jpg           1835x934    1.97:1 panorama; letterboxed or
//                                         cropped to a third of its width
//
// THE NUMBERING HAS FOUR GAPS AND THEY ARE THOSE FOUR. Renumbering the pool
// would have rewritten thirteen unchanged binaries into the history of a
// public tree for no change in content, and the gaps say what happened more
// plainly than a comment would.
//
// EVERY ENTRY IS LICENCE-CHECKED against Wikimedia Commons extmetadata:
// public domain, CC0, CC BY, or CC BY-SA only - never NC, never ND. The gate
// is machine-applied (an unrecognised or restricted licence string is
// rejected, not guessed at) and the `credit` string is rendered ON the photo
// it licenses (screens/Onboarding.tsx's credit pill), which is CC BY/BY-SA's
// condition and plain provenance for the rest. A photo added here without
// having been through that check is the regression to refuse in review.
//
// PEOPLE APPEAR ONLY DISTANT OR FACING AWAY, and that survived the growth:
// the five entries in this pool with a recognisable human figure in them
// (32, 34, 39, 50, 51) were each looked at full-size for exactly this, and
// every one is a back turned or a silhouette too small to identify. Nothing
// with a readable face is in here.
//
// WEIGHT, so nobody "fixes" it: none of these are precached - the service
// worker's globPatterns take js/css/html, glyphs and woff2 only
// (vite.config.ts), the same deliberate exclusion the share screen's detector
// model rides. An install pays for ZERO of these; a first run fetches exactly
// the one it drew, through the ordinary HTTP cache. Offline first run gets no
// photo and opens on the overlay's own pine ground (onboarding.css
// .onboarding__hero) - calm, and never a broken image. That is what makes a
// forty-eight-photo pool cost a hiker the same as a one-photo pool.
//
// MASTERING, and the one number worth carrying: each file is resized to
// 1600px wide from the Commons original (a modification, noted here as the
// licences ask) and encoded at whatever JPEG quality brings it under 260 KB,
// walking down from 82 and stopping at 62. Per-photograph rather than one
// setting for all of them because dense foliage costs about three times what
// a gradient sky does at the same quality - twelve of the thirty-five new
// frames reached the floor, and the largest is 534 KB, which is the shape the
// pool already had (13-angels-rest.jpg, 522 KB, predates this). The pool is
// 14 MB on disk for 48 photographs, measured 2026-08-27.
//
// 1600px wide, not 1920, and it is a real trade rather than an oversight: at
// 1920 the set measured 13 MB against 9.2 MB, permanently, in a public tree,
// to remove a 1.2x upscale on the widest common desktop. The existing pool
// was already 1600 and already upscaled that far in the band, so this keeps
// one number instead of introducing a second.

import mcafeeDusk from '../design-system/assets/photos/heroes/01-mcafee-knob-dusk.jpg'
import mcafeeLedge from '../design-system/assets/photos/heroes/02-mcafee-knob.jpg'
import maxPatchBald from '../design-system/assets/photos/heroes/03-max-patch-bald.jpg'
import maxPatchStars from '../design-system/assets/photos/heroes/04-max-patch-stars.jpg'
import blueFolds from '../design-system/assets/photos/heroes/05-blue-folds.jpg'
import maxPatchWalker from '../design-system/assets/photos/heroes/06-max-patch-walker.jpg'
import franconiaRidge from '../design-system/assets/photos/heroes/07-franconia-ridge.jpg'
import wilburnRidge from '../design-system/assets/photos/heroes/11-wilburn-ridge.jpg'
import graysonHighlands from '../design-system/assets/photos/heroes/12-grayson-highlands.jpg'
import angelsRest from '../design-system/assets/photos/heroes/13-angels-rest.jpg'
import jeffersonRock from '../design-system/assets/photos/heroes/14-jefferson-rock.jpg'
import waterGapBlaze from '../design-system/assets/photos/heroes/16-water-gap-blaze.jpg'
import petersMountain from '../design-system/assets/photos/heroes/17-peters-mountain.jpg'
import lionsHeadInversion from '../design-system/assets/photos/heroes/18-lions-head-inversion.jpg'
import brownedGrassSlope from '../design-system/assets/photos/heroes/19-browned-grass-slope.jpg'
import asteriskedSky from '../design-system/assets/photos/heroes/20-asterisked-sky.jpg'
import patternedField from '../design-system/assets/photos/heroes/21-patterned-field.jpg'
import blazeInSnow from '../design-system/assets/photos/heroes/22-blaze-in-snow.jpg'
import downriverView from '../design-system/assets/photos/heroes/23-downriver-view.jpg'
import shenandoahFallSunrise from '../design-system/assets/photos/heroes/24-shenandoah-fall-sunrise.jpg'
import rainyBlueRidge from '../design-system/assets/photos/heroes/25-rainy-blue-ridge.jpg'
import downhillClouds from '../design-system/assets/photos/heroes/26-downhill-clouds.jpg'
import graysonSunrise from '../design-system/assets/photos/heroes/27-grayson-sunrise.jpg'
import fallColourRidge from '../design-system/assets/photos/heroes/28-fall-colour-ridge.jpg'
import oldSnagSunrise from '../design-system/assets/photos/heroes/29-old-snag-sunrise.jpg'
import hogwallowFlatsDawn from '../design-system/assets/photos/heroes/30-hogwallow-flats-dawn.jpg'
import grassyRidgeBald from '../design-system/assets/photos/heroes/31-grassy-ridge-bald.jpg'
import baldTraverse from '../design-system/assets/photos/heroes/32-bald-traverse.jpg'
import greenleafOldMan from '../design-system/assets/photos/heroes/33-greenleaf-old-man.jpg'
import mistToMountRogers from '../design-system/assets/photos/heroes/34-mist-to-mount-rogers.jpg'
import anotherDayShenandoah from '../design-system/assets/photos/heroes/35-another-day-shenandoah.jpg'
import oldRagAutumn from '../design-system/assets/photos/heroes/36-old-rag-autumn.jpg'
import tannersRidgeOverlook from '../design-system/assets/photos/heroes/37-tanners-ridge-overlook.jpg'
import fogInTheWoods from '../design-system/assets/photos/heroes/38-fog-in-the-woods.jpg'
import hikerInFog from '../design-system/assets/photos/heroes/39-hiker-in-fog.jpg'
import presidentialRange from '../design-system/assets/photos/heroes/40-presidential-range.jpg'
import springerMountain from '../design-system/assets/photos/heroes/41-springer-mountain.jpg'
import rockytopOverlook from '../design-system/assets/photos/heroes/42-rockytop-overlook.jpg'
import panthertownValley from '../design-system/assets/photos/heroes/43-panthertown-valley.jpg'
import greatNorthWoods from '../design-system/assets/photos/heroes/44-great-north-woods.jpg'
import mcafeeRime from '../design-system/assets/photos/heroes/45-mcafee-rime.jpg'
import blackrockSummit from '../design-system/assets/photos/heroes/46-blackrock-summit.jpg'
import windsweptSlope from '../design-system/assets/photos/heroes/47-windswept-slope.jpg'
import annapolisRocks from '../design-system/assets/photos/heroes/48-annapolis-rocks.jpg'
import vermontAutumnPath from '../design-system/assets/photos/heroes/49-vermont-autumn-path.jpg'
import threeOnTheTrail from '../design-system/assets/photos/heroes/50-three-on-the-trail.jpg'
import charliesBunion from '../design-system/assets/photos/heroes/51-charlies-bunion.jpg'
import winterCorridor from '../design-system/assets/photos/heroes/52-winter-corridor.jpg'

export interface HeroPhoto {
  /** The bundled asset URL. */
  src: string
  /** Rendered on the frame: photographer · licence. CC BY/BY-SA's condition;
   *  courtesy for CC0 and public domain. */
  credit: string
}

/* Commons provenance, one line per entry, in pool order. The gaps at 08,
 * 09, 10 and 15 are the four removed by #1084 - see the header.
 *
 *  1 File:McAfee Knob, United States (Unsplash).jpg
 *    dusk on the ledge
 *  2 File:McAfee Knob, Virginia. - Flickr - asafantman.jpg
 *    the classic ledge
 *  3 File:Appalachian Trail crosses the grassy bald area atop Max Patch Mountain.jpg
 *    the bald
 *  4 File:Max Patch, United States (Unsplash qBX6EMdy0a4).jpg
 *    stars over tents
 *  5 File:Blue folds (Unsplash).jpg
 *    layered blue ridges at dawn
 *  6 File:Hiking man in green field (Unsplash).jpg
 *    walker on the Max Patch bald
 *  7 File:Franconia Ridge.jpg
 *    the AT under storm light
 * 11 File:2017-05-16 ... Wilburn Ridge ... Grayson County, Virginia.jpg
 *    Wilburn Ridge
 * 12 File:Grayson Highlands State Park-27527.jpg
 *    Wilburn Ridge, spring
 * 13 File:Appalachian Trail to Angels Rest Cluster.jpg
 *    the green corridor
 * 14 File:Appalachian trail near Jefferson Rock (21848557659).jpg
 *    Harpers Ferry
 * 16 File:Pennsylvania - Delaware Water Gap - Appalachian Trail - White Blaze.jpg
 *    a white blaze
 * 17 File:Appalachian Trail, Peter's Mountain WV-VA.jpg
 *    blazed post, big sky
 * 18 File:Foggy view east from Lion's Head.jpg
 *    cloud inversion filling the valley below Lion’s Head
 * 19 File:Browned (8177486291).jpg
 *    a golden grass slope running out to the ridges
 * 20 File:Flickr - Nicholas T - Asterisked.jpg
 *    orange forest under a torn sky
 * 21 File:Flickr - Nicholas T - Patterned.jpg
 *    a bronze field and a long weather front
 * 22 File:Appalachian Trail Blaze (50907882988).jpg
 *    a white blaze on a trunk, in snow
 * 23 File:Downriver View (10369273563).jpg
 *    a river bend seen from above, in autumn
 * 24 File:Fall 2016- 10-10-16 - 10-14-16 (30270490462).jpg
 *    sunrise from a boulder, Shenandoah in October
 * 25 File:Rainy Blue Ridge-27527.jpg
 *    the Blue Ridge folding away in rain light
 * 26 File:Flickr - Nicholas T - Downhill.jpg
 *    cumulus stacked over farmland and forest
 * 27 File:Sunrise above grayson highlands state park (26461007376).jpg
 *    a violet dawn over the Grayson Highlands
 * 28 File:2016 Fall Color- Week of 10-17 - 10-21 (30386403361).jpg
 *    autumn colour along the ridge, mid-October
 * 29 File:Old Snag Sunrise (30600723565).jpg
 *    a dead snag against the sunrise
 * 30 File:Sunrise - Hogwallow Flats Overlook (19f9741b-155d-451f-679c-eb35bff722aa).jpg
 *    first light over Hogwallow Flats — almost nothing but gradient
 * 31 File:Grassy Ridge Bald.jpg
 *    the footpath crossing Grassy Ridge Bald, fog on the mountain
 * 32 File:Hike desktop 14.jpg
 *    the corridor traversing a green bald, two hikers small in it
 * 33 File:Greenleaf Hut and Old Man of the Mountain.JPG
 *    Greenleaf Hut under the Franconia peaks
 * 34 File:Watching the mist as we hiked to Mt. Rogers (32427342800).jpg
 *    a hiker walking into the mist below Mount Rogers
 * 35 File:Another Day Begins in Shenandoah (1a4a9015-155d-451f-6701-16928a040e74).jpg
 *    sunburst over red forest, Shenandoah
 * 36 File:Old Rag Mountain (Shenandoah National Park).jpg
 *    Old Rag under autumn colour
 * 37 File:Tanners Ridge Overlook - September 22, 2024 - 54016342491.jpg
 *    a red maple in a meadow at Tanners Ridge
 * 38 File:Heavy fog in the woods (Unsplash).jpg
 *    heavy fog in a birch wood
 * 39 File:Contest Entry (31993931323).jpg
 *    a hiker in fog on an open ridge
 * 40 File:Presidential Range from Mt. Moriah.JPG
 *    the Presidential Range from Mount Moriah
 * 41 File:Springer Mountain view.JPG
 *    the view from Springer Mountain, the southern terminus
 * 42 File:Rockytop Overlook (b49ae659-63cc-4d0d-b4cc-cc09dc84d8c1).jpg
 *    ridge behind ridge from Rockytop Overlook
 * 43 File:Scene above Panthertown Valley Wetland.jpg
 *    fog sitting in Panthertown Valley
 * 44 File:Great North Woods - New Hampshire.jpg
 *    autumn running north into the White Mountains
 * 45 File:McAfee's Knob summit during winter - panoramio.jpg
 *    rime ice on the McAfee Knob summit
 * 46 File:Blackrock Summit - Shenandoah National Park (52494870820).jpg
 *    talus and a big sky at Blackrock Summit
 * 47 File:Windswept trees on a slope (Unsplash).jpg
 *    windswept conifers on a fogged slope
 * 48 File:Annapolis rocks overlook.jpg
 *    the ledge at Annapolis Rocks over the green
 * 49 File:Appalachian National Scenic Trail (Vermont) (bf3dda3e-d16d-4ed3-8155-09950385fa1b).jpg
 *    a leaf-covered path through Vermont in October
 * 50 File:Hiking on Appalachian Trail.jpg
 *    three backpackers walking up into cloud
 * 51 File:Charlies Bunion.jpg
 *    a figure alone on the pinnacle at Charlies Bunion
 * 52 File:Appalachian Trail in winter - Flickr - pellaea.jpg
 *    the corridor under snow
 */
export const HERO_PHOTOS: readonly HeroPhoto[] = [
  { src: mcafeeDusk, credit: 'Emma Frances Logan · CC0' },
  { src: mcafeeLedge, credit: 'Asaf Antman · CC BY 2.0' },
  { src: maxPatchBald, credit: 'Washedwithblood7 · Public domain' },
  { src: maxPatchStars, credit: 'Keghan Crossland · CC0' },
  { src: blueFolds, credit: 'Evelyn Mostrom · CC0' },
  { src: maxPatchWalker, credit: 'Joshua Ness · CC0' },
  { src: franconiaRidge, credit: 'Jeff Pang · CC BY 2.0' },
  { src: wilburnRidge, credit: 'Famartin · CC BY-SA 4.0' },
  { src: graysonHighlands, credit: 'Ken Thomas · Public domain' },
  { src: angelsRest, credit: 'WilderAddict · CC BY-SA 4.0' },
  { src: jeffersonRock, credit: 'Harpers Ferry NPS · CC BY 2.0' },
  { src: waterGapBlaze, credit: 'C. G. P. Grey · CC BY 2.0' },
  { src: petersMountain, credit: 'Smithh05 · CC BY-SA 4.0' },
  { src: lionsHeadInversion, credit: 'Juliancolton · CC BY-SA 4.0' },
  { src: brownedGrassSlope, credit: 'Nicholas A. Tonelli · CC BY 2.0' },
  { src: asteriskedSky, credit: 'Nicholas A. Tonelli · CC BY 2.0' },
  { src: patternedField, credit: 'Nicholas A. Tonelli · CC BY 2.0' },
  { src: blazeInSnow, credit: 'Shenandoah NPS · Public domain' },
  { src: downriverView, credit: 'Nicholas A. Tonelli · CC BY 2.0' },
  { src: shenandoahFallSunrise, credit: 'Shenandoah NPS · Public domain' },
  { src: rainyBlueRidge, credit: 'Ken Thomas · Public domain' },
  { src: downhillClouds, credit: 'Nicholas A. Tonelli · CC BY 2.0' },
  { src: graysonSunrise, credit: 'Virginia State Parks · CC BY 2.0' },
  { src: fallColourRidge, credit: 'Shenandoah NPS · Public domain' },
  { src: oldSnagSunrise, credit: 'Shenandoah NPS · Public domain' },
  { src: hogwallowFlatsDawn, credit: 'NPS · Public domain' },
  { src: grassyRidgeBald, credit: 'Chaneyforkriver · CC0' },
  { src: baldTraverse, credit: 'Bryanrjoyce · CC BY-SA 4.0' },
  { src: greenleafOldMan, credit: 'Andrew Weinert · CC BY-SA 3.0' },
  { src: mistToMountRogers, credit: 'Virginia State Parks · CC BY 2.0' },
  { src: anotherDayShenandoah, credit: 'NPS · Public domain' },
  { src: oldRagAutumn, credit: 'Shenandoah NPS · Public domain' },
  { src: tannersRidgeOverlook, credit: 'Shenandoah NPS · Public domain' },
  { src: fogInTheWoods, credit: 'Macie Jones · CC0' },
  { src: hikerInFog, credit: 'Virginia State Parks · CC BY 2.0' },
  { src: presidentialRange, credit: 'AlexiusHoratius · CC BY-SA 3.0' },
  { src: springerMountain, credit: 'Thomson200 · CC0' },
  { src: rockytopOverlook, credit: "Mary O'Neill · Public domain" },
  { src: panthertownValley, credit: 'NC Wetlands · CC0' },
  { src: greatNorthWoods, credit: 'Will Leavitt · CC BY-SA 4.0' },
  { src: mcafeeRime, credit: 'Idawriter · CC BY-SA 3.0' },
  { src: blackrockSummit, credit: 'Andrew Parlette · CC BY 2.0' },
  { src: windsweptSlope, credit: 'Mika Matin · CC0' },
  { src: annapolisRocks, credit: 'Patorjk · CC BY-SA 4.0' },
  { src: vermontAutumnPath, credit: 'Victoria Stauffenberg · Public domain' },
  { src: threeOnTheTrail, credit: 'Chewonki Semester School · CC BY 2.0' },
  { src: charliesBunion, credit: 'Fig2021 · CC BY-SA 4.0' },
  { src: winterCorridor, credit: 'Jason Hollinger · CC BY 2.0' },
]

/**
 * One backdrop, drawn once per first run.
 *
 * Random rather than rotating-by-date or hashed-off-anything: the maintainer
 * asked for "display them randomly", and there is nothing for a repeat draw
 * to be stable AGAINST - first run happens approximately once per install.
 * The draw is taken once at mount (screens/Onboarding.tsx holds it in state),
 * so the photo does not reshuffle as the steps advance.
 *
 * `random` is injectable for tests; the default is the real thing.
 */
export function pickHero(random: () => number = Math.random): HeroPhoto {
  const index = Math.min(
    HERO_PHOTOS.length - 1,
    Math.floor(random() * HERO_PHOTOS.length),
  )
  return HERO_PHOTOS[index]
}
