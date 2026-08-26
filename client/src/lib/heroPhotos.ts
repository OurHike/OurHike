// The first-run backdrops (#1054): every hero-eligible photograph from the
// maintainer's own gallery review of 2026-08-26, served one-at-random.
//
// One photo shipped first - the maintainer's original pick - and was sent
// back the same day: "too bright green and too busy... maybe just use all
// the options you provided me earlier." So the pool IS that review's option
// list, all seventeen hero candidates, in the gallery's own numbering. A
// photo added here without having been through a licence-and-privacy review
// is the regression to refuse in review.
//
// EVERY ENTRY WAS LICENCE-CHECKED against Wikimedia Commons extmetadata when
// the gallery was built: public domain, CC0, CC BY, or CC BY-SA only - never
// NC or ND. The `credit` string is rendered ON the photo it licenses
// (screens/Onboarding.tsx's credit pill), which is CC BY/BY-SA's condition
// and plain provenance for the rest. People appear only distant or facing
// away in this set; the gallery's one identifiable-faces candidate was
// thumb-only and is deliberately not in this pool.
//
// WEIGHT, so nobody "fixes" it: none of these are precached - the service
// worker's globPatterns take js/css/html, glyphs and woff2 only
// (vite.config.ts), the same deliberate exclusion the share screen's
// detector model rides. An install pays for ZERO of these; a first run
// fetches exactly the one it drew, through the ordinary HTTP cache. Offline
// first run gets no photo and the inert map backdrop shows instead - the
// pre-#1054 backdrop, as the fallback.
//
// Files are resized/recompressed from the Commons originals (a modification,
// noted here as the licences ask). Four are natively small or panoramic and
// render softer than the rest full-bleed: 8 (638px), 9 (800px), 14 (1080px
// square), 15 (1835x934 pano). Kept because the maintainer asked for all of
// them; dropping any is a one-line deletion.

import mcafeeDusk from '../design-system/assets/photos/heroes/01-mcafee-knob-dusk.jpg'
import mcafeeLedge from '../design-system/assets/photos/heroes/02-mcafee-knob.jpg'
import maxPatchBald from '../design-system/assets/photos/heroes/03-max-patch-bald.jpg'
import maxPatchStars from '../design-system/assets/photos/heroes/04-max-patch-stars.jpg'
import blueFolds from '../design-system/assets/photos/heroes/05-blue-folds.jpg'
import maxPatchWalker from '../design-system/assets/photos/heroes/06-max-patch-walker.jpg'
import franconiaRidge from '../design-system/assets/photos/heroes/07-franconia-ridge.jpg'
import roanGrassyBald from '../design-system/assets/photos/heroes/08-roan-grassy-bald.jpg'
import theHumps from '../design-system/assets/photos/heroes/09-the-humps-roan.jpg'
import roanSunset from '../design-system/assets/photos/heroes/10-roan-sunset.jpg'
import wilburnRidge from '../design-system/assets/photos/heroes/11-wilburn-ridge.jpg'
import graysonHighlands from '../design-system/assets/photos/heroes/12-grayson-highlands.jpg'
import angelsRest from '../design-system/assets/photos/heroes/13-angels-rest.jpg'
import jeffersonRock from '../design-system/assets/photos/heroes/14-jefferson-rock.jpg'
import bigBald from '../design-system/assets/photos/heroes/15-big-bald.jpg'
import waterGapBlaze from '../design-system/assets/photos/heroes/16-water-gap-blaze.jpg'
import petersMountain from '../design-system/assets/photos/heroes/17-peters-mountain.jpg'

export interface HeroPhoto {
  /** The bundled asset URL. */
  src: string
  /** Rendered on the frame: photographer · licence. CC BY/BY-SA's condition;
   *  courtesy for CC0 and public domain. */
  credit: string
}

/* Commons provenance, one line per entry, in gallery order:
 *  1 File:McAfee Knob, United States (Unsplash).jpg - dusk on the ledge
 *  2 File:McAfee Knob, Virginia. - Flickr - asafantman.jpg - the classic ledge
 *  3 File:Appalachian Trail crosses the grassy bald area atop Max Patch Mountain.jpg
 *  4 File:Max Patch, United States (Unsplash qBX6EMdy0a4).jpg - stars over tents
 *  5 File:Blue folds (Unsplash).jpg - layered blue ridges at dawn
 *  6 File:Hiking man in green field (Unsplash).jpg - walker on the Max Patch bald
 *  7 File:Franconia Ridge.jpg - the AT under storm light
 *  8 File:Grassy-bald-roan-mountain.jpg - Roan bald looking west
 *  9 File:HumpsRoan.jpg - backpacker on the Humps
 * 10 File:Roan Mountain by Briian S Woods.jpg - Blue Ridge sunset
 * 11 File:2017-05-16 ... Wilburn Ridge ... Grayson County, Virginia.jpg
 * 12 File:Grayson Highlands State Park-27527.jpg - Wilburn Ridge, spring
 * 13 File:Appalachian Trail to Angels Rest Cluster.jpg - the green corridor
 * 14 File:Appalachian trail near Jefferson Rock (21848557659).jpg - Harpers Ferry
 * 15 File:Appalachian-trail-big-bald-tnnc1.jpg - amber grasses to Big Bald
 * 16 File:Pennsylvania - Delaware Water Gap - Appalachian Trail - White Blaze.jpg
 * 17 File:Appalachian Trail, Peter's Mountain WV-VA.jpg - blazed post, big sky
 */
export const HERO_PHOTOS: readonly HeroPhoto[] = [
  { src: mcafeeDusk, credit: 'Emma Frances Logan · CC0' },
  { src: mcafeeLedge, credit: 'Asaf Antman · CC BY 2.0' },
  { src: maxPatchBald, credit: 'Washedwithblood7 · Public domain' },
  { src: maxPatchStars, credit: 'Keghan Crossland · CC0' },
  { src: blueFolds, credit: 'Evelyn Mostrom · CC0' },
  { src: maxPatchWalker, credit: 'Joshua Ness · CC0' },
  { src: franconiaRidge, credit: 'Jeff Pang · CC BY 2.0' },
  { src: roanGrassyBald, credit: 'Brian Stansberry · CC BY 2.5' },
  { src: theHumps, credit: 'Omarcheeseboro · CC BY-SA 3.0' },
  { src: roanSunset, credit: 'Brian S. Woods · CC BY-SA 4.0' },
  { src: wilburnRidge, credit: 'Famartin · CC BY-SA 4.0' },
  { src: graysonHighlands, credit: 'Ken Thomas · Public domain' },
  { src: angelsRest, credit: 'WilderAddict · CC BY-SA 4.0' },
  { src: jeffersonRock, credit: 'Harpers Ferry NPS · CC BY 2.0' },
  { src: bigBald, credit: 'Brian Stansberry · CC BY 3.0' },
  { src: waterGapBlaze, credit: 'C. G. P. Grey · CC BY 2.0' },
  { src: petersMountain, credit: 'Smithh05 · CC BY-SA 4.0' },
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
