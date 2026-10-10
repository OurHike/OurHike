// A plumbed tap's card, with decision 65's season caution under the
// unconfirmed line.
//
// WHAT THIS FRAME IS EVIDENCE FOR. Decision 65 (pipeline/ELT.md's decisions
// table, chosen by poll 2026-10-04) puts the plumbed water BLM, NPS, NJDEP,
// IATA, NCTA, FLTC, Tennessee and NY Parks publish on the map as unconfirmed
// water - the hollow pin - with `water_caution: 'no_shutoff_season'` on the
// feature, because none of those layers says when a tap is shut off. The
// card reads the field (lib/trailData.ts's readPois) and prints, under the
// ordinary unconfirmed line and apart from it (chrome/PoiCard.tsx's
// seasonCautionLine):
//
//   "Tap water. Its listing doesn't say when it's turned off for the season,
//   and taps like this are often off out of season. Carry enough to reach
//   the next water."
//
// (It read "Plumbed water. Its publisher does not say when it is shut off,
// ... the next source." until the word-choice review of #1805, 2026-10-09:
// "source" meant a publisher in one sentence and a water point in the next.)
//
// THE TAP IS INVENTED, AND THE CAPTION SAYS SO. The release this build pins
// (lib/dataRelease.ts) was published before decision 65 was built, and no
// feature in its nearby_poi.geojson carries `water_caution` (UA's
// 2026-10-03-2, read 2026-10-04: 0 of 19,802). The recipe's `before` adds
// one record to that file on the way in and rewrites the manifest's hash to
// match (fixtures/releaseInjection.mjs): named "Example tap (preview
// fixture)", source key `preview_fixture`, which no organization holds, so
// the card credits nobody. It sits beside Bear Mountain State Park's public
// parking area; there is no claim that a tap is there. Everything else on screen is
// the pinned release as it stands.
//
// Reached by search rather than by pin, for the reason
// waypoint-site-parts.mjs gives: a tap on the canvas needs pixel coordinates a
// recipe cannot know, and a search result opens the same card a pin does.
//
// NOTHING HERE IS ANYBODY'S: an invented point on public ground, no account,
// no report, no location fix, no campsite (the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear).
//
// WHEN IT SHOWS LESS. A search panel reading "Nothing here by that name"
// means the pinned release has no nearby_poi.geojson to add the record to (a
// fork's pull request gets no secrets), so there was nothing to inject into.
import { injectIntoRelease } from './fixtures/releaseInjection.mjs'

export const caption =
  'Decision 65: a plumbed tap shown as unconfirmed water, with the season caution under the unconfirmed line. The tap is INVENTED (“Example tap (preview fixture)”), added to the pinned release’s nearby_poi.geojson by the recipe, because no published release carries water_caution yet'
export const alt =
  'A waypoint card for “Example tap (preview fixture)”, a water point marked unconfirmed, with a separate boxed note reading “Tap water. Its listing doesn’t say when it’s turned off for the season, and taps like this are often off out of season. Carry enough to reach the next water.” Or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

/** waypoint-site-parts.mjs's settle: the drive waits on the card itself, so
 *  this only covers the fly-to finishing under it. */
export const wait = 5000

const TAP_NAME = 'Example tap (preview fixture)'
const LON = -73.9886
const LAT = 41.3115

export async function before(page) {
  await injectIntoRelease(page, {
    'nearby_poi.geojson': (published) => ({
      ...published,
      features: [
        ...(published.features ?? []),
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [LON, LAT] },
          properties: {
            id: 'preview_fixture:seasonal-tap',
            poi_type: 'water',
            source: 'preview_fixture',
            source_feature_id: 'seasonal-tap',
            name: TAP_NAME,
            lat: LAT,
            lon: LON,
            confidence: 'low',
            water_caution: 'no_shutoff_season',
          },
        },
      ],
    }),
  })
}

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()

  await page.getByRole('button', { name: 'Search' }).click()
  await page
    .getByRole('searchbox', { name: 'Search the downloaded map' })
    .fill('Example tap')

  const result = page.getByRole('button').filter({ hasText: TAP_NAME }).first()
  await result.waitFor({ timeout: 40000 }).catch(() => {})
  if ((await result.count()) === 0) return
  await result.click()

  // The caution is on the peek itself (chrome/PoiCard.tsx), so the card is
  // not pulled open: the frame is the first thing a hiker reads.
  await page
    .getByRole('note')
    .filter({ hasText: 'Tap water.' })
    .first()
    .waitFor({ timeout: 20000 })
    .catch(() => {})
}
