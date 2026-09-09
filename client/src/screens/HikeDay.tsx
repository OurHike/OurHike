// One day inside a long hike (#1317).
//
// NOTHING HERE DEPENDS ON A TAP, and that is the rule the whole screen is
// built around rather than a caveat on one button. Day rollover comes from
// the calendar and miles walked come from position, so a hiker who never
// opens this screen still has day 7 open tomorrow with the miles they walked
// still walked. "Call it a day here" records an EXPLICIT end-of-day at a
// place - the evening you stop somewhere that is not on the plan, or stop
// early on purpose, and want the days after it to know - and skipping it
// changes nothing. The sentence under the button says exactly that, because
// a button a hiker is afraid of not pressing is a button that has invented
// an obligation.
//
// THE RIBBON IS THE REAL ONE. `chrome/ElevationRibbon.tsx`, with
// `subject="todays-walk"` and not `'ahead'` - the accessible name is a
// claim, and "ahead" over a whole day's profile tells a screen-reader user
// something false about where they are. The waypoint lane underneath is
// positioned in the ribbon's own 0-100 space and shares its `domain`, so a
// pin sits under the ground it belongs to rather than a sample-width off.
//
// THE GLYPHS ARE `poiGlyphPath`'s. Never redrawn: a shelter that looked
// slightly different here from the one on the map would be a second symbol
// for one thing, which is the failure map/poiIcons.ts exists to prevent.

import { ElevationRibbon, type ElevationSample } from '../chrome/ElevationRibbon'
import { poiColor, poiGlyphPath } from '../map/poiIcons'
import { formatElevation, type UnitSystem } from '../lib/units'
import { mileMarker } from '../lib/planDisplay'
import './today.css'
import './plan.css'

export interface HikeDayWaypoint {
  id: string
  type: string
  name: string
  mile: number
}

export interface HikeDayProps {
  /** The hike this day belongs to, for the way back. */
  hikeName: string
  /** `Day 6 · Tue 8 Sep`. */
  title: string
  /** `Pine Swamp Branch → Bailey Gap · 11.2 mi`. */
  subtitle: string
  /** The day's own profile, or empty when this download has none - and then
   *  the card says so rather than drawing a flat line, which would read as
   *  "no climb" instead of "no measurement". */
  samples: readonly ElevationSample[]
  /** What x=0 and x=100 mean, shared with the waypoint lane below so the two
   *  cannot disagree about which ground the width covers. */
  domain: { startMile: number; endMile: number }
  ascentFt: number | null
  currentMile: number | null
  waypoints: readonly HikeDayWaypoint[]
  units: UnitSystem
  onBack: () => void
  onOpenWaypoint: (id: string) => void
  onStopShort: () => void
  onPushOn: () => void
  onTakeZero: () => void
  onCallItADay: () => void
}

export function HikeDay({
  hikeName,
  title,
  subtitle,
  samples,
  domain,
  ascentFt,
  currentMile,
  waypoints,
  units,
  onBack,
  onOpenWaypoint,
  onStopShort,
  onPushOn,
  onTakeZero,
  onCallItADay,
}: HikeDayProps) {
  const span = domain.endMile - domain.startMile

  return (
    <div className="hike-day">
      <header className="hike-day__head">
        <button type="button" className="plan__crumb" onClick={onBack}>
          <span aria-hidden="true">‹ </span>
          {hikeName}
        </button>
        <h1 className="plan-band__word">{title}</h1>
        <p className="hike-day__sub">{subtitle}</p>
      </header>

      <div className="hike-day__body">
        <section className="today__card" aria-label="The day’s climb">
          <div className="today__climb-head">
            <span className="today__rule-label">The day’s climb</span>
            {/* Absent rather than zero on a download with no profile: a
                hiker deciding whether they beat the dark is better served by
                no answer than by a made-up one, and "+0 ft" is a made-up
                one. */}
            {ascentFt !== null && (
              <span className="today__climb-figure">
                +{formatElevation(ascentFt, units)}
              </span>
            )}
          </div>

          {samples.length === 0 ? (
            <p className="hike-day__no-profile">
              No elevation profile in this download — distance only.
            </p>
          ) : (
            <>
              <ElevationRibbon
                samples={[...samples]}
                currentMile={currentMile}
                subject="todays-walk"
                domain={domain}
                units={units}
              />
              {/* The lane rides in the ribbon's own space, inset by the same
                  36px gutter the ribbon keeps for its min/max labels - so a
                  pin under a summit is under that summit. */}
              <div className="hike-day__lane" aria-hidden="true">
                {waypoints.map((waypoint) => (
                  <span
                    className="hike-day__pin"
                    key={waypoint.id}
                    style={{
                      left: `${span <= 0 ? 0 : ((waypoint.mile - domain.startMile) / span) * 100}%`,
                      background: `color-mix(in srgb, ${poiColor(waypoint.type)} 22%, var(--surface-card))`,
                    }}
                  >
                    <svg viewBox="0 0 1 1" width="13" height="13">
                      <path
                        d={poiGlyphPath(waypoint.type)}
                        fill={poiColor(waypoint.type)}
                        fillRule="evenodd"
                      />
                    </svg>
                  </span>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="hike-day__stops" aria-label="Stops today">
          <p className="today__rule-label">Stops today</p>
          {waypoints.length === 0 ? (
            <p className="hike-day__no-profile">
              Nothing of the journal’s kinds is on today’s stretch.
            </p>
          ) : (
            waypoints.map((waypoint) => (
              <div className="today__row" key={waypoint.id}>
                {/* A mile MARKER, never a distance: `mi 470.8` is WHERE
                    somebody is - the reference a guidebook, a shelter
                    register and a shuttle driver all share - and converting
                    it hands a metric hiker "757.7 km", which names nothing
                    and, read as a marker, names somewhere else (#986). */}
                <span className="today__gutter">{mileMarker(waypoint.mile)}</span>
                <button
                  type="button"
                  className="today__card today__card--entry"
                  onClick={() => onOpenWaypoint(waypoint.id)}
                >
                  {waypoint.name}
                </button>
              </div>
            ))
          )}
        </section>

        <section className="today__card" aria-label="Change today">
          <p className="today__rule-label">Change today</p>
          <div className="today__actions">
            <button type="button" className="today__action" onClick={onStopShort}>
              Stop short
            </button>
            <button type="button" className="today__action" onClick={onPushOn}>
              Push on
            </button>
            <button type="button" className="today__action" onClick={onTakeZero}>
              Take a zero
            </button>
          </div>
          <p className="hike-day__note">
            Changing today offers to shift the days after it. Nothing moves until you say
            so.
          </p>
        </section>

        <button type="button" className="plan__primary" onClick={onCallItADay}>
          Call it a day here
        </button>
        {/* The answer to "what happens if I never press it", on the screen
            rather than only in this file. See the header. */}
        <p className="hike-day__note">
          Nothing waits on this button. Don’t press it and tomorrow simply opens as the
          next day — the miles you walked stay walked, and this day is left as planned
          rather than marked short. It exists for the evening you stop somewhere that
          isn’t on the plan, or stop early on purpose, and want the days after it to know.
        </p>
      </div>
    </div>
  )
}
