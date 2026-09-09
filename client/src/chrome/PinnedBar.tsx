// The persistent find/plan bar (#1373, the flow review's PinnedBar).
//
// "The bar carries Find a hike and Plan on every state of this screen,
// forever." Today used to offer Find a hike as a row inside the suggested
// shelf and Plan as a button somewhere in the column, so a hiker on a Today
// with nothing loaded met three refusals before meeting a way in (the
// review's defect D6). This is the way in, pinned above the tab bar where the
// thumb already is, on every state the screen can be in.
//
// Two buttons, never a third: everything else a hiker can start - a report,
// a switch of hike, a download - has its own door on the screen it belongs
// to. `emphasis` says which of the two is the next step on THIS state: on a
// Today with nothing loaded it is Plan; once a walk is loaded neither is.

import './pinnedBar.css'

export interface PinnedBarProps {
  onFind: () => void
  onPlan: () => void
  /** Which button is the next step on this state of the screen. */
  emphasis?: 'plan' | 'find' | 'none'
}

export function PinnedBar({ onFind, onPlan, emphasis = 'none' }: PinnedBarProps) {
  const button = (label: string, key: 'find' | 'plan', onClick: () => void) => (
    <button
      type="button"
      className={
        emphasis === key
          ? 'pinned-bar__button pinned-bar__button--primary'
          : 'pinned-bar__button'
      }
      onClick={onClick}
    >
      {label}
    </button>
  )

  return (
    <div className="pinned-bar" role="group" aria-label="Find or plan a hike">
      {button('Find a hike', 'find', onFind)}
      {button('Plan a hike', 'plan', onPlan)}
    </div>
  )
}
