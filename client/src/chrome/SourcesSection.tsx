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

import { layerCountLine, type Stewards } from '../lib/stewards'

export interface SourcesSectionProps {
  stewards: Stewards
}

/**
 * The framing sentence.
 *
 * The wireframe's version continues "...and takes its own donations — OurHike
 * takes no cut and holds no money", and that half is deliberately not here:
 * no card carries a donate link yet (the registry has no donate fields at all
 * - #932), so promising a hiker something about donations this screen does not
 * show would be a claim about a thing that is not on it. The sentence lands
 * whole when the donate line does.
 */
const FRAMING = 'Each organization below sets its own licence for the data it publishes.'

export function SourcesSection({ stewards }: SourcesSectionProps) {
  // Nothing at all rather than an empty heading. A phone that has downloaded
  // no data, or is holding a release built before the exporter existed, has
  // no steward list - both ordinary, neither a failure, and a bordered
  // section with nothing in it reads as a rendering fault.
  if (stewards.length === 0) return null

  return (
    <section className="settings__group" aria-labelledby="sources-heading">
      <h2 className="settings__heading" id="sources-heading">
        Where this map comes from
      </h2>
      <p className="settings__note">{FRAMING}</p>

      <ul className="sources__list">
        {stewards.map((steward) => {
          const layers = layerCountLine(steward)
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
            </li>
          )
        })}
      </ul>
    </section>
  )
}
