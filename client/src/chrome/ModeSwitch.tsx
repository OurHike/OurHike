// The "today I'm…" control (#1054): Day hike · Long hike · Volunteer.
// The middle segment said Thru-hike until #1127: it serves everyone living
// on the trail - thru, section, LASH, flip-flop - and a section hiker five
// years into the whole trail could not honestly tap the old word.
//
// ALL THREE SEGMENTS, ALWAYS RENDERED. This is a product decision, not a
// layout preference: the redesign took Volunteer out of the tab bar on the
// promise that a hiker reads the word every single day (chrome/tabs.ts), and
// this control is where that promise is kept. A dropdown, or a chip that
// hides the unselected two, breaks the deal the removal was approved on -
// so this component has no collapsed form and exposes no way to build one.
//
// Changing mode re-ranks and re-emphasises what the Today screen shows. It
// never hides a feature and never gates one (lib/hikerMode.ts).
//
// One component for its three homes - the Today header (pine), the Settings
// "You" group (paper), and the desktop sidebar - because three hand-rolled
// copies of a three-way control is how one of them quietly becomes a
// dropdown. The surface passes a variant class; the semantics stay here.

import { HIKER_MODE_LABELS, HIKER_MODE_VALUES, type HikerMode } from '../lib/hikerMode'
import { ModeIcon } from './ModeIcon'
import './modeSwitch.css'

export interface ModeSwitchProps {
  mode: HikerMode
  onChange: (mode: HikerMode) => void
  /** 'chrome' on pine (Today header, sidebar), 'paper' on light surfaces. */
  variant?: 'chrome' | 'paper'
  /**
   * The selection is not settled yet (#1317).
   *
   * True only while the "which long hike?" sheet is open, which is the one
   * place in the app where tapping a segment is not instantaneous: closing
   * that sheet without picking puts the mode back. Showing the segment
   * selected at full strength and then quietly reverting it would teach a
   * hiker the control lies, so it is drawn as chosen-but-pending instead and
   * the revert is not a surprise arriving after the fact.
   */
  pending?: boolean
}

export function ModeSwitch({
  mode,
  onChange,
  variant = 'chrome',
  pending = false,
}: ModeSwitchProps) {
  return (
    <div
      className={`mode-switch mode-switch--${variant}`}
      role="radiogroup"
      aria-label="Today I'm"
    >
      {HIKER_MODE_VALUES.map((value) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={value === mode}
          className={
            value === mode
              ? pending
                ? 'mode-switch__segment mode-switch__segment--selected mode-switch__segment--pending'
                : 'mode-switch__segment mode-switch__segment--selected'
              : 'mode-switch__segment'
          }
          // Fires even when already selected - a no-op, and cheaper than a
          // control that sometimes ignores a tap.
          onClick={() => onChange(value)}
        >
          {/* The glyph is decorative - the word is the segment's name - and
              it is the same glyph the read-out above the tab bar and the
              volunteer pin draw (chrome/ModeIcon.tsx). */}
          <ModeIcon mode={value} size={16} className="mode-switch__icon" />
          <span>{HIKER_MODE_LABELS[value]}</span>
        </button>
      ))}
    </div>
  )
}
