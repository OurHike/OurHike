// "Where this map comes from" - one card per organization whose data is on
// this phone (#927, the v2 wireframe's frame `1h`).
//
// WHAT THIS IS NOT: the map corner. chrome/MapAttribution.tsx answers "whose
// pixels am I looking at right now" in one line, and is deliberately terse
// because every line it wraps to is a line of map a hiker does not get. This
// answers a different question - which organizations' data is on this phone,
// and under what terms - in a settings tab where there is room to answer it
// properly.
//
// It inherits the corner's rule whole, though: name what is actually there,
// never what could be. map/credits.ts's comment is the argument, and
// pipeline/export_sources.py enforces the same rule one layer down by
// publishing only stewards whose data ships. Two real organizations are
// excluded by it today - GATC and NYS OPRHP, both fetched for review only
// pending a licence answer - and that is the feature working.
//
// EVERY LINE IS INDEPENDENTLY OMITTED. The registry's real state is ragged:
// the ATC has a licence and no attribution and no tier; OpenStreetMap and the
// U.S. Drought Monitor have attributions and no licence. A card shows what its
// steward recorded and stays quiet about the rest, because "Licence: unknown"
// under an organization's name is this app making a claim about their terms.
//
// TWO LINKS A CARD CAN CARRY SINCE #1574, and both are the organization's
// own words: how to support it (`support`, the block #932 added to the
// registry, unrendered until now) and where to buy its paper maps (`store`).
// Each renders only where the organization granted THIS screen - the two
// grants are separate lists on the pipeline side, because buying a thing is
// not giving - and a steward that recorded neither renders exactly as it did
// before: no button, no empty row, no placeholder.

import {
  layerCountLine,
  type Steward,
  type Stewards,
  type StewardStore,
  type StewardSupport,
} from '../lib/stewards'

export interface SourcesSectionProps {
  stewards: Stewards
}

/** This screen's name in both permission lists - pipeline/export_sources.py's
 *  DONATE_SURFACES and STORE_SURFACES. */
const THIS_SURFACE = 'sources_screen'

/**
 * The framing sentence.
 *
 * The wireframe's version continues "...and takes its own donations — OurHike
 * takes no cut and holds no money", and that half was held back from
 * 2026-08-23 to 2026-09-17 because no card rendered a link: promising a hiker
 * something about donations this screen did not show would have been a claim
 * about a thing that was not on it (#932 added the data; #1574 added the
 * link). It is printed now as FRAMING_LINKS, and only while at least one
 * card actually carries a link - which is the same rule, kept.
 */
const FRAMING = 'Each organization below sets its own licence for the data it publishes.'
const FRAMING_LINKS =
  'Every link below opens the organization’s own site — OurHike takes no cut and holds no money.'

/** The support line, where the organization granted this screen. */
function donateLink(steward: Steward): StewardSupport | null {
  const support = steward.support
  return support !== null && support.donateSurfaces.includes(THIS_SURFACE)
    ? support
    : null
}

/** The store line, where the organization granted this screen. */
function storeLink(steward: Steward): StewardStore | null {
  const store = steward.store
  return store !== null && store.storeSurfaces.includes(THIS_SURFACE) ? store : null
}

export function SourcesSection({ stewards }: SourcesSectionProps) {
  // Nothing at all rather than an empty heading. A phone that has downloaded
  // no data, or is holding a release built before the exporter existed, has
  // no steward list - both ordinary, neither a failure, and a bordered
  // section with nothing in it reads as a rendering fault.
  if (stewards.length === 0) return null

  const anyLink = stewards.some(
    (steward) => donateLink(steward) !== null || storeLink(steward) !== null,
  )

  return (
    <section className="settings__group" aria-labelledby="sources-heading">
      <h2 className="settings__heading" id="sources-heading">
        Where this map comes from
      </h2>
      <p className="settings__note">
        {anyLink ? `${FRAMING} ${FRAMING_LINKS}` : FRAMING}
      </p>

      <ul className="sources__list">
        {stewards.map((steward) => {
          const layers = layerCountLine(steward)
          const donate = donateLink(steward)
          const store = storeLink(steward)
          return (
            <li className="sources__card" key={steward.provider}>
              <p className="sources__name">{steward.name}</p>

              {/* The count and the tier on one line - both are facts about
                  the steward's data rather than about the steward, and a tier
                  alone on a line reads as a badge this app awarded. */}
              {(layers !== null || steward.trust !== null) && (
                <p className="sources__meta">
                  {layers}
                  {layers !== null && steward.trust !== null && ' · '}
                  {steward.trust !== null && (
                    <span className="sources__trust">{steward.trust}</span>
                  )}
                </p>
              )}

              {/* Verbatim, both of them. A licence is a condition somebody
                  agreed to and an attribution is what it obliges; neither is
                  this app's wording to adjust. */}
              {steward.licence !== null && (
                <p className="sources__terms">{steward.licence}</p>
              )}
              {steward.attribution !== null && (
                <p className="sources__terms">{steward.attribution}</p>
              )}

              {/* THE FULL AGREEMENT, where the steward's block quotes one.
                  NJDEP's is why this exists: their Data Distribution Agreement
                  says the data "may not be reproduced or redistributed without
                  all the metadata provided", so the terms travel with the
                  lines rather than being summarised away.

                  BEHIND A DISCLOSURE, not inline. NJDEP's runs to 1,901
                  characters; printed open it would be most of this screen and
                  would bury the nine other organizations whose cards sit under
                  it. Closed, it is present, findable and one tap from being
                  read - which is what "provided with" asks for - and it opens
                  to the agreement verbatim, never a paraphrase.

                  The link is the other half: a hiker or a club can check this
                  app's copy against the steward's own, which is the only way
                  anybody could ever catch it drifting. */}
              {steward.terms !== null && (
                <details className="sources__agreement">
                  <summary className="sources__agreement-open">The full terms</summary>
                  <p className="sources__terms sources__terms--full">{steward.terms}</p>
                  {steward.termsSource !== null && (
                    <p className="sources__terms sources__source">
                      Read from {steward.termsSource}
                    </p>
                  )}
                </details>
              )}

              {/* The organization's own two buttons, in its own words: the
                  registry records `donate_cta` and `store_cta` verbatim off
                  the org's site (pipeline/sources.json), and the URL is the
                  one the pipeline published, referral query and all. Opened
                  in a new tab like every other link out of this app
                  (chrome/OrgNoticeSheet.tsx), so the map is still here when
                  they come back. */}
              {(donate !== null || store !== null) && (
                <p className="sources__links">
                  {donate !== null && (
                    <a
                      className="sources__link"
                      href={donate.donateUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {donate.donateCta} ›
                    </a>
                  )}
                  {store !== null && (
                    <a
                      className="sources__link"
                      href={store.storeUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {store.storeCta} ›
                    </a>
                  )}
                </p>
              )}

              {/* Where the money does not reach the steward this card names
                  - NYS OPRHP's "Donate" resolves to the Natural Heritage
                  Trust, a separate 501(c)(3) - the recipient is named under
                  the button, and the block's own rule is that a surface
                  rendering the button MUST render this (sources.json's
                  oprhp_support). Never let a display outrun its source. */}
              {donate !== null && donate.donateRecipient !== null && (
                <p className="sources__terms">
                  Goes to {donate.donateRecipient}, not to {steward.name}.
                </p>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
