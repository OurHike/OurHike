// The forecast's sky icons (#1056): a sun or a moon, and clouds in front of
// it as the sky fills. Drawn here as 1.5 px line icons on a 24-unit grid - the
// icon style the design system asks for (its readme's "Iconography") - since
// the app has no icon set to take them from.
//
// Day or night is lib/daylight.ts's answer at the waypoint for that hour, so
// no sun is drawn at 11 pm. The maintainer chose sun and cloud icons over the
// station-model circles the first build drew (poll, 2026-09-30).
//
// Every icon is decoration: the words ("Partly cloudy") travel beside it for
// a screen reader, and the numbers beside it carry the forecast.

import type { SkyCover } from '../lib/weatherForecast'

function Sun({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  const rays = Array.from({ length: 8 }, (_, i) => {
    const a = (i * Math.PI) / 4
    const from = r + 2
    const to = r + 3.6
    return (
      <line
        key={i}
        x1={(cx + from * Math.cos(a)).toFixed(2)}
        y1={(cy + from * Math.sin(a)).toFixed(2)}
        x2={(cx + to * Math.cos(a)).toFixed(2)}
        y2={(cy + to * Math.sin(a)).toFixed(2)}
      />
    )
  })
  return (
    <g className="weather-icon__sun">
      <circle cx={cx} cy={cy} r={r} />
      {rays}
    </g>
  )
}

function Moon({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  // A crescent: from the top, a shallow arc in to the right-hand point, then
  // the full curve round the left back to the top.
  const d = `M ${cx} ${cy - r} A ${r * 0.7} ${r * 0.7} 0 0 0 ${cx + r} ${cy} A ${r} ${r} 0 1 1 ${cx} ${cy - r} Z`
  return <path className="weather-icon__moon" d={d} />
}

/** A cloud whose base runs from `x` to `x + w` at height `y`. */
function Cloud({ x, y, w }: { x: number; y: number; w: number }) {
  const h = w * 0.62
  const d = [
    `M ${x + w * 0.22} ${y}`,
    `H ${x + w * 0.8}`,
    `A ${w * 0.2} ${w * 0.2} 0 0 0 ${x + w * 0.82} ${y - h * 0.62}`,
    `A ${w * 0.3} ${w * 0.3} 0 0 0 ${x + w * 0.3} ${y - h * 0.58}`,
    `A ${w * 0.22} ${w * 0.22} 0 0 0 ${x + w * 0.22} ${y}`,
    'Z',
  ].join(' ')
  return <path className="weather-icon__cloud" d={d} />
}

export function SkyIcon({ cover, day }: { cover: SkyCover; day: boolean }) {
  const Body = day ? Sun : Moon
  return (
    <svg
      className="weather-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      fill="none"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {cover === 'clear' && <Body cx={12} cy={12} r={day ? 4.2 : 6.5} />}
      {cover === 'mostly-clear' && (
        <>
          <Body cx={10.5} cy={10} r={day ? 3.8 : 6} />
          <Cloud x={11.5} y={20} w={10} />
        </>
      )}
      {cover === 'partly-cloudy' && (
        <>
          <Body cx={9} cy={8.5} r={day ? 3.2 : 5} />
          <Cloud x={5.5} y={20} w={16} />
        </>
      )}
      {cover === 'mostly-cloudy' && (
        <>
          <Body cx={16.5} cy={6.5} r={day ? 2.4 : 3.8} />
          <Cloud x={2} y={19.5} w={18} />
        </>
      )}
      {cover === 'cloudy' && (
        <>
          <Cloud x={9} y={13.5} w={12.5} />
          <Cloud x={2.5} y={20} w={17} />
        </>
      )}
    </svg>
  )
}

/** A raindrop, for a chance of rain or snow. */
export function DropIcon() {
  return (
    <svg
      className="weather-icon weather-icon--drop"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 3.5c0 0-6 6.6-6 10.6a6 6 0 0 0 12 0C18 10.1 12 3.5 12 3.5Z" />
    </svg>
  )
}

/** Three lines of moving air. */
export function WindIcon() {
  return (
    <svg
      className="weather-icon weather-icon--wind"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      fill="none"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <path d="M3 9h11a2.5 2.5 0 1 0-2.5-2.5" />
      <path d="M3 13h15a2.5 2.5 0 1 1-2.5 2.5" />
      <path d="M3 17h7" />
    </svg>
  )
}

/** A warning triangle, for an NWS alert. */
export function AlertIcon() {
  return (
    <svg
      className="weather-icon weather-icon--alert"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      fill="none"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10.3 4.2 2.6 17.6A2 2 0 0 0 4.3 20.6h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9.5v4.5" />
      <path d="M12 17.2h.01" />
    </svg>
  )
}
