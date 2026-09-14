// The planning spine's rail: Hike → Route → Details (#1373, review rule R3).
//
// "One rail, three stops. The rail shows where you are and lets you go back
// to a finished step without losing the later one." That last clause is the
// contract: a step behind the current one is a button, and pressing it never
// discards what was built on the steps after it - the shell keeps the draft
// and this rail only says where the hiker is standing. A step ahead is a
// button too once it has been reached (`reached`), so a hiker who stepped back
// from Details to Route can step forward again without re-answering Route.
// A step never reached is a plain label: nothing there yet to go to.
//
// The first stop names the KIND OF HIKE rather than the word "Hike", because
// the kind was answered by the mode switch and never asked again (D6) - the
// rail is where that answer stays visible without a second control.
//
// The rail is the same three stops on a phone and on a desktop; the step
// column differs, the rail does not.

import './stepRail.css'

export type PlanStep = 1 | 2 | 3

export interface StepRailProps {
  step: PlanStep
  /** "Day hike" or "Long hike" - the mode's answer, printed on stop one. */
  kind: string
  /** The furthest step the hiker has reached; steps up to it are doors.
   *  Defaults to the current step. */
  reached?: PlanStep
  /** Go to a step behind (or a reached step ahead). Omitted, the rail only
   *  reads. */
  onStep?: (step: PlanStep) => void
}

const STEPS: readonly PlanStep[] = [1, 2, 3]

export function StepRail({ step, kind, reached = step, onStep }: StepRailProps) {
  const labels: Record<PlanStep, string> = { 1: kind, 2: 'Route', 3: 'Details' }

  return (
    <nav className="step-rail" aria-label="Planning steps">
      <ol className="step-rail__list">
        {STEPS.map((n) => {
          const done = n < step
          const current = n === step
          const door = onStep !== undefined && !current && n <= Math.max(reached, step)
          const mark = done ? '✓' : String(n)
          const classes = [
            'step-rail__step',
            done && 'step-rail__step--done',
            current && 'step-rail__step--current',
          ]
            .filter(Boolean)
            .join(' ')
          const inner = (
            <>
              <span className="step-rail__mark" aria-hidden="true">
                {mark}
              </span>
              <span className="step-rail__label">{labels[n]}</span>
            </>
          )
          return (
            <li key={n} className={classes} aria-current={current ? 'step' : undefined}>
              {door ? (
                <button
                  type="button"
                  className="step-rail__door"
                  onClick={() => onStep(n)}
                  aria-label={`Step ${n}, ${labels[n]}`}
                >
                  {inner}
                </button>
              ) : (
                <span className="step-rail__stop">
                  <span className="visually-hidden">{`Step ${n}, `}</span>
                  {inner}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
