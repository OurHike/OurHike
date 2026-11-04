// One tile of the blaze card (#1962, features/CHALLENGES_BLAZE_CARD.md): an
// item's glyph, on dark green until it is earned and on karma gold once it
// is (the maintainer's poll, 2026-11-04 - it was white, drawn as a blaze,
// and blazes are official trail marking). Taller than wide, 1 by 1.3; the
// sizes are BlazeCard.tsx's.
//
// NO HANDLER BELOW 44 PX. A tile is a `<button>` only when `onPress` is
// given, and BlazeCard gives one only in its expanded state, where a tile is
// 56 px (the brief's first hard requirement). At the card's own 26 px and
// the strip's 8 px it is a span inside a section the hiker taps as a whole.
//
// NO STAMP ANIMATION (maintainer, 2026-09-30): a tile becoming earned is a
// 150 ms colour change in the stylesheet, nothing else.

import { blazeIconPath } from './blazeIcons'
import '../screens/challenges.css'

export interface BlazeTileProps {
  /** The glyph's name (lib/challenges.ts `icon`); null draws `learn`. */
  icon: string | null
  done: boolean
  /** A mystery item still sealed: a dashed outline round a question mark. */
  sealed: boolean
  /** Given only where the tile is big enough to be a target. */
  onPress?: () => void
  /** The accessible name of a pressable tile - the item's title. */
  label?: string
}

export function BlazeTile({ icon, done, sealed, onPress, label }: BlazeTileProps) {
  const classes = ['blaze-tile']
  if (done) classes.push('blaze-tile--done')
  else if (sealed) classes.push('blaze-tile--sealed')
  const glyph = (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={blazeIconPath(sealed ? 'mystery' : icon)} />
    </svg>
  )
  if (onPress === undefined) {
    return <span className={classes.join(' ')}>{glyph}</span>
  }
  classes.push('blaze-tile--press')
  return (
    <button
      type="button"
      className={classes.join(' ')}
      aria-label={label}
      onClick={onPress}
    >
      {glyph}
    </button>
  )
}
