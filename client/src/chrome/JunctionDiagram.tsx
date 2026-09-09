// The junction, drawn from the graph's own bearings (#1041, frame `D10`).
//
// THE MAP NEVER ZOOMS, WHICH IS WHY THIS EXISTS.
//
// Frame `D10`'s annotation is the rule: "It holds the whole day from first
// step to car, always at the same scale, and the junction arrives as a small
// callout window instead - so you never lose where you are in the day to see
// where you are at your feet. Nothing under you moves while you're reading
// it." A camera that dives to a fork and comes back has taken away the one
// thing the map was answering, at the moment a hiker is least able to
// re-orient themselves.
//
// SO WHAT IS DRAWN HERE IS NOT A MAP, and the difference is stated rather
// than implied: each arm is a STRAIGHT RAY at the bearing that trail leaves
// the junction on, over lib/dayHikeTurns.ts's first 20 metres of it. It is
// not the trail's shape, it does not scale, and nothing about the ground
// between the rays is claimed. What it answers is the one question a fork
// asks - which of these three is mine - and it answers it in the same
// arrangement the hiker is looking at, because the whole picture is rotated
// so their direction of travel points up the screen.
//
// It renders NOTHING when any bearing is missing, rather than a diagram with
// an arm left out. A junction drawn with three arms where four meet is worse
// than no diagram: a hiker would count them against what they can see and
// conclude they are somewhere else.

import type { DayHikeTurn, TurnArm } from '../lib/dayHikeTurns'

const SIZE = 116
const CENTRE = SIZE / 2
const RAY = 44

/** Where an arm's ray ends, with the hiker's travel direction pointing up. */
function tip(bearingDeg: number, facingDeg: number): { x: number; y: number } {
  const radians = (((bearingDeg - facingDeg) % 360) * Math.PI) / 180
  return {
    x: CENTRE + Math.sin(radians) * RAY,
    // Negative because SVG's y grows downward and this angle is a compass
    // bearing, where 0 is the top of the screen.
    y: CENTRE - Math.cos(radians) * RAY,
  }
}

export interface JunctionDiagramProps {
  turn: DayHikeTurn
}

export function JunctionDiagram({ turn }: JunctionDiagramProps) {
  const arms: TurnArm[] = [turn.from, turn.onto, ...turn.others]
  if (arms.some((arm) => arm.bearingDeg === null)) return null
  if (turn.from.bearingDeg === null) return null

  // The hiker arrived along `from`, so they are facing the reverse of the
  // bearing that arm leaves by. Same derivation lib/dayHikeTurns.ts uses to
  // decide left from right, so the picture and the words cannot disagree.
  const facing = (turn.from.bearingDeg + 180) % 360

  return (
    <svg
      className="junction-diagram"
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      width={SIZE}
      height={SIZE}
      role="img"
      aria-label="The junction, with your route drawn from the direction you are walking"
    >
      {turn.others.map((arm, at) => {
        const end = tip(arm.bearingDeg as number, facing)
        return (
          <line
            key={`other-${at}`}
            className="junction-diagram__arm"
            x1={CENTRE}
            y1={CENTRE}
            x2={end.x}
            y2={end.y}
          />
        )
      })}

      {/* The way in, drawn like the others: it is not the route from here on,
          and drawing it as route would say a hiker could carry straight on
          down it. */}
      <line
        className="junction-diagram__arm"
        x1={CENTRE}
        y1={CENTRE}
        x2={tip(turn.from.bearingDeg, facing).x}
        y2={tip(turn.from.bearingDeg, facing).y}
      />

      <line
        className="junction-diagram__arm junction-diagram__arm--route"
        x1={CENTRE}
        y1={CENTRE}
        x2={tip(turn.onto.bearingDeg as number, facing).x}
        y2={tip(turn.onto.bearingDeg as number, facing).y}
      />

      {/* The hiker, at the junction, facing up. */}
      <circle className="junction-diagram__you" cx={CENTRE} cy={CENTRE} r={5} />
    </svg>
  )
}
